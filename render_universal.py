"""
render_universal.py — Cinematic 9:16 rendering engine (3b1b-flavored).
Nothing is ever static: every wait is a live_wait with breathing motion,
camera moves, or a running value tracker.
"""

from __future__ import annotations

import json, math, os, re, textwrap
from typing import Any

import numpy as np
from manim import *

from manim_fx import (
    PALETTE, RF_SOFT, RF_SNAP, RF_SPRING,
    live_wait, idle_float, pop_in, staggered_reveal, card_reveal,
    glow_pulse, underline_brace, traced_graph, value_counter,
    morph_equations, CameraDirector, wipe_transition,
)

# ---------------------------------------------------------------- config
config.pixel_width  = 1080
config.pixel_height = 1920
config.frame_width  = 9.0
config.frame_height = 16.0
config.frame_rate   = 30

# ---------------------------------------------------------------- zones (frame-units)
ZONE_HEADER    = +6.90
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


# ---------------------------------------------------------------- helpers (kept from original)
def clean_str(text: str | None) -> str:
    return "" if not text else str(text).strip().strip('"\'').strip()

def to_3d_point(p: Any) -> np.ndarray:
    if p is None: return np.zeros(3)
    arr = np.array(p, dtype=float)
    if arr.ndim == 1:
        if len(arr) == 2: return np.array([arr[0], arr[1], 0.0])
        if len(arr) >= 3: return arr[:3]
    return np.zeros(3)

def sanitize_latex(s: str) -> str:
    for uni, tex in _UNICODE_TO_LATEX.items():
        s = s.replace(uni, tex)
    return s

def safe_mathtex(s: str, font_size: int = 24, color=WHITE) -> Mobject:
    if s is None: s = ""
    s_clean = sanitize_latex(str(s).strip())
    if not s_clean:
        return Text("", font_size=font_size, color=color)
    for ctor in (MathTex, Tex):
        try: return ctor(s_clean, font_size=font_size, color=color)
        except Exception: continue
    fallback = re.sub(r"\\[a-zA-Z]+", "", s_clean).replace("{", "").replace("}", "")
    return Text(fallback, font_size=font_size, color=color)

def format_latex_option(opt_text: str) -> str:
    opt_text = clean_str(opt_text)
    if not opt_text: return ""
    prefix = ""
    if opt_text.lower().startswith("correct answer:"):
        prefix = r"\text{Correct Answer: }"
        opt_text = opt_text[15:].strip()
    m = re.match(r"^(\([A-Da-d]\))\s*(.*)$", opt_text)
    if m:
        label, rest = m.group(1), m.group(2)
        if not rest: body = r"\text{" + label + r"}"
        elif re.search(r"[\$\\_^{}]", rest): body = r"\text{" + label + r" }" + rest
        else: body = r"\text{" + label + " " + rest + r"}"
        return prefix + body
    if not re.search(r"[\$\\_^{}]", opt_text):
        return prefix + r"\text{" + opt_text + r"}"
    return prefix + opt_text

def safe_eval_math(expr_str: str, x_val: float) -> float:
    if not expr_str: return 0.0
    expr = str(expr_str).replace("^", "**")
    expr = re.sub(r"(\d|\bx\b|\))\s*([a-zA-Z\(])", r"\1*\2", expr)
    expr = re.sub(r"\*{3,}", "**", expr)
    allowed = {"sin": np.sin, "cos": np.cos, "tan": np.tan,
               "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs,
               "log": np.log, "pi": np.pi, "e": np.e, "x": x_val}
    try: return float(eval(expr, {"__builtins__": None}, allowed))
    except Exception: return 0.0

def parse_json_list(raw: str | None) -> list[Any]:
    if not raw: return []
    try:
        parsed = json.loads(str(raw).strip())
        if isinstance(parsed, str): parsed = json.loads(parsed)
        if isinstance(parsed, list): return parsed
    except Exception: pass
    return []


# ================================================================ SCENE
class UniversalPhysicsScene(MovingCameraScene):
    """MovingCameraScene gives us cinematic camera control."""

    def construct(self):
        self.camera.background_color = PALETTE["bg"]
        self.MAX_WIDTH = 7.8
        self.director = CameraDirector(self)

        concept_type   = os.environ.get("CONCEPT_TYPE", "GENERIC").upper().strip()
        header_title   = clean_str(os.environ.get("HEADER_TITLE", "Physics Concept"))
        tagline        = clean_str(os.environ.get("TAGLINE", "3b1b Visual Intuition"))
        audio_duration = float(os.environ.get("AUDIO_DURATION", 20.0) or 20.0)

        visual_json = os.environ.get("VISUAL_DATA_JSON", "")
        self.equations = self._read_equations()

        # ---------------- header (always present, always breathing)
        self.build_header(header_title, tagline)

        is_pyq = concept_type in ("PYQ", "MCQ", "QUESTION")
        has_visual = bool(parse_json_list(visual_json))

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
                err = Text(f"[render error]\n{type(exc).__name__}: {exc}",
                           font_size=18, color=PALETTE["pos"]).move_to(ORIGIN)
                self.add(err)
                self._live_wait_remaining(audio_duration)
            else:
                raise

        self._live_wait_remaining(audio_duration)

    # ---------------------------------------------------------------- timeline
    def _live_wait_remaining(self, audio_duration: float):
        rem = audio_duration - self.renderer.time
        if rem > 0.1:
            live_wait(self, rem)

    def _read_equations(self) -> list[str]:
        raw = os.environ.get("EQUATIONS_JSON", "")
        return [str(x) for x in parse_json_list(raw) if x]

    # ---------------------------------------------------------------- header
    def build_header(self, title_text: str, tagline_text: str):
        kw_t = dict(font_size=30, color=PALETTE["accent"])
        kw_s = dict(font_size=18, color=PALETTE["muted"])
        if HINDI_FONT:
            kw_t["font"] = HINDI_FONT; kw_s["font"] = HINDI_FONT
        else:
            kw_t["weight"] = BOLD; kw_s["slant"] = ITALIC

        title = Text(title_text, **kw_t)
        sub   = Text(tagline_text, **kw_s)
        rule  = Line(LEFT, RIGHT, color=PALETTE["accent"], stroke_width=2).set_width(3.2)

        header = VGroup(title, rule, sub).arrange(DOWN, buff=0.14).move_to([0, ZONE_HEADER, 0])
        if header.width > self.MAX_WIDTH:
            header.scale_to_fit_width(self.MAX_WIDTH)

        self.play(FadeIn(title, shift=DOWN * 0.15), run_time=0.5)
        self.play(GrowFromCenter(rule), run_time=0.4)
        self.play(FadeIn(sub, shift=UP * 0.1), run_time=0.4)
        self.header = header

    # ---------------------------------------------------------------- equation card
    def draw_math_card(self, equations: list[str], y_center: float = ZONE_EQUATIONS) -> VGroup:
        if not equations:
            return VGroup()
        eq_group = VGroup(*[safe_mathtex(eq, font_size=28, color=PALETTE["white"])
                            for eq in equations if eq])
        if len(eq_group) == 0:
            return VGroup()
        eq_group.arrange(DOWN, buff=0.24)
        if eq_group.width > self.MAX_WIDTH - 0.4:
            eq_group.scale_to_fit_width(self.MAX_WIDTH - 0.4)

        card_bg = RoundedRectangle(
            corner_radius=0.22, width=self.MAX_WIDTH,
            height=eq_group.height + 0.55,
            fill_color=PALETTE["card"], fill_opacity=0.96,
            stroke_color=PALETTE["border"], stroke_width=1.5,
        ).move_to([0, y_center, 0])
        eq_group.move_to(card_bg.get_center())
        return VGroup(card_bg, eq_group)

    # ================================================================ SCENE BUILDERS
    # ------------------------------------------------------------------ PYQ + visual
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
                             color=PALETTE["white"], line_spacing=0.75)
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

        ans_text = safe_mathtex(format_latex_option(correct_ans), 24, color=PALETTE["force"])
        ans_box = VGroup(
            RoundedRectangle(corner_radius=0.15,
                             width=max(ans_text.width + 0.6, 5.0),
                             height=ans_text.height + 0.4,
                             fill_color=PALETTE["card"], fill_opacity=0.95,
                             stroke_color=PALETTE["force"], stroke_width=2.5),
            ans_text,
        ).move_to([0, ZONE_ANSWER, 0])

        eq_card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)
        visual_group, pending_rotations = self._build_visual_group(visual_json_str)
        visual_group.move_to([0, ZONE_VISUAL, 0])
        if visual_group.height > 4.0: visual_group.scale_to_fit_height(4.0)
        if visual_group.width > self.MAX_WIDTH: visual_group.scale_to_fit_width(self.MAX_WIDTH)

        # ---------------- narrative timeline (runs WITH audio, not before)
        total = audio_duration
        t_question = total * 0.18
        t_visual   = total * 0.32
        t_options  = total * 0.22
        t_answer   = total * 0.28

        # 1) Question types on
        self.play(FadeIn(question, shift=DOWN * 0.2), run_time=0.7)
        live_wait(self, t_question - 0.7, [question])

        # 2) Visual group assembles + camera zoom-in
        staggered_reveal(self, visual_group, run_time=1.1)
        self.director.zoom(1.15, run_time=1.0, center=np.array([0, ZONE_VISUAL, 0]))
        for mob, angle, pivot in pending_rotations:
            piv = mob.get_center() if pivot is None else pivot
            self.play(Rotate(mob, angle=angle, about_point=piv), run_time=0.9)
        live_wait(self, max(0.5, t_visual - 2.0), [visual_group])
        self.director.reset(run_time=0.8)

        # 3) Options cascade
        staggered_reveal(self, options_grid, run_time=1.0)
        live_wait(self, max(0.5, t_options - 1.0), [options_grid])

        # 4) Equation card + answer
        if len(eq_card) > 0:
            card_reveal(self, eq_card, run_time=1.2)
        pop_in(self, ans_box, run_time=0.6)
        self.play(Circumscribe(ans_box, color=PALETTE["accent"], buff=0.12, run_time=1.0))
        live_wait(self, max(0.5, t_answer - 1.5), [ans_box, eq_card[1]] if len(eq_card) else [ans_box])

    # ------------------------------------------------------------------ PYQ (no visual)
    def build_pyq_scene(self, audio_duration: float):
        # Simplified — same pattern as above minus the visual
        self.build_pyq_with_visual_scene("[]", audio_duration)

    # ------------------------------------------------------------------ dynamic JSON
    def build_dynamic_json_scene(self, visual_json_str: str, audio_duration: float):
        group, pending_rotations = self._build_visual_group(visual_json_str)
        group.move_to([0, ZONE_VISUAL - 0.3, 0])

        # Reveal with camera ease-in
        self.director.zoom(1.12, run_time=1.0, center=np.array([0, ZONE_VISUAL, 0]))
        staggered_reveal(self, group, run_time=1.3)

        for mob, angle, pivot in pending_rotations:
            piv = mob.get_center() if pivot is None else pivot
            self.play(Rotate(mob, angle=angle, about_point=piv), run_time=1.0)

        card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.2)

        # ============ HERE is the key difference ============
        # Instead of a frozen wait, use the remaining audio time for
        # continuous motion: camera drifts, equations breathe, visuals pulse.
        remaining = audio_duration - self.renderer.time
        if remaining > 0.5:
            self._live_wait_remaining(audio_duration)

    # ------------------------------------------------------------------ DIPOLE (fully animated)
    def build_dipole_torque_scene(self, audio_duration: float):
        equations = self.equations or [
            r"\vec{F}_{\text{net}} = \vec{0}",
            r"\tau = pE\sin\theta",
            r"\vec{\tau} = \vec{p}\times\vec{E}",
        ]
        # field lines with animated opacity shimmer
        field_lines = VGroup()
        for y in np.linspace(1.8, -3.2, 7):
            arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y,
                        buff=0, stroke_width=2.5, color=PALETTE["field"]).set_opacity(0.32)
            field_lines.add(arr)
        field_lines.add(safe_mathtex(r"\vec{E}", 36, PALETTE["field"]).next_to(field_lines[0], RIGHT, buff=0.2))
        field_lines.move_to([0, ZONE_VISUAL, 0])

        center_pt = np.array([0, ZONE_VISUAL - 1.4, 0])
        a_len = 1.4
        rod = Line(center_pt - RIGHT * a_len, center_pt + RIGHT * a_len,
                   color=PALETTE["muted"], stroke_width=4)
        c_pos = VGroup(Dot(center_pt + RIGHT * a_len, radius=0.22, color=PALETTE["pos"]),
                       safe_mathtex("+q", 20, WHITE).move_to(center_pt + RIGHT * a_len))
        c_neg = VGroup(Dot(center_pt - RIGHT * a_len, radius=0.22, color=PALETTE["neg"]),
                       safe_mathtex("-q", 20, WHITE).move_to(center_pt - RIGHT * a_len))
        dipole = VGroup(rod, c_pos, c_neg)

        # reveal field
        self.play(LaggedStart(*[Create(a) for a in field_lines[:-1]], lag_ratio=0.08), run_time=1.2)
        self.play(FadeIn(field_lines[-1]), run_time=0.3)

        # assemble dipole
        self.play(FadeIn(dipole, shift=UP * 0.2), run_time=0.8)

        # THE key animated moment: torque rotation
        p_arrow = Arrow(center_pt - RIGHT * a_len * 0.6, center_pt + RIGHT * a_len * 0.6,
                        buff=0.2, color=PALETTE["accent"], stroke_width=4)
        p_lbl = safe_mathtex(r"\vec{p}", 30, PALETTE["accent"]).next_to(p_arrow.get_center(), UP, buff=0.1)
        self.play(Create(p_arrow), FadeIn(p_lbl), run_time=0.6)

        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.2)

        # Rotate the dipole while the remaining audio plays
        remaining = audio_duration - self.renderer.time
        if remaining > 1.0:
            # Oscillating rotation — the actual physics of a torque
            self.play(
                Rotate(dipole, angle=35 * DEGREES, about_point=center_pt),
                Rotate(p_arrow, angle=35 * DEGREES, about_point=center_pt),
                Rotate(p_lbl, angle=35 * DEGREES, about_point=center_pt),
                run_time=remaining * 0.35, rate_func=RF_SOFT,
            )
            self.play(
                Rotate(dipole, angle=-35 * DEGREES, about_point=center_pt),
                Rotate(p_arrow, angle=-35 * DEGREES, about_point=center_pt),
                Rotate(p_lbl, angle=-35 * DEGREES, about_point=center_pt),
                run_time=remaining * 0.35, rate_func=RF_SOFT,
            )
            self._live_wait_remaining(audio_duration)

    # ------------------------------------------------------------------ PROJECTILE (real trajectory animation)
    def build_projectile_scene(self, audio_duration: float):
        equations = self.equations or [
            r"y = x\tan\theta - \frac{g x^2}{2u^2\cos^2\theta}",
            r"R = \frac{u^2\sin 2\theta}{g}",
        ]
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 3, 1],
                    x_length=6, y_length=3.5,
                    axis_config={"color": PALETTE["muted"]}).move_to([0, ZONE_VISUAL - 1.0, 0])
        fn = lambda x: 2.5 * x - 0.6 * x ** 2

        graph, dot = traced_graph(self, axes, fn, [0, 4.16],
                                  color=PALETTE["accent"], duration=2.4,
                                  dot_color=PALETTE["pos"])

        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.2)

        # Ball continues to pulse with the audio
        remaining = audio_duration - self.renderer.time
        if remaining > 0.5:
            self.play(dot.animate.scale(1.4), run_time=0.3)
            self.play(dot.animate.scale(1 / 1.4), run_time=0.3)
            self._live_wait_remaining(audio_duration)

    # ------------------------------------------------------------------ LORENTZ (spiral motion)
    def build_lorentz_force_scene(self, audio_duration: float):
        equations = self.equations or [r"\vec{F} = q(\vec{v}\times\vec{B})", r"r = \frac{mv}{qB}"]
        field_group = VGroup()
        for y in np.linspace(1.5, -3.5, 6):
            arr = Arrow(LEFT * 3.8 + UP * y, RIGHT * 3.8 + UP * y,
                        buff=0, stroke_width=2, color=PALETTE["accent"]).set_opacity(0.35)
            field_group.add(arr)
        field_group.add(safe_mathtex(r"\vec{B}", 34, PALETTE["accent"])
                        .next_to(field_group[0], RIGHT, buff=0.2))
        field_group.move_to([0, ZONE_VISUAL, 0])

        charge = Dot(LEFT * 2.5 + DOWN * 1.0 + np.array([0, ZONE_VISUAL, 0]),
                     radius=0.25, color=PALETTE["pos"])
        v_arrow = Arrow(charge.get_center(), charge.get_center() + UP * 1.8,
                        buff=0, color=PALETTE["force"])

        self.play(LaggedStart(*[Create(a) for a in field_group[:-1]], lag_ratio=0.06),
                  FadeIn(field_group[-1]), run_time=1.0)
        self.play(FadeIn(charge), GrowArrow(v_arrow), run_time=0.6)

        # Real circular motion — this is what the charge actually does
        center = np.array([-2.5 + 1.6, ZONE_VISUAL - 1.0 + 1.6, 0])
        radius = 1.6
        circle = Circle(radius=radius, color=PALETTE["pos"], stroke_width=2,
                        stroke_opacity=0.35).move_to(center)
        self.play(Create(circle), run_time=0.8)

        # Full loop — this fills the beat with continuous motion
        dur_loop = min(audio_duration - self.renderer.time - 1.5, 5.0)
        if dur_loop > 1.0:
            self.play(MoveAlongPath(charge, circle), run_time=dur_loop, rate_func=linear)

        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        self._live_wait_remaining(audio_duration)

    # ------------------------------------------------------------------ WAVE (live propagation)
    def build_wave_shm_scene(self, audio_duration: float):
        equations = self.equations or [
            r"y(x,t) = A\sin(kx - \omega t + \phi)",
            r"v = f\lambda,\quad k = \frac{2\pi}{\lambda}",
        ]
        axes = Axes(x_range=[0, 6, 1], y_range=[-2, 2, 1],
                    x_length=6.5, y_length=3.0,
                    axis_config={"color": PALETTE["muted"]}).move_to([0, ZONE_VISUAL - 0.6, 0])
        self.play(Create(axes), run_time=0.5)

        # animate the wave: a tracker drives phase
        phase = ValueTracker(0.0)
        wave = always_redraw(lambda: axes.plot(
            lambda x: 1.2 * np.sin(2 * x - phase.get_value()),
            x_range=[0, 6], color=PALETTE["field"], stroke_width=4,
        ))
        self.add(wave, phase)

        # reveal duration
        dur = min(audio_duration - self.renderer.time - 1.5, 5.0)
        if dur > 0.5:
            self.play(phase.animate.set_value(TAU * 2), run_time=dur, rate_func=linear)

        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)

        # continue propagation through remaining time
        remaining = audio_duration - self.renderer.time
        if remaining > 0.3:
            self.play(phase.animate.set_value(TAU * 2 + remaining * 3),
                      run_time=remaining, rate_func=linear)
        phase.clear_updaters()

    # ------------------------------------------------------------------ OPTICS (animated rays)
    def build_optics_scene(self, audio_duration: float):
        equations = self.equations or [
            r"\frac{1}{f} = \frac{1}{v} - \frac{1}{u}",
            r"P = (n-1)\!\left(\frac{1}{R_1} - \frac{1}{R_2}\right)",
        ]
        base = np.array([0, ZONE_VISUAL - 1.0, 0])
        axis = Line(LEFT * 3.5, RIGHT * 3.5, color=PALETTE["muted"]).move_to(base)
        lens = Ellipse(width=0.6, height=3.0, color=PALETTE["field"],
                       fill_color=PALETTE["field"], fill_opacity=0.3).move_to(base)
        self.play(Create(axis), FadeIn(lens), run_time=0.7)

        # Animated incoming ray
        ray_in = Line(LEFT * 3.5 + UP * 0.2 + base, UP * 0.2 + base,
                      color=PALETTE["accent"], stroke_width=3)
        ray_out = Line(UP * 0.2 + base, RIGHT * 3.5 + DOWN * 1.2 + base,
                       color=PALETTE["accent"], stroke_width=3)
        self.play(Create(ray_in), run_time=0.6)
        self.play(Create(ray_out), run_time=0.6)

        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)

        # pulse the lens with remaining time
        remaining = audio_duration - self.renderer.time
        if remaining > 0.4:
            self.play(lens.animate.set_fill(PALETTE["accent"], opacity=0.35),
                      run_time=remaining * 0.4)
            self.play(lens.animate.set_fill(PALETTE["field"], opacity=0.3),
                      run_time=remaining * 0.6)

    # ------------------------------------------------------------------ CIRCUIT (charging animation)
    def build_circuit_scene(self, audio_duration: float):
        equations = self.equations or [
            r"q(t) = Q_0\!\left(1 - e^{-t/RC}\right)",
            r"\tau = RC",
        ]
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 2, 1],
                    x_length=6.0, y_length=3.0,
                    axis_config={"color": PALETTE["muted"]}).move_to([0, ZONE_VISUAL - 0.6, 0])

        fn = lambda x: 1.8 * (1 - np.exp(-x))
        graph, dot = traced_graph(self, axes, fn, [0, 5],
                                  color=PALETTE["accent"], duration=2.2,
                                  dot_color=PALETTE["pos"])

        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        self._live_wait_remaining(audio_duration)

    # ------------------------------------------------------------------ GENERIC
    def build_generic_vector_scene(self, audio_duration: float):
        base = np.array([0, ZONE_VISUAL, 0])
        v1 = Arrow(ORIGIN, RIGHT * 2 + UP * 1, buff=0, color=PALETTE["field"]).move_to(base)
        v2 = Arrow(ORIGIN, RIGHT * 1 + DOWN * 2, buff=0, color=PALETTE["force"]).move_to(base)

        self.play(GrowArrow(v1), run_time=0.6)
        self.play(GrowArrow(v2), run_time=0.6)

        card = self.draw_math_card(self.equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        self._live_wait_remaining(audio_duration)

    # ================================================================ JSON element builder
    def _build_visual_group(self, visual_json_str: str) -> tuple[VGroup, list[tuple]]:
        elements = parse_json_list(visual_json_str)
        pending_rotations = []
        group = VGroup()
        for idx, item in enumerate(elements):
            if not isinstance(item, dict): continue
            mob = self._build_json_element(item, idx)
            if mob is None: continue
            group.add(mob)
            if item.get("animate") == "rotate":
                angle = float(item.get("rotate_angle", 45)) * DEGREES
                pivot = to_3d_point(item.get("pivot")) if item.get("pivot") is not None else None
                pending_rotations.append((mob, angle, pivot))
        return group, pending_rotations

    def _build_json_element(self, item: dict, idx: int) -> Mobject | None:
        e_type = str(item.get("type", "")).lower()
        color = item.get("color", PALETTE["accent"])
        lbl_text = item.get("label", "")
        mob: Mobject | None = None

        if e_type in ("field", "vector_field"):
            direction = str(item.get("direction", "RIGHT")).upper()
            rows = int(item.get("rows", 7))
            field = VGroup()
            if direction in ("UP", "DOWN"):
                x_pts = np.linspace(-3.5, 3.5, rows)
                for x in x_pts:
                    if direction == "UP":
                        arr = Arrow(RIGHT * x + DOWN * 2.0, RIGHT * x + UP * 2.0, buff=0, stroke_width=2.5, color=color)
                    else:
                        arr = Arrow(RIGHT * x + UP * 2.0, RIGHT * x + DOWN * 2.0, buff=0, stroke_width=2.5, color=color)
                    arr.set_opacity(float(item.get("opacity", 0.35)))
                    field.add(arr)
            else:
                y_pts = np.linspace(1.8, -3.2, rows)
                for y in y_pts:
                    if direction == "RIGHT":
                        arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=color)
                    else:
                        arr = Arrow(RIGHT * 4.0 + UP * y, LEFT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=color)
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
            end   = to_3d_point(item.get("end", [1, 1, 0]))
            vec = Arrow(start, end, buff=0, stroke_width=3.5, color=color)
            if lbl_text:
                v_lbl = safe_mathtex(lbl_text, 24, color=color).next_to(vec, UP, buff=0.1)
                mob = VGroup(vec, v_lbl)
            else:
                mob = vec

        elif e_type in ("line", "rod", "segment"):
            start = to_3d_point(item.get("start", [0, 0, 0]))
            end   = to_3d_point(item.get("end", [1, 1, 0]))
            dashed = bool(item.get("dashed", False))
            line = DashedLine(start, end, color=color, stroke_width=2.5) if dashed \
                   else Line(start, end, color=color, stroke_width=4)
            if lbl_text:
                line = VGroup(line, safe_mathtex(lbl_text, 22, color=color).next_to(line, RIGHT, buff=0.1))
            mob = line

        elif e_type in ("arc", "angle", "angle_arc"):
            center = to_3d_point(item.get("center", [0, 0, 0]))
            radius = float(item.get("radius", 0.8))
            s_angle = float(item.get("start_angle", 0)) * DEGREES
            angle = float(item.get("angle", 45)) * DEGREES
            arc = Arc(radius=radius, start_angle=s_angle, angle=angle, arc_center=center, color=color)
            if lbl_text:
                arc = VGroup(arc, safe_mathtex(lbl_text, 22, color=color).next_to(arc, RIGHT, buff=0.1))
            mob = arc

        elif e_type in ("graph", "function", "curve"):
            expr = item.get("expression", "sin(x)")
            x_min, x_max = item.get("x_range", [0, 5])
            y_min, y_max = item.get("y_range", [-2, 2])
            axes = Axes(x_range=[x_min, x_max, 1], y_range=[y_min, y_max, 1],
                        x_length=6.0, y_length=3.0, axis_config={"color": PALETTE["muted"]})
            graph = axes.plot(lambda x: safe_eval_math(expr, x), x_range=[x_min, x_max], color=color)
            mob = VGroup(axes, graph)

        elif e_type in ("shape", "lens", "circle", "rectangle", "ellipse", "polygon"):
            kind = str(item.get("kind", e_type if e_type != "shape" else "circle")).lower()
            pos  = to_3d_point(item.get("pos", [0, -1, 0]))
            if kind == "rectangle":
                dims = item.get("dims", [2, 1])
                mob = Rectangle(width=dims[0], height=dims[1], color=color,
                                fill_opacity=float(item.get("fill_opacity", 0.2))).move_to(pos)
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
                if sm is not None: sub.add(sm)
            mob = sub

        if mob is None: return None
        if "opacity" in item: mob.set_opacity(float(item["opacity"]))
        if "scale" in item:   mob.scale(float(item["scale"]))
        if "rotate" in item:  mob.rotate(float(item["rotate"]) * DEGREES)
        if "shift" in item:   mob.shift(to_3d_point(item["shift"]))
        if "z_index" in item: mob.set_z_index(int(item["z_index"]))
        return mob
