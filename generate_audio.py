import os
import wave
import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, lfilter
from TTS.api import TTS

os.environ["COQUI_TOS_AGREED"] = "1"

_TTS_MODEL = None


def get_tts_model(use_gpu: bool = None) -> TTS:
    """Lazy-loads and caches the XTTS-v2 voice model."""
    global _TTS_MODEL
    if _TTS_MODEL is None:
        if use_gpu is None:
            use_gpu = torch.cuda.is_available()
        print(f"[TTS] Loading XTTS-v2 Model (GPU: {use_gpu})...")
        _TTS_MODEL = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_gpu)
    return _TTS_MODEL


def clean_audio_text(text: str) -> str:
    """Ensures text ends with proper punctuation to prevent voice artifacts."""
    if not text:
        return ""
    text = text.strip('"\'').strip()
    if text and text[-1] not in ['.', '!', '?']:
        text += '.'
    return text


def get_wav_duration(file_path: str) -> float:
    """Returns exact duration of a WAV file in seconds."""
    with wave.open(file_path, 'r') as wave_file:
        return wave_file.getnframes() / float(wave_file.getframerate())


def create_ambient_pad(voice_path: str, output_pad_path: str, target_gain_db: float = -28.0):
    """Generates warm background noise matched to the voice track duration."""
    data, samplerate = sf.read(voice_path)
    num_samples = len(data) if data.ndim == 1 else data.shape[0]

    nyq = 0.5 * samplerate
    cutoff = min(400.0, nyq - 1.0)
    b, a = butter(2, cutoff / nyq, btype='low', analog=False)

    np.random.seed(42)
    raw_noise = np.random.normal(0, 0.05, num_samples)
    warm_noise = lfilter(b, a, raw_noise)
    gain_linear = 10 ** (target_gain_db / 20.0)

    sf.write(output_pad_path, warm_noise * gain_linear, samplerate)


def synthesize_audio_for_row(
    row: dict,
    speaker_wav: str = "saem_voice_sample.wav",
    output_dir: str = "."
) -> tuple[str, str, float]:
    """Synthesizes voice track and ambient background pad for a single CSV entry."""
    vid_id = row.get('video_id', 'short_video')
    os.makedirs(output_dir, exist_ok=True)

    voice_path = os.path.join(output_dir, f"{vid_id}_voice.wav")
    pad_path = os.path.join(output_dir, f"{vid_id}_pad.wav")

    raw_script = row.get('audio_script', '')
    clean_script = clean_audio_text(raw_script)

    if not clean_script:
        raise ValueError(f"Audio script for '{vid_id}' is missing or empty.")

    if not os.path.exists(speaker_wav):
        raise FileNotFoundError(f"Reference voice sample '{speaker_wav}' not found.")

    print(f"[TTS] Synthesizing Voice: {vid_id}")
    tts = get_tts_model()

    tts.tts_to_file(
        text=clean_script,
        file_path=voice_path,
        speaker_wav=speaker_wav,
        language="en",
        temperature=0.45,
        speed=1.0,
        repetition_penalty=3.0
    )

    duration = get_wav_duration(voice_path)
    create_ambient_pad(voice_path, pad_path)

    print(f"[TTS] Success: {vid_id} ({duration:.2f}s)")
    return voice_path, pad_path, duration
