"""
batch_runner.py — Subprocess orchestrator & FFmpeg stitcher.

Fixes in this version:
  * Explicit --resolution 1080,1920 (portrait) — no more -qh landscape
  * Env var length guard for BEATS_JSON / BINDINGS_JSON
  * Stale-render detection via mtime
  * alimiter prevents audio clipping after amix
  * faststart MP4 for web playback
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

from generate_audio import synthesize_audio_for_row

OUTPUT_DIR   = Path("output_shorts")
CSV_FILE     = Path("content_batch.csv")
VOICE_SAMPLE = Path("saem_voice_sample.wav")
MEDIA_DIR    = Path("media")
TEMP_AUDIO   = Path("temp_audio")

RESOLUTION = "1080,1920"
FPS = 30
FFMPEG_PRESET = "veryfast"
FFMPEG_CRF = "20"

ENV_VAR_MAX_BYTES = 100_000    # safe margin under Linux 128KB limit

ENV_WHITELIST = {
    "PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM",
    "PYTHONPATH", "PYTHONUNBUFFERED", "TMPDIR",
    "COQUI_TOS_AGREED",
    "VIDEO_ID", "CONCEPT_TYPE", "HEADER_TITLE", "TAGLINE",
    "QUESTION_TEXT", "OPTION_A", "OPTION_B", "OPTION_C", "OPTION_D",
    "CORRECT_ANSWER", "EQUATIONS_JSON", "VISUAL_DATA_JSON",
    "AUDIO_DURATION", "SAFE_MODE", "HINDI_FONT", "SCENE_STYLE",
    "BEATS_JSON", "BINDINGS_JSON",
}


# =================================================================== HELPERS
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", (name or "").strip())


def str_val(row: dict, key: str) -> str:
    v = row.get(key)
    return str(v).strip() if v is not None else ""


def build_row_env(row: dict, audio_duration: float) -> dict:
    env = {k: v for k, v in os.environ.items() if k in ENV_WHITELIST}
    for k, v in row.items():
        if k and v is not None:
            key = k.strip().upper()
            val = str(v).strip()
            # guard against env var overflow (Linux limit ~128KB)
            if len(val.encode("utf-8")) > ENV_VAR_MAX_BYTES:
                print(f"  ! WARNING: env var {key} exceeds {ENV_VAR_MAX_BYTES} bytes; skipping")
                continue
            env[key] = val
    env["AUDIO_DURATION"] = f"{audio_duration:.3f}"
    env["SAFE_MODE"] = env.get("SAFE_MODE", "1")
    env["SCENE_STYLE"] = env.get("SCENE_STYLE", "cinematic")
    return env


def find_rendered_file(vid_id: str, min_mtime: float) -> Path | None:
    candidates = [
        p for p in MEDIA_DIR.rglob(f"{vid_id}.mp4")
        if p.stat().st_mtime >= min_mtime
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def stitch_av(raw_video: Path, voice: Path, pad: Path, out: Path) -> None:
    # amix voice + pad → limiter → pad tail; video holds last frame for 2s
    filter_complex = (
        "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amix];"
        "[amix]alimiter=limit=0.95,apad=pad_len=96000[aout];"
        f"[0:v]tpad=stop_mode=clone:stop_duration=2,fps={FPS},format=yuv420p[vout]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw_video),
            "-i", str(voice),
            "-i", str(pad),
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", FFMPEG_CRF,
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart",
            "-shortest",
            str(out),
        ],
        check=True,
    )


# =================================================================== MAIN
def parse_args():
    p = argparse.ArgumentParser(description="Batch producer for Manim physics shorts.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", type=str, default="")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--chunk", type=int, default=0)
    p.add_argument("--total-chunks", type=int, default=1)
    p.add_argument("--log-file", type=str, default="")
    p.add_argument("--retries", type=int, default=2)
    return p.parse_args()


def process_batch() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(exist_ok=True)

    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV file '{CSV_FILE}' not found")
    if not VOICE_SAMPLE.exists():
        raise FileNotFoundError(f"Reference voice '{VOICE_SAMPLE}' not found")

    with CSV_FILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    only_set = {sanitize_filename(x) for x in args.only.split(",") if x.strip()}
    if only_set:
        rows = [r for r in rows if sanitize_filename(str_val(r, "video_id")) in only_set]

    rows.sort(key=lambda r: str_val(r, "video_id"))

    if args.total_chunks > 1:
        rows = [r for i, r in enumerate(rows) if i % args.total_chunks == args.chunk]

    total = len(rows)
    print(f"\n{'=' * 60}")
    print(f"  Production Engine — {total} video(s)")
    if args.total_chunks > 1:
        print(f"  Chunk {args.chunk + 1}/{args.total_chunks}")
    print(f"{'=' * 60}\n")

    runlog: list[dict] = []

    for idx, row in enumerate(rows, 1):
        raw_vid_id = str_val(row, "video_id") or f"short_{idx}"
        vid_id = sanitize_filename(raw_vid_id)
        concept = str_val(row, "concept_type").upper() or "GENERIC"
        final_output = OUTPUT_DIR / f"{vid_id}_final.mp4"

        if args.resume and final_output.exists():
            print(f"[{idx}/{total}] SKIP (resume)  {vid_id}")
            runlog.append({"video_id": vid_id, "status": "skipped"})
            continue

        if args.dry_run:
            print(f"[{idx}/{total}] DRY RUN  {vid_id}  ({concept})")
            runlog.append({"video_id": vid_id, "status": "dry_run",
                           "concept_type": concept})
            continue

        print(f"[{idx}/{total}] BUILD {vid_id}  ({concept})")

        last_err: Exception | None = None
        for attempt in range(1, args.retries + 2):
            try:
                _render_one(row, vid_id, final_output)
                runlog.append({"video_id": vid_id, "status": "ok",
                               "attempt": attempt})
                last_err = None
                break
            except Exception as e:
                last_err = e
                print(f"  ! Attempt {attempt} failed: {e}")
                if attempt <= args.retries:
                    time.sleep(2 ** attempt)

        if last_err is not None:
            runlog.append({"video_id": vid_id, "status": "error",
                           "error": f"{type(last_err).__name__}: {last_err}"})
            traceback.print_exc()

    if args.log_file:
        Path(args.log_file).parent.mkdir(parents=True, exist_ok=True)
        Path(args.log_file).write_text(json.dumps(runlog, indent=2),
                                       encoding="utf-8")

    if TEMP_AUDIO.exists() and not any(TEMP_AUDIO.iterdir()):
        TEMP_AUDIO.rmdir()


def _render_one(row: dict, vid_id: str, final_output: Path) -> None:
    voice = pad = None
    try:
        voice, pad, duration = synthesize_audio_for_row(
            row, speaker_wav=str(VOICE_SAMPLE), output_dir=str(TEMP_AUDIO)
        )

        env = build_row_env(row, duration)
        env["VIDEO_ID"] = vid_id

        t0 = time.time()
        print("  [Manim] Rendering scene...")
        subprocess.run(
            [
                "manim", "--disable_caching",
                "--resolution", RESOLUTION,
                "--fps", str(FPS),
                "-o", f"{vid_id}.mp4",
                "render_universal.py", "UniversalPhysicsScene",
            ],
            env=env, check=True, stdout=sys.stdout, stderr=sys.stderr,
        )

        raw_video = find_rendered_file(vid_id, min_mtime=t0)
        if raw_video is None:
            raise FileNotFoundError(
                f"Render output '{vid_id}.mp4' not found under {MEDIA_DIR}/"
            )

        print("  [FFmpeg] Stitching audio/video...")
        stitch_av(raw_video, Path(voice), Path(pad), final_output)
        print(f"  → SUCCESS: {final_output}\n")

        raw_video.unlink(missing_ok=True)

    finally:
        for p in (voice, pad):
            if p and Path(p).exists():
                Path(p).unlink(missing_ok=True)


if __name__ == "__main__":
    process_batch()
