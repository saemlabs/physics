#!/usr/bin/env python3
"""
soundscape.py — Ambient drone generator + audio mixer.

Fixes vs. previous version:
  * Length mismatch guard between narration and pad
  * Pad pitched at A2 (110 Hz) — audible on phone speakers
  * Handles empty input gracefully
  * Integer-dtype safe throughout
"""

from __future__ import annotations

import numpy as np
from scipy.io import wavfile

CANONICAL_SR = 44100
PAD_FREQ_HZ = 110.0          # A2 — audible on small speakers
PAD_GAIN = 0.030             # keep well under narration
PEAK_TARGET = 0.891          # -1 dBFS


def generate_ambient_pad(duration_sec: float,
                         sample_rate: int = CANONICAL_SR) -> np.ndarray:
    """Soft low-frequency drone with two harmonics and a 0.5 s fade in/out."""
    n = max(1, int(sample_rate * duration_sec))
    t = np.linspace(0, duration_sec, n, endpoint=False)

    # Fundamental + fifth harmonic for warmth
    drone = (
        PAD_GAIN * np.sin(2 * np.pi * PAD_FREQ_HZ * t)
        + 0.4 * PAD_GAIN * np.sin(2 * np.pi * (PAD_FREQ_HZ * 1.5) * t)
    )

    fade_len = min(int(sample_rate * 0.5), n // 2)
    envelope = np.ones(n, dtype=np.float32)
    if fade_len > 0:
        envelope[:fade_len] = np.linspace(0, 1, fade_len)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)

    return (drone * envelope).astype(np.float32)


def _to_float_mono(data: np.ndarray, dtype: np.dtype) -> np.ndarray:
    if dtype == np.int16:
        out = data.astype(np.float32) / 32768.0
    elif dtype == np.int32:
        out = data.astype(np.float32) / 2147483648.0
    else:
        out = data.astype(np.float32)

    if out.ndim > 1:
        out = np.mean(out, axis=1)
    return out


def process_and_normalize_wav(input_wav: str,
                              output_wav: str,
                              sample_rate: int = CANONICAL_SR) -> None:
    """
    Resample narration to mono float, mix ambient pad, normalize peak to -1 dBFS,
    write 16-bit PCM WAV.
    """
    sr, raw = wavfile.read(input_wav)
    narr = _to_float_mono(raw, raw.dtype)

    if narr.size == 0:
        raise ValueError(f"Input WAV '{input_wav}' has no samples")

    duration_sec = len(narr) / float(sr)
    pad = generate_ambient_pad(duration_sec, sample_rate=sr)

    # Length guard — trim pad to exactly match narration
    L = min(len(narr), len(pad))
    mixed = narr[:L] + pad[:L]

    peak = float(np.max(np.abs(mixed)))
    if peak > 0:
        mixed = (mixed / peak) * PEAK_TARGET

    pcm = np.clip(mixed * 32767.0, -32768, 32767).astype(np.int16)
    wavfile.write(output_wav, sr, pcm)
