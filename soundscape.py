#!/usr/bin/env python3
"""
soundscape.py — Voice mastering chain tuned to PRESERVE the cloned identity.

Chain (in order):
  1. Read input (XTTS gives 24 kHz; Edge-TTS gave 44.1 kHz)
  2. Resample to 44.1 kHz FIRST  ← fixes the Nyquist crash
  3. Gentle high-pass 70 Hz (removes rumble, keeps chest tone)
  4. Very light soft-compress (peak smoothing only, does NOT reshape voice)
  5. Gentle low-pass 14 kHz (keeps full vocal timbre)
  6. LUFS-normalize to -14 (YouTube standard)
  7. Mix ambient pad (A2 drone, -35 dB under voice)
  8. Peak-limit to -1 dBFS, write 16-bit PCM
"""

from __future__ import annotations
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, resample_poly

CANONICAL_SR = 44100
PAD_FREQ_HZ  = 110.0
PAD_GAIN     = 0.018
PEAK_TARGET  = 0.891        # -1 dBFS
LUFS_TARGET  = -14.0


# ============================================================ filters
def _highpass(sig: np.ndarray, sr: int, cutoff: float = 70.0) -> np.ndarray:
    nyq = sr / 2.0
    cutoff = max(1.0, min(cutoff, nyq * 0.95))
    sos = butter(2, cutoff / nyq, btype="high", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _lowpass(sig: np.ndarray, sr: int, cutoff: float = 14000.0) -> np.ndarray:
    nyq = sr / 2.0
    cutoff = min(cutoff, nyq * 0.95)
    sos = butter(2, cutoff / nyq, btype="low", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _soft_compress(sig: np.ndarray, threshold: float = 0.40,
                   ratio: float = 2.0) -> np.ndarray:
    """Gentle peak-smoothing only — does NOT reshape voice character."""
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
    """A2 drone with fifth + octave harmonics, faded 0.6s in/out."""
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

    # ★ Resample FIRST — this is the Nyquist fix
    voice = _resample(voice, sr, CANONICAL_SR)
    sr = CANONICAL_SR

    # Gentle, identity-preserving cleanup
    voice = _highpass(voice, sr, 70.0)
    voice = _soft_compress(voice, 0.40, 2.0)
    voice = _lowpass(voice, sr, 14000.0)
    voice = _loudness_normalize(voice, LUFS_TARGET)

    duration = len(voice) / float(sr)
    pad = generate_ambient_pad(duration, sr)
    L = min(len(voice), len(pad))
    mixed = voice[:L] + pad[:L]

    mixed = _peak_limit(mixed, PEAK_TARGET)
    pcm = np.clip(mixed * 32767.0, -32768, 32767).astype(np.int16)
    wavfile.write(output_wav, sr, pcm)
