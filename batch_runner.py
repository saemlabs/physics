import os
import csv
import subprocess
import glob
import shutil
import traceback
from generate_audio import synthesize_audio_for_row

OUTPUT_DIR = "output_shorts"
MANIM_QUALITY = "-qh"  # '-qh' for 1080x1920 (60fps), '-ql' for fast low-res draft
CSV_FILE = "content_batch.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def process_batch():
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"Batch file '{CSV_FILE}' not found.")

    with open(CSV_FILE, mode='r', encoding='utf-8') as file:
        reader = list(csv.DictReader(file))
        total_videos = len(reader)
        print(f"\n--- Batch Pipeline Started: {total_videos} Videos ---\n")

        for idx, row in enumerate(reader, 1):
            vid_id = row.get('video_id', f'short_video_{idx}')
            print(f"[{idx}/{total_videos}] Processing Video: {vid_id}")

            voice_path, pad_path = None, None

            try:
                # 1. Voice Synthesis
                voice_path, pad_path, audio_duration = synthesize_audio_for_row(row, output_dir="temp_audio")

                # 2. Map CSV fields to Environment Variables
                env = os.environ.copy()
                for k, v in row.items():
                    if k and v:
                        env[k.upper()] = str(v)
                env["AUDIO_DURATION"] = str(audio_duration)
                env["VIDEO_ID"] = str(vid_id)

                # 3. Clear Stale Media
                if os.path.exists("media"):
                    shutil.rmtree("media", ignore_errors=True)

                # 4. Render Manim Animation
                print(f"[Manim] Rendering video scene...")
                subprocess.run([
                    "manim", MANIM_QUALITY,
                    "--disable_caching",
                    "-o", f"{vid_id}.mp4",
                    "render_pyq.py", "JEEShort"
                ], env=env, check=True)

                found_videos = glob.glob(f"media/**/{vid_id}.mp4", recursive=True)
                if not found_videos:
                    raise FileNotFoundError(f"Rendered file {vid_id}.mp4 missing from media/")
                
                raw_video = found_videos[0]

                # 5. FFmpeg Audio/Video Sync
                final_output = os.path.join(OUTPUT_DIR, f"{vid_id}_final.mp4")
                print(f"[FFmpeg] Stitching audio & video into {final_output}...")

                filter_complex = (
                    "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout];"
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
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

                print(f" COMPLETED -> {final_output}\n")

            except Exception as e:
                print(f" FAILED processing {vid_id}: {str(e)}")
                traceback.print_exc()
                continue

            finally:
                for path in [voice_path, pad_path]:
                    if path and os.path.exists(path):
                        os.remove(path)

    if os.path.exists("temp_audio") and not os.listdir("temp_audio"):
        os.rmdir("temp_audio")


if __name__ == "__main__":
    process_batch()
