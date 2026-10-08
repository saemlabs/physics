import os
import re
import textwrap
from manim import *

# Vertical 9:16 aspect ratio setup for YouTube Shorts (1080x1920)
config.pixel_width = 1080
config.pixel_height = 1920
config.frame_width = 9.0
config.frame_height = 16.0


def clean_str(text: str) -> str:
    """Strips quotes and extra spaces from environment variables."""
    if not text:
        return ""
    return text.strip('"\'').strip()


def format_latex_option(opt_text: str) -> str:
    """Wraps plain text in LaTeX formatting safely."""
    opt_text = clean_str(opt_text)
    if not opt_text:
        return ""
    if not re.search(r'[\$\\_^{}]', opt_text):
        return r"\text{" + opt_text + r"}"
    return opt_text


class JEEShort(Scene):
    def construct(self):
        # Color Palette
        COLOR_BG = "#121212"
        COLOR_CARD_BG = "#1E1E1E"
        COLOR_GOLD = "#F1C40F"
        COLOR_BLUE = "#3498DB"
        COLOR_GREEN = "#2ECC71"
        COLOR_BORDER = "#333333"

        self.camera.background_color = COLOR_BG
        MAX_WIDTH = 7.8

        # 1. Environment Inputs
        header_text = clean_str(os.environ.get("HEADER_TITLE", "Physics Problem"))
        tagline_text = clean_str(os.environ.get("TAGLINE", "Concept Revision"))
        question_str = clean_str(os.environ.get("QUESTION_TEXT", "Sample Question"))

        opt_a = clean_str(os.environ.get("OPTION_A", "(A) Option 1"))
        opt_b = clean_str(os.environ.get("OPTION_B", "(B) Option 2"))
        opt_c = clean_str(os.environ.get("OPTION_C", "(C) Option 3"))
        opt_d = clean_str(os.environ.get("OPTION_D", "(D) Option 4"))

        eq1_str = clean_str(os.environ.get("EQUATION_1", ""))
        eq2_str = clean_str(os.environ.get("EQUATION_2", ""))
        correct_ans = clean_str(os.environ.get("CORRECT_ANSWER", "Correct Answer"))

        total_audio_time = float(os.environ.get("AUDIO_DURATION", 20.0))

        # 2. Header Zone
        title = Text(header_text, color=COLOR_GOLD, font_size=32, weight=BOLD)
        if title.width > MAX_WIDTH:
            title.scale_to_fit_width(MAX_WIDTH)
        title.to_edge(UP, buff=0.5)

        tagline = Text(tagline_text, color=GRAY_B, font_size=20, slant=ITALIC)
        if tagline.width > MAX_WIDTH:
            tagline.scale_to_fit_width(MAX_WIDTH)
        tagline.next_to(title, DOWN, buff=0.12)

        self.add(VGroup(title, tagline))

        # 3. Question Card & Options
        wrapped_lines = []
        for line in question_str.replace(r'\n', '\n').split('\n'):
            wrapped_lines.extend(textwrap.wrap(line, width=32) if len(line) > 32 else [line])

        question = Paragraph(*wrapped_lines, alignment="center", font_size=26, color=WHITE, line_spacing=0.8)
        if question.width > MAX_WIDTH:
            question.scale_to_fit_width(MAX_WIDTH)

        opts = [opt_a, opt_b, opt_c, opt_d]
        max_opt_len = max(len(o) for o in opts)

        if max_opt_len <= 14:
            row1 = MathTex(format_latex_option(opt_a), r"\qquad", format_latex_option(opt_b), font_size=26)
            row2 = MathTex(format_latex_option(opt_c), r"\qquad", format_latex_option(opt_d), font_size=26)
            mcq_group = VGroup(row1, row2).arrange(DOWN, buff=0.3, aligned_edge=LEFT)
        else:
            mcq_group = VGroup(
                MathTex(format_latex_option(opt_a), font_size=24),
                MathTex(format_latex_option(opt_b), font_size=24),
                MathTex(format_latex_option(opt_c), font_size=24),
                MathTex(format_latex_option(opt_d), font_size=24)
            ).arrange(DOWN, buff=0.25, aligned_edge=LEFT)

        if mcq_group.width > MAX_WIDTH:
            mcq_group.scale_to_fit_width(MAX_WIDTH)

        card_content = VGroup(question, mcq_group).arrange(DOWN, buff=0.45)
        card_bg = RoundedRectangle(
            corner_radius=0.2,
            width=MAX_WIDTH + 0.4,
            height=card_content.height + 0.6,
            fill_color=COLOR_CARD_BG,
            fill_opacity=0.85,
            stroke_color=COLOR_BORDER,
            stroke_width=2
        )
        question_card = VGroup(card_bg, card_content).move_to(UP * 1.8)

        # 4. Math Equations
        equations_group = VGroup()
        if eq1_str:
            e1 = MathTex(eq1_str, font_size=36, color=COLOR_BLUE)
            if e1.width > MAX_WIDTH:
                e1.scale_to_fit_width(MAX_WIDTH)
            equations_group.add(e1)

        if eq2_str:
            e2 = MathTex(eq2_str, font_size=38, color=COLOR_GOLD)
            if e2.width > MAX_WIDTH:
                e2.scale_to_fit_width(MAX_WIDTH)
            equations_group.add(e2)

        if len(equations_group) > 0:
            equations_group.arrange(DOWN, buff=0.35).move_to(DOWN * 2.2)

        # 5. Answer Card
        ans_text = MathTex(format_latex_option(correct_ans), font_size=30, color=COLOR_GREEN)
        if ans_text.width > MAX_WIDTH - 0.4:
            ans_text.scale_to_fit_width(MAX_WIDTH - 0.4)

        ans_border = RoundedRectangle(
            corner_radius=0.15,
            width=max(ans_text.width + 0.6, 5.0),
            height=ans_text.height + 0.4,
            fill_color=COLOR_CARD_BG,
            fill_opacity=0.9,
            stroke_color=COLOR_GREEN,
            stroke_width=2.5
        )
        ans_box = VGroup(ans_border, ans_text).move_to(DOWN * 5.8)

        # 6. Synchronized Animations
        step_pause = max(0.8, (total_audio_time - 8.0) / 4.0)

        self.play(FadeIn(question_card, shift=UP * 0.3), run_time=1.2)
        self.wait(step_pause)

        if len(equations_group) == 1:
            self.play(Write(equations_group[0]), run_time=1.2)
            self.wait(step_pause)
        elif len(equations_group) == 2:
            self.play(Write(equations_group[0]), run_time=1.0)
            self.wait(step_pause * 0.5)
            self.play(TransformMatchingTex(equations_group[0].copy(), equations_group[1]), run_time=1.0)
            self.wait(step_pause)

        self.play(FadeIn(ans_box, shift=UP * 0.2), run_time=1.0)
        self.play(Circumscribe(ans_box, color=COLOR_GOLD, buff=0.1, run_time=1.2))

        remaining = total_audio_time - self.renderer.time
        if remaining > 0:
            self.wait(remaining)
