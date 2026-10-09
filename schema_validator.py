#!/usr/bin/env python3
"""
schema_validator.py — CSV pre-flight validator.

Fixes vs. previous version:
  * safe_json_loads matches render_universal.py (single-backslash tolerant)
  * Validates optional beats_json / bindings_json columns if present
  * Robust handling of None / empty cells
"""

from __future__ import annotations

import csv
import json
import re
import sys

X_MIN, X_MAX = -3.5, 3.5
Y_MIN, Y_MAX = -2.2, 1.8

WORD_MIN, WORD_MAX = 70, 160


def safe_json_loads(val_str: str):
    if not val_str or val_str.strip() in ('""', ""):
        return []
    cleaned = re.sub(r"(?<!\\)\\(?!\\)", r"\\\\", val_str)
    return json.loads(cleaned)


def check_spatial_bounds(item: dict, video_id: str, row_idx: int) -> list[str]:
    warnings = []
    for key in ("pos", "start", "end", "center", "pivot"):
        if key not in item:
            continue
        coords = item[key]
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            continue
        try:
            x, y = float(coords[0]), float(coords[1])
        except (TypeError, ValueError):
            continue
        if not (X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX):
            warnings.append(
                f"[WARN] Row {row_idx} ({video_id}) primitive '{item.get('type')}' "
                f"key '{key}'=({x}, {y}) is outside safe bounds "
                f"X∈[{X_MIN}, {X_MAX}], Y∈[{Y_MIN}, {Y_MAX}]"
            )
    return warnings


def validate_csv(csv_path: str) -> bool:
    has_errors = False
    with open(csv_path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print("[ERROR] CSV file is empty.")
            return False

        if len(header) < 13:
            print(f"[ERROR] CSV header has only {len(header)} columns; expected ≥ 13.")
            return False

        has_beats = "beats_json" in header
        has_bindings = "bindings_json" in header

        for row_idx, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) < 13:
                print(f"[ERROR] Row {row_idx}: only {len(row)} columns (need ≥ 13).")
                has_errors = True
                continue

            video_id = row[0].strip() or f"row_{row_idx}"
            eq_raw = row[10].strip()
            vis_raw = row[11].strip()
            script = row[12].strip()

            # word count
            words = script.split()
            if words and not (WORD_MIN <= len(words) <= WORD_MAX):
                print(f"[WARN] Row {row_idx} ({video_id}): script has "
                      f"{len(words)} words (recommended {WORD_MIN}-{WORD_MAX}).")

            # equations_json
            try:
                eqs = safe_json_loads(eq_raw)
                if not isinstance(eqs, list):
                    print(f"[ERROR] Row {row_idx} ({video_id}): equations_json not a list.")
                    has_errors = True
            except Exception as e:
                print(f"[ERROR] Row {row_idx} ({video_id}): equations_json — {e}")
                has_errors = True

            # visual_data_json
            try:
                visuals = safe_json_loads(vis_raw)
                if not isinstance(visuals, list):
                    print(f"[ERROR] Row {row_idx} ({video_id}): visual_data_json not a list.")
                    has_errors = True
                else:
                    for item in visuals:
                        if isinstance(item, dict):
                            for w in check_spatial_bounds(item, video_id, row_idx):
                                print(w)
            except Exception as e:
                print(f"[ERROR] Row {row_idx} ({video_id}): visual_data_json — {e}")
                has_errors = True

            # optional beats / bindings
            if has_beats:
                try:
                    idx = header.index("beats_json")
                    raw = row[idx].strip() if idx < len(row) else ""
                    if raw:
                        beats = safe_json_loads(raw)
                        if not isinstance(beats, list):
                            print(f"[ERROR] Row {row_idx}: beats_json not a list.")
                            has_errors = True
                except Exception as e:
                    print(f"[ERROR] Row {row_idx} ({video_id}): beats_json — {e}")
                    has_errors = True

            if has_bindings:
                try:
                    idx = header.index("bindings_json")
                    raw = row[idx].strip() if idx < len(row) else ""
                    if raw:
                        bindings = safe_json_loads(raw)
                        if not isinstance(bindings, list):
                            print(f"[ERROR] Row {row_idx}: bindings_json not a list.")
                            has_errors = True
                except Exception as e:
                    print(f"[ERROR] Row {row_idx} ({video_id}): bindings_json — {e}")
                    has_errors = True

    return not has_errors


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "content_batch.csv"
    print(f"[INFO] Validating {target}")
    if validate_csv(target):
        print("[SUCCESS] All dataset checks passed.")
        return 0
    print("[FATAL] Pre-flight validation failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
