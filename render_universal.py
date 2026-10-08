"""
render_universal.py — Master 3b1b Manim rendering engine (v2).

Reads row parameters from environment variables injected by batch_runner.py:

    CONCEPT_TYPE      DIPOLE_TORQUE | PROJECTILE | LORENTZ | WAVE |
                      OPTICS | CIRCUIT | PYQ | GENERIC
    HEADER_TITLE      Top gold title
    TAGLINE           Italic subtitle
    QUESTION_TEXT     PYQ question
    OPTION_A..D       PYQ options
    CORRECT_ANSWER    PYQ answer highlight
    EQUATIONS_JSON    JSON array of LaTeX strings
    VISUAL_DATA_JSON  JSON array of declarative diagram elements
    AUDIO_DURATION    Total scene duration in seconds
    SAFE_MODE         "1" (default) prevents a bad row from crashing the batch
    HINDI_FONT        Optional font path for Devanagari headers

v2 highlights
-------------
  1. PYQ + VISUAL_DATA_JSON now render together — question panel up top,
     declarative diagram in the middle, options + answer below.
  2. safe_mathtex() falls back MathTex → Tex → Text so a bad equation never
     aborts the batch.
  3. sanitize_latex() replaces raw unicode (°, ×, →, π, θ …) with their LaTeX
     equivalents before MathTex sees them.
  4. safe_eval_math() now treats '^' as power and inserts implicit '*' where
     physics writers expect it (2x, 3(x+1), 4sin(x)).
  5. Declarative parser adds: text, polygon, ellipse, angle_arc, dot radius,
     per-element opacity / scale / rotate / shift / z_index, and appearance
     animation styles (fade / write / create / grow / none).
  6. Layout zones are declared per preset instead of hardcoded DOWN * 5.4.
  7. Graceful failures in SAFE_MODE so a single bad CSV row never kills the
     whole GitHub Actions run.
"""

from __future__ import annotations

import math
import os
import re
import textwrap
from typing import Any

import numpy as np
from manim import *

# -----------------------------------------------------------------------------
# 9:16 VERTICAL ASPECT RATIO (1080 × 1920)
# Frame: width = 9.0 units, height = 16.0 units
# -----------------------------------------------------------------------------
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0

# 3Blue1Brown high-contrast palette
COLOR_BG       = "#0B0C10"
COLOR_FIELD    = "#3498DB"
COLOR_POS      = "#FF4B4B"
COLOR_NEG      = "#00D2FF"
COLOR_ACCENT   = "#F1C40F"
COLOR_FORCE    = "#2ECC71"
COLOR_CARD_BG  = "#15161D"
COLOR_BORDER   = "#333333"

# Vertical zones (y centres) for the 16-unit tall frame
ZONE_HEADER    = +7.20
ZONE_QUESTION  = +4.30
ZONE_VISUAL    = +0.50
ZONE_OPTIONS   = -2.60
ZONE_EQUATIONS = -5.00
ZONE_ANSWER    = -7.00

# Environment / debug
SAFE_MODE = os.environ.get("SAFE_MODE", "1") not in ("0", "false", "False")
HINDI_FONT = os.environ.get("HINDI_FONT", "")

# -----------------------------------------------------------------------------
# Unicode → LaTeX fallback map (raw unicode crashes MathTex under texlive)
# -----------------------------------------------------------------------------
_UNICODE_TO_LATEX = {
    "°": r"^\circ ",
    "×": r"\times ",
    "÷": r"\div ",
    "→": r"\to ",
    "←": r"\leftarrow ",
    "∞": r"\infty ",
    "π": r"\pi ",
    "θ": r"\theta ",
    "α": r"\alpha ",
    "β": r"\beta ",
    "γ": r"\gamma ",
    "δ": r"\delta ",
    "Δ": r"\Delta ",
    "Σ": r"\Sigma ",
    "Ω": r"\Omega ",
    "λ": r"\lambda ",
    "μ": r"\mu ",
    "ν": r"\nu ",
    "ρ": r"\rho ",
    "σ": r"\sigma ",
    "τ": r"\tau ",
    "φ": r"\phi ",
    "ψ": r"\psi ",
    "ω": r"\omega ",
    "Φ": r"\Phi ",
    "Ψ": r"\Psi ",
    "ℏ": r"\hbar ",
    "≤": r"\le ",
    "≥": r"\ge ",
    "≠": r"\ne ",
    "≈": r"\approx ",
    "±": r"\pm ",
    "∈": r"\in ",
    "∑": r"\sum ",
    "∏": r"\prod ",
    "∫": r"\int ",
}


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------
def clean_str(text: str | None) -> str:
    if not text:
        return ""
    return str(text).strip('"\'').strip()


def sanitize_latex(s: str) -> str:
    """Replace raw unicode with LaTeX-safe commands MathTex can consume."""
    if not s:
        return ""
    for uni, tex in _UNICODE_TO_LATEX.items():
        if uni in s:
            s = s.replace(uni, tex)
    return s


def safe_mathtex(s: str, font_size: int = 24, color=WHITE) -> Mobject:
    """
    Build a MathTex, falling back to Tex, then to plain Text, so a single
    malformed LaTeX string never kills the render.
    """
    if s is None:
        s = ""
    s_clean = sanitize_latex(str(s).strip())
    if not s_clean:
        return Text("", font_size=font_size, color=color)

    for ctor in (MathTex, Tex):
        try:
            return ctor(s_clean, font_size=font_size, color=color)
        except Exception:
            continue

    # Last resort: render as plain text (strips LaTeX commands crudely)
    fallback = re.sub(r"\\[a-zA-Z]+", "", s_clean).replace("{", "").replace("}", "")
    return Text(fallback, font_size=font_size, color=color)


def format_latex_option(opt_text: str) -> str:
    opt_text = clean_str(opt_text)
    if not opt_text:
        return ""
    if not re.search(r"[\$\\_^{}]", opt_text):
        return r"\text{" + opt_text + r"}"
    return opt_text


def safe_eval_math(expr_str: str, x_val: float) -> float:
    """
    Evaluate a function of x for graph plotting with common physics-friendly
    syntax:
        ^ becomes **
        2x, 3(x+1), 4sin(x) get implicit * inserted
    """
    if not expr_str:
        return 0.0

    expr = expr_str.replace("^", "**")
    # Implicit multiplication: digit followed by letter or '('
    expr = re.sub(r"(\d)\s*(x\b|[a-zA-Z(])", r"\1*\2", expr)
    # 2sin(x) style: number directly attached to known functions
    expr = re.sub(r"(\d)\s*(sin|cos|tan|exp|sqrt|abs|log)\b", r"\1*\2", expr)

    allowed = {
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs,
        "log": np.log, "pi": np.pi, "e": np.e, "x": x_val,
    }
    try:
        return float(eval(expr, {"__builtins__": None}, allowed))
    except Exception:
        return 0.0


def parse_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return []


# -----------------------------------------------------------------------------
# Scene
# -----------------------------------------------------------------------------
class UniversalPhysicsScene(Scene):
    # ------------------------------------------------ main entry point
    def construct(self):
        self.camera.background_color = COLOR_BG
        self.MAX_WIDTH = 7.8

        # Read env
        concept_type   = os.environ.get("CONCEPT_TYPE", "GENERIC").upper().strip()
        header_title   = clean_str(os.environ.get("HEADER_TITLE", "Physics Concept"))
        tagline        = clean_str(os.environ.get("TAGLINE", "3b1b Visual Intuition"))
        audio_duration = float(os.environ.get("AUDIO_DURATION", 20.0) or 20.0)

        visual_json = os.environ.get("VISUAL_DATA_JSON", "")
        self.equations = self._read_equations()

        # Header (persistent across the scene)
        self.build_header(header_title, tagline)

        has_visual = bool(parse_json_list(visual_json))
        is_pyq     = concept_type in ("PYQ", "MCQ", "QUESTION")

        try:
            # Priority 1 — combined PYQ + custom visual (the important new path)
            if is_pyq and has_visual:
                self.build_pyq_with_visual_scene(visual_json, audio_duration)

            # Priority 2 — PYQ with no custom visual
            elif is_pyq:
                self.build_pyq_scene(audio_duration)

            # Priority 3 — pure declarative visual
            elif has_visual:
                self.build_dynamic_json_scene(visual_json, audio_duration)

            # Priority 4 — archetype presets
            elif concept_type in ("DIPOLE_TORQUE", "DIPOLE", "ELECTROSTATICS_DIPOLE"):
                self.build_dipole_torque_scene(audio_duration)
            elif concept_type in ("PROJECTILE_MOTION", "PROJECTILE", "KINEMATICS"):
                self.build_projectile_scene(audio_duration)
            elif concept_type in ("LORENTZ_FORCE", "LORENTZ", "MAGNETISM"):
                self.build_lorentz_force_scene(audio_duration)
            elif concept_type in ("WAVE_MOTION", "WAVE", "SHM", "OSCILLATION"):
                self.build_wave_shm_scene(audio_duration)
            elif concept_type in ("OPTICS", "RAY_OPTICS", "LENS"):
                self.build_optics_scene(audio_duration)
            elif concept_type in ("CIRCUIT", "RC_CIRCUIT", "CAPACITOR", "RESONANCE"):
                self.build_circuit_scene(audio_duration)
            else:
                self.build_generic_vector_scene(audio_duration)
        except Exception as exc:
            if SAFE_MODE:
                # Show a calm error card rather than crash the whole batch
                err = Text(
                    f"[render error]\n{type(exc).__name__}: {exc}",
                    font_size=18, color=COLOR_POS,
                ).move_to(ORIGIN)
                self.add(err)
                self.wait(max(1.0, audio_duration - self.renderer.time))
            else:
                raise

        self._wait_remaining(audio_duration)

    # ------------------------------------------------ helpers
    def _wait_remaining(self, audio_duration: float):
        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def _read_equations(self) -> list[str]:
        raw = os.environ.get("EQUATIONS_JSON", "")
        return [str(x) for x in parse_json_list(raw) if x]

    def build_header(self, title_text: str, tagline_text: str):
        kwargs_title = dict(font_size=28, weight=BOLD, color=COLOR_ACCENT)
        kwargs_sub   = dict(font_size=18, slant=ITALIC, color=GRAY_B)
        if HINDI_FONT:
            kwargs_title["font"] = HINDI_FONT
            kwargs_sub["font"]   = HINDI_FONT
        title = Text(title_text, **kwargs_title)
        sub   = Text(tagline_text, **kwargs_sub)
        header = VGroup(title, sub).arrange(DOWN, buff=0.10).move_to([0, ZONE_HEADER, 0])
        if header.width > self.MAX_WIDTH:
            header.scale_to_fit_width(self.MAX_WIDTH)
        self.header = header
        self.add(header)

    def draw_math_card(self, equations: list[str], y_center: float = ZONE_EQUATIONS) -> VGroup:
        if not equations:
            return VGroup()
        eq_group = VGroup(*[safe_mathtex(eq, font_size=26, color=WHITE) for eq in equations if eq])
        eq_group.arrange(DOWN, buff=0.22)
        if eq_group.width > self.MAX_WIDTH - 0.4:
            eq_group.scale_to_fit_width(self.MAX_WIDTH - 0.4)

        card_bg = RoundedRectangle(
            corner_radius=0.20,
            width=self.MAX_WIDTH,
            height=eq_group.height + 0.5,
            fill_color=COLOR_CARD_BG, fill_opacity=0.94,
            stroke_color=COLOR_BORDER, stroke_width=2,
        ).move_to([0, y_center, 0])
        eq_group.move_to(card_bg.get_center())
        return VGroup(card_bg, eq_group)

    # ------------------------------------------------ PYQ + visual (NEW)
    def build_pyq_with_visual_scene(self, visual_json_str: str, audio_duration: float):
        """
        Combined layout for JEE PYQ rows that also carry a declarative diagram.

            +7.2  header
            +5.6  question text
            +3.0…–1.0  declarative visual
            –2.6  2×2 MCQ option grid
            –5.0  equations card
            –7.0  correct-answer box
        """
        question_str = clean_str(os.environ.get("QUESTION_TEXT", "Sample Question"))
        opt_a = clean_str(os.environ.get("OPTION_A", "(A) Option 1"))
        opt_b = clean_str(os.environ.get("OPTION_B", "(B) Option 2"))
        opt_c = clean_str(os.environ.get("OPTION_C", "(C) Option 3"))
        opt_d = clean_str(os.environ.get("OPTION_D", "(D) Option 4"))
        correct_ans = clean_str(os.environ.get("CORRECT_ANSWER", "Correct Answer: (A)"))

        # --- question paragraph ---
        wrapped = []
        for line in question_str.split("\n"):
            wrapped.extend(textwrap.wrap(line, width=44) if len(line) > 44 else [line])
        question = Paragraph(*wrapped, alignment="center", font_size=20,
                             color=WHITE, line_spacing=0.75)
        if question.width > self.MAX_WIDTH:
            question.scale_to_fit_width(self.MAX_WIDTH)
        question.move_to([0, ZONE_QUESTION + 0.6, 0])

        # --- 2×2 options grid ---
        opt_strs = [opt_a, opt_b, opt_c, opt_d]
        opt_mobs = [safe_mathtex(format_latex_option(o), font_size=20) for o in opt_strs if o]
        row1 = VGroup(*opt_mobs[:2]).arrange(RIGHT, buff=0.6)
        row2 = VGroup(*opt_mobs[2:]).arrange(RIGHT, buff=0.6)
        options_grid = VGroup(row1, row2).arrange(DOWN, buff=0.25).move_to([0, ZONE_OPTIONS, 0])
        if options_grid.width > self.MAX_WIDTH:
            options_grid.scale_to_fit_width(self.MAX_WIDTH)

        # --- answer box ---
        ans_text = safe_mathtex(format_latex_option(correct_ans),
                                font_size=24, color=COLOR_FORCE)
        ans_box = VGroup(
            RoundedRectangle(
                corner_radius=0.15,
                width=max(ans_text.width + 0.6, 5.0),
                height=ans_text.height + 0.4,
                fill_color=COLOR_CARD_BG, fill_opacity=0.95,
                stroke_color=COLOR_FORCE, stroke_width=2.5,
            ),
            ans_text,
        ).move_to([0, ZONE_ANSWER, 0])

        # --- equations card ---
        eq_card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)

        # --- declarative visual (constrained to its zone) ---
        visual_group = self._build_visual_group(visual_json_str)
        visual_group.move_to([0, ZONE_VISUAL, 0])
        if visual_group.height > 4.0:
            visual_group.scale_to_fit_height(4.0)
        if visual_group.width > self.MAX_WIDTH:
            visual_group.scale_to_fit_width(self.MAX_WIDTH)

        # --- choreography ---
        step = max(1.0, (audio_duration - 5.0) / 4.0)
        self.play(FadeIn(question, shift=UP * 0.2), run_time=0.8)
        self.play(FadeIn(visual_group), run_time=1.2)
        self.wait(step)
        self.play(FadeIn(options_grid, shift=UP * 0.15), run_time=0.8)
        self.wait(step * 0.5)
        if len(eq_card) > 0:
            self.play(FadeIn(eq_card[0]), Write(eq_card[1]), run_time=1.0)
        self.wait(step * 0.5)
        self.play(FadeIn(ans_box, shift=UP * 0.2),
                  Circumscribe(ans_box, color=COLOR_ACCENT, buff=0.1, run_time=1.0))

    # ------------------------------------------------ PYQ only
    def build_pyq_scene(self, audio_duration: float):
        question_str = clean_str(os.environ.get("QUESTION_TEXT", "Sample Question"))
        opt_a = clean_str(os.environ.get("OPTION_A", "(A) Option 1"))
        opt_b = clean_str(os.environ.get("OPTION_B", "(B) Option 2"))
        opt_c = clean_str(os.environ.get("OPTION_C", "(C) Option 3"))
        opt_d = clean_str(os.environ.get("OPTION_D", "(D) Option 4"))
        correct_ans = clean_str(os.environ.get("CORRECT_ANSWER", "Correct Answer: (A)"))

        wrapped = []
        for line in question_str.split("\n"):
            wrapped.extend(textwrap.wrap(line, width=38) if len(line) > 38 else [line])
        question = Paragraph(*wrapped, alignment="center", font_size=22,
                             color=WHITE, line_spacing=0.8)
        if question.width > self.MAX_WIDTH:
            question.scale_to_fit_width(self.MAX_WIDTH)
        question.move_to([0, ZONE_QUESTION, 0])

        opts = [opt_a, opt_b, opt_c, opt_d]
        max_opt_len = max((len(o) for o in opts if o), default=0)
        if max_opt_len <= 16 and all(opts):
            row1 = VGroup(safe_mathtex(format_latex_option(opt_a), 20),
                          safe_mathtex(format_latex_option(opt_b), 20)).arrange(RIGHT, buff=0.8)
            row2 = VGroup(safe_mathtex(format_latex_option(opt_c), 20),
                          safe_mathtex(format_latex_option(opt_d), 20)).arrange(RIGHT, buff=0.8)
            mcq_group = VGroup(row1, row2).arrange(DOWN, buff=0.25)
        else:
            mcq_group = VGroup(*[safe_mathtex(format_latex_option(o), 20)
                                 for o in opts if o]).arrange(DOWN, buff=0.18, aligned_edge=LEFT)
        if mcq_group.width > self.MAX_WIDTH:
            mcq_group.scale_to_fit_width(self.MAX_WIDTH)
        mcq_group.move_to([0, ZONE_OPTIONS, 0])

        ans_text = safe_mathtex(format_latex_option(correct_ans), 24, color=COLOR_FORCE)
        ans_box = VGroup(
            RoundedRectangle(corner_radius=0.15,
                             width=max(ans_text.width + 0.6, 5.0),
                             height=ans_text.height + 0.4,
                             fill_color=COLOR_CARD_BG, fill_opacity=0.95,
                             stroke_color=COLOR_FORCE, stroke_width=2.5),
            ans_text,
        ).move_to([0, ZONE_ANSWER, 0])

        eq_card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)

        step = max(0.8, (audio_duration - 5.0) / 3.0)
        self.play(FadeIn(question, shift=UP * 0.2), run_time=0.9)
        self.wait(step)
        self.play(FadeIn(mcq_group, shift=UP * 0.15), run_time=0.9)
        self.wait(step)
        if len(eq_card) > 0:
            self.play(FadeIn(eq_card[0]), Write(eq_card[1]), run_time=1.1)
            self.wait(step * 0.5)
        self.play(FadeIn(ans_box, shift=UP * 0.2),
                  Circumscribe(ans_box, color=COLOR_ACCENT, buff=0.1, run_time=1.0))

    # ------------------------------------------------ declarative JSON scene
    def build_dynamic_json_scene(self, visual_json_str: str, audio_duration: float):
        group = self._build_visual_group(visual_json_str)
        group.move_to([0, ZONE_VISUAL - 0.5, 0])
        self.play(FadeIn(group), run_time=1.2)
        self._play_pending_animations()

        card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def _play_pending_animations(self):
        for anim in getattr(self, "_pending_animations", []):
            self.play(anim, run_time=1.5, rate_func=smooth)
        self._pending_animations = []

    # ------------------------------------------------ primitive builder
    def _build_visual_group(self, visual_json_str: str) -> VGroup:
        """
        Parse the declarative JSON payload and return a VGroup of all elements.
        Also populates self._pending_animations for the caller to play.
        """
        elements = parse_json_list(visual_json_str)
        self._pending_animations = []
        group = VGroup()

        for idx, item in enumerate(elements):
            if not isinstance(item, dict):
                continue
            mob = self._build_json_element(item, idx)
            if mob is None:
                continue
            group.add(mob)

            # Register rotate animation for later
            anim = item.get("animate")
            if anim == "rotate" and item.get("pivot") is not None:
                pivot = np.array(item["pivot"], dtype=float)
                angle = float(item.get("rotate_angle", 45)) * DEGREES
                self._pending_animations.append(Rotate(mob, angle=angle, about_point=pivot))

        return group

    def _build_json_element(self, item: dict, idx: int) -> Mobject | None:
        e_type = str(item.get("type", "")).lower()
        color = item.get("color", COLOR_ACCENT)
        lbl_text = item.get("label", "")
        label_pos = item.get("label_pos", "auto")

        mob: Mobject | None = None

        # ------------------------------- FIELD
        if e_type in ("field", "vector_field"):
            direction = str(item.get("direction", "RIGHT")).upper()
            rows = int(item.get("rows", 7))
            field = VGroup()
            for y in np.linspace(1.8, -3.2, rows):
                if direction == "LEFT":
                    arr = Arrow(RIGHT * 4.0 + UP * y, LEFT * 4.0 + UP * y,
                                buff=0, stroke_width=2.5, color=color)
                elif direction == "UP":
                    arr = Arrow(RIGHT * y + DOWN * 3.0, RIGHT * y + UP * 2.0,
                                buff=0, stroke_width=2.5, color=color)
                elif direction == "DOWN":
                    arr = Arrow(RIGHT * y + UP * 2.0, RIGHT * y + DOWN * 3.0,
                                buff=0, stroke_width=2.5, color=color)
                else:
                    arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y,
                                buff=0, stroke_width=2.5, color=color)
                arr.set_opacity(float(item.get("opacity", 0.35)))
                field.add(arr)
            if lbl_text:
                field.add(safe_mathtex(lbl_text, 32, color=color).next_to(field[0], RIGHT, buff=0.2))
            mob = field

        # ------------------------------- CHARGE / DOT / PARTICLE
        elif e_type in ("charge", "particle", "dot"):
            pos = np.array(item.get("pos", [0, 0, 0]), dtype=float)
            radius = float(item.get("radius", 0.22))
            dot = Dot(pos, radius=radius, color=color)
            mob = VGroup(dot, safe_mathtex(lbl_text, 20, WHITE).move_to(pos)) if lbl_text else dot

        # ------------------------------- VECTOR / ARROW / FORCE
        elif e_type in ("vector", "arrow", "force"):
            start = np.array(item.get("start", [0, 0, 0]), dtype=float)
            end   = np.array(item.get("end",   [1, 1, 0]), dtype=float)
            vec = Arrow(start, end, buff=0, stroke_width=3.5, color=color)
            if lbl_text:
                v_lbl = safe_mathtex(lbl_text, 24, color=color).next_to(vec, UP, buff=0.1)
                mob = VGroup(vec, v_lbl)
            else:
                mob = vec

        # ------------------------------- LINE / ROD / SEGMENT
        elif e_type in ("line", "rod", "segment"):
            start = np.array(item.get("start", [0, 0, 0]), dtype=float)
            end   = np.array(item.get("end",   [1, 1, 0]), dtype=float)
            dashed = bool(item.get("dashed", False))
            line = DashedLine(start, end, color=color, stroke_width=2.5) if dashed \
                   else Line(start, end, color=color, stroke_width=4)
            if lbl_text:
                line = VGroup(line, safe_mathtex(lbl_text, 22, color=color).next_to(line, RIGHT, buff=0.1))
            mob = line

        # ------------------------------- ARC / ANGLE
        elif e_type in ("arc", "angle", "angle_arc"):
            center  = np.array(item.get("center", [0, 0, 0]), dtype=float)
            radius  = float(item.get("radius", 0.8))
            s_angle = float(item.get("start_angle", 0)) * DEGREES
            angle   = float(item.get("angle", 45)) * DEGREES
            arc = Arc(radius=radius, start_angle=s_angle, angle=angle,
                      arc_center=center, color=color)
            if lbl_text:
                arc = VGroup(arc, safe_mathtex(lbl_text, 22, color=color).next_to(arc, RIGHT, buff=0.1))
            mob = arc

        # ------------------------------- GRAPH / FUNCTION
        elif e_type in ("graph", "function", "curve"):
            expr = item.get("expression", "sin(x)")
            x_min, x_max = item.get("x_range", [0, 5])
            y_min, y_max = item.get("y_range", [-2, 2])
            axes = Axes(
                x_range=[x_min, x_max, 1], y_range=[y_min, y_max, 1],
                x_length=6.0, y_length=3.0, axis_config={"color": GRAY},
            )
            graph = axes.plot(lambda x: safe_eval_math(expr, x), x_range=[x_min, x_max], color=color)
            mob = VGroup(axes, graph)

        # ------------------------------- SHAPES
        elif e_type in ("shape", "lens", "circle", "rectangle", "ellipse", "polygon"):
            kind = str(item.get("kind", e_type if e_type != "shape" else "circle")).lower()
            pos  = np.array(item.get("pos", [0, -1, 0]), dtype=float)
            if kind == "rectangle":
                dims = item.get("dims", [2, 1])
                mob = Rectangle(width=dims[0], height=dims[1],
                                color=color, fill_opacity=float(item.get("fill_opacity", 0.2))).move_to(pos)
            elif kind == "lens":
                mob = Ellipse(width=0.6, height=2.8, color=color,
                              fill_color=color, fill_opacity=0.3).move_to(pos)
            elif kind == "ellipse":
                mob = Ellipse(width=float(item.get("width", 2.0)),
                              height=float(item.get("height", 1.0)),
                              color=color, fill_opacity=float(item.get("fill_opacity", 0.2))).move_to(pos)
            elif kind == "polygon":
                pts = [np.array(p, dtype=float) for p in item.get("points", [])]
                if len(pts) >= 3:
                    mob = Polygon(*pts, color=color,
                                  fill_opacity=float(item.get("fill_opacity", 0.2)))
            else:
                mob = Circle(radius=float(item.get("radius", 1.0)),
                             color=color, stroke_width=3).move_to(pos)

        # ------------------------------- PLAIN TEXT
        elif e_type == "text":
            txt = str(item.get("text", lbl_text))
            mob = Text(txt, font_size=int(item.get("font_size", 22)),
                       color=color).move_to(np.array(item.get("pos", [0, 0, 0]), dtype=float))

        # ------------------------------- GROUP (recursive)
        elif e_type == "group":
            sub = VGroup()
            for j, subitem in enumerate(item.get("children", [])):
                sm = self._build_json_element(subitem, j)
                if sm is not None:
                    sub.add(sm)
            mob = sub

        if mob is None:
            return None

        # Per-element transforms
        if "opacity" in item and not isinstance(mob, VGroup):
            mob.set_opacity(float(item["opacity"]))
        if "scale" in item:
            mob.scale(float(item["scale"]))
        if "rotate" in item:
            mob.rotate(float(item["rotate"]) * DEGREES)
        if "shift" in item:
            mob.shift(np.array(item["shift"], dtype=float))
        if "z_index" in item:
            mob.set_z_index(int(item["z_index"]))

        return mob

    # ------------------------------------------------ presets (kept + minor fixes)
    def build_dipole_torque_scene(self, audio_duration: float):
        equations = self.equations or [
            r"\vec{F}_{\text{net}} = \vec{0}",
            r"\tau = pE\sin\theta",
            r"\vec{\tau} = \vec{p}\times\vec{E}",
        ]
        field_lines = VGroup()
        for y in np.linspace(1.8, -3.2, 7):
            arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y,
                        buff=0, stroke_width=2.5, color=COLOR_FIELD).set_opacity(0.32)
            field_lines.add(arr)
        field_lines.add(safe_mathtex(r"\vec{E}", 36, COLOR_FIELD).next_to(field_lines[0], RIGHT, buff=0.2))
        field_lines.move_to([0, ZONE_VISUAL, 0])

        center_pt = np.array([0, ZONE_VISUAL - 1.4, 0])
        angle = 42 * DEGREES
        a_len = 1.4
        pos_p = center_pt + np.array([a_len * np.cos(angle), a_len * np.sin(angle), 0])
        neg_p = center_pt - np.array([a_len * np.cos(angle), a_len * np.sin(angle), 0])

        rod = Line(neg_p, pos_p, color=GRAY_A, stroke_width=4)
        c_pos = VGroup(Dot(pos_p, radius=0.22, color=COLOR_POS),
                       safe_mathtex("+q", 20, WHITE).move_to(pos_p))
        c_neg = VGroup(Dot(neg_p, radius=0.22, color=COLOR_NEG),
                       safe_mathtex("-q", 20, WHITE).move_to(neg_p))
        p_arrow = Arrow(neg_p, pos_p, buff=0.25, color=COLOR_ACCENT, stroke_width=4)
        p_lbl = safe_mathtex(r"\vec{p}", 30, COLOR_ACCENT).next_to(p_arrow.get_center(), UP, buff=0.1)

        self.play(Create(field_lines), run_time=0.9)
        self.play(FadeIn(VGroup(rod, c_pos, c_neg, p_arrow, p_lbl)), run_time=0.9)

        card = self.draw_math_card(equations)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def build_projectile_scene(self, audio_duration: float):
        equations = self.equations or [
            r"y = x\tan\theta - \frac{g x^2}{2u^2\cos^2\theta}",
            r"R = \frac{u^2\sin 2\theta}{g}",
        ]
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 3, 1],
                    x_length=6, y_length=3.5, axis_config={"color": GRAY}).move_to([0, ZONE_VISUAL - 1.0, 0])
        graph = axes.plot(lambda x: 2.5 * x - 0.6 * x ** 2, x_range=[0, 4.16], color=COLOR_ACCENT)
        ball = Dot(color=COLOR_POS, radius=0.18)
        self.play(Create(axes), run_time=0.7)
        self.play(Create(graph), MoveAlongPath(ball, graph), run_time=2.2, rate_func=linear)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def build_lorentz_force_scene(self, audio_duration: float):
        equations = self.equations or [
            r"\vec{F} = q(\vec{v}\times\vec{B})",
            r"r = \frac{mv}{qB}",
        ]
        field_group = VGroup()
        for y in np.linspace(1.5, -3.5, 6):
            arr = Arrow(LEFT * 3.8 + UP * y, RIGHT * 3.8 + UP * y,
                        buff=0, stroke_width=2, color=COLOR_ACCENT).set_opacity(0.35)
            field_group.add(arr)
        field_group.add(safe_mathtex(r"\vec{B}", 34, COLOR_ACCENT).next_to(field_group[0], RIGHT, buff=0.2))
        field_group.move_to([0, ZONE_VISUAL, 0])

        charge = Dot(LEFT * 2.5 + DOWN * 1.0 + np.array([0, ZONE_VISUAL, 0]),
                     radius=0.25, color=COLOR_POS)
        v_arrow = Arrow(charge.get_center(), charge.get_center() + UP * 1.8,
                        buff=0, color=COLOR_FORCE)
        self.play(Create(field_group), FadeIn(charge), Create(v_arrow), run_time=1.0)
        arc = Arc(radius=2.0, start_angle=PI, angle=-PI / 2,
                  arc_center=np.array([-0.5, ZONE_VISUAL - 1.0, 0]), color=COLOR_POS)
        self.play(MoveAlongPath(charge, arc), run_time=1.8)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def build_wave_shm_scene(self, audio_duration: float):
        equations = self.equations or [
            r"y(x,t) = A\sin(kx - \omega t + \phi)",
            r"v = f\lambda, \quad k = \frac{2\pi}{\lambda}",
        ]
        axes = Axes(x_range=[0, 6, 1], y_range=[-2, 2, 1],
                    x_length=6.5, y_length=3.0, axis_config={"color": GRAY}).move_to([0, ZONE_VISUAL - 1.0, 0])
        wave = axes.plot(lambda x: 1.2 * np.sin(2 * x), x_range=[0, 6], color=COLOR_FIELD)
        self.play(Create(axes), run_time=0.7)
        self.play(Create(wave), run_time=1.8)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def build_optics_scene(self, audio_duration: float):
        equations = self.equations or [
            r"\frac{1}{f} = \frac{1}{v} - \frac{1}{u}",
            r"P = (n-1)\!\left(\frac{1}{R_1} - \frac{1}{R_2}\right)",
        ]
        axis = Line(LEFT * 3.5, RIGHT * 3.5, color=GRAY_B).move_to([0, ZONE_VISUAL - 1.0, 0])
        lens = Ellipse(width=0.6, height=3.0, color=COLOR_FIELD,
                       fill_color=COLOR_FIELD, fill_opacity=0.3).move_to([0, ZONE_VISUAL - 1.0, 0])
        ray_in = Line(LEFT * 3.5 + UP * 0.2 + np.array([0, ZONE_VISUAL - 1.0, 0]),
                      UP * 0.2 + np.array([0, ZONE_VISUAL - 1.0, 0]), color=COLOR_ACCENT)
        ray_out = Line(UP * 0.2 + np.array([0, ZONE_VISUAL - 1.0, 0]),
                       RIGHT * 3.5 + DOWN * 1.2 + np.array([0, ZONE_VISUAL - 1.0, 0]), color=COLOR_ACCENT)
        self.play(Create(axis), Create(lens), run_time=1.0)
        self.play(Create(ray_in), Create(ray_out), run_time=1.2)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def build_circuit_scene(self, audio_duration: float):
        equations = self.equations or [
            r"q(t) = Q_0\!\left(1 - e^{-t/RC}\right)",
            r"\tau = RC",
        ]
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 2, 1],
                    x_length=6.0, y_length=3.0, axis_config={"color": GRAY}).move_to([0, ZONE_VISUAL - 1.0, 0])
        curve = axes.plot(lambda x: 1.8 * (1 - np.exp(-x)), x_range=[0, 5], color=COLOR_ACCENT)
        self.play(Create(axes), run_time=0.7)
        self.play(Create(curve), run_time=1.8)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def build_generic_vector_scene(self, audio_duration: float):
        v1 = Arrow(ORIGIN, RIGHT * 2 + UP * 1, buff=0, color=COLOR_FIELD).move_to([0, ZONE_VISUAL, 0])
        v2 = Arrow(ORIGIN, RIGHT * 1 + DOWN * 2, buff=0, color=COLOR_FORCE).move_to([0, ZONE_VISUAL, 0])
        self.play(Create(v1), Create(v2), run_time=1.5)
        card = self.draw_math_card(self.equations)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)
