import os
import json
import re
import textwrap
import numpy as np
from manim import *

# -------------------------------------------------------------
# 9:16 VERTICAL ASPECT RATIO FOR SHORTS (1080x1920)
# -------------------------------------------------------------
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0

COLOR_BG = "#0B0C10"
COLOR_E_ARROW = "#3498DB"
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


def format_latex(opt_text: str) -> str:
    opt_text = clean_str(opt_text)
    if not opt_text:
        return ""
    if not re.search(r'[\$\\_^{}]', opt_text):
        return r"\text{" + opt_text + r"}"
    return opt_text


class UniversalPhysicsScene(Scene):
    def construct(self):
        self.camera.background_color = COLOR_BG
        MAX_WIDTH = 7.8

        concept_type = os.environ.get("CONCEPT_TYPE", "GENERIC").upper().strip()
        header_title = os.environ.get("HEADER_TITLE", "Physics Concept")
        tagline = os.environ.get("TAGLINE", "JEE Revision")
        audio_duration = float(os.environ.get("AUDIO_DURATION", 20.0))

        # Top Header
        title = Text(header_title, font_size=28, weight=BOLD, color=COLOR_ACCENT)
        sub = Text(tagline, font_size=18, slant=ITALIC, color=GRAY_B)
        header = VGroup(title, sub).arrange(DOWN, buff=0.1).to_edge(UP, buff=0.5)
        if header.width > MAX_WIDTH:
            header.scale_to_fit_width(MAX_WIDTH)
        self.add(header)

        # Automatic Visual Dispatcher
        if concept_type in ["PYQ", "MCQ"]:
            self.build_pyq_card_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["DIPOLE_TORQUE", "DIPOLE"]:
            self.build_dipole_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["PROJECTILE", "KINEMATICS"]:
            self.build_projectile_scene(audio_duration, MAX_WIDTH)
        elif concept_type in ["LORENTZ", "CIRCULAR_MOTION", "SHM"]:
            self.build_circular_shm_scene(audio_duration, MAX_WIDTH)
        else:
            self.build_generic_vector_scene(audio_duration, MAX_WIDTH)

    # -------------------------------------------------------------
    # COMMON MATH CARD BUILDER
    # -------------------------------------------------------------
    def draw_math_card(self, equations, max_width):
        eq_group = VGroup(*[MathTex(eq, font_size=26, color=WHITE) for eq in equations]).arrange(DOWN, buff=0.25)
        if eq_group.width > max_width - 0.4:
            eq_group.scale_to_fit_width(max_width - 0.4)

        card_bg = RoundedRectangle(
            corner_radius=0.2, width=max_width, height=eq_group.height + 0.5,
            fill_color=COLOR_CARD_BG, fill_opacity=0.94, stroke_color=COLOR_BORDER, stroke_width=2
        ).move_to(DOWN * 5.4)

        eq_group.move_to(card_bg.get_center())
        return VGroup(card_bg, eq_group)

    # -------------------------------------------------------------
    # TEMPLATE 1: ELECTRIC / MAGNETIC DIPOLE TORQUE
    # -------------------------------------------------------------
    def build_dipole_scene(self, audio_duration, max_width):
        raw_eqs = os.environ.get("EQUATIONS_JSON", '["\\vec{F}_{net} = 0", "\\vec{\\tau} = \\vec{p} \\times \\vec{E}"]')
        try:
            equations = json.loads(raw_eqs)
        except Exception:
            equations = []

        # Field Lines
        field_lines = VGroup()
        for y in np.linspace(1.8, -3.2, 7):
            arrow = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y, buff=0, stroke_width=2.5, color=COLOR_E_ARROW)
            arrow.set_opacity(0.32)
            field_lines.add(arrow)
        e_lbl = MathTex(r"\vec{E}", color=COLOR_E_ARROW, font_size=36).next_to(field_lines[0], RIGHT, buff=0.2)
        self.play(Create(field_lines), Write(e_lbl), run_time=1.0)

        center_pt = DOWN * 0.7
        angle_deg = 42
        angle = angle_deg * DEGREES
        a_len = 1.4

        pos_p = center_pt + np.array([a_len * np.cos(angle), a_len * np.sin(angle), 0])
        neg_p = center_pt - np.array([a_len * np.cos(angle), a_len * np.sin(angle), 0])

        rod = Line(neg_p, pos_p, color=GRAY_A, stroke_width=4)
        dot_pos = Dot(pos_p, radius=0.22, color=COLOR_POS)
        lbl_pos = MathTex("+q", font_size=22, color=WHITE).move_to(pos_p)
        dot_neg = Dot(neg_p, radius=0.22, color=COLOR_NEG)
        lbl_neg = MathTex("-q", font_size=22, color=WHITE).move_to(neg_p)

        p_arrow = Arrow(neg_p, pos_p, buff=0.25, color=COLOR_ACCENT, stroke_width=4)
        p_label = MathTex(r"\vec{p}", color=COLOR_ACCENT, font_size=32).next_to(p_arrow.get_center(), UP * 0.8, buff=0.1)

        dipole_group = VGroup(rod, dot_pos, lbl_pos, dot_neg, lbl_neg, p_arrow, p_label)

        f_pos = Arrow(pos_p, pos_p + RIGHT * 1.3, buff=0, color=COLOR_FORCE, stroke_width=4)
        f_neg = Arrow(neg_p, neg_p + LEFT * 1.3, buff=0, color=COLOR_FORCE, stroke_width=4)
        forces_group = VGroup(f_pos, f_neg)

        perp_line = DashedLine(pos_p, np.array([pos_p[0], neg_p[1], 0]), color=COLOR_ACCENT, stroke_width=2.5)
        lever_lbl = MathTex(r"2a\sin\theta", color=COLOR_ACCENT, font_size=22).next_to(perp_line, RIGHT, buff=0.1)

        self.play(FadeIn(dipole_group), Create(forces_group), run_time=1.0)
        self.play(Create(perp_line), Write(lever_lbl), run_time=0.8)

        all_interactive = VGroup(rod, dot_pos, lbl_pos, dot_neg, lbl_neg, p_arrow, p_label, f_pos, f_neg, perp_line, lever_lbl)
        self.play(Rotate(all_interactive, angle=-angle, about_point=center_pt), run_time=1.8, rate_func=smooth)
        self.play(Rotate(all_interactive, angle=angle, about_point=center_pt), run_time=1.0)

        if equations:
            card = self.draw_math_card(equations, max_width)
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    # -------------------------------------------------------------
    # TEMPLATE 2: PROJECTILE / PARABOLIC TRAJECTORY
    # -------------------------------------------------------------
    def build_projectile_scene(self, audio_duration, max_width):
        raw_eqs = os.environ.get("EQUATIONS_JSON", '[]')
        try:
            equations = json.loads(raw_eqs)
        except Exception:
            equations = []

        axes = Axes(x_range=[0, 5, 1], y_range=[0, 3, 1], x_length=6, y_length=3.5, axis_config={"color": GRAY}).move_to(DOWN * 1.0)
        graph = axes.plot(lambda x: 2.5 * x - 0.6 * (x ** 2), x_range=[0, 4.16], color=COLOR_ACCENT)
        ball = Dot(color=COLOR_POS, radius=0.18)

        self.play(Create(axes), run_time=0.8)
        self.play(Create(graph), MoveAlongPath(ball, graph), run_time=2.5, rate_func=linear)

        if equations:
            card = self.draw_math_card(equations, max_width)
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    # -------------------------------------------------------------
    # TEMPLATE 3: CIRCULAR DEFLECTION / LORENTZ / SHM
    # -------------------------------------------------------------
    def build_circular_shm_scene(self, audio_duration, max_width):
        raw_eqs = os.environ.get("EQUATIONS_JSON", '[]')
        try:
            equations = json.loads(raw_eqs)
        except Exception:
            equations = []

        charge = Dot(LEFT * 2.5 + DOWN * 1.0, radius=0.25, color=COLOR_POS)
        v_arrow = Arrow(charge.get_center(), charge.get_center() + UP * 1.8, buff=0, color=COLOR_FORCE)
        arc = Arc(radius=2.0, start_angle=PI, angle=-PI/2, arc_center=LEFT * 0.5 + DOWN * 1.0, color=COLOR_POS)

        self.play(FadeIn(charge), Create(v_arrow), run_time=1.0)
        self.play(MoveAlongPath(charge, arc), run_time=2.0)

        if equations:
            card = self.draw_math_card(equations, max_width)
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    # -------------------------------------------------------------
    # TEMPLATE 4: MCQ / PYQ CARD SLIDE
    # -------------------------------------------------------------
    def build_pyq_card_scene(self, audio_duration, max_width):
        question_str = os.environ.get("QUESTION_TEXT", "")
        opt_a = os.environ.get("OPTION_A", "")
        opt_b = os.environ.get("OPTION_B", "")
        opt_c = os.environ.get("OPTION_C", "")
        opt_d = os.environ.get("OPTION_D", "")
        correct_ans = os.environ.get("CORRECT_ANSWER", "")

        raw_eqs = os.environ.get("EQUATIONS_JSON", '[]')
        try:
            equations = json.loads(raw_eqs)
        except Exception:
            equations = []

        wrapped_lines = []
        for line in question_str.replace(r'\n', '\n').split('\n'):
            wrapped_lines.extend(textwrap.wrap(line, width=32) if len(line) > 32 else [line])

        question = Paragraph(*wrapped_lines, alignment="center", font_size=24, color=WHITE, line_spacing=0.8)
        if question.width > max_width:
            question.scale_to_fit_width(max_width)

        opts = [opt_a, opt_b, opt_c, opt_d]
        mcq_group = VGroup(
            MathTex(format_latex(opt_a), font_size=22),
            MathTex(format_latex(opt_b), font_size=22),
            MathTex(format_latex(opt_c), font_size=22),
            MathTex(format_latex(opt_d), font_size=22)
        ).arrange(DOWN, buff=0.2, aligned_edge=LEFT)

        card_content = VGroup(question, mcq_group).arrange(DOWN, buff=0.35)
        card_bg = RoundedRectangle(
            corner_radius=0.2, width=max_width + 0.2, height=card_content.height + 0.5,
            fill_color=COLOR_CARD_BG, fill_opacity=0.9, stroke_color=COLOR_BORDER, stroke_width=2
        ).move_to(UP * 1.5)

        eq_group = VGroup(*[MathTex(eq, font_size=30, color=COLOR_E_ARROW) for eq in equations]).arrange(DOWN, buff=0.3).move_to(DOWN * 2.2)

        ans_text = MathTex(format_latex(correct_ans), font_size=28, color=COLOR_FORCE)
        ans_border = RoundedRectangle(
            corner_radius=0.15, width=max(ans_text.width + 0.6, 4.8), height=ans_text.height + 0.4,
            fill_color=COLOR_CARD_BG, fill_opacity=0.95, stroke_color=COLOR_FORCE, stroke_width=2.5
        ).move_to(DOWN * 5.6)
        ans_box = VGroup(ans_border, ans_text)

        self.play(FadeIn(VGroup(card_bg, card_content)), run_time=1.0)
        if equations:
            self.play(Write(eq_group), run_time=1.2)
        self.play(FadeIn(ans_box), Circumscribe(ans_box, color=COLOR_ACCENT, run_time=1.0))

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    # -------------------------------------------------------------
    # TEMPLATE 5: GENERIC CONCEPT & VECTOR DERIVATION
    # -------------------------------------------------------------
    def build_generic_vector_scene(self, audio_duration, max_width):
        raw_eqs = os.environ.get("EQUATIONS_JSON", '[]')
        try:
            equations = json.loads(raw_eqs)
        except Exception:
            equations = []

        v1 = Arrow(ORIGIN, RIGHT * 2 + UP * 1, buff=0, color=COLOR_E_ARROW).move_to(DOWN * 1.0)
        v2 = Arrow(ORIGIN, RIGHT * 1 + DOWN * 2, buff=0, color=COLOR_FORCE).move_to(DOWN * 1.0)
        self.play(Create(v1), Create(v2), run_time=1.5)

        if equations:
            card = self.draw_math_card(equations, max_width)
            self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)
