"""
render_universal.py — Cinematic 9:16 physics-short engine with narrative
beat timeline and symbol ↔ visual binding layer.

Config MUST be set before importing manim_fx.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from typing import Any

import numpy as np
from manim import *

# ---------------- config BEFORE any fx import ------------------------------
config.pixel_width  = 1080
config.pixel_height = 1920
config.frame_width  = 9.0
config.frame_height = 16.0
config.frame_rate   = 30

# ---------------- fx layer --------------------------------------------------
from manim_fx import (
    PALETTE, resolve_color, RF_SOFT, RF_SNAP, RF_SPRING, RF_LINEAR,
    live_wait, idle_float, pulse_loop,
    pop_in, staggered_reveal, card_reveal, grow_in,
    glow_pulse, underline_brace, highlight_bound, color_code_terms,
    traced_graph, value_counter, morph_equations, color_code_equation,
    CameraDirector, wipe_transition,
)

# =================================================================== ZONES
ZONE_HEADER    = +6.90
ZONE_QUESTION  = +4.30
ZONE_VISUAL    = +0.30
ZONE_OPTIONS   = -2.80
ZONE_EQUATIONS = -5.10
ZONE_ANSWER    = -7.00

SAFE_MODE  = os.environ.get("SAFE_MODE", "1") not in ("0", "false", "False")
HINDI_FONT = os.environ.get("HINDI_FONT", "")

# =================================================================== UNICODE → LATEX
_UNICODE_TO_LATEX = {
    "°": r"^\circ ", "×": r"\times ", "÷": r"\div ", "→": r"\to ",
    "←": r"\leftarrow ", "∞": r"\infty ", "π": r"\pi ", "θ": r"\theta ",
    "α": r"\alpha ", "β": r"\beta ", "γ": r"\gamma ", "δ": r"\delta ",
    "Δ": r"\Delta ", "Σ": r"\Sigma ", "Ω": r"\Omega ", "λ": r"\lambda ",
    "μ": r"\mu ", "ν": r"\nu ", "ρ": r"\rho ", "σ": r"\sigma ",
    "τ": r"\tau ", "φ": r"\phi ", "ψ": r"\psi ", "ω": r"\omega ",
    "Φ": r"\Phi ", "Ψ": r"\Psi ", "ℏ": r"\hbar ", "≤": r"\le ",
    "≥": r"\ge ", "≠": r"\ne ", "≈": r"\approx ", "±": r"\pm ",
    "∈": r"\in ", "∑": r"\sum ", "∏": r"\prod ", "∫": r"\int ",
}


# =================================================================== HELPERS
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
    fallback = re.sub(r"\\[a-zA-Z]+", "", s_clean)
    fallback = fallback.replace("{", "").replace("}", "")
    try:
        return Text(fallback, font_size=font_size, color=color)
    except Exception:
        return Text("?", font_size=font_size, color=color)


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
            body = r"\text{" + label + " " + rest + r"}"
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


# =================================================================== SCENE
class UniversalPhysicsScene(MovingCameraScene):

    def construct(self):
        self.camera.background_color = PALETTE["bg"]
        self.MAX_WIDTH = 7.8
        self.director = CameraDirector(self)
        self._equation_mobs: list[Mobject] = []

        concept_type   = os.environ.get("CONCEPT_TYPE", "GENERIC").upper().strip()
        header_title   = clean_str(os.environ.get("HEADER_TITLE", "Physics Concept"))
        tagline        = clean_str(os.environ.get("TAGLINE", "3b1b Visual Intuition"))
        audio_duration = float(os.environ.get("AUDIO_DURATION", 20.0) or 20.0)
        visual_json    = os.environ.get("VISUAL_DATA_JSON", "")

        self.equations = self._read_equations()

        try:
            self.build_header(header_title, tagline)
        except Exception:
            if not SAFE_MODE:
                raise

        is_pyq     = concept_type in ("PYQ", "MCQ", "QUESTION")
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
            self._handle_error(exc, audio_duration)

        self._live_wait_remaining(audio_duration)

    # ---------------------------------------------------------------- recovery
    def _handle_error(self, exc: Exception, audio_duration: float):
        if not SAFE_MODE:
            raise exc
        try:
            err = Text(
                f"[render error]\n{type(exc).__name__}: {exc}",
                font_size=18, color=PALETTE["pos"],
            ).move_to(ORIGIN)
            self.add(err)
            rem = audio_duration - self.renderer.time
            if rem > 0.1:
                live_wait(self, rem, [err])
        except Exception:
            self.wait(max(0.5, audio_duration - self.renderer.time))

    def _live_wait_remaining(self, audio_duration: float) -> None:
        rem = audio_duration - self.renderer.time
        if rem > 0.1:
            try:
                live_wait(self, rem)
            except Exception:
                self.wait(rem)

    def _read_equations(self) -> list[str]:
        raw = os.environ.get("EQUATIONS_JSON", "")
        return [str(x) for x in parse_json_list(raw) if x]

    def _alloc(self, total: float, *ratios: float) -> list[float]:
        s = sum(ratios)
        if s <= 0:
            return [total / len(ratios)] * len(ratios)
        return [total * r / s for r in ratios]

    # ---------------------------------------------------------------- header
    def build_header(self, title_text: str, tagline_text: str) -> None:
        kw_t = dict(font_size=30, color=PALETTE["accent"])
        kw_s = dict(font_size=18, color=PALETTE["muted"])
        if HINDI_FONT:
            kw_t["font"] = HINDI_FONT
            kw_s["font"] = HINDI_FONT
        else:
            kw_t["weight"] = BOLD
            kw_s["slant"] = ITALIC

        try:
            title = Text(title_text, **kw_t)
        except Exception:
            title = Text(title_text[:30], font_size=28,
                         color=PALETTE["accent"])
        try:
            sub = Text(tagline_text, **kw_s)
        except Exception:
            sub = Text(tagline_text[:40], font_size=18,
                       color=PALETTE["muted"])

        rule = Line(LEFT, RIGHT, color=PALETTE["accent"],
                    stroke_width=2).set_width(3.2)
        header = VGroup(title, rule, sub).arrange(DOWN, buff=0.14).move_to([0, ZONE_HEADER, 0])
        if header.width > self.MAX_WIDTH:
            header.scale_to_fit_width(self.MAX_WIDTH)

        self.play(FadeIn(title, shift=DOWN * 0.15), run_time=0.5)
        self.play(GrowFromCenter(rule), run_time=0.4)
        self.play(FadeIn(sub, shift=UP * 0.1), run_time=0.4)
        self.header = header

    # ---------------------------------------------------------------- equation card
    def draw_math_card(self, equations: list[str],
                       y_center: float = ZONE_EQUATIONS) -> VGroup:
        if not equations:
            self._equation_mobs = []
            return VGroup()

        eq_mobs = [safe_mathtex(eq, font_size=28, color=PALETTE["white"])
                   for eq in equations if eq]
        if not eq_mobs:
            self._equation_mobs = []
            return VGroup()

        self._equation_mobs = eq_mobs

        eq_group = VGroup(*eq_mobs).arrange(DOWN, buff=0.24)
        if eq_group.width > self.MAX_WIDTH - 0.4:
            eq_group.scale_to_fit_width(self.MAX_WIDTH - 0.4)

        card_bg = RoundedRectangle(
            corner_radius=0.22,
            width=self.MAX_WIDTH,
            height=eq_group.height + 0.55,
            fill_color=PALETTE["card"], fill_opacity=0.96,
            stroke_color=PALETTE["border"], stroke_width=1.5,
        ).move_to([0, y_center, 0])
        eq_group.move_to(card_bg.get_center())
        return VGroup(card_bg, eq_group)

    # ================================================================ BEAT SYSTEM
    def _parse_bindings(self, bindings_raw: list) -> dict:
        """visual_id → [(eq_idx, term_idx), ...], skipping invalid refs."""
        out: dict[str, list[tuple[int, int]]] = {}
        for b in bindings_raw:
            if not isinstance(b, dict):
                continue
            vid = b.get("visual_id")
            if not vid:
                continue
            eq_idx = int(b.get("eq_idx", 0))
            if eq_idx < 0 or eq_idx >= len(self._equation_mobs):
                continue

            idx_list: list[int] = []
            if "term_idx" in b:
                raw = b["term_idx"]
                idx_list = [int(x) for x in (raw if isinstance(raw, list) else [raw])]
            elif "term" in b:
                try:
                    eq = self._equation_mobs[eq_idx]
                    needle = str(b["term"])
                    for i, sub in enumerate(eq[0]):
                        s = getattr(sub, "tex_string", "") or ""
                        if needle and needle in s:
                            idx_list.append(i)
                except Exception:
                    pass

            # validate term indices
            try:
                max_idx = len(self._equation_mobs[eq_idx][0]) - 1
            except Exception:
                max_idx = -1

            for ti in idx_list:
                if 0 <= ti <= max_idx:
                    out.setdefault(vid, []).append((eq_idx, ti))
        return out

    def _run_beat_timeline(self, beats: list, audio_duration: float,
                           ctx: dict) -> None:
        valid = [b for b in beats if isinstance(b, dict) and "t" in b]
        valid.sort(key=lambda b: float(b["t"]))

        # density warning
        for i in range(1, len(valid)):
            gap = float(valid[i]["t"]) - float(valid[i - 1]["t"])
            if gap < 0.3:
                print(f"[beats] warning: beats {i-1}→{i} spaced {gap:.2f}s apart")

        breathe = ctx.get("breathe_mobs", [])

        for beat in valid:
            t_target = float(beat.get("t", 0))
            gap = t_target - self.renderer.time
            if gap > 0.08:
                live_wait(self, gap, breathe)
            try:
                self._render_beat(beat, ctx)
            except Exception as e:
                if not SAFE_MODE:
                    raise
                print(f"[beat] skipped ({beat.get('type')}): {type(e).__name__}: {e}")

        remaining = audio_duration - self.renderer.time
        if remaining > 0.1:
            live_wait(self, remaining, breathe)

    def _render_beat(self, beat: dict, ctx: dict) -> None:
        kind = str(beat.get("type", "emphasis")).lower()
        focus_id = beat.get("focus")
        visuals = ctx.get("visuals_by_id", {})
        bindings = ctx.get("bindings", {})
        eq_card = ctx.get("eq_card", VGroup())
        eq_mobs = ctx.get("equations_by_idx", [])

        focus_mob = visuals.get(focus_id) if focus_id else None

        # ------------------------------------------------------- hook
        if kind == "hook":
            text = str(beat.get("content", "")).strip()
            if not text:
                return
            try:
                t_mob = Text(text, font_size=26, color=PALETTE["white"],
                             weight=BOLD)
            except Exception:
                t_mob = Text(text, font_size=26, color=PALETTE["white"])
            if t_mob.width > self.MAX_WIDTH - 0.4:
                t_mob.scale_to_fit_width(self.MAX_WIDTH - 0.4)
            t_mob.move_to([0, ZONE_QUESTION, 0])
            self.play(Write(t_mob), run_time=0.9)
            ctx["hook_mob"] = t_mob

        # ------------------------------------------------------- analogy
        elif kind == "analogy":
            if len(eq_card) > 0:
                self.play(eq_card.animate.set_opacity(0.35), run_time=0.5)
            if focus_mob is not None:
                self.play(focus_mob.animate.scale(1.10),
                          run_time=0.6, rate_func=RF_SOFT)
                self.play(focus_mob.animate.scale(1 / 1.10),
                          run_time=0.5, rate_func=RF_SOFT)

        # ------------------------------------------------------- experiment
        elif kind == "experiment":
            if focus_mob is not None:
                try:
                    self.play(Create(focus_mob), run_time=1.4)
                except Exception:
                    glow_pulse(self, focus_mob)

        # ------------------------------------------------------- law
        elif kind == "law":
            if len(eq_card) > 0:
                self.play(eq_card.animate.set_opacity(1.0), run_time=0.3)
                try:
                    color_code_terms(eq_mobs, bindings, visuals)
                except Exception:
                    pass
                card_reveal(self, eq_card, run_time=1.2)

        # ------------------------------------------------------- punchline
        elif kind == "punchline":
            target = focus_mob or (eq_card[1] if len(eq_card) > 0 else None)
            if target is not None:
                self.play(Circumscribe(target, color=PALETTE["accent"],
                                       buff=0.15, run_time=1.0))
            if len(eq_card) > 0:
                self.play(eq_card.animate.set_opacity(1.0), run_time=0.3)

        # ------------------------------------------------------- transition
        elif kind == "transition":
            wipe_transition(self, RIGHT)

        # ------------------------------------------------------- emphasis (default)
        else:
            if focus_id and focus_id in bindings and eq_mobs:
                for eq_idx, term_idx in bindings[focus_id]:
                    try:
                        sub = eq_mobs[eq_idx][0][term_idx]
                        highlight_bound(self, sub, focus_mob)
                    except Exception:
                        if focus_mob is not None:
                            glow_pulse(self, focus_mob)
            elif focus_mob is not None:
                glow_pulse(self, focus_mob)

    # ================================================================ PYQ
    def build_pyq_with_visual_scene(self, visual_json_str: str,
                                    audio_duration: float):
        question_str = clean_str(os.environ.get("QUESTION_TEXT", "Sample Question"))
        opt_a = clean_str(os.environ.get("OPTION_A", "(A) Option 1"))
        opt_b = clean_str(os.environ.get("OPTION_B", "(B) Option 2"))
        opt_c = clean_str(os.environ.get("OPTION_C", "(C) Option 3"))
        opt_d = clean_str(os.environ.get("OPTION_D", "(D) Option 4"))
        correct_ans = clean_str(os.environ.get("CORRECT_ANSWER", "Correct Answer: (A)"))

        wrapped = []
        for line in question_str.split("\n"):
            wrapped.extend(textwrap.wrap(line, width=44) if len(line) > 44 else [line])
        try:
            question = Paragraph(*wrapped, alignment="center", font_size=20,
                                 color=PALETTE["white"], line_spacing=0.75)
        except Exception:
            question = Text(question_str[:200], font_size=20,
                            color=PALETTE["white"])
        if question.width > self.MAX_WIDTH:
            question.scale_to_fit_width(self.MAX_WIDTH)
        question.move_to([0, ZONE_QUESTION + 0.6, 0])

        opts = [opt_a, opt_b, opt_c, opt_d]
        max_len = max((len(o) for o in opts if o), default=0)
        if max_len <= 16 and all(opts):
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

        ans_text = safe_mathtex(format_latex_option(correct_ans), 24,
                                color=PALETTE["force"])
        ans_box = VGroup(
            RoundedRectangle(corner_radius=0.15,
                             width=max(ans_text.width + 0.6, 5.0),
                             height=ans_text.height + 0.4,
                             fill_color=PALETTE["card"], fill_opacity=0.95,
                             stroke_color=PALETTE["force"], stroke_width=2.5),
            ans_text,
        ).move_to([0, ZONE_ANSWER, 0])

        eq_card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)
        visual_group, rotations, ids = self._build_visual_group_from(
            parse_json_list(visual_json_str), ZONE_VISUAL
        )

        beats_raw = parse_json_list(os.environ.get("BEATS_JSON", ""))
        bindings_raw = parse_json_list(os.environ.get("BINDINGS_JSON", ""))

        if beats_raw:
            ctx = {
                "visuals_by_id": ids,
                "bindings": self._parse_bindings(bindings_raw),
                "eq_card": eq_card,
                "equations_by_idx": self._equation_mobs,
                "breathe_mobs": [m for m in (visual_group, eq_card) if len(m) > 0],
            }
            self.play(FadeIn(question, shift=DOWN * 0.2), run_time=0.6)
            if len(visual_group) > 0:
                staggered_reveal(self, visual_group, run_time=1.0)
                for mob, angle, pivot in rotations:
                    piv = mob.get_center() if pivot is None else pivot
                    self.play(Rotate(mob, angle=angle, about_point=piv),
                              run_time=0.7)
            staggered_reveal(self, options_grid, run_time=0.9)
            pop_in(self, ans_box, run_time=0.5)
            self._run_beat_timeline(beats_raw, audio_duration, ctx)
            return

        # legacy sequential
        t_q, t_v, t_o, t_a = self._alloc(audio_duration, 0.18, 0.32, 0.22, 0.28)
        self.play(FadeIn(question, shift=DOWN * 0.2), run_time=0.7)
        live_wait(self, max(0.3, t_q - 0.7), [question])
        if len(visual_group) > 0:
            staggered_reveal(self, visual_group, run_time=1.1)
            self.director.zoom(1.12, run_time=0.9, center=np.array([0, ZONE_VISUAL, 0]))
            for mob, angle, pivot in rotations:
                piv = mob.get_center() if pivot is None else pivot
                self.play(Rotate(mob, angle=angle, about_point=piv), run_time=0.8)
            live_wait(self, max(0.3, t_v - 2.0), [visual_group])
            self.director.reset(run_time=0.7)
        staggered_reveal(self, options_grid, run_time=1.0)
        live_wait(self, max(0.3, t_o - 1.0), [options_grid])
        if len(eq_card) > 0:
            card_reveal(self, eq_card, run_time=1.2)
        pop_in(self, ans_box, run_time=0.6)
        self.play(Circumscribe(ans_box, color=PALETTE["accent"],
                               buff=0.12, run_time=1.0))
        live_wait(self, max(0.3, t_a - 1.6), [ans_box])

    def build_pyq_scene(self, audio_duration: float):
        self.build_pyq_with_visual_scene("[]", audio_duration)

    # ================================================================ DYNAMIC JSON
    def build_dynamic_json_scene(self, visual_json_str: str,
                                 audio_duration: float):
        elements = parse_json_list(visual_json_str)

        graph_elems = [e for e in elements if isinstance(e, dict) and
                       str(e.get("type", "")).lower() in
                       ("graph", "function", "curve", "wave_packet", "potential_well")]
        other_elems = [e for e in elements if e not in graph_elems]

        graph_group = VGroup()
        graph_ids: dict = {}
        if graph_elems:
            graph_group, _, graph_ids = self._build_visual_group_from(
                graph_elems, y_center=ZONE_VISUAL + 1.4
            )
            if len(graph_group) > 0:
                graph_group.scale(0.85)
                if graph_group.width > self.MAX_WIDTH:
                    graph_group.scale_to_fit_width(self.MAX_WIDTH)

        other_group, rotations, other_ids = self._build_visual_group_from(
            other_elems, y_center=ZONE_VISUAL - 1.8
        )

        ids = {**graph_ids, **other_ids}
        eq_card = self.draw_math_card(self.equations, y_center=ZONE_EQUATIONS)

        beats_raw = parse_json_list(os.environ.get("BEATS_JSON", ""))
        bindings_raw = parse_json_list(os.environ.get("BINDINGS_JSON", ""))

        if beats_raw:
            if len(graph_group) > 0:
                staggered_reveal(self, graph_group, run_time=1.3)
            if len(other_group) > 0:
                staggered_reveal(self, other_group, run_time=1.2)
                for mob, angle, pivot in rotations:
                    piv = mob.get_center() if pivot is None else pivot
                    self.play(Rotate(mob, angle=angle, about_point=piv),
                              run_time=0.8)

            breathe = [g for g in (graph_group, other_group, eq_card) if len(g) > 0]
            ctx = {
                "visuals_by_id": ids,
                "bindings": self._parse_bindings(bindings_raw),
                "eq_card": eq_card,
                "equations_by_idx": self._equation_mobs,
                "breathe_mobs": breathe,
            }
            self._run_beat_timeline(beats_raw, audio_duration, ctx)
            return

        # legacy branch
        if len(graph_group) > 0:
            staggered_reveal(self, graph_group, run_time=1.4)
            live_wait(self, 0.6, [graph_group])
        if len(other_group) > 0:
            staggered_reveal(self, other_group, run_time=1.2)
            for mob, angle, pivot in rotations:
                piv = mob.get_center() if pivot is None else pivot
                self.play(Rotate(mob, angle=angle, about_point=piv), run_time=0.8)
            live_wait(self, 0.8, [other_group])
        if len(eq_card) > 0:
            card_reveal(self, eq_card, run_time=1.2)
        remaining = audio_duration - self.renderer.time
        if remaining > 0.5:
            focus = [m for m in (graph_group, other_group) if len(m) > 0]
            live_wait(self, remaining, focus[0] if focus else None)

    # ================================================================ PHYSICS SCENES
    def build_dipole_torque_scene(self, audio_duration: float):
        equations = self.equations or [r"\vec{F}_{\text{net}} = \vec{0}",
                                       r"\tau = pE\sin\theta",
                                       r"\vec{\tau} = \vec{p}\times\vec{E}"]
        field_lines = VGroup()
        for y in np.linspace(1.8, -3.2, 7):
            field_lines.add(Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y,
                                  buff=0, stroke_width=2.5,
                                  color=PALETTE["field"]).set_opacity(0.32))
        field_lines.add(safe_mathtex(r"\vec{E}", 36, PALETTE["field"])
                        .next_to(field_lines[0], RIGHT, buff=0.2))
        field_lines.move_to([0, ZONE_VISUAL + 0.5, 0])
        self.play(LaggedStart(*[Create(a) for a in field_lines[:-1]], lag_ratio=0.08),
                  run_time=1.2)
        self.play(FadeIn(field_lines[-1]), run_time=0.3)

        center_pt = np.array([0, ZONE_VISUAL - 1.4, 0])
        a_len = 1.4
        rod = Line(center_pt - RIGHT * a_len, center_pt + RIGHT * a_len,
                   color=PALETTE["muted"], stroke_width=4)
        c_pos = VGroup(Dot(center_pt + RIGHT * a_len, radius=0.22, color=PALETTE["pos"]),
                       safe_mathtex("+q", 20, WHITE).move_to(center_pt + RIGHT * a_len))
        c_neg = VGroup(Dot(center_pt - RIGHT * a_len, radius=0.22, color=PALETTE["neg"]),
                       safe_mathtex("-q", 20, WHITE).move_to(center_pt - RIGHT * a_len))
        dipole = VGroup(rod, c_pos, c_neg)
        p_arrow = Arrow(center_pt - RIGHT * a_len * 0.6, center_pt + RIGHT * a_len * 0.6,
                        buff=0.2, color=PALETTE["accent"], stroke_width=4)
        p_lbl = safe_mathtex(r"\vec{p}", 30, PALETTE["accent"]).next_to(p_arrow.get_center(), UP, buff=0.1)
        self.play(FadeIn(dipole, shift=UP * 0.2), run_time=0.8)
        self.play(Create(p_arrow), FadeIn(p_lbl), run_time=0.6)

        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.2)

        remaining = audio_duration - self.renderer.time
        if remaining > 1.5:
            swing = 35 * DEGREES
            half = remaining * 0.45
            self.play(Rotate(dipole, angle=swing, about_point=center_pt),
                      Rotate(p_arrow, angle=swing, about_point=center_pt),
                      Rotate(p_lbl, angle=swing, about_point=center_pt),
                      run_time=half, rate_func=RF_SOFT)
            self.play(Rotate(dipole, angle=-swing, about_point=center_pt),
                      Rotate(p_arrow, angle=-swing, about_point=center_pt),
                      Rotate(p_lbl, angle=-swing, about_point=center_pt),
                      run_time=remaining - half, rate_func=RF_SOFT)
        self._live_wait_remaining(audio_duration)

    def build_projectile_scene(self, audio_duration: float):
        equations = self.equations or [r"y = x\tan\theta - \frac{g x^2}{2u^2\cos^2\theta}",
                                       r"R = \frac{u^2\sin 2\theta}{g}"]
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 3, 1], x_length=6, y_length=3.5,
                    axis_config={"color": PALETTE["muted"]}).move_to([0, ZONE_VISUAL - 0.4, 0])
        fn = lambda x: 2.5 * x - 0.6 * x ** 2
        _, dot, _ = traced_graph(self, axes, fn, [0, 4.16],
                                 color=PALETTE["accent"], duration=2.4,
                                 dot_color=PALETTE["pos"])
        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        remaining = audio_duration - self.renderer.time
        if remaining > 0.4:
            pulse_loop(self, dot, cycles=max(1, int(remaining / 0.6)),
                       scale=1.35, cycle_time=0.6)
        self._live_wait_remaining(audio_duration)

    def build_lorentz_force_scene(self, audio_duration: float):
        equations = self.equations or [r"\vec{F} = q(\vec{v}\times\vec{B})",
                                       r"r = \frac{mv}{qB}"]
        field_group = VGroup()
        for y in np.linspace(1.5, -3.5, 6):
            field_group.add(Arrow(LEFT * 3.8 + UP * y, RIGHT * 3.8 + UP * y,
                                  buff=0, stroke_width=2,
                                  color=PALETTE["accent"]).set_opacity(0.35))
        field_group.add(safe_mathtex(r"\vec{B}", 34, PALETTE["accent"])
                        .next_to(field_group[0], RIGHT, buff=0.2))
        field_group.move_to([0, ZONE_VISUAL + 0.4, 0])
        self.play(LaggedStart(*[Create(a) for a in field_group[:-1]], lag_ratio=0.06),
                  FadeIn(field_group[-1]), run_time=1.0)
        center = np.array([0, ZONE_VISUAL - 0.8, 0])
        radius = 1.5
        circle = Circle(radius=radius, color=PALETTE["pos"],
                        stroke_width=2, stroke_opacity=0.4).move_to(center)
        charge = Dot(center + RIGHT * radius, radius=0.22, color=PALETTE["pos"])
        v_arrow = Arrow(charge.get_center(), charge.get_center() + UP * 1.0,
                        buff=0, color=PALETTE["force"])
        self.play(Create(circle), FadeIn(charge), GrowArrow(v_arrow), run_time=0.8)
        orbit_dur = min(audio_duration - self.renderer.time - 1.5, 6.0)
        if orbit_dur > 0.8:
            self.play(MoveAlongPath(charge, circle),
                      run_time=orbit_dur, rate_func=RF_LINEAR)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        self._live_wait_remaining(audio_duration)

    def build_wave_shm_scene(self, audio_duration: float):
        equations = self.equations or [r"y(x,t) = A\sin(kx - \omega t + \phi)",
                                       r"v = f\lambda,\quad k = \frac{2\pi}{\lambda}"]
        axes = Axes(x_range=[0, 6, 1], y_range=[-2, 2, 1], x_length=6.5, y_length=2.8,
                    axis_config={"color": PALETTE["muted"]}).move_to([0, ZONE_VISUAL - 0.4, 0])
        self.play(Create(axes), run_time=0.5)
        phase = ValueTracker(0.0)
        wave = always_redraw(lambda: axes.plot(
            lambda x: 1.2 * np.sin(2 * x - phase.get_value()),
            x_range=[0, 6], color=PALETTE["field"], stroke_width=4))
        self.add(wave, phase)
        dur = min(max(audio_duration - self.renderer.time - 2.0, 1.5), 5.0)
        self.play(phase.animate.set_value(TAU * 2),
                  run_time=dur, rate_func=RF_LINEAR)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        remaining = audio_duration - self.renderer.time
        if remaining > 0.3:
            self.play(phase.animate.set_value(TAU * 2 + remaining * 3),
                      run_time=remaining, rate_func=RF_LINEAR)
        phase.clear_updaters()

    def build_optics_scene(self, audio_duration: float):
        equations = self.equations or [r"\frac{1}{f} = \frac{1}{v} - \frac{1}{u}",
                                       r"P = (n-1)\!\left(\frac{1}{R_1} - \frac{1}{R_2}\right)"]
        base = np.array([0, ZONE_VISUAL - 0.8, 0])
        axis = Line(LEFT * 3.5, RIGHT * 3.5, color=PALETTE["muted"]).move_to(base)
        lens = Ellipse(width=0.6, height=3.0, color=PALETTE["field"],
                       fill_color=PALETTE["field"], fill_opacity=0.3).move_to(base)
        self.play(Create(axis), FadeIn(lens), run_time=0.7)
        ray_in = Line(LEFT * 3.5 + UP * 0.2 + base, UP * 0.2 + base,
                      color=PALETTE["accent"], stroke_width=3)
        ray_out = Line(UP * 0.2 + base, RIGHT * 3.5 + DOWN * 1.2 + base,
                       color=PALETTE["accent"], stroke_width=3)
        self.play(Create(ray_in), run_time=0.5)
        self.play(Create(ray_out), run_time=0.5)
        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        remaining = audio_duration - self.renderer.time
        if remaining > 0.6:
            self.play(lens.animate.set_fill(PALETTE["accent"], opacity=0.35),
                      run_time=remaining * 0.4, rate_func=RF_SOFT)
            self.play(lens.animate.set_fill(PALETTE["field"], opacity=0.3),
                      run_time=remaining * 0.6, rate_func=RF_SOFT)
        self._live_wait_remaining(audio_duration)

    def build_circuit_scene(self, audio_duration: float):
        equations = self.equations or [r"q(t) = Q_0\!\left(1 - e^{-t/RC}\right)",
                                       r"\tau = RC"]
        axes = Axes(x_range=[0, 5, 1], y_range=[0, 2, 1], x_length=6.0, y_length=3.0,
                    axis_config={"color": PALETTE["muted"]}).move_to([0, ZONE_VISUAL - 0.4, 0])
        fn = lambda x: 1.8 * (1 - np.exp(-x))
        _, dot, _ = traced_graph(self, axes, fn, [0, 5],
                                 color=PALETTE["accent"], duration=2.2,
                                 dot_color=PALETTE["pos"])
        card = self.draw_math_card(equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        remaining = audio_duration - self.renderer.time
        if remaining > 0.4:
            pulse_loop(self, dot, cycles=max(1, int(remaining / 0.6)),
                       scale=1.35, cycle_time=0.6)
        self._live_wait_remaining(audio_duration)

    def build_generic_vector_scene(self, audio_duration: float):
        base = np.array([0, ZONE_VISUAL, 0])
        v1 = Arrow(ORIGIN, RIGHT * 2 + UP * 1, buff=0,
                   color=PALETTE["field"]).move_to(base)
        v2 = Arrow(ORIGIN, RIGHT * 1 + DOWN * 2, buff=0,
                   color=PALETTE["force"]).move_to(base)
        self.play(GrowArrow(v1), run_time=0.6)
        self.play(GrowArrow(v2), run_time=0.6)
        card = self.draw_math_card(self.equations)
        if len(card) > 0:
            card_reveal(self, card, run_time=1.0)
        self._live_wait_remaining(audio_duration)

    # ================================================================ JSON BUILDERS
    def _build_visual_group_from(self, elements: list,
                                 y_center: float = ZONE_VISUAL
                                 ) -> tuple[VGroup, list[tuple], dict]:
        pending_rotations = []
        group = VGroup()
        ids: dict = {}

        for idx, item in enumerate(elements):
            if not isinstance(item, dict):
                continue
            mob = self._build_json_element(item, idx)
            if mob is None:
                continue
            group.add(mob)
            # consistent ids: use explicit `id` or auto `elem_{idx}` keyed by
            # position in the original `elements` list, not filtered counter
            explicit = item.get("id")
            key = str(explicit) if explicit else f"elem_{idx}"
            ids[key] = mob

            anim = item.get("animate")
            if anim == "rotate":
                angle = float(item.get("rotate_angle", 45)) * DEGREES
                pivot = to_3d_point(item.get("pivot")) if item.get("pivot") is not None else None
                pending_rotations.append((mob, angle, pivot))
            elif anim == "swing":
                angle = float(item.get("swing_angle", 25)) * DEGREES
                pivot = to_3d_point(item.get("pivot", [0, 1.8, 0]))
                pending_rotations.append((mob, angle, pivot))

        if len(group) > 0:
            group.move_to([0, y_center, 0])
            if group.width > self.MAX_WIDTH:
                group.scale_to_fit_width(self.MAX_WIDTH)
        return group, pending_rotations, ids

    def _build_visual_group(self, visual_json_str: str):
        return self._build_visual_group_from(
            parse_json_list(visual_json_str), ZONE_VISUAL
        )

    def _build_json_element(self, item: dict, idx: int) -> Mobject | None:
        e_type = str(item.get("type", "")).lower()
        color = resolve_color(item)
        lbl_text = item.get("label", "")

        mob: Mobject | None = None

        try:
            # -------------------------------------------------- field / vector_field
            if e_type in ("field", "vector_field"):
                direction = str(item.get("direction", "RIGHT")).upper()
                rows = int(item.get("rows", 7))
                field = VGroup()
                if direction in ("UP", "DOWN"):
                    for x in np.linspace(-3.5, 3.5, rows):
                        if direction == "UP":
                            arr = Arrow(RIGHT * x + DOWN * 2.0, RIGHT * x + UP * 2.0,
                                        buff=0, stroke_width=2.5, color=color)
                        else:
                            arr = Arrow(RIGHT * x + UP * 2.0, RIGHT * x + DOWN * 2.0,
                                        buff=0, stroke_width=2.5, color=color)
                        arr.set_opacity(float(item.get("opacity", 0.35)))
                        field.add(arr)
                else:
                    for y in np.linspace(1.8, -3.2, rows):
                        if direction == "RIGHT":
                            arr = Arrow(LEFT * 4.0 + UP * y, RIGHT * 4.0 + UP * y,
                                        buff=0, stroke_width=2.5, color=color)
                        else:
                            arr = Arrow(RIGHT * 4.0 + UP * y, LEFT * 4.0 + UP * y,
                                        buff=0, stroke_width=2.5, color=color)
                        arr.set_opacity(float(item.get("opacity", 0.35)))
                        field.add(arr)
                if lbl_text:
                    field.add(safe_mathtex(lbl_text, 32, color=color)
                              .next_to(field[0], RIGHT, buff=0.2))
                mob = field

            # -------------------------------------------------- charge / particle / dot
            elif e_type in ("charge", "particle", "dot"):
                pos = to_3d_point(item.get("pos", [0, 0, 0]))
                radius = float(item.get("radius", 0.22))
                dot = Dot(pos, radius=radius, color=color)
                mob = (VGroup(dot, safe_mathtex(lbl_text, 20, WHITE).move_to(pos))
                       if lbl_text else dot)

            # -------------------------------------------------- vector / arrow / force
            elif e_type in ("vector", "arrow", "force"):
                start = to_3d_point(item.get("start", [0, 0, 0]))
                end = to_3d_point(item.get("end", [1, 1, 0]))
                vec = Arrow(start, end, buff=0, stroke_width=3.5, color=color)
                if lbl_text:
                    v_lbl = safe_mathtex(lbl_text, 24, color=color).next_to(vec, UP, buff=0.1)
                    mob = VGroup(vec, v_lbl)
                else:
                    mob = vec

            # -------------------------------------------------- line / rod / segment
            elif e_type in ("line", "rod", "segment"):
                start = to_3d_point(item.get("start", [0, 0, 0]))
                end = to_3d_point(item.get("end", [1, 1, 0]))
                dashed = bool(item.get("dashed", False))
                line = (DashedLine(start, end, color=color, stroke_width=2.5)
                        if dashed else Line(start, end, color=color, stroke_width=4))
                if lbl_text:
                    line = VGroup(line, safe_mathtex(lbl_text, 22, color=color)
                                  .next_to(line, RIGHT, buff=0.1))
                mob = line

            # -------------------------------------------------- arc
            elif e_type in ("arc", "angle", "angle_arc"):
                center = to_3d_point(item.get("center", [0, 0, 0]))
                radius = float(item.get("radius", 0.8))
                s_angle = float(item.get("start_angle", 0)) * DEGREES
                angle = float(item.get("angle", 45)) * DEGREES
                arc = Arc(radius=radius, start_angle=s_angle, angle=angle,
                          arc_center=center, color=color)
                if lbl_text:
                    arc = VGroup(arc, safe_mathtex(lbl_text, 22, color=color)
                                 .next_to(arc, RIGHT, buff=0.1))
                mob = arc

            # -------------------------------------------------- graph / function / curve
            elif e_type in ("graph", "function", "curve"):
                expr = item.get("expression", "sin(x)")
                x_range = item.get("x_range", [0, 5])
                y_range = item.get("y_range", [-2, 2])
                axes = Axes(
                    x_range=[x_range[0], x_range[1], 1],
                    y_range=[y_range[0], y_range[1], 1],
                    x_length=float(item.get("x_length", 5.5)),
                    y_length=float(item.get("y_length", 2.5)),
                    axis_config={"color": PALETTE["muted"]},
                )
                graph = axes.plot(lambda x: safe_eval_math(expr, x),
                                  x_range=[x_range[0], x_range[1]],
                                  color=color, stroke_width=4)
                mob = VGroup(axes, graph)

            # ============ NEW: pendulum ============
            elif e_type == "pendulum":
                pivot = to_3d_point(item.get("pivot", [0, 1.8, 0]))
                length = float(item.get("length", 2.0))
                angle = float(item.get("angle", 30)) * DEGREES
                bob_r = float(item.get("bob_radius", 0.20))
                bob_pos = pivot + length * np.array([np.sin(angle), -np.cos(angle), 0])
                rod = Line(pivot, bob_pos, color=PALETTE["muted"], stroke_width=3)
                bob = Dot(bob_pos, radius=bob_r, color=color)
                pivot_dot = Dot(pivot, radius=0.06, color=PALETTE["white"])
                grp = VGroup(rod, pivot_dot, bob)
                if lbl_text:
                    grp.add(safe_mathtex(lbl_text, 20, color=color)
                            .next_to(bob, RIGHT, buff=0.15))
                mob = grp

            # ============ NEW: wave_packet ============
            elif e_type in ("wave_packet", "packet"):
                xr = item.get("x_range", [-4, 4])
                yr = item.get("y_range", [-1.5, 1.5])
                center = float(item.get("center", 0.0))
                width = float(item.get("width", 1.2))
                k = float(item.get("k", 4.0))
                axes = Axes(
                    x_range=[xr[0], xr[1], 1], y_range=[yr[0], yr[1], 1],
                    x_length=float(item.get("x_length", 6.0)),
                    y_length=float(item.get("y_length", 2.4)),
                    axis_config={"color": PALETTE["muted"]},
                )

                def packet(x, c=center, w=width, kk=k):
                    return np.exp(-((x - c) / w) ** 2) * np.sin(kk * x)

                curve = axes.plot(packet, x_range=[xr[0], xr[1]],
                                  color=color, stroke_width=4)
                mob = VGroup(axes, curve)

            # ============ NEW: potential_well ============
            elif e_type in ("potential_well", "well"):
                xr = item.get("x_range", [-4, 4])
                depth = float(item.get("depth", 2.0))
                width = float(item.get("width", 2.5))
                axes = Axes(
                    x_range=[xr[0], xr[1], 1],
                    y_range=[-depth * 1.4, 1.0, 1],
                    x_length=float(item.get("x_length", 6.0)),
                    y_length=float(item.get("y_length", 2.6)),
                    axis_config={"color": PALETTE["muted"]},
                )

                def well(x, d=depth, w=width):
                    return -d * np.exp(-(x / w) ** 2)

                curve = axes.plot(well, x_range=[xr[0], xr[1]],
                                  color=color, stroke_width=4)
                extras = VGroup()
                for lv in item.get("levels", []) or []:
                    try:
                        y = float(lv)
                        if not (-depth < y < 0.0):
                            continue
                        arg = -depth / y
                        if arg <= 0:
                            continue
                        x_half = float(width * np.sqrt(max(0.0, np.log(arg))))
                        x_half = float(np.clip(x_half, 0.4, 2.2))
                        line = DashedLine(axes.c2p(-x_half, y), axes.c2p(x_half, y),
                                          color=PALETTE["accent"], stroke_width=2)
                        extras.add(line)
                    except Exception:
                        continue
                mob = VGroup(axes, curve, extras)

            # -------------------------------------------------- shapes
            elif e_type in ("shape", "lens", "circle", "rectangle",
                            "ellipse", "polygon"):
                kind = str(item.get("kind", e_type if e_type != "shape" else "circle")).lower()
                pos = to_3d_point(item.get("pos", [0, -1, 0]))
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
                                  color=color,
                                  fill_opacity=float(item.get("fill_opacity", 0.2))).move_to(pos)
                elif kind == "polygon":
                    pts = [to_3d_point(p) for p in item.get("points", [])]
                    if len(pts) >= 3:
                        mob = Polygon(*pts, color=color,
                                      fill_opacity=float(item.get("fill_opacity", 0.2)))
                else:
                    mob = Circle(radius=float(item.get("radius", 1.0)),
                                 color=color, stroke_width=3).move_to(pos)

            # -------------------------------------------------- text
            elif e_type == "text":
                txt = str(item.get("text", lbl_text))
                pos = to_3d_point(item.get("pos", [0, 0, 0]))
                if item.get("use_latex", False) or "$" in txt or "\\" in txt:
                    mob = safe_mathtex(txt, font_size=int(item.get("font_size", 22)),
                                       color=color).move_to(pos)
                else:
                    mob = Text(txt, font_size=int(item.get("font_size", 22)),
                               color=color).move_to(pos)

            # -------------------------------------------------- group
            elif e_type == "group":
                sub = VGroup()
                for j, subitem in enumerate(item.get("children", [])):
                    sm = self._build_json_element(subitem, j)
                    if sm is not None:
                        sub.add(sm)
                mob = sub

        except Exception:
            if not SAFE_MODE:
                raise
            return None

        if mob is None:
            return None

        # attach semantic color metadata BEFORE transformations
        _attach_semantic(mob, color)

        try:
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
        except Exception:
            pass

        return mob
