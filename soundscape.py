#!/usr/bin/env python3
"""
soundscape.py — Voice mastering chain + ambient pad.

Critical order (this is what fixed the SciPy Nyquist crash):
  1. read input (may be any sample rate — XTTS gives 24 kHz)
  2. resample to 44.1 kHz FIRST
  3. high-pass → soft-compress → low-pass  (all safe at 44.1 kHz)
  4. loudness normalize to -14 LUFS (YouTube standard)
  5. mix ambient pad
  6. peak-limit, write 16-bit PCM
"""

from __future__ import annotations
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, resample_poly

CANONICAL_SR = 44100
PAD_FREQ_HZ  = 110.0
PAD_GAIN     = 0.020
PEAK_TARGET  = 0.891       # -1 dBFS
LUFS_TARGET  = -14.0


# ============================================================ filters
def _highpass(sig: np.ndarray, sr: int, cutoff: float = 80.0) -> np.ndarray:
    """High-pass with Nyquist guard."""
    nyq = sr / 2.0
    cutoff = max(1.0, min(cutoff, nyq * 0.95))
    sos = butter(2, cutoff / nyq, btype="high", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _lowpass(sig: np.ndarray, sr: int, cutoff: float = 12000.0) -> np.ndarray:
    """Low-pass with Nyquist guard — prevents Wn=1.0 ValueError."""
    nyq = sr / 2.0
    cutoff = min(cutoff, nyq * 0.95)
    sos = butter(2, cutoff / nyq, btype="low", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _soft_compress(sig: np.ndarray, threshold: float = 0.25,
                   ratio: float = 3.0) -> np.ndarray:
    out = sig.copy()
    mask = np.abs(sig) > threshold
    over = np.abs(sig[mask]) - threshold
    out[mask] = np.sign(sig[mask]) * (threshold + over / ratio)
    return out


def _loudness_normalize(sig: np.ndarray,
                        target_lufs: float = LUFS_TARGET) -> np.ndarray:
    rms = float(np.sqrt(np.mean(sig ** 2) + 1e-12))
    if rms < 1e-6:
        return sig
    target_rms = 10 ** (target_lufs / 20.0) * 0.30
    gain = float(np.clip(target_rms / rms, 0.2, 8.0))
    return sig * gain


def _peak_limit(sig: np.ndarray, ceiling: float = PEAK_TARGET) -> np.ndarray:
    peak = float(np.max(np.abs(sig)))
    if peak > ceiling:
        sig = sig * (ceiling / peak)
    return sig.astype(np.float32)


def _resample(sig: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return sig.astype(np.float32)
    g = int(np.gcd(sr_in, sr_out))
    up, down = sr_out // g, sr_in // g
    return resample_poly(sig, up, down).astype(np.float32)


# ============================================================ pad
def generate_ambient_pad(duration_sec: float,
                         sample_rate: int = CANONICAL_SR) -> np.ndarray:
    """A2 drone (110 Hz) with fifth + octave harmonics, faded 0.6s in/out."""
    n = max(1, int(sample_rate * duration_sec))
    t = np.linspace(0, duration_sec, n, endpoint=False)
    drone = (
        PAD_GAIN * np.sin(2 * np.pi * PAD_FREQ_HZ * t)
        + 0.35 * PAD_GAIN * np.sin(2 * np.pi * PAD_FREQ_HZ * 1.5 * t)
        + 0.15 * PAD_GAIN * np.sin(2 * np.pi * PAD_FREQ_HZ * 2.0 * t)
    ).astype(np.float32)
    fade = min(int(sample_rate * 0.6), n // 2)
    if fade > 0:
        env = np.ones(n, dtype=np.float32)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        drone *= env
    return drone


# ============================================================ helpers
def _to_mono_float(data: np.ndarray, dtype: np.dtype) -> np.ndarray:
    if dtype == np.int16:
        out = data.astype(np.float32) / 32768.0
    elif dtype == np.int32:
        out = data.astype(np.float32) / 2147483648.0
    else:
        out = data.astype(np.float32)
    if out.ndim > 1:
        out = np.mean(out, axis=1)
    return out


# ============================================================ main
def master_voice(input_wav: str, output_wav: str) -> None:
    sr, raw = wavfile.read(input_wav)
    voice = _to_mono_float(raw, raw.dtype)
    if voice.size == 0:
        raise ValueError(f"'{input_wav}' has no samples")

    # ★ Resample BEFORE filtering — this is the fix for the Nyquist crash
    voice = _resample(voice, sr, CANONICAL_SR)
    sr = CANONICAL_SR

    voice = _highpass(voice, sr, 80.0)
    voice = _soft_compress(voice, 0.25, 3.0)
    voice = _lowpass(voice, sr, 12000.0)
    voice = _loudness_normalize(voice, LUFS_TARGET)

    duration = len(voice) / float(sr)
    pad = generate_ambient_pad(duration, sr)
    L = min(len(voice), len(pad))
    mixed = voice[:L] + pad[:L]

    mixed = _peak_limit(mixed, PEAK_TARGET)
    pcm = np.clip(mixed * 32767.0, -32768, 32767).astype(np.int16)
    wavfile.write(output_wav, sr, pcm)
