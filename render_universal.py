#!/usr/bin/env python3
"""
render_universal.py — Manim 9:16 vertical physics renderer.

Fixes vs. previous version:
  * safe_json_loads escapes ALL single backslashes (fixes \text, \theta)
  * Individual primitive positions are preserved (no group move_to collapse)
  * Options/correct_answer use MathTex when LaTeX detected
  * Question text uses textwrap for word wrapping
  * config.disable_caching = True
  * graph expressions evaluated safely (no builtins)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap

import numpy as np
from manim import *

# ---------------- 9:16 vertical config -------------------------------------
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0
config.frame_rate = 30
config.background_color = "#0B0C10"
config.disable_caching = True

# ---------------- palette ---------------------------------------------------
COLOR_MAP = {
    "FIELD":    "#3498DB",
    "POSITIVE": "#FF4B4B",
    "NEGATIVE": "#00D2FF",
    "ACCENT":   "#F1C40F",
    "SUCCESS":  "#2ECC71",
    "WHITE":    "#FFFFFF",
    "MUTED":    "#8A8F9C",
}

SEMANTIC = {
    "force":    COLOR_MAP["FIELD"],
    "energy":   COLOR_MAP["ACCENT"],
    "charge":   COLOR_MAP["POSITIVE"],
    "field":    COLOR_MAP["FIELD"],
    "velocity": COLOR_MAP["SUCCESS"],
    "momentum": "#E67E22",
    "accent":   COLOR_MAP["ACCENT"],
    "muted":    COLOR_MAP["MUTED"],
}


# =================================================================== helpers
def safe_json_loads(val_str: str):
    """
    Handles LaTeX-authored CSV where backslashes are single, not double.

    JSON requires \\\\ for a literal backslash, but CSV authors write \\theta.
    We escape every single backslash (not already part of a pair) so json.loads
    produces the intended LaTeX string.
    """
    if not val_str or val_str.strip() in ('""', ""):
        return []
    cleaned = re.sub(r"(?<!\\)\\(?!\\)", r"\\\\", val_str)
    return json.loads(cleaned)


def to_3d_point(p) -> list[float]:
    if p is None:
        return [0.0, 0.0, 0.0]
    if not isinstance(p, (list, tuple)):
        return [0.0, 0.0, 0.0]
    if len(p) == 2:
        return [float(p[0]), float(p[1]), 0.0]
    if len(p) >= 3:
        return [float(p[0]), float(p[1]), float(p[2])]
    return [0.0, 0.0, 0.0]


def resolve_color(item: dict) -> str:
    if "color" in item:
        return item["color"]
    key = str(item.get("semantic", "")).lower().strip()
    return SEMANTIC.get(key, COLOR_MAP["FIELD"])


def safe_latex_or_text(s: str, font_size: int = 22, color=WHITE) -> Mobject:
    """Try MathTex, fall back to Text."""
    if s is None:
        return Text("", font_size=font_size, color=color)
    s = str(s).strip()
    if not s:
        return Text("", font_size=font_size, color=color)
    if "$" in s or "\\" in s:
        try:
            return MathTex(s, font_size=font_size, color=color)
        except Exception:
            pass
    return Text(s, font_size=font_size, color=color)


_ALLOWED_MATH = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs,
    "log": np.log, "pi": np.pi, "e": np.e,
}


def eval_expr(expr: str, x: float) -> float:
    expr = str(expr).replace("^", "**")
    ns = {**_ALLOWED_MATH, "x": x}
    try:
        return float(eval(expr, {"__builtins__": None}, ns))
    except Exception:
        return 0.0


# =================================================================== scene
class UniversalPhysicsScene(Scene):

    def __init__(self, scene_kwargs=None, **kwargs):
        super().__init__(**kwargs)
        self.scene_kwargs = scene_kwargs or {}

    def construct(self):
        sk = self.scene_kwargs
        header_title = sk.get("header_title", "")
        tagline = sk.get("tagline", "")
        question_text = sk.get("question_text", "")
        options = sk.get("options", []) or []
        correct_answer = sk.get("correct_answer", "")
        equations = safe_json_loads(sk.get("equations_json", "[]"))
        visual_data = safe_json_loads(sk.get("visual_data_json", "[]"))
        target_duration = float(sk.get("duration", 15.0))

        # ---- header (top) ----
        header_parts = []
        if header_title:
            try:
                header_parts.append(
                    Text(header_title, weight=BOLD, font_size=30,
                         color=WHITE)
                )
            except Exception:
                header_parts.append(Text(header_title, font_size=30, color=WHITE))
        if tagline:
            header_parts.append(
                Text(tagline, font_size=20, color=COLOR_MAP["ACCENT"])
            )
        if header_parts:
            header = VGroup(*header_parts).arrange(DOWN, buff=0.15)
            if header.width > 8.0:
                header.scale_to_fit_width(8.0)
            header.move_to([0, 6.6, 0])
            self.add(header)

        # ---- question (PYQ mode) ----
        if question_text:
            lines = textwrap.wrap(question_text, width=38) or [question_text]
            q_mob = Paragraph(*lines, alignment="center",
                              font_size=20, line_spacing=0.75,
                              color=WHITE)
            if q_mob.width > 8.0:
                q_mob.scale_to_fit_width(8.0)
            q_mob.move_to([0, 4.8, 0])
            self.add(q_mob)

        # ---- visuals (middle) ----
        visual_mobjects = VGroup()
        for item in visual_data:
            mob = self.build_visual_primitive(item)
            if mob is not None:
                visual_mobjects.add(mob)
        # NOTE: do NOT call move_to() here — each primitive keeps its declared position.

        # ---- equations / options / answer card (bottom) ----
        card_parts = []
        if equations:
            eq_vgroup = VGroup()
            for eq_str in equations:
                eq_vgroup.add(safe_latex_or_text(eq_str, font_size=28, color=WHITE))
            eq_vgroup.arrange(DOWN, buff=0.25)
            card_parts.append(eq_vgroup)

        clean_options = [o.strip() for o in options if o and o.strip()]
        if clean_options:
            opts_vgroup = VGroup(*[
                safe_latex_or_text(o, font_size=20, color=WHITE)
                for o in clean_options
            ]).arrange(DOWN, aligned_edge=LEFT, buff=0.15)
            card_parts.append(opts_vgroup)

        if correct_answer:
            card_parts.append(
                safe_latex_or_text(correct_answer, font_size=22,
                                   color=COLOR_MAP["SUCCESS"])
            )

        card_group = VGroup()
        if card_parts:
            card_group = VGroup(*card_parts).arrange(DOWN, buff=0.35)
            if card_group.width > 8.0:
                card_group.scale_to_fit_width(8.0)
            card_group.move_to([0, -4.8, 0])

        # ---- animation timeline ----
        if len(visual_mobjects) > 0:
            self.play(Create(visual_mobjects), run_time=1.8)

        if len(card_group) > 0:
            self.play(FadeIn(card_group, shift=UP * 0.3), run_time=1.2)

        elapsed = self.renderer.time
        remaining = max(0.5, target_duration - elapsed)
        self.wait(remaining)

    # ================================================================ primitives
    def build_visual_primitive(self, item: dict) -> Mobject | None:
        if not isinstance(item, dict):
            return None

        itype = str(item.get("type", "")).lower()
        color_hex = resolve_color(item)
        label = item.get("label", "")

        try:
            # ---------- field ----------
            if itype in ("field", "vector_field"):
                direction = str(item.get("direction", "RIGHT")).upper()
                rows = int(item.get("rows", 5))
                opacity = float(item.get("opacity", 0.4))
                dir_vec = {
                    "RIGHT": RIGHT, "LEFT": LEFT,
                    "UP": UP, "DOWN": DOWN,
                }.get(direction, RIGHT)

                field = VGroup()
                for y in np.linspace(-1.5, 1.5, rows):
                    for x in np.linspace(-2.5, 2.5, 5):
                        start = np.array([x, y, 0.0])
                        end = start + dir_vec * 0.6
                        arr = Arrow(start=start, end=end, buff=0,
                                    color=color_hex, stroke_width=2,
                                    max_tip_length_to_length_ratio=0.3)
                        arr.set_opacity(opacity)
                        field.add(arr)
                if label:
                    field.add(
                        safe_latex_or_text(label, font_size=28, color=color_hex)
                        .next_to(field, UP, buff=0.2)
                    )
                return field

            # ---------- charge / dot ----------
            if itype in ("charge", "particle", "dot"):
                pos = to_3d_point(item.get("pos", [0, 0, 0]))
                radius = float(item.get("radius", 0.25))
                dot = Dot(point=pos, radius=radius, color=color_hex)
                if label:
                    lbl = safe_latex_or_text(label, font_size=22, color=WHITE)
                    lbl.next_to(dot, UP, buff=0.1)
                    return VGroup(dot, lbl)
                return dot

            # ---------- vector / arrow ----------
            if itype in ("vector", "arrow", "force"):
                start = to_3d_point(item.get("start", [0, 0, 0]))
                end = to_3d_point(item.get("end", [1, 0, 0]))
                arrow = Arrow(start=start, end=end, buff=0,
                              color=color_hex, stroke_width=4)
                if label:
                    lbl = safe_latex_or_text(label, font_size=22, color=color_hex)
                    lbl.next_to(arrow.get_end(), RIGHT, buff=0.1)
                    return VGroup(arrow, lbl)
                return arrow

            # ---------- line ----------
            if itype in ("line", "rod", "segment"):
                start = to_3d_point(item.get("start", [-1, 0, 0]))
                end = to_3d_point(item.get("end", [1, 0, 0]))
                if item.get("dashed", False):
                    return DashedLine(start=start, end=end, color=color_hex)
                return Line(start=start, end=end, color=color_hex, stroke_width=3)

            # ---------- arc ----------
            if itype in ("arc", "angle", "angle_arc"):
                center = to_3d_point(item.get("center", [0, 0, 0]))
                arc = Arc(
                    radius=float(item.get("radius", 0.8)),
                    start_angle=np.radians(float(item.get("start_angle", 0))),
                    angle=np.radians(float(item.get("angle", 60))),
                    arc_center=center, color=color_hex,
                )
                if label:
                    lbl = safe_latex_or_text(label, font_size=20, color=color_hex)
                    lbl.next_to(arc, RIGHT, buff=0.1)
                    return VGroup(arc, lbl)
                return arc

            # ---------- graph ----------
            if itype in ("graph", "function", "curve"):
                x_range = item.get("x_range", [0, 5])
                y_range = item.get("y_range", [-2, 2])
                axes = Axes(
                    x_range=[x_range[0], x_range[1], 1],
                    y_range=[y_range[0], y_range[1], 1],
                    x_length=float(item.get("x_length", 5.0)),
                    y_length=float(item.get("y_length", 2.5)),
                    axis_config={"color": COLOR_MAP["MUTED"], "stroke_width": 2},
                )
                expr = item.get("expression", "x")
                graph = axes.plot(
                    lambda x: eval_expr(expr, x),
                    x_range=[x_range[0], x_range[1]],
                    color=color_hex, stroke_width=4,
                )
                return VGroup(axes, graph)

            # ---------- shape ----------
            if itype in ("shape", "lens", "circle", "rectangle", "ellipse", "polygon"):
                kind = str(item.get("kind", "rectangle")).lower()
                pos = to_3d_point(item.get("pos", [0, 0, 0]))
                fill_op = float(item.get("fill_opacity", 0.2))

                if kind == "rectangle":
                    dims = item.get("dims", [2.0, 1.0])
                    return Rectangle(width=dims[0], height=dims[1],
                                     color=color_hex, fill_opacity=fill_op).move_to(pos)
                if kind == "ellipse":
                    return Ellipse(width=float(item.get("width", 3.0)),
                                   height=float(item.get("height", 1.8)),
                                   color=color_hex,
                                   fill_opacity=fill_op).move_to(pos)
                if kind == "lens":
                    return Ellipse(width=0.6, height=2.8, color=color_hex,
                                   fill_color=color_hex,
                                   fill_opacity=0.3).move_to(pos)
                if kind == "polygon":
                    pts = [to_3d_point(p) for p in item.get("points", [])]
                    if len(pts) >= 3:
                        return Polygon(*pts, color=color_hex, fill_opacity=fill_op)
                    return None
                return Circle(radius=float(item.get("radius", 1.0)),
                              color=color_hex, stroke_width=3).move_to(pos)

            # ---------- text ----------
            if itype == "text":
                txt = str(item.get("text", label))
                pos = to_3d_point(item.get("pos", [0, 0, 0]))
                mob = safe_latex_or_text(txt,
                                         font_size=int(item.get("font_size", 22)),
                                         color=color_hex)
                return mob.move_to(pos)

            # ---------- group ----------
            if itype == "group":
                sub = VGroup()
                for j, child in enumerate(item.get("children", [])):
                    m = self.build_visual_primitive(child)
                    if m is not None:
                        sub.add(m)
                return sub if len(sub) > 0 else None

        except Exception as e:
            print(f"[WARN] primitive '{itype}' failed: {e}", file=sys.stderr)
            return None

        return None


# =================================================================== main
def main() -> int:
    p = argparse.ArgumentParser(description="Manim 9:16 renderer.")
    p.add_argument("--video_id", required=True)
    p.add_argument("--header_title", default="")
    p.add_argument("--tagline", default="")
    p.add_argument("--question_text", default="")
    p.add_argument("--options_json", default="[]")
    p.add_argument("--correct_answer", default="")
    p.add_argument("--equations_json", default="[]")
    p.add_argument("--visual_data_json", default="[]")
    p.add_argument("--duration", type=float, default=15.0)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    try:
        options = safe_json_loads(args.options_json)
    except Exception:
        options = []

    scene_kwargs = {
        "header_title": args.header_title,
        "tagline": args.tagline,
        "question_text": args.question_text,
        "options": options,
        "correct_answer": args.correct_answer,
        "equations_json": args.equations_json,
        "visual_data_json": args.visual_data_json,
        "duration": args.duration,
    }

    scene = UniversalPhysicsScene(scene_kwargs=scene_kwargs)
    scene.render()

    # Locate the rendered file using the renderer's file writer
    out_path = None
    try:
        out_path = str(scene.renderer.file_writer.movie_file_path)
    except Exception:
        pass

    if out_path is None or not os.path.exists(out_path):
        # Fallback: search media dir
        import glob
        candidates = glob.glob(
            os.path.join("media", "videos", "**", "UniversalPhysicsScene.mp4"),
            recursive=True,
        )
        if candidates:
            out_path = max(candidates, key=os.path.getmtime)

    if out_path is None or not os.path.exists(out_path):
        print("[ERROR] Could not locate rendered output", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    os.replace(out_path, args.output)
    print(f"[SUCCESS] Rendered: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
