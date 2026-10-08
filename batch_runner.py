import os
import csv
import subprocess
import glob
import shutil
import traceback
from generate_audio import synthesize_audio_for_row

OUTPUT_DIR = "output_shorts"
MANIM_QUALITY = "-qh"  # High quality 1080x1920 60fps rendering ('-ql' for fast low-res drafts)
CSV_FILE = "content_batch.csv"
VOICE_SAMPLE = "saem_voice_sample.wav"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def process_batch():
    # 1. Pre-flight Checks
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"Batch configuration '{CSV_FILE}' not found.")
    
    if not os.path.exists(VOICE_SAMPLE):
        raise FileNotFoundError(f"Reference voice sample '{VOICE_SAMPLE}' not found in root directory.")

    with open(CSV_FILE, mode='r', encoding='utf-8') as file:
        reader = list(csv.DictReader(file))
        total = len(reader)
        print(f"\n==========================================")
        print(f" Starting Production Engine for {total} Videos ")
        print(f"==========================================\n")

        for idx, row in enumerate(reader, 1):
            vid_id = row.get('video_id', f'short_{idx}').strip()
            concept_type = row.get('concept_type', 'GENERIC').strip().upper()
            print(f"[{idx}/{total}] Building Video '{vid_id}' (Type: {concept_type})")

            voice_path, pad_path = None, None

            try:
                # 2. Synthesize Voiceover & Audio Pad
                voice_path, pad_path, audio_duration = synthesize_audio_for_row(row, speaker_wav=VOICE_SAMPLE, output_dir="temp_audio")

                # 3. Populate Environment Payload for Universal Scene Engine
                env = os.environ.copy()
                for key, val in row.items():
                    if key and val:
                        env[key.strip().upper()] = str(val).strip()
                env["AUDIO_DURATION"] = str(audio_duration)
                env["VIDEO_ID"] = str(vid_id)

                # 4. Clean Stale Intermediate Frames
                if os.path.exists("media"):
                    shutil.rmtree("media", ignore_errors=True)

                # 5. Render Scene with Universal Physics Engine
                print(f"[Manim Engine] Rendering 3b1b Animation...")
                subprocess.run([
                    "manim", MANIM_QUALITY,
                    "--disable_caching",
                    "-o", f"{vid_id}.mp4",
                    "render_universal.py", "UniversalPhysicsScene"
                ], env=env, check=True, capture_output=True, text=True)

                found = glob.glob(f"media/**/{vid_id}.mp4", recursive=True)
                if not found:
                    raise FileNotFoundError(f"Render output '{vid_id}.mp4' not found in media/")
                raw_video = found[0]

                # 6. FFmpeg Audio/Video Sync and Post-Processing
                final_output = os.path.join(OUTPUT_DIR, f"{vid_id}_final.mp4")
                print(f"[FFmpeg] Stitching media into {final_output}...")

                # Combine voice + background pad, add trailing pad to audio, freeze final video frame 2s
                filter_complex = (
                    "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amixout];"
                    "[amixout]apad=pad_len=96000[aout];"
                    "[0:v]tpad=stop_mode=clone:stop_duration=2[vout]"
                )

                subprocess.run([
                    "ffmpeg", "-y",
                    "-i", raw_video,
                    "-i", voice_path,
                    "-i", pad_path,
                    "-filter_complex", filter_complex,
                    "-map", "[vout]",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-shortest",
                    final_output
                ], check=True, capture_output=True, text=True)

                print(f" SUCCESS: {final_output}\n")

            except subprocess.CalledProcessError as cpe:
                print(f" ERROR processing '{vid_id}': Command failed with exit code {cpe.returncode}")
                if cpe.stderr:
                    print(f"--- Process Error Log ---\n{cpe.stderr.strip()}\n-------------------------")
                traceback.print_exc()
                continue
            except Exception as e:
                print(f" ERROR processing '{vid_id}': {str(e)}")
                traceback.print_exc()
                continue

            finally:
                # Cleanup temporary WAV files per iteration
                for path in [voice_path, pad_path]:
                    if path and os.path.exists(path):
                        os.remove(path)

    # Clean empty audio directory on completion
    if os.path.exists("temp_audio") and not os.listdir("temp_audio"):
        os.rmdir("temp_audio")


if __name__ == "__main__":
    process_batch()
