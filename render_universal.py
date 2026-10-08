import os
import json
import numpy as np
from manim import *

# -------------------------------------------------------------
# 9:16 VERTICAL ASPECT RATIO FOR SHORTS (1080x1920)
# -------------------------------------------------------------
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0

# Theme Palette (3b1b Dark Style)
COLOR_BG = "#0E0E10"
COLOR_FIELD = "#2980B9"
COLOR_POS = "#E74C3C"
COLOR_NEG = "#3498DB"
COLOR_ACCENT = "#F1C40F"
COLOR_FORCE = "#2ECC71"
COLOR_CARD_BG = "#18181C"

class UniversalPhysicsScene(Scene):
    def construct(self):
        self.camera.background_color = COLOR_BG
        MAX_WIDTH = 7.8

        # Read Inputs from Environment Variables
        concept_type = os.environ.get("CONCEPT_TYPE", "DIPOLE_TORQUE").upper()
        header_title = os.environ.get("HEADER_TITLE", "Physics Concept")
        tagline = os.environ.get("TAGLINE", "Visual Intuition")
        audio_duration = float(os.environ.get("AUDIO_DURATION", 20.0))
        
        # Raw JSON payload for equations or parameters
        raw_eqs = os.environ.get("EQUATIONS_JSON", '["\\vec{F}_{net} = 0", "\\vec{\\tau} = \\vec{p} \\times \\vec{E}"]')
        try:
            equations = json.loads(raw_eqs)
        except Exception:
            equations = [r"\text{Formula 1}", r"\text{Formula 2}"]

        # 1. Render Universal Top Header
        title = Text(header_title, font_size=30, weight=BOLD, color=COLOR_ACCENT)
        sub = Text(tagline, font_size=18, slant=ITALIC, color=GRAY_B)
        header = VGroup(title, sub).arrange(DOWN, buff=0.1).to_edge(UP, buff=0.5)
        if header.width > MAX_WIDTH:
            header.scale_to_fit_width(MAX_WIDTH)
        self.add(header)

        # 2. Dispatch Visual Builder based on Concept Type
        if concept_type == "DIPOLE_TORQUE":
            self.build_dipole_torque_scene(equations, audio_duration, MAX_WIDTH)
        elif concept_type == "PROJECTILE_MOTION":
            self.build_projectile_scene(equations, audio_duration, MAX_WIDTH)
        elif concept_type == "LORENTZ_FORCE":
            self.build_lorentz_force_scene(equations, audio_duration, MAX_WIDTH)
        else:
            self.build_generic_vector_scene(equations, audio_duration, MAX_WIDTH)

    # -------------------------------------------------------------
    # REUSABLE GEOMETRIC BUILDERS
    # -------------------------------------------------------------
    def draw_uniform_field(self, direction=RIGHT, label=r"\vec{E}", color=COLOR_FIELD):
        """Builds a set of parallel vector field lines across the viewport."""
        field = VGroup()
        for y in np.linspace(1.5, -3.5, 6):
            start_pt = LEFT * 3.8 + UP * y
            end_pt = RIGHT * 3.8 + UP * y
            arrow = Arrow(start_pt, end_pt, buff=0, stroke_width=2, color=color)
            arrow.set_opacity(0.35)
            field.add(arrow)
        field_lbl = MathTex(label, color=color, font_size=34).next_to(field[0], RIGHT, buff=0.2)
        return VGroup(field, field_lbl)

    def draw_math_card(self, equations, max_width):
        """Generates a floating LaTeX derivation card at the bottom of the frame."""
        eq_group = VGroup(*[MathTex(eq, font_size=30, color=WHITE) for eq in equations]).arrange(DOWN, buff=0.3)
        if eq_group.width > max_width - 0.4:
            eq_group.scale_to_fit_width(max_width - 0.4)

        card_bg = RoundedRectangle(
            corner_radius=0.2,
            width=max_width,
            height=eq_group.height + 0.6,
            fill_color=COLOR_CARD_BG,
            fill_opacity=0.92,
            stroke_color="#333333",
            stroke_width=2
        ).move_to(DOWN * 5.2)

        eq_group.move_to(card_bg.get_center())
        return VGroup(card_bg, eq_group)

    # -------------------------------------------------------------
    # SPECIFIC CONCEPT ANIMATION TEMPLATES
    # -------------------------------------------------------------
    def build_dipole_torque_scene(self, equations, audio_duration, max_width):
        # Step 1: Field Setup
        field_group = self.draw_uniform_field(direction=RIGHT, label=r"\vec{E}")
        self.play(Create(field_group), run_time=1.0)

        # Step 2: Dipole Construction
        center = DOWN * 1.0
        angle = 35 * DEGREES
        a = 1.5

        pos_p = center + np.array([a * np.cos(angle), a * np.sin(angle), 0])
        neg_p = center - np.array([a * np.cos(angle), a * np.sin(angle), 0])

        rod = Line(neg_p, pos_p, color=GRAY_A, stroke_width=4)
        c_pos = VGroup(Dot(pos_p, radius=0.2, color=COLOR_POS), MathTex("+q", font_size=20).move_to(pos_p))
        c_neg = VGroup(Dot(neg_p, radius=0.2, color=COLOR_NEG), MathTex("-q", font_size=20).move_to(neg_p))
        p_vec = Arrow(neg_p, pos_p, buff=0.2, color=COLOR_ACCENT, stroke_width=3)
        
        dipole = VGroup(rod, c_pos, c_neg, p_vec)
        self.play(FadeIn(dipole), run_time=1.0)

        # Step 3: Forces & Rotation
        f_pos = Arrow(pos_p, pos_p + RIGHT * 1.2, buff=0, color=COLOR_FORCE)
        f_neg = Arrow(neg_p, neg_p + LEFT * 1.2, buff=0, color=COLOR_FORCE)
        forces = VGroup(f_pos, f_neg)

        self.play(Create(forces), run_time=0.8)
        self.play(Rotate(VGroup(dipole, forces), angle=-angle, about_point=center), run_time=1.8, rate_func=smooth)
        self.play(Rotate(VGroup(dipole, forces), angle=angle, about_point=center), run_time=1.0)

        # Step 4: Math Card
        card = self.draw_math_card(equations, max_width)
        self.play(FadeIn(card[0]), Write(card[1]), run_time=1.2)
        
        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_projectile_scene(self, equations, audio_duration, max_width):
        # 2D Axes setup for Trajectory
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 3, 1], x_length=6, y_length=3.5, axis_config={"color": GRAY}).move_to(DOWN * 1.0)
        graph = axes.plot(lambda x: 2.5 * x - 0.6 * (x ** 2), x_range=[0, 4.16], color=COLOR_ACCENT)
        ball = Dot(color=COLOR_POS, radius=0.18)

        self.play(Create(axes), run_time=0.8)
        self.play(Create(graph), MoveAlongPath(ball, graph), run_time=2.5, rate_func=linear)

        card = self.draw_math_card(equations, max_width)
        self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_lorentz_force_scene(self, equations, audio_duration, max_width):
        field_group = self.draw_uniform_field(direction=RIGHT, label=r"\vec{B}", color=COLOR_ACCENT)
        charge = Dot(LEFT * 2.5 + DOWN * 1.0, radius=0.25, color=COLOR_POS)
        v_arrow = Arrow(charge.get_center(), charge.get_center() + UP * 1.8, buff=0, color=COLOR_FORCE)
        
        self.play(Create(field_group), FadeIn(charge), Create(v_arrow), run_time=1.0)
        
        # Circular Deflection Path
        arc = Arc(radius=2.0, start_angle=PI, angle=-PI/2, arc_center=LEFT * 0.5 + DOWN * 1.0, color=COLOR_POS)
        self.play(MoveAlongPath(charge, arc), run_time=2.0)

        card = self.draw_math_card(equations, max_width)
        self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)

    def build_generic_vector_scene(self, equations, audio_duration, max_width):
        v1 = Arrow(ORIGIN, RIGHT * 2 + UP * 1, buff=0, color=COLOR_FIELD).move_to(DOWN * 1.0)
        v2 = Arrow(ORIGIN, RIGHT * 1 + DOWN * 2, buff=0, color=COLOR_FORCE).move_to(DOWN * 1.0)
        
        self.play(Create(v1), Create(v2), run_time=1.5)
        card = self.draw_math_card(equations, max_width)
        self.play(FadeIn(card[0]), Write(card[1]), run_time=1.0)

        rem = audio_duration - self.renderer.time
        if rem > 0:
            self.wait(rem)
