#!/usr/bin/env python3
"""schema_validator.py — Pre-flight CSV & JSON validator."""

from __future__ import annotations
import csv
import json
import re
import sys

X_MIN, X_MAX = -3.5, 3.5
Y_MIN, Y_MAX = -2.2, 1.8
WORD_MIN, WORD_MAX = 70, 200


def safe_json_loads(val_str: str):
    if not val_str or val_str.strip() in ('""', ""):
        return []
    cleaned = re.sub(r"(?<!\\)\\(?!\\)", r"\\\\", val_str)
    return json.loads(cleaned)


def _check_bounds(item, vid, row):
    out = []
    for k in ("pos", "start", "end", "center", "pivot"):
        if k not in item:
            continue
        c = item[k]
        if not isinstance(c, (list, tuple)) or len(c) < 2:
            continue
        try:
            x, y = float(c[0]), float(c[1])
        except (TypeError, ValueError):
            continue
        if not (X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX):
            out.append(f"[WARN] Row {row} ({vid}) '{item.get('type')}' {k}=({x},{y}) "
                       f"outside X∈[{X_MIN},{X_MAX}] Y∈[{Y_MIN},{Y_MAX}]")
    return out


def validate_csv(path: str) -> bool:
    has_errors = False
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print("[ERROR] CSV is empty.")
            return False
        if len(header) < 13:
            print(f"[ERROR] Header has {len(header)} cols, expected ≥13.")
            return False

        for row_idx, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) < 13:
                print(f"[ERROR] Row {row_idx}: {len(row)} cols, need ≥13.")
                has_errors = True
                continue

            vid = row[0].strip() or f"row_{row_idx}"
            script = row[12].strip()
            words = script.split()
            if words and not (WORD_MIN <= len(words) <= WORD_MAX):
                print(f"[WARN] Row {row_idx} ({vid}): {len(words)} words "
                      f"(want {WORD_MIN}-{WORD_MAX}).")

            for col_name, col_idx in (("equations_json", 10), ("visual_data_json", 11)):
                try:
                    parsed = safe_json_loads(row[col_idx].strip())
                    if not isinstance(parsed, list):
                        print(f"[ERROR] Row {row_idx} ({vid}): {col_name} not a list.")
                        has_errors = True
                    elif col_name == "visual_data_json":
                        for it in parsed:
                            if isinstance(it, dict):
                                for w in _check_bounds(it, vid, row_idx):
                                    print(w)
                except Exception as e:
                    print(f"[ERROR] Row {row_idx} ({vid}): {col_name} — {e}")
                    has_errors = True

            # Optional beats_json column (index 13)
            if len(row) > 13 and row[13].strip():
                try:
                    beats = safe_json_loads(row[13].strip())
                    if not isinstance(beats, list):
                        print(f"[ERROR] Row {row_idx} ({vid}): beats_json not a list.")
                        has_errors = True
                    else:
                        for b in beats:
                            if isinstance(b, dict) and "t" in b:
                                if not isinstance(b["t"], (int, float)):
                                    print(f"[WARN] Row {row_idx} ({vid}): "
                                          f"beat 't' not numeric")
                except Exception as e:
                    print(f"[ERROR] Row {row_idx} ({vid}): beats_json — {e}")
                    has_errors = True

            # Optional bindings_json column (index 14)
            if len(row) > 14 and row[14].strip():
                try:
                    binds = safe_json_loads(row[14].strip())
                    if not isinstance(binds, list):
                        print(f"[ERROR] Row {row_idx} ({vid}): bindings_json not a list.")
                        has_errors = True
                except Exception as e:
                    print(f"[ERROR] Row {row_idx} ({vid}): bindings_json — {e}")
                    has_errors = True

    return not has_errors


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "content_batch.csv"
    print(f"[INFO] Validating {target}")
    if validate_csv(target):
        print("[SUCCESS] All checks passed.")
        return 0
    print("[FATAL] Validation failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
