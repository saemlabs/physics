#!/usr/bin/env python3
"""
generate_audio.py — XTTS-v2 voice cloning tuned for MAXIMUM identity match.

Identity-critical parameters:
  temperature = 0.55      low = stays close to reference (was 0.70)
  top_k       = 20        narrow sampling = more reference-like (was 50)
  top_p       = 0.75      tight nucleus = less improvisation (was 0.85)
  repetition_penalty = 2.5   conservative; high values distort cadence (was 5.0)
  speed       = 1.0       MUST match reference pace (was 0.95)
"""

from __future__ import annotations
import argparse
import hashlib
import os
import sys

from soundscape import master_voice

CANONICAL_SR = 44100
_TTS_MODEL = None
_SPEAKER_LATENT: dict = {}

# ------------------------------------------------------------------ identity
IDENTITY_PARAMS = {
    "temperature": 0.55,
    "top_k": 20,
    "top_p": 0.75,
    "repetition_penalty": 2.5,
    "speed": 1.0,
    "enable_text_splitting": True,
}


def _log(msg: str) -> None:
    print(f"[audio] {msg}", file=sys.stderr, flush=True)


def get_deterministic_seed(video_id: str) -> int:
    return int(hashlib.sha256(video_id.encode("utf-8")).hexdigest()[:8], 16)


def _inspect_reference(path: str) -> dict:
    """Deep audit of the reference sample; warns on identity-degrading issues."""
    import soundfile as sf
    info = sf.info(path)
    dur = info.frames / float(info.samplerate)
    _log(f"Reference: {dur:.2f}s, {info.samplerate} Hz, {info.channels} ch")

    # Identity-critical warnings
    if dur < 6.0:
        _log(f"!! CRITICAL: reference is {dur:.1f}s — XTTS clones poorly below 10s")
    elif dur < 10.0:
        _log(f"!! WARN: reference is {dur:.1f}s — 10-20s gives a much tighter clone")
    elif dur > 30.0:
        _log(f"!! WARN: reference is {dur:.1f}s — trim to 15s for sharper identity")

    if info.samplerate < 16000:
        _log(f"!! WARN: {info.samplerate} Hz reference loses vocal detail")

    # Optional: measure noise floor to warn on noisy references
    try:
        import numpy as np
        data, _ = sf.read(path, always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        # Estimate noise from the quietest 10% of windows
        win = max(1, int(info.samplerate * 0.02))
        energies = np.array([np.sqrt(np.mean(data[i:i+win]**2))
                            for i in range(0, len(data) - win, win)])
        if len(energies) > 10:
            noise_floor = np.percentile(energies, 10)
            signal = np.percentile(energies, 90)
            snr_db = 20 * np.log10((signal + 1e-12) / (noise_floor + 1e-12))
            _log(f"Reference SNR ~ {snr_db:.1f} dB")
            if snr_db < 25:
                _log("!! WARN: SNR < 25 dB — background noise will leak into the clone")
    except Exception:
        pass

    return {"duration": dur, "sr": info.samplerate}


def _get_tts(use_gpu: bool | None = None):
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


def synthesize(text: str, speaker_wav: str, output_wav: str, seed: int) -> None:
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
            text=text,
            language="en",
            gpt_cond_latent=g,
            speaker_embedding=e,
            **IDENTITY_PARAMS,
        )

    try:
        result = _infer(tts, gpt, emb)
    except Exception as e:
        msg = str(e).lower()
        if "cuda" in msg or "out of memory" in msg:
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

    target_sr = 24000
    try:
        model_sr = (
            getattr(tts.synthesizer.tts_model, "output_sample_rate", None)
            or getattr(tts.synthesizer.tts_model, "sample_rate", None)
        )
        if model_sr:
            target_sr = int(model_sr)
    except Exception:
        pass

    _log(f"XTTS output: {target_sr} Hz, {len(wav)/target_sr:.2f}s of speech")
    sf.write(output_wav, wav, target_sr, subtype="PCM_16")


def main() -> int:
    p = argparse.ArgumentParser(description="XTTS-v2 identity-tuned voice cloning.")
    p.add_argument("--video_id", required=True)
    p.add_argument("--script", required=True)
    p.add_argument("--speaker_wav", default="saem_voice_sample.wav")
    p.add_argument("--output", required=True)
    args = p.parse_args()

    if not os.path.exists(args.speaker_wav):
        _log(f"FATAL reference not found: '{args.speaker_wav}'")
        return 1

    seed = get_deterministic_seed(args.video_id)
    raw_wav = args.output + ".raw.wav"

    try:
        _inspect_reference(args.speaker_wav)
        _log(f"Synthesizing '{args.video_id}' (seed={seed}, {len(args.script.split())} words)")
        synthesize(args.script, args.speaker_wav, raw_wav, seed)
    except Exception as e:
        _log(f"FATAL XTTS failed: {type(e).__name__}: {e}")
        if os.path.exists(raw_wav):
            try:
                os.remove(raw_wav)
            except OSError:
                pass
        return 1

    if not os.path.exists(raw_wav):
        _log("FATAL XTTS produced no file")
        return 1

    try:
        master_voice(raw_wav, args.output)
    finally:
        if os.path.exists(raw_wav):
            try:
                os.remove(raw_wav)
            except OSError:
                pass

    _log(f"SUCCESS {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
