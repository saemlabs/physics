import os
import soundfile as sf
import torch
import numpy as np
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
        print(f"[TTS] Loading XTTS-v2 Model (GPU Acceleration: {use_gpu})...")
        _TTS_MODEL = TTS("tts_models/multilingual/multi-dataset/xtts_v2", gpu=use_gpu)
    return _TTS_MODEL


def clean_audio_text(text: str) -> str:
    """Cleans script text and enforces terminating punctuation to prevent trailing XTTS hallucinations."""
    if not text:
        return ""
    # Strip whitespace first, then quotes, then whitespace again
    text = str(text).strip().strip('"\'').strip()
    if text and text[-1] not in ['.', '!', '?']:
        text += '.'
    return text


def get_wav_duration(file_path: str) -> float:
    """Calculates the exact duration of a WAV file in seconds using SoundFile."""
    return float(sf.info(file_path).duration)


def create_ambient_pad(voice_path: str, output_pad_path: str, target_gain_db: float = -28.0):
    """Generates low-pass warm background noise matching the sample duration of the voice track."""
    data, samplerate = sf.read(voice_path)
    num_samples = len(data) if data.ndim == 1 else data.shape[0]

    nyq = 0.5 * samplerate
    cutoff = min(400.0, nyq - 1.0)
    b, a = butter(2, cutoff / nyq, btype='low', analog=False)

    np.random.seed(42)
    raw_noise = np.random.normal(0, 0.05, num_samples)
    warm_noise = lfilter(b, a, raw_noise)
    gain_linear = 10 ** (target_gain_db / 20.0)

    # Force 16-bit PCM output format for universal FFmpeg compatibility
    sf.write(output_pad_path, warm_noise * gain_linear, samplerate, subtype='PCM_16')


def synthesize_audio_for_row(
    row: dict,
    speaker_wav: str = "saem_voice_sample.wav",
    output_dir: str = "."
) -> tuple[str, str, float]:
    """Synthesizes voice track and ambient background pad for a single CSV entry."""
    raw_vid_id = str(row.get('video_id') or 'short_video').strip()
    vid_id = raw_vid_id if raw_vid_id else 'short_video'
    
    os.makedirs(output_dir, exist_ok=True)

    voice_path = os.path.join(output_dir, f"{vid_id}_voice.wav")
    pad_path = os.path.join(output_dir, f"{vid_id}_pad.wav")

    raw_script = str(row.get('audio_script') or '')
    clean_script = clean_audio_text(raw_script)

    if not clean_script:
        raise ValueError(f"Audio script for video ID '{vid_id}' is missing or empty.")

    if not os.path.exists(speaker_wav):
        raise FileNotFoundError(f"Reference voice sample '{speaker_wav}' was not found in the working directory.")

    print(f"[TTS] Synthesizing Voice for: {vid_id}")
    tts = get_tts_model()

    # Optimized TTS synthesis parameters for clear voice output
    tts.tts_to_file(
        text=clean_script,
        file_path=voice_path,
        speaker_wav=speaker_wav,
        language="en",
        temperature=0.45,       # Lower temperature forces deterministic voice output
        speed=1.0,
        repetition_penalty=3.0  # Prevents word repetition and stuttering
    )

    duration = get_wav_duration(voice_path)
    create_ambient_pad(voice_path, pad_path)

    print(f"[TTS] Completed '{vid_id}' | Voice Track Duration: {duration:.2f}s")
    return voice_path, pad_path, duration
