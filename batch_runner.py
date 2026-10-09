#!/usr/bin/env python3
"""
batch_runner.py — Orchestrator: CSV → audio → Manim → FFmpeg → MP4.

Fixes vs. previous version:
  * Explicit --resolution 1080,1920 --fps 30 to Manim CLI
  * subprocess calls have timeouts
  * Temp files cleaned even on failure
  * faststart + alimiter in FFmpeg stitcher
  * passes --speaker_wav through to generate_audio
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from wave import open as wave_open

from schema_validator import safe_json_loads, validate_csv

MANIM_TIMEOUT = 600     # 10 min per video
AUDIO_TIMEOUT = 300     # 5 min
FFMPEG_TIMEOUT = 120


def get_wav_duration(wav_path: str) -> float:
    with wave_open(wav_path, "rb") as f:
        return f.getnframes() / float(f.getframerate())


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "", name or "")


def parse_csv_file(csv_file: str) -> list[dict]:
    rows = []
    with open(csv_file, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if not row or len(row) < 13:
                continue
            rows.append({
                "video_id":        row[0].strip(),
                "concept_type":    row[1].strip(),
                "header_title":    row[2].strip(),
                "tagline":         row[3].strip(),
                "question_text":   row[4].strip(),
                "option_a":        row[5].strip(),
                "option_b":        row[6].strip(),
                "option_c":        row[7].strip(),
                "option_d":        row[8].strip(),
                "correct_answer":  row[9].strip(),
                "equations_json":  row[10].strip(),
                "visual_data_json": row[11].strip(),
                "audio_script":    row[12].strip(),
            })
    return rows


def run_pipeline_for_row(row: dict,
                         output_dir: str,
                         speaker_wav: str,
                         dry_run: bool = False) -> bool:
    video_id = sanitize_filename(row["video_id"])
    script = row["audio_script"]
    word_count = len(script.split())

    print("\n" + "=" * 60)
    print(f" Processing: {video_id} ({word_count} words)")
    print(f" Header    : {row['header_title']}")
    print("=" * 60)

    if dry_run:
        # Validate JSON structures
        safe_json_loads(row["equations_json"])
        safe_json_loads(row["visual_data_json"])
        print("[DRY-RUN] Syntax validated.")
        return True

    os.makedirs(output_dir, exist_ok=True)
    temp_audio = os.path.join(output_dir, f"{video_id}_audio.wav")
    temp_video = os.path.join(output_dir, f"{video_id}_raw.mp4")
    final_output = os.path.join(output_dir, f"{video_id}.mp4")

    try:
        # ---- Step 1: audio ----
        audio_cmd = [
            sys.executable, "generate_audio.py",
            "--video_id", video_id,
            "--script", script,
            "--speaker_wav", speaker_wav,
            "--output", temp_audio,
        ]
        subprocess.run(audio_cmd, check=True, timeout=AUDIO_TIMEOUT)

        if not os.path.exists(temp_audio):
            raise FileNotFoundError(f"Audio synthesis produced no file: {temp_audio}")

        duration = get_wav_duration(temp_audio) + 2.0

        # ---- Step 2: options array ----
        options_arr = [
            row[f"option_{ch}"]
            for ch in ("a", "b", "c", "d")
            if row.get(f"option_{ch}", "").strip()
        ]

        # ---- Step 3: Manim render ----
        render_cmd = [
            sys.executable, "render_universal.py",
            "--video_id", video_id,
            "--header_title", row["header_title"],
            "--tagline", row["tagline"],
            "--question_text", row["question_text"],
            "--options_json", json.dumps(options_arr),
            "--correct_answer", row["correct_answer"],
            "--equations_json", row["equations_json"],
            "--visual_data_json", row["visual_data_json"],
            "--duration", str(duration),
            "--output", temp_video,
        ]
        subprocess.run(render_cmd, check=True, timeout=MANIM_TIMEOUT)

        if not os.path.exists(temp_video):
            raise FileNotFoundError(f"Manim produced no file: {temp_video}")

        # ---- Step 4: FFmpeg stitch with broadcast mastering ----
              # Video: hold last frame 2s, fixed 30fps, yuv420p, faststart
              # Audio: skip external limiter (voice is already mastered);
        #        just encode to AAC 192k at 48kHz (YouTube-native)
ffmpeg_cmd = [
    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
    "-i", temp_video,
    "-i", temp_audio,
    "-filter_complex",
    "[0:v]tpad=stop_mode=clone:stop_duration=2,fps=30,format=yuv420p[v];"
    "[1:a]aresample=48000,apad=pad_len=96000[a]",
    "-map", "[v]", "-map", "[a]",
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-crf", "20",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
    "-movflags", "+faststart",
    "-shortest",
    final_output,
        ]
     
        subprocess.run(ffmpeg_cmd, check=True, timeout=FFMPEG_TIMEOUT)

        print(f"[COMPLETE] {final_output}")
        return True

    finally:
        for f in (temp_audio, temp_video):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass


def main() -> int:
    p = argparse.ArgumentParser(description="Batch pipeline runner.")
    p.add_argument("--csv", default="content_batch.csv")
    p.add_argument("--output_dir", default="dist")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", default="")
    p.add_argument("--speaker_wav", default="saem_voice_sample.wav")
    p.add_argument("--shard-index", type=int, default=0)
    p.add_argument("--shard-total", type=int, default=1)
    args = p.parse_args()

    if not validate_csv(args.csv):
        print("[FATAL] CSV validation failed.", file=sys.stderr)
        return 1

    rows = parse_csv_file(args.csv)

    if args.only:
        target_ids = {t.strip() for t in args.only.split(",") if t.strip()}
        rows = [r for r in rows if r["video_id"] in target_ids]

    if args.shard_total > 1:
        rows = [r for i, r in enumerate(rows) if i % args.shard_total == args.shard_index]

    print(f"[INFO] {len(rows)} jobs for worker {args.shard_index + 1}/{args.shard_total}")

    success = 0
    for row in rows:
        try:
            if run_pipeline_for_row(row, args.output_dir, args.speaker_wav, args.dry_run):
                success += 1
        except subprocess.TimeoutExpired as e:
            print(f"[ERROR] {row.get('video_id')}: timeout — {e}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] {row.get('video_id')}: {e}", file=sys.stderr)

    print(f"\n[FINISHED] {success}/{len(rows)} videos processed.")
    return 0 if success == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
