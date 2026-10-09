#!/usr/bin/env python3
"""
soundscape.py — Voice cleaning + ambient drone + mastering.

This module is the audio mastering stage. Every voice WAV from XTTS or
Edge-TTS passes through here before hitting FFmpeg.
"""

from __future__ import annotations

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

CANONICAL_SR = 44100
PAD_FREQ_HZ = 110.0          # A2 — audible on phone speakers
PAD_GAIN = 0.022             # ~-33 dB under narration
PEAK_TARGET = 0.891          # -1 dBFS
LUFS_TARGET = -14.0          # YouTube Shorts standard


# =================================================================== FILTERS
def _highpass(sig: np.ndarray, sr: int, cutoff: float = 80.0) -> np.ndarray:
    """Remove rumble below cutoff — voice has no useful content there."""
    sos = butter(2, cutoff / (sr / 2.0), btype="high", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _lowpass(sig: np.ndarray, sr: int, cutoff: float = 12000.0) -> np.ndarray:
    """Soften the top end — takes the 'digital' edge off synthetic speech."""
    sos = butter(2, cutoff / (sr / 2.0), btype="low", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _soft_compress(sig: np.ndarray, threshold: float = 0.25,
                   ratio: float = 3.0) -> np.ndarray:
    """
    Simple soft-knee compressor — evens out dynamics so loud syllables
    don't blow out and quiet ones don't disappear.
    """
    out = sig.copy()
    mask = np.abs(sig) > threshold
    over = np.abs(sig[mask]) - threshold
    compressed = threshold + over / ratio
    out[mask] = np.sign(sig[mask]) * compressed
    return out


def _loudness_normalize(sig: np.ndarray, sr: int,
                        target_lufs: float = LUFS_TARGET) -> np.ndarray:
    """
    Approximate ITU-R BS.1770 loudness normalization via RMS.
    Good enough for Shorts; not reference-grade for cinema.
    """
    # RMS over the whole signal
    rms = np.sqrt(np.mean(sig ** 2) + 1e-12)
    if rms < 1e-6:
        return sig
    # target RMS ~= 10^(LUFS/20) with empirical offset
    target_rms = 10 ** (target_lufs / 20.0) * 0.30
    gain = target_rms / rms
    # Limit to reasonable gain swing
    gain = float(np.clip(gain, 0.2, 8.0))
    out = sig * gain
    return out


def _peak_limit(sig: np.ndarray, ceiling: float = PEAK_TARGET) -> np.ndarray:
    peak = float(np.max(np.abs(sig)))
    if peak > ceiling:
        sig = sig * (ceiling / peak)
    return sig.astype(np.float32)


# =================================================================== PAD
def generate_ambient_pad(duration_sec: float,
                         sample_rate: int = CANONICAL_SR) -> np.ndarray:
    """
    A2 drone with fifth harmonic. Fades in over 0.6s and out over 0.6s.
    Mixed ~-33 dB under voice so it's felt more than heard.
    """
    n = max(1, int(sample_rate * duration_sec))
    t = np.linspace(0, duration_sec, n, endpoint=False)

    drone = (
        PAD_GAIN * np.sin(2 * np.pi * PAD_FREQ_HZ * t)
        + 0.35 * PAD_GAIN * np.sin(2 * np.pi * (PAD_FREQ_HZ * 1.5) * t)
        + 0.15 * PAD_GAIN * np.sin(2 * np.pi * (PAD_FREQ_HZ * 2.0) * t)
    ).astype(np.float32)

    fade = min(int(sample_rate * 0.6), n // 2)
    if fade > 0:
        env = np.ones(n, dtype=np.float32)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        drone *= env

    return drone


# =================================================================== MAIN
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


def master_voice(input_wav: str, output_wav: str) -> None:
    """
    Full mastering chain: highpass → soft-compress → lowpass → LUFS →
    mix pad → peak limit → write 16-bit PCM.
    """
    sr, raw = wavfile.read(input_wav)
    voice = _to_float_mono(raw, raw.dtype)

    if voice.size == 0:
        raise ValueError(f"'{input_wav}' has no samples")

    # 1) Clean the synthetic voice
    voice = _highpass(voice, sr, cutoff=80.0)
    voice = _soft_compress(voice, threshold=0.25, ratio=3.0)
    voice = _lowpass(voice, sr, cutoff=12000.0)

    # 2) Normalize to broadcast loudness
    voice = _loudness_normalize(voice, sr, target_lufs=LUFS_TARGET)

    # 3) Build pad to match exact narration length
    duration = len(voice) / float(sr)
    pad = generate_ambient_pad(duration, sample_rate=sr)
    L = min(len(voice), len(pad))
    mixed = voice[:L] + pad[:L]

    # 4) Peak-limit and write
    mixed = _peak_limit(mixed, ceiling=PEAK_TARGET)
    pcm = np.clip(mixed * 32767.0, -32768, 32767).astype(np.int16)
    wavfile.write(output_wav, sr, pcm)
