#!/usr/bin/env python3
"""
render_universal.py — Cinematic 9:16 Manim renderer with beat-driven narrative.

Key architecture:
  * Nothing is ever frozen: every wait is a live breathing wait.
  * Equation card is the punchline: revealed term-by-term on the `law` beat.
  * Symbol ↔ visual binding: on `emphasis` beats, equation term AND its
    visual partner pulse in sync — the 3b1b signature move.
  * Falls back gracefully to legacy reveal when beats_json is empty.
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
from manim import rate_functions as rf

# ★ Rate aliases — ease_* are NOT exported by `from manim import *`
RF_SOFT   = rf.ease_in_out_sine
RF_SNAP   = rf.ease_out_cubic
RF_SPRING = rf.ease_out_back

# ---------------- 9:16 vertical config -------------------------------------
config.pixel_width  = 1080
config.pixel_height = 1920
config.frame_width  = 9.0
config.frame_height = 16.0
config.frame_rate   = 30
config.background_color = "#0B0C10"
config.disable_caching = True

# ---------------- palette ---------------------------------------------------
COLOR = {
    "bg": "#0B0C10", "card": "#15161D", "border": "#2A2C36",
    "white": "#F2F3F5", "muted": "#8A8F9C",
    "field": "#3498DB", "pos": "#FF4B4B", "neg": "#00D2FF",
    "accent": "#F1C40F", "force": "#2ECC71", "momentum": "#E67E22",
}
SEMANTIC = {
    "force": COLOR["field"], "field": COLOR["field"],
    "energy": COLOR["accent"], "accent": COLOR["accent"],
    "charge": COLOR["pos"], "positive": COLOR["pos"],
    "negative": COLOR["neg"], "velocity": COLOR["force"],
    "momentum": COLOR["momentum"], "muted": COLOR["muted"],
}

ZONE_HEADER    =  6.90
ZONE_QUESTION  =  4.30
ZONE_VISUAL    =  0.30
ZONE_EQUATIONS = -5.00
ZONE_ANSWER    = -7.00

# Beat type constants
BEAT_HOOK       = "hook"
BEAT_ANALOGY    = "analogy"
BEAT_EXPERIMENT = "experiment"
BEAT_LAW        = "law"
BEAT_EMPHASIS   = "emphasis"
BEAT_PUNCHLINE  = "punchline"


def _log(m): print(f"[render] {m}", file=sys.stderr, flush=True)


# ============================================================ helpers
def safe_json_loads(val_str: str):
    if not val_str or val_str.strip() in ('""', ""):
        return []
    cleaned = re.sub(r"(?<!\\)\\(?!\\)", r"\\\\", val_str)
    return json.loads(cleaned)


def to_3d(p):
    if p is None:
        return np.zeros(3)
    if not isinstance(p, (list, tuple)):
        return np.zeros(3)
    if len(p) == 2:
        return np.array([float(p[0]), float(p[1]), 0.0])
    if len(p) >= 3:
        return np.array([float(p[0]), float(p[1]), float(p[2])])
    return np.zeros(3)


def resolve_color(item):
    if not isinstance(item, dict):
        return COLOR["accent"]
    if "color" in item:
        return item["color"]
    return SEMANTIC.get(str(item.get("semantic", "")).lower().strip(), COLOR["field"])


def safe_latex(s, font_size=26, color=WHITE):
    if s is None:
        return Text("", font_size=font_size, color=color)
    s = str(s).strip()
    if not s:
        return Text("", font_size=font_size, color=color)
    if "$" in s or "\\" in s or "^" in s or "_" in s:
        try:
            return MathTex(s, font_size=font_size, color=color)
        except Exception:
            pass
    try:
        return Text(s, font_size=font_size, color=color)
    except Exception:
        return Text("?", font_size=font_size, color=color)


_ALLOWED_MATH = {
    "sin": np.sin, "cos": np.cos, "tan": np.tan,
    "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs,
    "log": np.log, "pi": np.pi, "e": np.e,
}


def eval_expr(expr, x):
    expr = str(expr).replace("^", "**")
    try:
        return float(eval(expr, {"__builtins__": None}, {**_ALLOWED_MATH, "x": x}))
    except Exception:
        return 0.0


def has_updater(m):
    if getattr(m, "updaters", None):
        return True
    if hasattr(m, "submobjects"):
        return any(has_updater(s) for s in m.submobjects)
    return False


def live_wait(scene, duration, mobs=None, breathe_scale=0.014):
    if duration <= 0.05:
        return
    candidates = mobs if mobs is not None else \
                 [m for m in scene.mobjects if isinstance(m, VMobject)]
    targets = [m for m in candidates if isinstance(m, VMobject) and not has_updater(m)][:6]
    if not targets:
        scene.wait(duration)
        return
    cycles = max(1, int(duration / 2.4))
    per = duration / cycles
    for _ in range(cycles):
        anims = []
        for m in targets:
            try:
                anims.append(
                    m.animate(rate_func=there_and_back, run_time=per)
                     .scale(1 + breathe_scale)
                )
            except Exception:
                continue
        if anims:
            try:
                scene.play(*anims, run_time=per)
            except Exception:
                scene.wait(per)
        else:
            scene.wait(per)


# ============================================================ camera
class CameraDirector:
    def __init__(self, scene): self.s = scene

    def zoom(self, factor, run_time=1.0, center=None):
        frame = self.s.camera.frame
        builder = frame.animate.set(width=frame.get_width() / factor)
        if center is not None:
            builder = builder.move_to(center)
        self.s.play(builder, run_time=run_time, rate_func=RF_SOFT)

    def reset(self, run_time=0.7):
        self.s.play(
            self.s.camera.frame.animate.set(width=config.frame_width).move_to(ORIGIN),
            run_time=run_time, rate_func=RF_SOFT,
        )


def make_card(content, width=7.8):
    pad = 0.35
    bg = RoundedRectangle(
        corner_radius=0.22, width=width,
        height=content.height + pad * 2,
        fill_color=COLOR["card"], fill_opacity=0.96,
        stroke_color=COLOR["border"], stroke_width=1.5,
    )
    content.move_to(bg.get_center())
    return VGroup(bg, content)


# ============================================================ scene
class UniversalPhysicsScene(MovingCameraScene):

    def __init__(self, scene_kwargs=None, **kwargs):
        super().__init__(**kwargs)
        self.sk = scene_kwargs or {}
        self.eq_mobs: list[Mobject] = []
        self.visuals_by_id: dict = {}

    def construct(self):
        sk = self.sk
        self.director = CameraDirector(self)

        duration = float(sk.get("duration", 15.0))
        beats    = safe_json_loads(sk.get("beats_json", "[]"))
        bindings = safe_json_loads(sk.get("bindings_json", "[]"))

        self._build_header(sk.get("header_title", ""), sk.get("tagline", ""))

        if sk.get("question_text"):
            self._build_question(sk["question_text"])

        visual_group = self._build_visuals(
            safe_json_loads(sk.get("visual_data_json", "[]"))
        )
        if len(visual_group) > 0:
            self._reveal_visuals(visual_group)

        eq_card = self._build_equation_card(
            safe_json_loads(sk.get("equations_json", "[]"))
        )

        # ---- Beat-driven path OR legacy fallback ----
        if beats:
            self._run_beat_timeline(beats, bindings, eq_card, visual_group, duration)
        else:
            if len(eq_card) > 0:
                self._reveal_equation_card(eq_card)
            focus = [m for m in (visual_group, eq_card) if len(m) > 0]
            remaining = duration - self.renderer.time
            if remaining > 0.4:
                live_wait(self, remaining, focus[0] if focus else None)

        # ---- PYQ options + answer ----
        options = [o for o in (sk.get("options") or []) if o and o.strip()]
        correct = sk.get("correct_answer", "")
        if options or correct:
            ans_box = self._build_answers(options, correct)
            if ans_box is not None:
                self.play(FadeIn(ans_box, shift=UP * 0.2), run_time=0.5)
                self.play(Circumscribe(ans_box, color=COLOR["accent"],
                                       buff=0.15, run_time=0.8))

    # ============================================================ beats
    def _run_beat_timeline(self, beats, bindings, eq_card, visual_group, duration):
        # Prepare equation card: hide it and put it on the scene so beats can animate.
        if len(eq_card) > 0:
            eq_card.set_opacity(0)
            self.add(eq_card)

        # Build binding map: visual_id → (eq_idx, term_idx)
        bindings_map: dict[str, tuple[int, int]] = {}
        for b in bindings:
            if not isinstance(b, dict):
                continue
            vid = str(b.get("visual_id", "")).strip()
            if not vid or vid not in self.visuals_by_id:
                continue
            bindings_map[vid] = (
                int(b.get("eq_idx", 0)),
                int(b.get("term_idx", 0)),
            )

        eq_contents = eq_card[1] if len(eq_card) > 1 else None

        # Capture timeline start so beat `t` means "seconds after reveal"
        timeline_start = self.renderer.time

        # Sort beats by t
        valid_beats = sorted(
            [b for b in beats if isinstance(b, dict) and "t" in b],
            key=lambda b: float(b.get("t", 0)),
        )

        for beat in valid_beats:
            t_target = float(beat.get("t", 0))
            gap = t_target - (self.renderer.time - timeline_start)
            if gap > 0.05:
                live_wait(self, gap)

            kind  = str(beat.get("type", "")).lower()
            focus = str(beat.get("focus", "")).strip()

            try:
                if kind == BEAT_HOOK:
                    self._beat_hook(beat)
                elif kind == BEAT_ANALOGY:
                    self._beat_analogy(focus, eq_card)
                elif kind == BEAT_EXPERIMENT:
                    self._beat_experiment(focus)
                elif kind == BEAT_LAW:
                    self._beat_law(eq_card)
                elif kind == BEAT_EMPHASIS:
                    self._beat_emphasis(focus, bindings_map, self.eq_mobs, eq_contents)
                elif kind == BEAT_PUNCHLINE:
                    self._beat_punchline(eq_card)
            except Exception as e:
                _log(f"beat '{kind}' failed: {type(e).__name__}: {e}")

        # Tail
        remaining = duration - self.renderer.time
        if remaining > 0.4:
            live_wait(self, remaining)

    def _beat_hook(self, beat: dict):
        content = str(beat.get("content", "")).strip()
        if not content:
            return
        lines = textwrap.wrap(content, width=32) or [content]
        hook = Paragraph(*lines, alignment="center", font_size=28,
                         color=COLOR["accent"], line_spacing=0.9)
        if hook.width > 7.5:
            hook.scale_to_fit_width(7.5)
        hook.move_to([0, ZONE_QUESTION, 0])
        self.play(Write(hook), run_time=0.9)

    def _beat_analogy(self, focus_id: str, eq_card: VGroup):
        # Dim the equation card (if present)
        if len(eq_card) > 0:
            self.play(eq_card.animate.set_opacity(0.30), run_time=0.4)
        # Pulse the focus visual
        mob = self.visuals_by_id.get(focus_id)
        if mob is not None:
            self.play(
                mob.animate(rate_func=there_and_back, run_time=0.7).scale(1.10)
            )

    def _beat_experiment(self, focus_id: str):
        mob = self.visuals_by_id.get(focus_id)
        if mob is not None:
            try:
                self.play(Create(mob), run_time=1.2)
            except Exception:
                self.play(Indicate(mob, color=COLOR["accent"], scale_factor=1.08),
                          run_time=0.8)

    def _beat_law(self, eq_card: VGroup):
        """Reveal equations term-by-term. This is the signature 3b1b move."""
        if len(eq_card) == 0:
            return
        bg, content = eq_card[0], eq_card[1]

        # Reveal bg
        self.play(bg.animate.set_opacity(0.96), run_time=0.5)

        # Camera push on equations
        self.director.zoom(1.14, run_time=0.7,
                           center=np.array([0, ZONE_EQUATIONS, 0]))

        # Write each equation
        if isinstance(content, VGroup):
            content.set_opacity(1)
            for eq in content:
                # Reset stroke to invisible so Write animates from 0
                try:
                    eq.set_stroke(opacity=0)
                except Exception:
                    pass
            for eq in content:
                self.play(Write(eq, rate_func=smooth), run_time=0.7)
                self.wait(0.1)

        self.director.reset(run_time=0.6)

    def _beat_emphasis(self, focus_id: str, bindings_map: dict,
                       eq_mobs: list, eq_contents):
        """
        SYMBOL ↔ VISUAL BINDING — the 3b1b signature move.
        The equation term AND its visual partner pulse together.
        """
        mob = self.visuals_by_id.get(focus_id)
        binding = bindings_map.get(focus_id)

        anims = []
        if mob is not None:
            anims.append(Indicate(mob, color=COLOR["accent"], scale_factor=1.15))

        if binding is not None and eq_contents is not None:
            eq_idx, term_idx = binding
            try:
                term_mob = eq_mobs[eq_idx][0][term_idx]
                anims.append(Indicate(term_mob, color=COLOR["accent"],
                                      scale_factor=1.20))
            except (IndexError, AttributeError):
                pass

        if anims:
            self.play(*anims, run_time=0.9)
        elif mob is not None:
            self.play(Indicate(mob, color=COLOR["accent"]), run_time=0.9)

    def _beat_punchline(self, eq_card: VGroup):
        target = eq_card if len(eq_card) > 0 else None
        if target is not None:
            self.play(Circumscribe(target, color=COLOR["accent"],
                                   buff=0.20, run_time=1.0))

    # ============================================================ header
    def _build_header(self, title, tagline):
        parts = []
        if title:
            try:
                parts.append(Text(title, weight=BOLD, font_size=30, color=WHITE))
            except Exception:
                parts.append(Text(title, font_size=30, color=WHITE))
        rule = Line(LEFT, RIGHT, color=COLOR["accent"], stroke_width=2).set_width(3.2)
        if tagline:
            parts.append(rule)
            parts.append(Text(tagline, font_size=18, color=COLOR["muted"], slant=ITALIC))
        if not parts:
            return
        header = VGroup(*parts).arrange(DOWN, buff=0.14)
        if header.width > 8.0:
            header.scale_to_fit_width(8.0)
        header.move_to([0, ZONE_HEADER, 0])
        if title:
            self.play(FadeIn(parts[0], shift=DOWN * 0.15), run_time=0.5)
        if tagline:
            self.play(GrowFromCenter(rule), run_time=0.4)
            self.play(FadeIn(parts[-1], shift=UP * 0.1), run_time=0.4)

    # ============================================================ question
    def _build_question(self, text):
        lines = textwrap.wrap(text, width=38) or [text]
        q = Paragraph(*lines, alignment="center", font_size=20,
                      line_spacing=0.75, color=WHITE)
        if q.width > 8.0:
            q.scale_to_fit_width(8.0)
        q.move_to([0, ZONE_QUESTION, 0])
        self.play(FadeIn(q, shift=DOWN * 0.2), run_time=0.6)
        return q

    # ============================================================ visuals
    def _build_visuals(self, visual_data):
        group = VGroup()
        for idx, item in enumerate(visual_data):
            if not isinstance(item, dict):
                continue
            mob = self._build_primitive(item, idx)
            if mob is None:
                continue
            group.add(mob)
            key = str(item.get("id") or f"elem_{idx}")
            self.visuals_by_id[key] = mob
        return group

    def _reveal_visuals(self, group):
        self.play(
            LaggedStart(*[FadeIn(m, shift=UP * 0.25) for m in group],
                        lag_ratio=0.20),
            run_time=1.4,
        )
        self.director.zoom(1.10, run_time=0.9, center=np.array([0, ZONE_VISUAL, 0]))
        self.director.reset(run_time=0.7)

    # ============================================================ equations
    def _build_equation_card(self, equations):
        if not equations:
            return VGroup()
        eq_mobs = [safe_latex(eq, font_size=28, color=WHITE) for eq in equations if eq]
        if not eq_mobs:
            return VGroup()
        self.eq_mobs = eq_mobs
        eq_group = VGroup(*eq_mobs).arrange(DOWN, buff=0.26)
        if eq_group.width > 7.0:
            eq_group.scale_to_fit_width(7.0)
        return make_card(eq_group, width=7.8).move_to([0, ZONE_EQUATIONS, 0])

    def _reveal_equation_card(self, card):
        """Legacy reveal — used only when no beats are present."""
        bg, content = card[0], card[1]
        bg.save_state()
        bg.set_opacity(0).scale(0.94)
        content.save_state()
        content.set_opacity(0)
        self.play(Restore(bg, rate_func=RF_SNAP), run_time=0.6)
        self.director.zoom(1.14, run_time=0.7, center=np.array([0, ZONE_EQUATIONS, 0]))
        if isinstance(content, VGroup):
            for i, eq in enumerate(content):
                self.play(Write(eq, rate_func=smooth),
                          run_time=0.9 if i == 0 else 0.7)
                self.wait(0.15)
        live_wait(self, 0.6, [content])
        self.director.reset(run_time=0.7)

    # ============================================================ answers
    def _build_answers(self, options, correct):
        parts = []
        if options:
            opts = VGroup(*[safe_latex(o, 20, WHITE) for o in options]) \
                .arrange(DOWN, aligned_edge=LEFT, buff=0.18)
            parts.append(opts)
        if correct:
            ans = safe_latex(correct, 22, color=COLOR["force"])
            ans_box = VGroup(
                RoundedRectangle(
                    corner_radius=0.15,
                    width=max(ans.width + 0.5, 5.5),
                    height=ans.height + 0.4,
                    fill_color=COLOR["card"], fill_opacity=0.95,
                    stroke_color=COLOR["force"], stroke_width=2.5,
                ),
                ans,
            )
            parts.append(ans_box)
        if not parts:
            return None
        group = VGroup(*parts).arrange(DOWN, buff=0.35)
        if group.width > 7.8:
            group.scale_to_fit_width(7.8)
        group.move_to([0, ZONE_ANSWER + 1.5, 0])
        return group

    # ============================================================ primitives
    def _build_primitive(self, item, idx):
        itype = str(item.get("type", "")).lower()
        color = resolve_color(item)
        label = item.get("label", "")

        try:
            # ----- field -----
            if itype in ("field", "vector_field"):
                direction = str(item.get("direction", "RIGHT")).upper()
                rows = int(item.get("rows", 5))
                op = float(item.get("opacity", 0.4))
                dv = {"RIGHT": RIGHT, "LEFT": LEFT,
                      "UP": UP, "DOWN": DOWN}.get(direction, RIGHT)
                field = VGroup()
                for y in np.linspace(-1.2, 1.2, rows):
                    for x in np.linspace(-2.5, 2.5, 5):
                        s = np.array([x, y, 0.0])
                        e = s + dv * 0.55
                        arr = Arrow(start=s, end=e, buff=0, color=color,
                                    stroke_width=2,
                                    max_tip_length_to_length_ratio=0.32)
                        arr.set_opacity(op)
                        field.add(arr)
                if label:
                    field.add(safe_latex(label, 28, color).next_to(field, UP, buff=0.2))
                return field

            # ----- charge -----
            if itype in ("charge", "particle", "dot"):
                pos = to_3d(item.get("pos", [0, 0, 0]))
                r = float(item.get("radius", 0.22))
                dot = Dot(point=pos, radius=r, color=color)
                if label:
                    return VGroup(dot, safe_latex(label, 20, WHITE)
                                  .next_to(dot, UP, buff=0.1))
                return dot

            # ----- vector -----
            if itype in ("vector", "arrow", "force"):
                s = to_3d(item.get("start", [0, 0, 0]))
                e = to_3d(item.get("end", [1, 0, 0]))
                arr = Arrow(start=s, end=e, buff=0, color=color, stroke_width=4)
                if label:
                    return VGroup(arr, safe_latex(label, 22, color)
                                  .next_to(arr.get_end(), RIGHT, buff=0.1))
                return arr

            # ----- line -----
            if itype in ("line", "rod", "segment"):
                s = to_3d(item.get("start", [-1, 0, 0]))
                e = to_3d(item.get("end", [1, 0, 0]))
                if item.get("dashed", False):
                    return DashedLine(start=s, end=e, color=color)
                return Line(start=s, end=e, color=color, stroke_width=3)

            # ----- arc -----
            if itype in ("arc", "angle", "angle_arc"):
                c = to_3d(item.get("center", [0, 0, 0]))
                arc = Arc(
                    radius=float(item.get("radius", 0.8)),
                    start_angle=np.radians(float(item.get("start_angle", 0))),
                    angle=np.radians(float(item.get("angle", 60))),
                    arc_center=c, color=color,
                )
                if label:
                    return VGroup(arc, safe_latex(label, 20, color)
                                  .next_to(arc, RIGHT, buff=0.1))
                return arc

            # ----- graph -----
            if itype in ("graph", "function", "curve"):
                xr = item.get("x_range", [0, 5])
                yr = item.get("y_range", [-2, 2])
                axes = Axes(
                    x_range=[xr[0], xr[1], 1],
                    y_range=[yr[0], yr[1], 1],
                    x_length=float(item.get("x_length", 5.0)),
                    y_length=float(item.get("y_length", 2.5)),
                    axis_config={"color": COLOR["muted"], "stroke_width": 2},
                )
                expr = item.get("expression", "x")
                g = axes.plot(lambda x: eval_expr(expr, x),
                              x_range=[xr[0], xr[1]], color=color, stroke_width=4)
                return VGroup(axes, g)

            # ----- shapes -----
            if itype in ("shape", "lens", "circle", "rectangle", "ellipse", "polygon"):
                kind = str(item.get("kind", "rectangle")).lower()
                pos = to_3d(item.get("pos", [0, 0, 0]))
                fo = float(item.get("fill_opacity", 0.2))
                if kind == "rectangle":
                    d = item.get("dims", [2.0, 1.0])
                    return Rectangle(width=d[0], height=d[1], color=color,
                                     fill_opacity=fo).move_to(pos)
                if kind == "ellipse":
                    return Ellipse(width=float(item.get("width", 3.0)),
                                   height=float(item.get("height", 1.8)),
                                   color=color, fill_opacity=fo).move_to(pos)
                if kind == "lens":
                    return Ellipse(width=0.6, height=2.8, color=color,
                                   fill_color=color, fill_opacity=0.3).move_to(pos)
                if kind == "polygon":
                    pts = [to_3d(p) for p in item.get("points", [])]
                    if len(pts) >= 3:
                        return Polygon(*pts, color=color, fill_opacity=fo)
                    return None
                return Circle(radius=float(item.get("radius", 1.0)),
                              color=color, stroke_width=3).move_to(pos)

            # ----- text -----
            if itype == "text":
                txt = str(item.get("text", label))
                pos = to_3d(item.get("pos", [0, 0, 0]))
                return safe_latex(txt, int(item.get("font_size", 22)),
                                  color).move_to(pos)

            # ----- group -----
            if itype == "group":
                sub = VGroup()
                for j, child in enumerate(item.get("children", [])):
                    m = self._build_primitive(child, j)
                    if m is not None:
                        sub.add(m)
                return sub if len(sub) > 0 else None

        except Exception as e:
            _log(f"primitive '{itype}' failed: {type(e).__name__}: {e}")
            return None

        return None


# ============================================================ CLI
def main() -> int:
    p = argparse.ArgumentParser(description="Manim 9:16 cinematic renderer.")
    p.add_argument("--video_id", required=True)
    p.add_argument("--header_title", default="")
    p.add_argument("--tagline", default="")
    p.add_argument("--question_text", default="")
    p.add_argument("--options_json", default="[]")
    p.add_argument("--correct_answer", default="")
    p.add_argument("--equations_json", default="[]")
    p.add_argument("--visual_data_json", default="[]")
    p.add_argument("--beats_json", default="[]")
    p.add_argument("--bindings_json", default="[]")
    p.add_argument("--duration", type=float, default=15.0)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    try:
        options = safe_json_loads(args.options_json)
    except Exception:
        options = []

    scene_kwargs = {
        "header_title":     args.header_title,
        "tagline":          args.tagline,
        "question_text":    args.question_text,
        "options":          options,
        "correct_answer":   args.correct_answer,
        "equations_json":   args.equations_json,
        "visual_data_json": args.visual_data_json,
        "beats_json":       args.beats_json,
        "bindings_json":    args.bindings_json,
        "duration":         args.duration,
    }

    scene = UniversalPhysicsScene(scene_kwargs=scene_kwargs)
    scene.render()

    out_path = None
    try:
        out_path = str(scene.renderer.file_writer.movie_file_path)
    except Exception:
        pass

    if out_path is None or not os.path.exists(out_path):
        import glob
        candidates = glob.glob(
            os.path.join("media", "videos", "**", "UniversalPhysicsScene.mp4"),
            recursive=True,
        )
        if candidates:
            out_path = max(candidates, key=os.path.getmtime)

    if out_path is None or not os.path.exists(out_path):
        _log("FATAL could not locate rendered output")
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    os.replace(out_path, args.output)
    _log(f"SUCCESS {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
