#!/usr/bin/env python3
"""
batch_runner.py — Orchestrator for the XTTS-v2 physics-shorts pipeline.

Flow per row:
    1. generate_audio.py  → XTTS-v2 voice clone + mastering  → <id>_audio.wav
    2. render_universal.py → Manim 9:16 cinematic render    → <id>_raw.mp4
    3. ffmpeg              → stitch audio + video           → <id>.mp4

Guarantees:
    * Never leaves temp files behind (finally block)
    * Streams subprocess output to CI logs so failures are visible
    * Each step has a hard timeout
    * Fails fast if the reference voice sample is missing
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

# ------------------------------------------------------------------ config
MANIM_TIMEOUT  = 600   # 10 min per Manim render
AUDIO_TIMEOUT  = 300   #  5 min per XTTS synthesis
FFMPEG_TIMEOUT = 120   #  2 min per stitch

DEFAULT_CSV         = "content_batch.csv"
DEFAULT_OUTPUT_DIR  = "dist"
DEFAULT_SPEAKER_WAV = "saem_voice_sample.wav"


# ------------------------------------------------------------------ logging
def _log(msg: str) -> None:
    """Flush every line so CI logs update live."""
    print(f"[batch] {msg}", flush=True)


# ------------------------------------------------------------------ helpers
def get_wav_duration(path: str) -> float:
    """Return duration in seconds of a WAV file."""
    with wave_open(path, "rb") as f:
        return f.getnframes() / float(f.getframerate())


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "", name or "")


def parse_csv_file(csv_file: str) -> list[dict]:
    """Parse the 13-column content_batch.csv into row dicts."""
    rows: list[dict] = []
    with open(csv_file, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
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


def _run(cmd: list[str], timeout: int, label: str) -> None:
    """
    Execute subprocess with timeout; stream its stdout+stderr to the CI log.
    Raise RuntimeError on non-zero exit so caller can decide what to do.
    """
    _log(f"{label}: {' '.join(str(x) for x in cmd[:4])} ...")
    try:
        proc = subprocess.run(
            cmd,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        _log(f"{label} TIMEOUT after {timeout}s")
        raise

    if proc.stdout:
        for line in proc.stdout.splitlines():
            _log(f"  | {line}")

    if proc.returncode != 0:
        raise RuntimeError(f"{label} exited with code {proc.returncode}")


# ------------------------------------------------------------------ per-row pipeline
def run_pipeline_for_row(
    row: dict,
    output_dir: str,
    speaker_wav: str,
    dry_run: bool = False,
) -> bool:
    video_id   = sanitize_filename(row["video_id"])
    script     = row["audio_script"]
    word_count = len(script.split())

    _log("=" * 60)
    _log(f"Processing: {video_id} ({word_count} words)")
    _log(f"Header    : {row['header_title']}")
    _log("=" * 60)

    # ---- dry-run: validate JSON only ----
    if dry_run:
        try:
            safe_json_loads(row["equations_json"])
            safe_json_loads(row["visual_data_json"])
            _log("[DRY-RUN] Syntax validated.")
            return True
        except Exception as e:
            _log(f"[DRY-RUN] FAILED: {type(e).__name__}: {e}")
            return False

    os.makedirs(output_dir, exist_ok=True)
    temp_audio   = os.path.join(output_dir, f"{video_id}_audio.wav")
    temp_video   = os.path.join(output_dir, f"{video_id}_raw.mp4")
    final_output = os.path.join(output_dir, f"{video_id}.mp4")

    try:
        # ============================================================
        # STEP 1 — XTTS-v2 voice cloning + mastering
        # ============================================================
        audio_cmd = [
            sys.executable, "generate_audio.py",
            "--video_id",    video_id,
            "--script",      script,
            "--speaker_wav", speaker_wav,
            "--output",      temp_audio,
        ]
        _run(audio_cmd, AUDIO_TIMEOUT, "audio")

        if not os.path.exists(temp_audio):
            raise FileNotFoundError(f"audio produced no file: {temp_audio}")

        duration = get_wav_duration(temp_audio) + 2.0   # 2s end-card hold
        _log(f"audio duration = {duration:.2f}s")

        # ============================================================
        # STEP 2 — collect PYQ options (blank for GENERIC rows)
        # ============================================================
        options_arr = [
            row[f"option_{ch}"]
            for ch in ("a", "b", "c", "d")
            if row.get(f"option_{ch}", "").strip()
        ]

        # ============================================================
        # STEP 3 — Manim 9:16 cinematic render
        # ============================================================
        render_cmd = [
            sys.executable, "render_universal.py",
            "--video_id",         video_id,
            "--header_title",     row["header_title"],
            "--tagline",          row["tagline"],
            "--question_text",    row["question_text"],
            "--options_json",     json.dumps(options_arr),
            "--correct_answer",   row["correct_answer"],
            "--equations_json",   row["equations_json"],
            "--visual_data_json", row["visual_data_json"],
            "--duration",         str(duration),
            "--output",           temp_video,
        ]
        _run(render_cmd, MANIM_TIMEOUT, "manim")

        if not os.path.exists(temp_video):
            raise FileNotFoundError(f"manim produced no file: {temp_video}")

        # ============================================================
        # STEP 4 — FFmpeg audio/video stitch
        # ============================================================
        # Voice is already mastered in soundscape.py — only need a
        # final limiter, an apad tail, and 48 kHz AAC (YouTube-native).
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", temp_video,
            "-i", temp_audio,
            "-filter_complex",
            "[1:a]alimiter=limit=0.95,apad=pad_len=96000[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
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
        # Always clean up temp files, whether we succeeded or not.
        for f in (temp_audio, temp_video):
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass


# ------------------------------------------------------------------ main
def main() -> int:
    p = argparse.ArgumentParser(description="Batch pipeline runner for physics shorts.")
    p.add_argument("--csv",          default=DEFAULT_CSV)
    p.add_argument("--output_dir",   default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--speaker_wav",  default=DEFAULT_SPEAKER_WAV)
    p.add_argument("--dry-run",      action="store_true")
    p.add_argument("--only",         default="",
                   help="Comma-separated video_ids to process")
    p.add_argument("--shard-index",  type=int, default=0)
    p.add_argument("--shard-total",  type=int, default=1)
    args = p.parse_args()

    # ---- preflight: CSV must validate ----
    if not validate_csv(args.csv):
        _log("FATAL — CSV validation failed.")
        return 1

    # ---- preflight: reference voice must exist (XTTS-only pipeline) ----
    if not os.path.exists(args.speaker_wav):
        _log(f"FATAL — reference voice sample missing: '{args.speaker_wav}'")
        _log("XTTS is the ONLY synthesizer. Place your sample at repo root.")
        return 1
    _log(f"Reference voice: {args.speaker_wav}")

    # ---- load rows ----
    rows = parse_csv_file(args.csv)

    # ---- --only filter ----
    if args.only:
        wanted = {t.strip() for t in args.only.split(",") if t.strip()}
        rows = [r for r in rows if r["video_id"] in wanted]

    # ---- sharding for CI matrix ----
    if args.shard_total > 1:
        rows = [
            r for i, r in enumerate(rows)
            if i % args.shard_total == args.shard_index
        ]

    _log(f"Worker {args.shard_index + 1}/{args.shard_total}: {len(rows)} job(s)")

    # ---- process each row ----
    success = 0
    for row in rows:
        if run_pipeline_for_row(row, args.output_dir, args.speaker_wav, args.dry_run):
            success += 1

    _log(f"FINISHED {success}/{len(rows)} videos succeeded.")

    # Non-zero exit if ANY row failed — tells CI the shard was incomplete.
    return 0 if success == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
