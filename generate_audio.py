#!/usr/bin/env python3
"""generate_audio.py — XTTS-v2 with Edge-TTS fallback + mastering."""

from __future__ import annotations
import argparse
import asyncio
import hashlib
import os
import subprocess
import sys

from soundscape import master_voice

CANONICAL_SR = 44100
_TTS_MODEL = None
_SPEAKER_LATENT: dict = {}


def get_deterministic_seed(video_id: str) -> int:
    return int(hashlib.sha256(video_id.encode("utf-8")).hexdigest()[:8], 16)


def _log(msg: str) -> None:
    print(f"[audio] {msg}", file=sys.stderr, flush=True)


def _validate_reference(path: str) -> None:
    try:
        import soundfile as sf
        info = sf.info(path)
        dur = info.frames / float(info.samplerate)
        if dur < 6.0:
            _log(f"WARN reference '{path}' is only {dur:.1f}s (want 10–30s)")
        if dur > 60.0:
            _log(f"WARN reference '{path}' is {dur:.1f}s (trim to 30s recommended)")
    except Exception as e:
        _log(f"WARN could not inspect reference: {e}")


def _get_tts(use_gpu=None):
    global _TTS_MODEL
    if _TTS_MODEL is None:
        import torch
        from TTS.api import TTS
        if use_gpu is None:
            use_gpu = torch.cuda.is_available()
        _log(f"Loading XTTS-v2 (GPU={use_gpu})")
        _TTS_MODEL = TTS(
            "tts_models/multilingual/multi-dataset/xtts_v2",
            gpu=use_gpu,
        )
    return _TTS_MODEL


def _reset_tts():
    global _TTS_MODEL, _SPEAKER_LATENT
    _TTS_MODEL = None
    _SPEAKER_LATENT = {}


def _get_speaker_latent(tts, speaker_wav: str):
    key = os.path.abspath(speaker_wav)
    if key not in _SPEAKER_LATENT:
        _log(f"Computing speaker latent from '{speaker_wav}'")
        gpt, emb = tts.synthesizer.tts_model.get_conditioning_latents(
            audio_path=[speaker_wav]
        )
        _SPEAKER_LATENT[key] = (gpt, emb)
    return _SPEAKER_LATENT[key]


def synthesize_coqui(text: str, speaker_wav: str, output_wav: str, seed: int) -> bool:
    try:
        import numpy as np
        import soundfile as sf
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)

        tts = _get_tts()
        gpt, emb = _get_speaker_latent(tts, speaker_wav)

        def _infer(model, g, e):
            return model.synthesizer.tts_model.inference(
                text=text, language="en",
                gpt_cond_latent=g, speaker_embedding=e,
                temperature=0.70, speed=0.95,
                repetition_penalty=5.0,
                top_k=50, top_p=0.85,
                enable_text_splitting=True,
            )

        try:
            result = _infer(tts, gpt, emb)
        except Exception as e:
            if "cuda" in str(e).lower() or "out of memory" in str(e).lower():
                _log("CUDA OOM — retrying on CPU")
                _reset_tts()
                tts = _get_tts(use_gpu=False)
                gpt, emb = _get_speaker_latent(tts, speaker_wav)
                result = _infer(tts, gpt, emb)
            else:
                raise

        wav = result["wav"]
        if isinstance(wav, torch.Tensor):
            wav = wav.detach().cpu().numpy()
        wav = np.asarray(wav, dtype=np.float32)
        sf.write(output_wav, wav, 24000, subtype="PCM_16")
        return True
    except Exception as e:
        _log(f"Coqui XTTS failed: {type(e).__name__}: {e}")
        return False


def synthesize_edge_tts(text: str, output_wav: str) -> bool:
    temp_mp3 = output_wav + ".tmp.mp3"
    try:
        import edge_tts

        async def _run():
            comm = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate="-3%")
            await comm.save(temp_mp3)

        asyncio.run(_run())
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", temp_mp3, "-acodec", "pcm_s16le",
             "-ar", str(CANONICAL_SR), "-ac", "1", output_wav],
            check=True, timeout=120,
        )
        return True
    except Exception as e:
        _log(f"Edge-TTS failed: {type(e).__name__}: {e}")
        return False
    finally:
        if os.path.exists(temp_mp3):
            try:
                os.remove(temp_mp3)
            except OSError:
                pass


def main() -> int:
    p = argparse.ArgumentParser(description="Voice synthesis.")
    p.add_argument("--video_id", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--speaker_wav", default="saem_voice_sample.wav")
    p.add_argument("--output", required=True)
    p.add_argument("--force-edge", action="store_true")
    args = p.parse_args()

    seed = get_deterministic_seed(args.video_id)
    raw_wav = args.output + ".raw.wav"

    success = False
    if not args.force_edge and os.path.exists(args.speaker_wav):
        _validate_reference(args.speaker_wav)
        success = synthesize_coqui(args.script, args.speaker_wav, raw_wav, seed)

    if not success:
        _log("Using Edge-TTS fallback")
        success = synthesize_edge_tts(args.script, raw_wav)

    if not success or not os.path.exists(raw_wav):
        _log(f"FATAL audio synthesis failed for {args.video_id}")
        return 1

    master_voice(raw_wav, args.output)

    if os.path.exists(raw_wav):
        try:
            os.remove(raw_wav)
        except OSError:
            pass

    _log(f"SUCCESS {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
