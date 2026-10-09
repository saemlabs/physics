#!/usr/bin/env python3
"""batch_runner.py — CSV → audio → Manim → FFmpeg pipeline."""

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

MANIM_TIMEOUT = 600
AUDIO_TIMEOUT = 300
FFMPEG_TIMEOUT = 120


def _log(m): print(f"[batch] {m}", flush=True)


def get_wav_duration(path):
    with wave_open(path, "rb") as f:
        return f.getnframes() / float(f.getframerate())


def sanitize_filename(name):
    return re.sub(r"[^a-zA-Z0-9_\-]", "", name or "")


def parse_csv_file(csv_file):
    rows = []
    with open(csv_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if not row or len(row) < 13:
                continue
            rows.append({
                "video_id":         row[0].strip(),
                "concept_type":     row[1].strip(),
                "header_title":     row[2].strip(),
                "tagline":          row[3].strip(),
                "question_text":    row[4].strip(),
                "option_a":         row[5].strip(),
                "option_b":         row[6].strip(),
                "option_c":         row[7].strip(),
                "option_d":         row[8].strip(),
                "correct_answer":   row[9].strip(),
                "equations_json":   row[10].strip(),
                "visual_data_json": row[11].strip(),
                "audio_script":     row[12].strip(),
            })
    return rows


def _run(cmd, timeout, label):
    """Run subprocess and stream stdout/stderr into CI logs. Raises on failure."""
    _log(f"{label}: {' '.join(str(x) for x in cmd[:3])}...")
    try:
        proc = subprocess.run(
            cmd, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.TimeoutExpired:
        _log(f"{label} TIMEOUT after {timeout}s")
        raise
    # Stream output regardless of success — CI needs visibility
    if proc.stdout:
        for line in proc.stdout.splitlines():
            _log(f"  | {line}")
    if proc.returncode != 0:
        raise RuntimeError(f"{label} exited with code {proc.returncode}")


def run_pipeline_for_row(row, output_dir, speaker_wav, dry_run=False) -> bool:
    video_id = sanitize_filename(row["video_id"])
    script = row["audio_script"]
    word_count = len(script.split())

    _log("=" * 60)
    _log(f"Processing: {video_id} ({word_count} words)")
    _log(f"Header    : {row['header_title']}")
    _log("=" * 60)

    if dry_run:
        safe_json_loads(row["equations_json"])
        safe_json_loads(row["visual_data_json"])
        _log("[DRY-RUN] Syntax validated.")
        return True

    os.makedirs(output_dir, exist_ok=True)
    temp_audio = os.path.join(output_dir, f"{video_id}_audio.wav")
    temp_video = os.path.join(output_dir, f"{video_id}_raw.mp4")
    final_output = os.path.join(output_dir, f"{video_id}.mp4")

    # ============================================================
    # We wrap the entire pipeline in try/except/finally.
    # Every step is isolated so we know exactly which one failed.
    # The finally block ALWAYS cleans up temp files.
    # ============================================================
    try:
        # ---------------- Step 1: Audio ----------------
        audio_cmd = [
            sys.executable, "generate_audio.py",
            "--video_id", video_id,
            "--script", script,
            "--speaker_wav", speaker_wav,
            "--output", temp_audio,
        ]
        _run(audio_cmd, AUDIO_TIMEOUT, "audio")

        if not os.path.exists(temp_audio):
            raise FileNotFoundError(f"audio produced no file: {temp_audio}")

        duration = get_wav_duration(temp_audio) + 2.0
        _log(f"audio duration = {duration:.2f}s")

        # ---------------- Step 2: Options ----------------
        options_arr = [
            row[f"option_{ch}"]
            for ch in ("a", "b", "c", "d")
            if row.get(f"option_{ch}", "").strip()
        ]

        # ---------------- Step 3: Manim render ----------------
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
        _run(render_cmd, MANIM_TIMEOUT, "manim")

        if not os.path.exists(temp_video):
            raise FileNotFoundError(f"manim produced no file: {temp_video}")

        # ---------------- Step 4: FFmpeg stitch ----------------
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", temp_video,
            "-i", temp_audio,
            "-filter_complex",
            "[1:a]alimiter=limit=0.95,apad=pad_len=96000[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            "-shortest",
            final_output,
        ]
        _run(ffmpeg_cmd, FFMPEG_TIMEOUT, "ffmpeg")

        _log(f"COMPLETE {final_output}")
        return True

    except subprocess.TimeoutExpired:
        _log(f"FAILED (timeout): {video_id}")
        return False
    except Exception as e:
        _log(f"FAILED ({type(e).__name__}): {video_id} — {e}")
        return False
    finally:
        # ALWAYS remove temp files, whether we succeeded or not
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
        print("[batch] FATAL — CSV validation failed.", file=sys.stderr)
        return 1

    rows = parse_csv_file(args.csv)

    if args.only:
        ids = {t.strip() for t in args.only.split(",") if t.strip()}
        rows = [r for r in rows if r["video_id"] in ids]

    if args.shard_total > 1:
        rows = [r for i, r in enumerate(rows) if i % args.shard_total == args.shard_index]

    print(f"[batch] {len(rows)} jobs for worker {args.shard_index + 1}/{args.shard_total}")

    success = 0
    for row in rows:
        if run_pipeline_for_row(row, args.output_dir, args.speaker_wav, args.dry_run):
            success += 1

    print(f"[batch] FINISHED {success}/{len(rows)}")
    return 0 if success == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
