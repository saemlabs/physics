"""
generate_audio.py — XTTS-v2 voice synthesis + ambient background pad.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, lfilter, resample_poly
from TTS.api import TTS

os.environ.setdefault("COQUI_TOS_AGREED", "1")

CANONICAL_SR = 44100
TARGET_PAD_DB = -34.0
_TTS_MODEL: TTS | None = None
_SPEAKER_LATENT: tuple | None = None


def get_tts_model(use_gpu: bool | None = None) -> TTS:
    global _TTS_MODEL
    if _TTS_MODEL is None:
        if use_gpu is None:
            use_gpu = torch.cuda.is_available()
        print(f"[TTS] Loading XTTS-v2 Model (GPU={use_gpu})...")
        _TTS_MODEL = TTS(
            "tts_models/multilingual/multi-dataset/xtts_v2",
            gpu=use_gpu,
        )
    return _TTS_MODEL


def _get_speaker_latent(tts: TTS, speaker_wav: str) -> tuple:
    global _SPEAKER_LATENT
    if _SPEAKER_LATENT is None:
        print(f"[TTS] Computing speaker latent from '{speaker_wav}'...")
        gpt_cond_latent, speaker_embedding = tts.synthesizer.tts_model.get_conditioning_latents(
            audio_path=[speaker_wav]
        )
        _SPEAKER_LATENT = (gpt_cond_latent, speaker_embedding)
    return _SPEAKER_LATENT


def clean_audio_text(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip().strip('"\'').strip()
    text = text.replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _seed_from_id(vid_id: str) -> int:
    h = hashlib.sha256(vid_id.encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def get_wav_duration(path: str | Path) -> float:
    info = sf.info(str(path))
    return float(info.frames) / float(info.samplerate)


def _resample_to_canonical(path: str | Path):
    data, sr = sf.read(str(path))
    if sr != CANONICAL_SR:
        gcd = np.gcd(int(sr), CANONICAL_SR)
        up = CANONICAL_SR // gcd
        down = int(sr) // gcd
        resampled = resample_poly(data, up, down, axis=0)
        resampled = np.clip(resampled, -1.0, 1.0)
        sf.write(str(path), resampled.astype(np.float32), CANONICAL_SR, subtype='PCM_16')


def create_ambient_pad(
    voice_path: str | Path,
    output_pad_path: str | Path,
    target_gain_db: float = TARGET_PAD_DB
):
    data, sr = sf.read(str(voice_path))
    n = len(data) if data.ndim == 1 else data.shape[0]

    nyq = 0.5 * sr
    cutoff = min(400.0, nyq - 1.0)
    b, a = butter(2, cutoff / nyq, btype="low", analog=False)

    rng = np.random.default_rng(42)
    noise = lfilter(b, a, rng.normal(0, 1.0, n))

    rms = np.sqrt(np.mean(noise ** 2) + 1e-12)
    target_rms = 10 ** (target_gain_db / 20.0)
    noise = (noise / rms) * target_rms
    noise = np.clip(noise, -1.0, 1.0)

    sf.write(str(output_pad_path), noise.astype(np.float32), int(sr), subtype='PCM_16')


def synthesize_audio_for_row(
    row: dict,
    speaker_wav: str = "saem_voice_sample.wav",
    output_dir: str = ".",
) -> tuple[str, str, float]:
    vid_id = (str(row.get("video_id") or "short_video")).strip() or "short_video"
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    voice_path = out / f"{vid_id}_voice.wav"
    pad_path   = out / f"{vid_id}_pad.wav"

    script = clean_audio_text(row.get("audio_script", ""))
    if not script:
        raise ValueError(f"Audio script is missing for video ID '{vid_id}'")
    if not Path(speaker_wav).exists():
        raise FileNotFoundError(f"Reference voice sample '{speaker_wav}' not found in working directory")

    language = (str(row.get("language") or "en")).strip() or "en"
    seed = _seed_from_id(vid_id)

    print(f"[TTS] Synthesizing '{vid_id}' (lang={language}, seed={seed})")
    tts = get_tts_model()

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)

    gpt_cond_latent, speaker_embedding = _get_speaker_latent(tts, speaker_wav)

    try:
        tts.tts_to_file(
            text=script,
            file_path=str(voice_path),
            speaker_wav=speaker_wav,
            gpt_cond_latent=gpt_cond_latent,
            speaker_embedding=speaker_embedding,
            language=language,
            temperature=0.65,
            speed=1.0,
            repetition_penalty=3.0,
            split_sentences=True,
        )
    except RuntimeError as e:
        if "cuda out of memory" in str(e).lower() or "cuda" in str(e).lower():
            print("[TTS] CUDA Out Of Memory detected. Retrying synthesis on CPU...")
            global _TTS_MODEL, _SPEAKER_LATENT
            _TTS_MODEL = None
            _SPEAKER_LATENT = None
            tts = get_tts_model(use_gpu=False)
            gpt_cond_latent, speaker_embedding = _get_speaker_latent(tts, speaker_wav)
            
            tts.tts_to_file(
                text=script,
                file_path=str(voice_path),
                speaker_wav=speaker_wav,
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
                language=language,
                temperature=0.65,
                speed=1.0,
                repetition_penalty=3.0,
                split_sentences=True,
            )
        else:
            raise

    _resample_to_canonical(voice_path)
    duration = get_wav_duration(voice_path)
    create_ambient_pad(voice_path, pad_path)

    print(f"[TTS] Completed '{vid_id}' | Voice Track Duration: {duration:.2f}s")
    return str(voice_path), str(pad_path), duration
