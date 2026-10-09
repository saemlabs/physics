#!/usr/bin/env python3
"""
generate_audio.py — Voice synthesis with XTTS-v2 primary + Edge-TTS fallback.

Fixes vs. previous version:
  * TTS instantiated with `gpu=` kwarg (no more .to(device))
  * TTS model cached at module level — one load per process
  * Speaker latent cached per wav path
  * CUDA OOM → CPU retry, then Edge-TTS fallback
  * Edge-TTS output saved as MP3, transcoded to PCM WAV via ffmpeg
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import subprocess
import sys

from soundscape import process_and_normalize_wav

CANONICAL_SR = 44100

_TTS_MODEL = None
_SPEAKER_LATENT: dict = {}


# =================================================================== helpers
def get_deterministic_seed(video_id: str) -> int:
    h = hashlib.sha256(video_id.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


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

        try:
            result = tts.synthesizer.tts_model.inference(
                text=text, language="en",
                gpt_cond_latent=gpt, speaker_embedding=emb,
                temperature=0.65, speed=1.0,
                repetition_penalty=3.0,
                enable_text_splitting=True,
            )
        except Exception as e:
            if "cuda" in str(e).lower() or "out of memory" in str(e).lower():
                print("[TTS] CUDA OOM — retrying on CPU", file=sys.stderr)
                _reset_tts()
                tts = _get_tts(use_gpu=False)
                gpt, emb = _get_speaker_latent(tts, speaker_wav)
                result = tts.synthesizer.tts_model.inference(
                    text=text, language="en",
                    gpt_cond_latent=gpt, speaker_embedding=emb,
                    temperature=0.65, speed=1.0,
                    repetition_penalty=3.0,
                    enable_text_splitting=True,
                )
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
    """Edge-TTS produces MP3; transcode to PCM WAV via ffmpeg."""
    temp_mp3 = output_wav + ".tmp.mp3"
    try:
        import edge_tts

        async def _run():
            communicate = edge_tts.Communicate(
                text, "en-US-ChristopherNeural", rate="+0%"
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
    args = p.parse_args()

    seed = get_deterministic_seed(args.video_id)
    raw_wav = args.output + ".raw.wav"

    success = False
    if os.path.exists(args.speaker_wav):
        success = synthesize_coqui(args.script, args.speaker_wav, raw_wav, seed)

    if not success:
        print("[INFO] Falling back to Edge-TTS", file=sys.stderr)
        success = synthesize_edge_tts(args.script, raw_wav)

    if not success or not os.path.exists(raw_wav):
        print(f"[FATAL] Audio synthesis failed for {args.video_id}", file=sys.stderr)
        return 1

    process_and_normalize_wav(raw_wav, args.output)

    if os.path.exists(raw_wav):
        os.remove(raw_wav)

    print(f"[SUCCESS] Audio generated: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
