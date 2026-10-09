#!/usr/bin/env python3
"""
generate_audio.py — Voice cloning with XTTS-v2 + Edge-TTS fallback.

Synthesis params tuned for Feynman-style narration:
  * temperature=0.70      (a touch of warmth; 0.65 is fine, 0.85 too wild)
  * speed=0.95            (deliberate, lecturer-paced; not hurried)
  * repetition_penalty=5.0(prevents the model from looping a phrase)
  * top_k=50, top_p=0.85  (natural sampling, avoids monotone)
  * enable_text_splitting (handles long scripts without truncation)
"""

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


# =================================================================== helpers
def get_deterministic_seed(video_id: str) -> int:
    h = hashlib.sha256(video_id.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _validate_reference(speaker_wav: str) -> None:
    """Warn (not fail) if the reference sample is suboptimal."""
    try:
        import soundfile as sf
        info = sf.info(speaker_wav)
        dur = info.frames / float(info.samplerate)
        if dur < 6.0:
            print(f"[WARN] Reference '{speaker_wav}' is {dur:.1f}s — "
                  f"XTTS wants 10-30s for a stable clone.", file=sys.stderr)
        if dur > 60.0:
            print(f"[WARN] Reference '{speaker_wav}' is {dur:.1f}s — "
                  f"trimming to 30s is recommended.", file=sys.stderr)
        if info.channels > 1:
            print(f"[INFO] Reference is stereo; XTTS will downmix.", file=sys.stderr)
    except Exception as e:
        print(f"[WARN] Could not inspect reference: {e}", file=sys.stderr)


def _get_tts(use_gpu: bool | None = None):
    global _TTS_MODEL
    if _TTS_MODEL is None:
        import torch
        from TTS.api import TTS

        if use_gpu is None:
            use_gpu = torch.cuda.is_available()
        print(f"[TTS] Loading XTTS-v2 (GPU={use_gpu})", file=sys.stderr)
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
        print(f"[TTS] Computing speaker latent from '{speaker_wav}'", file=sys.stderr)
        gpt, emb = tts.synthesizer.tts_model.get_conditioning_latents(
            audio_path=[speaker_wav]
        )
        _SPEAKER_LATENT[key] = (gpt, emb)
    return _SPEAKER_LATENT[key]


# =================================================================== synthesis
def synthesize_coqui(text: str, speaker_wav: str,
                     output_wav: str, seed: int) -> bool:
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

        def _infer():
            return tts.synthesizer.tts_model.inference(
                text=text,
                language="en",
                gpt_cond_latent=gpt,
                speaker_embedding=emb,
                temperature=0.70,
                speed=0.95,
                repetition_penalty=5.0,
                top_k=50,
                top_p=0.85,
                enable_text_splitting=True,
            )

        try:
            result = _infer()
        except Exception as e:
            if "cuda" in str(e).lower() or "out of memory" in str(e).lower():
                print("[TTS] CUDA OOM — retrying on CPU", file=sys.stderr)
                _reset_tts()
                tts = _get_tts(use_gpu=False)
                gpt, emb = _get_speaker_latent(tts, speaker_wav)
                result = _infer()
            else:
                raise

        wav = result["wav"]
        if isinstance(wav, torch.Tensor):
            wav = wav.detach().cpu().numpy()
        wav = np.asarray(wav, dtype=np.float32)
        sf.write(output_wav, wav, 24000, subtype="PCM_16")
        return True
    except Exception as e:
        print(f"[WARN] Coqui XTTS failed: {e}", file=sys.stderr)
        return False


def synthesize_edge_tts(text: str, output_wav: str) -> bool:
    temp_mp3 = output_wav + ".tmp.mp3"
    try:
        import edge_tts

        async def _run():
            # ChristopherNeural: warm, male, closest to Feynman's cadence
            communicate = edge_tts.Communicate(
                text, "en-US-ChristopherNeural", rate="-3%"
            )
            await communicate.save(temp_mp3)

        asyncio.run(_run())
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", temp_mp3,
                "-acodec", "pcm_s16le",
                "-ar", str(CANONICAL_SR),
                "-ac", "1",
                output_wav,
            ],
            check=True, timeout=120,
        )
        return True
    except Exception as e:
        print(f"[ERROR] Edge-TTS failed: {e}", file=sys.stderr)
        return False
    finally:
        if os.path.exists(temp_mp3):
            os.remove(temp_mp3)


# =================================================================== main
def main() -> int:
    p = argparse.ArgumentParser(description="Voice synthesis engine.")
    p.add_argument("--video_id", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--speaker_wav", default="saem_voice_sample.wav")
    p.add_argument("--output", required=True)
    p.add_argument("--force-edge", action="store_true",
                   help="Skip XTTS, use Edge-TTS only")
    args = p.parse_args()

    seed = get_deterministic_seed(args.video_id)
    raw_wav = args.output + ".raw.wav"

    success = False
    if not args.force_edge and os.path.exists(args.speaker_wav):
        _validate_reference(args.speaker_wav)
        success = synthesize_coqui(args.script, args.speaker_wav, raw_wav, seed)

    if not success:
        print("[INFO] Falling back to Edge-TTS", file=sys.stderr)
        success = synthesize_edge_tts(args.script, raw_wav)

    if not success or not os.path.exists(raw_wav):
        print(f"[FATAL] Audio synthesis failed for {args.video_id}", file=sys.stderr)
        return 1

    master_voice(raw_wav, args.output)

    if os.path.exists(raw_wav):
        os.remove(raw_wav)

    print(f"[SUCCESS] Mastered audio: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
