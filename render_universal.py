import os
import json
import re
import textwrap
import numpy as np
from manim import *

# -------------------------------------------------------------
# 9:16 VERTICAL ASPECT RATIO FOR YOUTUBE SHORTS (1080x1920)
# Frame dimensions: Width = 9.0 units, Height = 16.0 units
# -------------------------------------------------------------
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0

# 3Blue1Brown High-Contrast Dark Color Palette
COLOR_BG = "#0B0C10"
COLOR_FIELD = "#3498DB"
COLOR_POS = "#FF4B4B"
COLOR_NEG = "#00D2FF"
COLOR_ACCENT = "#F1C40F"
COLOR_FORCE = "#2ECC71"
COLOR_CARD_BG = "#15161D"
COLOR_BORDER = "#333333"


def clean_str(text: str) -> str:
    if not text:
        return ""
    return text.strip('"\'').strip()


def format_latex_option(opt_text: str) -> str:
    opt_text = clean_str(opt_text)
    if not opt_text:
        return ""
    if not re.search(r'[\$\\_^{}]', opt_text):
        return r"\text{" + opt_text + r"}"
    return opt_text


def safe_eval_math(expr_str: str, x_val: float) -> float:
    """Evaluates mathematical function expressions safely for dynamic graph plots."""
    allowed = {
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "exp": np.exp, "sqrt": np.sqrt, "abs": np.abs,
        "pi": np.pi, "e": np.e, "x": x_val
    }
    try:
        return float(eval(expr_str, {"__builtins__": None}, allowed))
    except Exception:
        return 0.0


class UniversalPhysicsScene(Scene):
    def construct(self):
        self.camera.background_color = COLOR_BG
        MAX_WIDTH = 7.8

        concept_type = os.environ.get("CONCEPT_TYPE", "GENERIC").upper().strip()
        header_title = os.environ.get("HEADER_TITLE", "Physics Concept")
        tagline = os.environ.get("TAGLINE", "3b1b Visual Intuition")
        audio_duration = float(os.environ.get("AUDIO_DURATION", 20.0))

        # Top Header Overlay
        title = Text(header_title, font_size=28, weight=BOLD, color=COLOR_ACCENT)
        sub = Text(tagline, font_size=18, slant=ITALIC, color=GRAY_B)
        header = VGroup(title, sub).arrange(DOWN, buff=0.1).to_edge(UP, buff=0.5)
        if header.width > MAX_WIDTH:
            header.scale_to_fit_width(MAX_WIDTH)
        self.add(header)

        # Priority 1: Check for Dynamic Declarative Visual JSON Payload in CSV
        visual_json = os.environ.get("VISUAL_DATA_JSON", "").strip()
        if visual_json and visual_json != "[]":
            self.build_dynamic_json_scene(visual_json, audio_duration, MAX_WIDTH)
            return

        # Priority 2: Built-in Physics Archetype Presets
        if concept_type in ["PYQ", "MCQ", "QUESTION"]:
            self.build_pyq_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["DIPOLE_TORQUE", "DIPOLE", "ELECTROSTATICS_DIPOLE"]:
            self.build_dipole_torque_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["PROJECTILE_MOTION", "PROJECTILE", "KINEMATICS"]:
            self.build_projectile_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["LORENTZ_FORCE", "LORENTZ", "MAGNETISM"]:
            self.build_lorentz_force_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["WAVE_MOTION", "WAVE", "SHM", "OSCILLATION"]:
            self.build_wave_shm_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["OPTICS", "RAY_OPTICS", "LENS"]:
            self.build_optics_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["CIRCUIT", "RC_CIRCUIT", "CAPACITOR"]:
            self.build_circuit_scene(audio_duration, MAX_WIDTH)
        else:
            self.build_generic_vector_scene(audio_duration, MAX_WIDTH)

    # -------------------------------------------------------------
    # HELPER: SAFE EQUATION & DERIVATION CARD BUILDERS
    # -------------------------------------------------------------
    def get_equations(self):
        raw_eqs = os.environ.get("EQUATIONS_JSON", "")
        if not raw_eqs:
            return []
        try:
            parsed = json.loads(raw_eqs)
            if isinstance(parsed, list):
                return [str(e) for e in parsed if e]
            elif isinstance(parsed, str):
                return [parsed]
        except Exception:
            return [raw_eqs]
        return []

    def draw_math_card(self, equations, max_width):
        if not equations:
            return VGroup()
        eq_group = VGroup(*[MathTex(eq, font_size=26, color=WHITE) for eq in equations if eq]).arrange(DOWN, buff=0.25)
        if len(eq_group) == 0:
            return VGroup()
        if eq_group.width > max_width - 0.4:
            eq_group.scale_to_fit_width(max_width - 0.4)

        card_bg = RoundedRectangle(
            corner_radius=0.2, width=max_width, height=eq_group.height + 0.5,
            fill_color=COLOR_CARD_BG, fill_opacity=0.94, stroke_color=COLOR_BORDER, stroke_width=2
        ).move_to(DOWN * 5.4)

        eq_group.move_to(card_bg.get_center())
        return VGroup(card_bg, eq_group)

    # -------------------------------------------------------------
    # DECLARATIVE JSON PARSER (BUILDS ANY CUSTOM DIAGRAM/ANIMATION)
    # -------------------------------------------------------------
    def build_dynamic_json_scene(self, visual_json_str, audio_duration, max_width):
        try:
            elements = json.loads(visual_json_str)
        except Exception:
            elements = []

        mobject_map = {}
        static_group = VGroup()
        animations = []

        for idx, item in enumerate(elements):
            e_type = item.get("type", "").lower()
            e_id = item.get("id", f"elem_{idx}")
            color = item.get("color", COLOR_ACCENT)
            lbl_text = item.get("label", "")

            mobj = None

            if e_type in ["field", "vector_field"]:
                direction = item.get("direction", "RIGHT").upper()
                field = VGroup()
                for y in np.linspace(1.8, -3.2, 7):
                    if direction == "LEFT":
                        arr = Arrow(RIGHT * 4.0 + UP * y, LEFT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=color)
                    elif direction == "UP":
                        arr = Arrow(LEFT * y + DOWN * 3.0, LEFT * y + UP * 2.0, buff=0, stroke_width=2.5, color=color)
                    else:
                        arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=color)
                    arr.set_opacity(0.35)
                    field.add(arr)
                if lbl_text:
                    f_lbl = MathTex(lbl_text, color=color, font_size=32).next_to(field[0], RIGHT, buff=0.2)
                    field.add(f_lbl)
                mobj = field

            elif e_type in ["charge", "particle", "dot"]:
                pos = np.array(item.get("pos", [0, 0, 0]))
                radius = item.get("radius", 0.22)
                dot = Dot(pos, radius=radius, color=color)
                if lbl_text:
                    lbl = MathTex(lbl_text, font_size=20, color=WHITE).move_to(pos)
                    mobj = VGroup(dot, lbl)
                else:
                    mobj = dot

            elif e_type in ["vector", "arrow", "force"]:
                start = np.array(item.get("start", [0, 0, 0]))
                end = np.array(item.get("end", [1, 1, 0]))
                vec = Arrow(start, end, buff=0, stroke_width=3.5, color=color)
                if lbl_text:
                    v_lbl = MathTex(lbl_text, color=color, font_size=24).next_to(vec, UP * 0.5, buff=0.1)
                    mobj = VGroup(vec, v_lbl)
                else:
                    mobj = vec

            elif e_type in ["line", "rod", "segment"]:
                start = np.array(item.get("start", [0, 0, 0]))
                end = np.array(item.get("end", [1, 1, 0]))
                is_dashed = item.get("dashed", False)
                line = DashedLine(start, end, color=color, stroke_width=2.5) if is_dashed else Line(start, end, color=color, stroke_width=4)
                if lbl_text:
                    l_lbl = MathTex(lbl_text, color=color, font_size=22).next_to(line, RIGHT, buff=0.1)
                    mobj = VGroup(line, l_lbl)
                else:
                    mobj = line

            elif e_type in ["arc", "angle"]:
                center = np.array(item.get("center", [0, 0, 0]))
                radius = item.get("radius", 0.8)
                s_angle = item.get("start_angle", 0) * DEGREES
                angle = item.get("angle", 45) * DEGREES
                arc = Arc(radius=radius, start_angle=s_angle, angle=angle, arc_center=center, color=color)
                if lbl_text:
                    a_lbl = MathTex(lbl_text, color=color, font_size=22).next_to(arc, RIGHT, buff=0.1)
                    mobj = VGroup(arc, a_lbl)
                else:
                    mobj = arc

            elif e_type in ["graph", "function", "curve"]:
                expr = item.get("expression", "sin(x)")
                x_min, x_max = item.get("x_range", [0, 5])
                axes = Axes(x_range=[x_min, x_max, 1], y_range=[-2, 2, 1], x_length=6, y_length=3.0, axis_config={"color": GRAY}).move_to(DOWN * 1.0)
                graph = axes.plot(lambda x: safe_eval_math(expr, x), x_range=[x_min, x_max], color=color)
                mobj = VGroup(axes, graph)

            elif e_type in ["shape", "lens", "circle", "rectangle"]:
                kind = item.get("kind", "circle")
                pos = np.array(item.get("pos", [0, -1, 0]))
                if kind == "rectangle":
                    dims = item.get("dims", [2, 1])
                    mobj = Rectangle(width=dims[0], height=dims[1], color=color, fill_opacity=0.2).move_to(pos)
                elif kind == "lens":
                    mobj = Ellipse(width=0.6, height=2.8, color=color, fill_color=color, fill_opacity=0.3).move_to(pos)
                else:
                    mobj = Circle(radius=item.get("radius", 1.0), color=color, stroke_width=3).move_to(pos)

            if mobj:
                mobject_map[e_id] = mobj
                static_group.add(mobj)

            # Process animation instructions
            anim_action = item.get("animate", None)
            if anim_action == "rotate" and mobj:
                pivot = np.array(item.get("pivot", [0, -0.7, 0]))
                rot_angle = item.get("rotate_angle", 45) * DEGREES
                animations.append(Rotate(mobj, angle=rot_angle, about_point=pivot))

        self.play(FadeIn(static_group), run_time=1.2)

        for anim in animations:
            self.play(anim, run_time=1.5, rate_func=smooth)

        equations = self.get_equations()
        card = self.draw_math_card(equations, max_width)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    # -------------------------------------------------------------
    # ARCHETYPE PRESETS (1 TO 7)
    # -------------------------------------------------------------
    def build_pyq_scene(self, audio_duration, max_width):
        question_str = clean_str(os.environ.get("QUESTION_TEXT", "Sample Question"))
        opt_a = clean_str(os.environ.get("OPTION_A", "(A) Option 1"))
        opt_b = clean_str(os.environ.get("OPTION_B", "(B) Option 2"))
        opt_c = clean_str(os.environ.get("OPTION_C", "(C) Option 3"))
        opt_d = clean_str(os.environ.get("OPTION_D", "(D) Option 4"))
        correct_ans = clean_str(os.environ.get("CORRECT_ANSWER", "Correct Answer: (A)"))

        equations = self.get_equations()
        wrapped = []
        for line in question_str.replace(r'\n', '\n').split('\n'):
            wrapped.extend(textwrap.wrap(line, width=32) if len(line) > 32 else [line])

        question = Paragraph(*wrapped, alignment="center", font_size=24, color=WHITE, line_spacing=0.8)
        if question.width > max_width:
            question.scale_to_fit_width(max_width)

        opts = [opt_a, opt_b, opt_c, opt_d]
        max_opt_len = max((len(o) for o in opts if o), default=0)

        if max_opt_len <= 14 and all(opts):
            row1 = MathTex(format_latex_option(opt_a), r"\qquad", format_latex_option(opt_b), font_size=22)
            row2 = MathTex(format_latex_option(opt_c), r"\qquad", format_latex_option(opt_d), font_size=22)
            mcq_group = VGroup(row1, row2).arrange(DOWN, buff=0.25, aligned_edge=LEFT)
        else:
            opt_texs = [MathTex(format_latex_option(o), font_size=22) for o in opts if o]
            mcq_group = VGroup(*opt_texs).arrange(DOWN, buff=0.2, aligned_edge=LEFT) if opt_texs else VGroup()

        if mcq_group.width > max_width:
            mcq_group.scale_to_fit_width(max_width)

        card_content = VGroup(question, mcq_group).arrange(DOWN, buff=0.35)
        card_bg = RoundedRectangle(
            corner_radius=0.2, width=max_width + 0.2, height=card_content.height + 0.5,
            fill_color=COLOR_CARD_BG, fill_opacity=0.9, stroke_color=COLOR_BORDER, stroke_width=2
        ).move_to(UP * 1.5)

        eq_group = VGroup(*[MathTex(eq, font_size=28, color=COLOR_FIELD) for eq in equations if eq]).arrange(DOWN, buff=0.25).move_to(DOWN * 2.2)

        ans_text = MathTex(format_latex_option(correct_ans), font_size=26, color=COLOR_FORCE)
        ans_box = VGroup(
            RoundedRectangle(corner_radius=0.15, width=max(ans_text.width + 0.6, 4.8), height=ans_text.height + 0.4, fill_color=COLOR_CARD_BG, fill_opacity=0.95, stroke_color=COLOR_FORCE, stroke_width=2.5),
            ans_text
        ).move_to(DOWN * 5.6)

        step_pause = max(0.8, (audio_duration - 6.0) / 3.0)
        self.play(FadeIn(VGroup(card_bg, card_content), shift=UP * 0.3), run_time=1.0)
        self.wait(step_pause)

        if len(eq_group) > 0:
            self.play(Write(eq_group), run_time=1.2)
            self.wait(step_pause)

        self.play(FadeIn(ans_box, shift=UP * 0.2), Circumscribe(ans_box, color=COLOR_ACCENT, buff=0.1, run_time=1.0))

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_dipole_torque_scene(self, audio_duration, max_width):
        equations = self.get_equations() or [
            r"\vec{F}_{\text{net}} = \vec{0} \quad \text{(No Translation)}",
            r"\tau = (qE)(2a\sin\theta) = pE\sin\theta",
            r"\vec{\tau} = \vec{p} \times \vec{E} \quad \text{(Restoring Torque)}",
            r"T = 2\pi\sqrt{\frac{I}{pE}} \quad \text{(Angular SHM)}"
        ]

        field_lines = VGroup()
        for y in np.linspace(1.8, -3.2, 7):
            arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=COLOR_FIELD)
            arr.set_opacity(0.32)
            field_lines.add(arr)
        e_lbl = MathTex(r"\vec{E}", color=COLOR_FIELD, font_size=36).next_to(field_lines[0], RIGHT, buff=0.2)
        self.play(Create(field_lines), Write(e_lbl), run_time=1.0)

        center_pt = DOWN * 0.7
        angle = 42 * DEGREES
        a_len = 1.4

        pos_p = center_pt + np.array([a_len * np.cos(angle), a_len * np.sin(angle), 0])
        neg_p = center_pt - np.array([a_len * np.cos(angle), a_len * np.sin(angle), 0])

        rod = Line(neg_p, pos_p, color=GRAY_A, stroke_width=4)
        c_pos = VGroup(Dot(pos_p, radius=0.22, color=COLOR_POS), MathTex("+q", font_size=22, color=WHITE).move_to(pos_p))
        c_neg = VGroup(Dot(neg_p, radius=0.22, color=COLOR_NEG), MathTex("-q", font_size=22, color=WHITE).move_to(neg_p))
        p_arrow = Arrow(neg_p, pos_p, buff=0.25, color=COLOR_ACCENT, stroke_width=4)
        p_label = MathTex(r"\vec{p}", color=COLOR_ACCENT, font_size=32).next_to(p_arrow.get_center(), UP * 0.8, buff=0.1)

        ref_line = DashedLine(center_pt, center_pt + RIGHT * 2.2, color=GRAY_C, stroke_width=2)
        angle_arc = Arc(radius=0.9, start_angle=0, angle=angle, arc_center=center_pt, color=COLOR_ACCENT)
        theta_lbl = MathTex(r"\theta", color=COLOR_ACCENT, font_size=24).next_to(angle_arc, RIGHT, buff=0.15)

        self.play(FadeIn(VGroup(rod, c_pos, c_neg, p_arrow, p_label), shift=UP * 0.2), Create(ref_line), Create(angle_arc), Write(theta_lbl), run_time=1.2)

        f_pos = Arrow(pos_p, pos_p + RIGHT * 1.3, buff=0, color=COLOR_FORCE, stroke_width=4)
        f_neg = Arrow(neg_p, neg_p + LEFT * 1.3, buff=0, color=COLOR_FORCE, stroke_width=4)
        f_pos_lbl = MathTex(r"\vec{F}_+", color=COLOR_FORCE, font_size=22).next_to(f_pos, RIGHT, buff=0.1)
        f_neg_lbl = MathTex(r"\vec{F}_-", color=COLOR_FORCE, font_size=22).next_to(f_neg, LEFT, buff=0.1)

        self.play(Create(f_pos), Write(f_pos_lbl), Create(f_neg), Write(f_neg_lbl), run_time=0.8)

        perp_line = DashedLine(pos_p, np.array([pos_p[0], neg_p[1], 0]), color=COLOR_ACCENT, stroke_width=2.5)
        lever_lbl = MathTex(r"d_\perp = 2a\sin\theta", color=COLOR_ACCENT, font_size=20).next_to(perp_line, RIGHT, buff=0.1)
        self.play(Create(perp_line), Write(lever_lbl), run_time=0.8)

        all_interactive = VGroup(rod, c_pos, c_neg, p_arrow, p_label, f_pos, f_pos_lbl, f_neg, f_neg_lbl, perp_line, lever_lbl)

        self.play(Rotate(all_interactive, angle=-angle, about_point=center_pt), FadeOut(angle_arc), FadeOut(theta_lbl), run_time=1.8, rate_func=smooth)
        self.play(Rotate(all_interactive, angle=angle, about_point=center_pt), FadeIn(angle_arc), FadeIn(theta_lbl), run_time=1.0)

        card = self.draw_math_card(equations, max_width)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.2)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_projectile_scene(self, audio_duration, max_width):
        equations = self.get_equations() or [
            r"y = x \tan\theta - \frac{g x^2}{2 u^2 \cos^2\theta}",
            r"R = \frac{u^2 \sin 2\theta}{g}, \quad H_{\max} = \frac{u^2 \sin^2\theta}{2g}"
        ]

        axes = Axes(x_range=[0, 5, 1], y_range=[0, 3, 1], x_length=6, y_length=3.5, axis_config={"color": GRAY}).move_to(DOWN * 1.0)
        graph = axes.plot(lambda x: 2.5 * x - 0.6 * (x ** 2), x_range=[0, 4.16], color=COLOR_ACCENT)
        ball = Dot(color=COLOR_POS, radius=0.18)

        self.play(Create(axes), run_time=0.8)
        self.play(Create(graph), MoveAlongPath(ball, graph), run_time=2.5, rate_func=linear)

        card = self.draw_math_card(equations, max_width)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_lorentz_force_scene(self, audio_duration, max_width):
        equations = self.get_equations() or [
            r"\vec{F} = q(\vec{v} \times \vec{B})",
            r"r = \frac{mv}{qB}, \quad T = \frac{2\pi m}{qB}"
        ]

        field_group = VGroup()
        for y in np.linspace(1.5, -3.5, 6):
            arr = Arrow(LEFT * 3.8 + UP * y, RIGHT * 3.8 + UP * y, buff=0, stroke_width=2, color=COLOR_ACCENT)
            arr.set_opacity(0.35)
            field_group.add(arr)
        b_lbl = MathTex(r"\vec{B}", color=COLOR_ACCENT, font_size=34).next_to(field_group[0], RIGHT, buff=0.2)

        charge = Dot(LEFT * 2.5 + DOWN * 1.0, radius=0.25, color=COLOR_POS)
        v_arrow = Arrow(charge.get_center(), charge.get_center() + UP * 1.8, buff=0, color=COLOR_FORCE)

        self.play(Create(field_group), Write(b_lbl), FadeIn(charge), Create(v_arrow), run_time=1.0)
        arc = Arc(radius=2.0, start_angle=PI, angle=-PI/2, arc_center=LEFT * 0.5 + DOWN * 1.0, color=COLOR_POS)
        self.play(MoveAlongPath(charge, arc), run_time=2.0)

        card = self.draw_math_card(equations, max_width)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_wave_shm_scene(self, audio_duration, max_width):
        equations = self.get_equations() or [
            r"y(x,t) = A \sin(kx - \omega t + \phi)",
            r"v = \frac{\omega}{k} = f \lambda, \quad k = \frac{2\pi}{\lambda}"
        ]

        axes = Axes(x_range=[0, 6, 1], y_range=[-2, 2, 1], x_length=6.5, y_length=3.0, axis_config={"color": GRAY}).move_to(DOWN * 1.0)
        wave_graph = axes.plot(lambda x: 1.2 * np.sin(2 * x), x_range=[0, 6], color=COLOR_FIELD)

        self.play(Create(axes), run_time=0.8)
        self.play(Create(wave_graph), run_time=2.0)

        card = self.draw_math_card(equations, max_width)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_optics_scene(self, audio_duration, max_width):
        equations = self.get_equations() or [
            r"\frac{1}{f} = \frac{1}{v} - \frac{1}{u} \quad \text{(Lens Formula)}",
            r"P = \frac{1}{f} = (n-1)\left(\frac{1}{R_1} - \frac{1}{R_2}\right)"
        ]

        axis = Line(LEFT * 3.5, RIGHT * 3.5, color=GRAY_B).move_to(DOWN * 1.0)
        lens = Ellipse(width=0.6, height=3.0, color=COLOR_FIELD, fill_color=COLOR_FIELD, fill_opacity=0.3).move_to(DOWN * 1.0)

        ray_in = Line(LEFT * 3.5 + UP * 0.2, RIGHT * 0.0 + UP * 0.2, color=COLOR_ACCENT)
        ray_out = Line(RIGHT * 0.0 + UP * 0.2, RIGHT * 3.5 + DOWN * 2.2, color=COLOR_ACCENT)

        self.play(Create(axis), Create(lens), run_time=1.0)
        self.play(Create(ray_in), run_time=0.8)
        self.play(Create(ray_out), run_time=1.0)

        card = self.draw_math_card(equations, max_width)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_circuit_scene(self, audio_duration, max_width):
        equations = self.get_equations() or [
            r"q(t) = Q_0\left(1 - e^{-t/RC}\right)",
            r"I(t) = \frac{V_0}{R} e^{-t/RC}, \quad \tau = RC"
        ]

        axes = Axes(x_range=[0, 5, 1], y_range=[0, 2, 1], x_length=6.0, y_length=3.0, axis_config={"color": GRAY}).move_to(DOWN * 1.0)
        curve = axes.plot(lambda x: 1.8 * (1 - np.exp(-x)), x_range=[0, 5], color=COLOR_ACCENT)

        self.play(Create(axes), run_time=0.8)
        self.play(Create(curve), run_time=2.0)

        card = self.draw_math_card(equations, max_width)
        if len(card) > 0:
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_generic_vector_scene(self, audio_duration, max_width):
        equations = self.get_equations()
        v1 = Arrow(ORIGIN, RIGHT * 2 + UP * 1, buff=0, color=COLOR_FIELD).move_to(DOWN * 1.0)
        v2 = Arrow(ORIGIN, RIGHT * 1 + DOWN * 2, buff=0, color=COLOR_FORCE).move_to(DOWN * 1.0)
        self.play(Create(v1), Create(v2), run_time=1.5)

        if equations:
            card = self.draw_math_card(equations, max_width)
            if len(card) > 0:
                self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)
