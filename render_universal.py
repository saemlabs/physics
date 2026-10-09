"""
render_universal.py — Master 3b1b Manim 9:16 rendering engine.
"""

from __future__ import annotations

import json
import math
import os
import re
import textwrap
from typing import Any

import numpy as np
from manim import *

config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0
config.frame_rate = 30

COLOR_BG       = "#0B0C10"
COLOR_FIELD    = "#3498DB"
COLOR_POS      = "#FF4B4B"
COLOR_NEG      = "#00D2FF"
COLOR_ACCENT   = "#F1C40F"
COLOR_FORCE    = "#2ECC71"
COLOR_CARD_BG  = "#15161D"
COLOR_BORDER   = "#333333"

ZONE_HEADER    = +7.20
ZONE_QUESTION  = +4.30
ZONE_VISUAL    = +0.50
ZONE_OPTIONS   = -2.60
ZONE_EQUATIONS = -5.00
ZONE_ANSWER    = -7.00

SAFE_MODE = os.environ.get("SAFE_MODE", "1") not in ("0", "false", "False")
HINDI_FONT = os.environ.get("HINDI_FONT", "")

_UNICODE_TO_LATEX = {
    "°": r"^\circ ", "×": r"\times ", "÷": r"\div ", "→": r"\to ", "←": r"\leftarrow ",
    "∞": r"\infty ", "π": r"\pi ", "θ": r"\theta ", "α": r"\alpha ", "β": r"\beta ",
    "γ": r"\gamma ", "δ": r"\delta ", "Δ": r"\Delta ", "Σ": r"\Sigma ", "Ω": r"\Omega ",
    "λ": r"\lambda ", "μ": r"\mu ", "ν": r"\nu ", "ρ": r"\rho ", "σ": r"\sigma ",
    "τ": r"\tau ", "φ": r"\phi ", "ψ": r"\psi ", "ω": r"\omega ", "Φ": r"\Phi ",
    "Ψ": r"\Psi ", "ℏ": r"\hbar ", "≤": r"\le ", "≥": r"\ge ", "≠": r"\ne ",
    "≈": r"\approx ", "±": r"\pm ", "∈": r"\in ", "∑": r"\sum ", "∏": r"\prod ", "∫": r"\int ",
}


def clean_str(text: str | None) -> str:
    if not text:
        return ""
    return str(text).strip().strip('"\'').strip()


def to_3d_point(p: Any) -> np.ndarray:
    if p is None:
        return np.zeros(3)
    arr = np.array(p, dtype=float)
    if arr.ndim == 1:
        if len(arr) == 2:
            return np.array([arr[0], arr[1], 0.0])
        if len(arr) >= 3:
            return arr[:3]
    return np.zeros(3)


def sanitize_latex(s: str) -> str:
    if not s:
        return ""
    for uni, tex in _UNICODE_TO_LATEX.items():
        if uni in s:
            s = s.replace(uni, tex)
    return s


def safe_mathtex(s: str, font_size: int = 24, color=WHITE) -> Mobject:
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

    fallback = re.sub(r"\\[a-zA-Z]+", "", s_clean).replace("{", "").replace("}", "")
    return Text(fallback, font_size=font_size, color=color)


def format_latex_option(opt_text: str) -> str:
    opt_text = clean_str(opt_text)
    if not opt_text:
        return ""
    
    prefix = ""
    if opt_text.lower().startswith("correct answer:"):
        prefix = r"\text{Correct Answer: }"
        opt_text = opt_text[15:].strip()

    m = re.match(r"^(\([A-Da-d]\))\s*(.*)$", opt_text)
    if m:
        label, rest = m.group(1), m.group(2)
        if not rest:
            body = r"\text{" + label + r"}"
        elif re.search(r"[\$\\_^{}]", rest):
            body = r"\text{" + label + r" }" + rest
        else:
            body = r"\text{" + label + r" " + rest + r"}"
        return prefix + body

    if not re.search(r"[\$\\_^{}]", opt_text):
        return prefix + r"\text{" + opt_text + r"}"
    return prefix + opt_text


def safe_eval_math(expr_str: str, x_val: float) -> float:
    if not expr_str:
        return 0.0

    expr = str(expr_str).replace("^", "**")
    expr = re.sub(r"(\d|\bx\b|\))\s*([a-zA-Z\(])", r"\1*\2", expr)
    expr = re.sub(r"\*{3,}", "**", expr)

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
        parsed = json.loads(str(raw).strip())
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return []


class UniversalPhysicsScene(Scene):
    def construct(self):
        self.camera.background_color = COLOR_BG
        self.MAX_WIDTH = 7.8

        concept_type   = os.environ.get("CONCEPT_TYPE", "GENERIC").upper().strip()
        header_title   = clean_str(os.environ.get("HEADER_TITLE", "Physics Concept"))
        tagline        = clean_str(os.environ.get("TAGLINE", "3b1b Visual Intuition"))
        audio_duration = float(os.environ.get("AUDIO_DURATION", 20.0) or 20.0)

        visual_json = os.environ.get("VISUAL_DATA_JSON", "")
        self.equations = self._read_equations()

        self.build_header(header_title, tagline)

        has_visual = bool(parse_json_list(visual_json))
        is_pyq     = concept_type in ("PYQ", "MCQ", "QUESTION")

        try:
            if is_pyq and has_visual:
                self.build_pyq_with_visual_scene(visual_json, audio_duration)
            elif is_pyq:
                self.build_pyq_scene(audio_duration)
            elif has_visual:
                self.build_dynamic_json_scene(visual_json, audio_duration)
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
                err = Text(
                    f"[render error]\n{type(exc).__name__}: {exc}",
                    font_size=18, color=COLOR_POS,
                ).move_to(ORIGIN)
                self.add(err)
                self.wait(max(1.0, audio_duration - self.renderer.time))
            else:
                raise

        self._wait_remaining(audio_duration)

    def _wait_remaining(self, audio_duration: float):
        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def _read_equations(self) -> list[str]:
        raw = os.environ.get("EQUATIONS_JSON", "")
        return [str(x) for x in parse_json_list(raw) if x]

    def build_header(self, title_text: str, tagline_text: str):
        kwargs_title = dict(font_size=28, color=COLOR_ACCENT)
        kwargs_sub   = dict(font_size=18, color=GRAY_B)
        
        if HINDI_FONT:
            kwargs_title["font"] = HINDI_FONT
            kwargs_sub["font"]   = HINDI_FONT
        else:
            kwargs_title["weight"] = BOLD
            kwargs_sub["slant"]   = ITALIC

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
        if len(eq_group) == 0:
            return VGroup()

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

    def build_pyq_with_visual_scene(self, visual_json_str: str, audio_duration: float):
        question_str = clean_str(os.environ.get("QUESTION_TEXT", "Sample Question"))
        opt_a = clean_str(os.environ.get("OPTION_A", "(A) Option 1"))
        opt_b = clean_str(os.environ.get("OPTION_B", "(B) Option 2"))
        opt_c = clean_str(os.environ.get("OPTION_C", "(C) Option 3"))
        opt_d = clean_str(os.environ.get("OPTION_D", "(D) Option 4"))
        correct_ans = clean_str(os.environ.get("CORRECT_ANSWER", "Correct Answer: (A)"))

        wrapped = []
        for line in question_str.split("\n"):
            wrapped.extend(textwrap.wrap(line, width=44) if len(line) > 44 else [line])
        question = Paragraph(*wrapped, alignment="center", font_size=20,
                             color=WHITE, line_spacing=0.75)
        if question.width > self.MAX_WIDTH:
            question.scale_to_fit_width(self.MAX_WIDTH)
        question.move_to([0, ZONE_QUESTION + 0.6, 0])

        opts = [opt_a, opt_b, opt_c, opt_d]
        max_opt_len = max((len(o) for o in opts if o), default=0)
        if max_opt_len <= 16 and all(opts):
            row1 = VGroup(safe_mathtex(format_latex_option(opt_a), 20),
                          safe_mathtex(format_latex_option(opt_b), 20)).arrange(RIGHT, buff=0.6)
            row2 = VGroup(safe_mathtex(format_latex_option(opt_c), 20),
                          safe_mathtex(format_latex_option(opt_d), 20)).arrange(RIGHT, buff=0.6)
            options_grid = VGroup(row1, row2).arrange(DOWN, buff=0.25)
        else:
            options_grid = VGroup(*[safe_mathtex(format_latex_option(o), 20)
                                    for o in opts if o]).arrange(DOWN, buff=0.18, aligned_edge=LEFT)
        
        if options_grid.width > self.MAX_WIDTH:
            options_grid.scale_to_fit_width(self.MAX_WIDTH)
        options_grid.move_to([0, ZONE_OPTIONS, 0])

        ans_text = safe_mathtex(format_latex_option(correct_ans), font_size=24, color=COLOR_FORCE)
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

        eq_card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)

        visual_group, pending_rotations = self._build_visual_group(visual_json_str)
        visual_group.move_to([0, ZONE_VISUAL, 0])
        if visual_group.height > 4.0:
            visual_group.scale_to_fit_height(4.0)
        if visual_group.width > self.MAX_WIDTH:
            visual_group.scale_to_fit_width(self.MAX_WIDTH)

        step = max(1.0, (audio_duration - 5.0) / 4.0)
        self.play(FadeIn(question, shift=UP * 0.2), run_time=0.8)
        self.play(FadeIn(visual_group), run_time=1.2)
        
        for mob, angle, pivot in pending_rotations:
            shifted_pivot = mob.get_center() if pivot is None else (pivot + (visual_group.get_center() - ORIGIN))
            self.play(Rotate(mob, angle=angle, about_point=shifted_pivot), run_time=1.2)

        self.wait(step)
        self.play(FadeIn(options_grid, shift=UP * 0.15), run_time=0.8)
        self.wait(step * 0.5)
        if len(eq_card) > 0:
            self.play(FadeIn(eq_card[0]), Write(eq_card[1]), run_time=1.0)
        self.wait(step * 0.5)
        self.play(FadeIn(ans_box, shift=UP * 0.2),
                  Circumscribe(ans_box, color=COLOR_ACCENT, buff=0.1, run_time=1.0))

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

    def build_dynamic_json_scene(self, visual_json_str: str, audio_duration: float):
        group, pending_rotations = self._build_visual_group(visual_json_str)
        group.move_to([0, ZONE_VISUAL - 0.5, 0])
        self.play(FadeIn(group), run_time=1.2)
        
        for mob, angle, pivot in pending_rotations:
            shifted_pivot = mob.get_center() if pivot is None else (pivot + (group.get_center() - ORIGIN))
            self.play(Rotate(mob, angle=angle, about_point=shifted_pivot), run_time=1.2)

        card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

    def _build_visual_group(self, visual_json_str: str) -> tuple[VGroup, list[tuple]]:
        elements = parse_json_list(visual_json_str)
        pending_rotations = []
        group = VGroup()

        for idx, item in enumerate(elements):
            if not isinstance(item, dict):
                continue
            mob = self._build_json_element(item, idx)
            if mob is None:
                continue
            group.add(mob)

            anim = item.get("animate")
            if anim == "rotate":
                angle = float(item.get("rotate_angle", 45)) * DEGREES
                pivot = to_3d_point(item.get("pivot")) if item.get("pivot") is not None else None
                pending_rotations.append((mob, angle, pivot))

        return group, pending_rotations

    def _build_json_element(self, item: dict, idx: int) -> Mobject | None:
        e_type = str(item.get("type", "")).lower()
        color = item.get("color", COLOR_ACCENT)
        lbl_text = item.get("label", "")

        mob: Mobject | None = None

        if e_type in ("field", "vector_field"):
            direction = str(item.get("direction", "RIGHT")).upper()
            rows = int(item.get("rows", 7))
            field = VGroup()
            
            if direction in ("UP", "DOWN"):
                x_pts = np.linspace(-3.5, 3.5, rows)
                for x in x_pts:
                    arr = Arrow(RIGHT * x + DOWN * 2.0, RIGHT * x + UP * 2.0, buff=0, stroke_width=2.5, color=color) if direction == "UP" \
                          else Arrow(RIGHT * x + UP * 2.0, RIGHT * x + DOWN * 2.0, buff=0, stroke_width=2.5, color=color)
                    arr.set_opacity(float(item.get("opacity", 0.35)))
                    field.add(arr)
            else:
                y_pts = np.linspace(1.8, -3.2, rows)
                for y in y_pts:
                    arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=color) if direction == "RIGHT" \
                          else Arrow(RIGHT * 4.0 + UP * y, LEFT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=color)
                    arr.set_opacity(float(item.get("opacity", 0.35)))
                    field.add(arr)

            if lbl_text:
                field.add(safe_mathtex(lbl_text, 32, color=color).next_to(field[0], RIGHT, buff=0.2))
            mob = field

        elif e_type in ("charge", "particle", "dot"):
            pos = to_3d_point(item.get("pos", [0, 0, 0]))
            radius = float(item.get("radius", 0.22))
            dot = Dot(pos, radius=radius, color=color)
            mob = VGroup(dot, safe_mathtex(lbl_text, 20, WHITE).move_to(pos)) if lbl_text else dot

        elif e_type in ("vector", "arrow", "force"):
            start = to_3d_point(item.get("start", [0, 0, 0]))
            end   = to_3d_point(item.get("end",   [1, 1, 0]))
            vec = Arrow(start, end, buff=0, stroke_width=3.5, color=color)
            if lbl_text:
                v_lbl = safe_mathtex(lbl_text, 24, color=color).next_to(vec, UP, buff=0.1)
                mob = VGroup(vec, v_lbl)
            else:
                mob = vec

        elif e_type in ("line", "rod", "segment"):
            start = to_3d_point(item.get("start", [0, 0, 0]))
            end   = to_3d_point(item.get("end",   [1, 1, 0]))
            dashed = bool(item.get("dashed", False))
            line = DashedLine(start, end, color=color, stroke_width=2.5) if dashed \
                   else Line(start, end, color=color, stroke_width=4)
            if lbl_text:
                line = VGroup(line, safe_mathtex(lbl_text, 22, color=color).next_to(line, RIGHT, buff=0.1))
            mob = line

        elif e_type in ("arc", "angle", "angle_arc"):
            center  = to_3d_point(item.get("center", [0, 0, 0]))
            radius  = float(item.get("radius", 0.8))
            s_angle = float(item.get("start_angle", 0)) * DEGREES
            angle   = float(item.get("angle", 45)) * DEGREES
            arc = Arc(radius=radius, start_angle=s_angle, angle=angle,
                      arc_center=center, color=color)
            if lbl_text:
                arc = VGroup(arc, safe_mathtex(lbl_text, 22, color=color).next_to(arc, RIGHT, buff=0.1))
            mob = arc

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

        elif e_type in ("shape", "lens", "circle", "rectangle", "ellipse", "polygon"):
            kind = str(item.get("kind", e_type if e_type != "shape" else "circle")).lower()
            pos  = to_3d_point(item.get("pos", [0, -1, 0]))
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
                pts = [to_3d_point(p) for p in item.get("points", [])]
                if len(pts) >= 3:
                    mob = Polygon(*pts, color=color,
                                  fill_opacity=float(item.get("fill_opacity", 0.2)))
            else:
                mob = Circle(radius=float(item.get("radius", 1.0)),
                             color=color, stroke_width=3).move_to(pos)

        elif e_type == "text":
            txt = str(item.get("text", lbl_text))
            pos = to_3d_point(item.get("pos", [0, 0, 0]))
            if item.get("use_latex", False) or "$" in txt or "\\" in txt:
                mob = safe_mathtex(txt, font_size=int(item.get("font_size", 22)), color=color).move_to(pos)
            else:
                mob = Text(txt, font_size=int(item.get("font_size", 22)), color=color).move_to(pos)

        elif e_type == "group":
            sub = VGroup()
            for j, subitem in enumerate(item.get("children", [])):
                sm = self._build_json_element(subitem, j)
                if sm is not None:
                    sub.add(sm)
            mob = sub

        if mob is None:
            return None

        if "opacity" in item:
            mob.set_opacity(float(item["opacity"]))
        if "scale" in item:
            mob.scale(float(item["scale"]))
        if "rotate" in item:
            mob.rotate(float(item["rotate"]) * DEGREES)
        if "shift" in item:
            mob.shift(to_3d_point(item["shift"]))
        if "z_index" in item:
            mob.set_z_index(int(item["z_index"]))

        return mob

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
