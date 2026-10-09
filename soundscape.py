#!/usr/bin/env python3
"""soundscape.py — Ambient pad + voice mastering chain."""

from __future__ import annotations
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, resample_poly

CANONICAL_SR = 44100
PAD_FREQ_HZ  = 110.0
PAD_GAIN     = 0.020
PEAK_TARGET  = 0.891
LUFS_TARGET  = -14.0


def _highpass(sig, sr, cutoff=80.0):
    sos = butter(2, cutoff / (sr / 2.0), btype="high", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _lowpass(sig, sr, cutoff=12000.0):
    sos = butter(2, cutoff / (sr / 2.0), btype="low", output="sos")
    return sosfilt(sos, sig).astype(np.float32)


def _soft_compress(sig, threshold=0.25, ratio=3.0):
    out = sig.copy()
    mask = np.abs(sig) > threshold
    over = np.abs(sig[mask]) - threshold
    out[mask] = np.sign(sig[mask]) * (threshold + over / ratio)
    return out


def _loudness_normalize(sig, target_lufs=LUFS_TARGET):
    rms = float(np.sqrt(np.mean(sig ** 2) + 1e-12))
    if rms < 1e-6:
        return sig
    target_rms = 10 ** (target_lufs / 20.0) * 0.30
    gain = float(np.clip(target_rms / rms, 0.2, 8.0))
    return sig * gain


def _peak_limit(sig, ceiling=PEAK_TARGET):
    peak = float(np.max(np.abs(sig)))
    if peak > ceiling:
        sig = sig * (ceiling / peak)
    return sig.astype(np.float32)


def _resample(sig, sr_in, sr_out):
    if sr_in == sr_out:
        return sig
    g = int(np.gcd(sr_in, sr_out))
    up, down = sr_out // g, sr_in // g
    return resample_poly(sig, up, down).astype(np.float32)


def generate_ambient_pad(duration_sec, sample_rate=CANONICAL_SR):
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


def _to_mono_float(data, dtype):
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
    """High-pass → compress → low-pass → LUFS → mix pad → peak-limit → 44.1kHz."""
    sr, raw = wavfile.read(input_wav)
    voice = _to_mono_float(raw, raw.dtype)
    if voice.size == 0:
        raise ValueError(f"'{input_wav}' has no samples")

    voice = _highpass(voice, sr, 80.0)
    voice = _soft_compress(voice, 0.25, 3.0)
    voice = _lowpass(voice, sr, 12000.0)
    voice = _loudness_normalize(voice, LUFS_TARGET)

    # Resample to canonical 44.1kHz before mixing pad
    voice = _resample(voice, sr, CANONICAL_SR)
    sr_out = CANONICAL_SR

    duration = len(voice) / float(sr_out)
    pad = generate_ambient_pad(duration, sr_out)
    L = min(len(voice), len(pad))
    mixed = voice[:L] + pad[:L]

    mixed = _peak_limit(mixed, PEAK_TARGET)
    pcm = np.clip(mixed * 32767.0, -32768, 32767).astype(np.int16)
    wavfile.write(output_wav, sr_out, pcm)
