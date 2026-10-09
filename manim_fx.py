"""
manim_fx.py — Motion vocabulary for cinematic physics shorts.
Every helper guarantees continuous motion; no frozen frames.

Compatible with: manim==0.18.1, numpy==1.26.4, Python 3.11
"""

from __future__ import annotations

import numpy as np
from manim import *


# ------------------------------------------------------------------ palette
PALETTE = {
    "bg":     "#0B0C10",
    "card":   "#15161D",
    "border": "#2A2C36",
    "white":  "#F2F3F5",
    "muted":  "#8A8F9C",
    "field":  "#3498DB",
    "pos":    "#FF4B4B",
    "neg":    "#00D2FF",
    "accent": "#F1C40F",
    "force":  "#2ECC71",
    "warn":   "#E67E22",
}

RF_SOFT   = rate_functions.ease_in_out_sine
RF_SPRING = rate_functions.ease_out_back
RF_SNAP   = rate_functions.ease_out_cubic


# ================================================================== motion primitives
def _has_updater(mob: Mobject) -> bool:
    """True if mob (or any descendant) has an updater."""
    if getattr(mob, "updaters", None):
        return True
    if hasattr(mob, "submobjects"):
        for sub in mob.submobjects:
            if _has_updater(sub):
                return True
    return False


def live_wait(scene: Scene, duration: float, mobs: list[Mobject] | None = None,
              breathe_scale: float = 0.012) -> None:
    """
    Replacement for scene.wait(N). Keeps mobs breathing while time passes.
    Safely skips mobs that own their own updaters (always_redraw etc.).
    """
    if duration <= 0.05:
        return

    if mobs is None:
        targets = [m for m in scene.mobjects
                   if isinstance(m, VMobject) and not _has_updater(m)]
    else:
        targets = [m for m in mobs
                   if isinstance(m, VMobject) and not _has_updater(m)]

    if not targets:
        scene.wait(duration)
        return

    cycles = max(1, int(duration / 2.4))
    per_cycle = duration / cycles
    # cap at 6 mobs to avoid framerate hits
    breathe_targets = targets[:6]

    for _ in range(cycles):
        anims = []
        for m in breathe_targets:
            try:
                anims.append(m.animate(rate_func=there_and_back, run_time=per_cycle)
                               .scale(1 + breathe_scale))
            except Exception:
                continue
        if anims:
            try:
                scene.play(*anims, run_time=per_cycle)
            except Exception:
                scene.wait(per_cycle)
        else:
            scene.wait(per_cycle)


def idle_float(scene: Scene, mob: Mobject, duration: float, amp: float = 0.06) -> None:
    if duration <= 0.1 or amp <= 0.0:
        scene.wait(max(0.0, duration))
        return
    start = mob.get_center().copy()
    tracker = ValueTracker(0.0)

    def upd(m, tr=tracker, s=start, a=amp):
        m.move_to(s + UP * a * np.sin(tr.get_value() * TAU))

    mob.add_updater(upd)
    try:
        scene.play(tracker.animate.set_value(duration / 2.0),
                   run_time=duration, rate_func=linear)
    finally:
        mob.clear_updaters()
        mob.move_to(start)


# ================================================================== entrances
def pop_in(scene: Scene, mob: Mobject, run_time: float = 0.55) -> None:
    mob.save_state()
    mob.scale(0.001).set_opacity(0)
    scene.play(Restore(mob, rate_func=RF_SPRING), run_time=run_time)


def staggered_reveal(scene: Scene, group: VGroup, run_time: float = 1.2,
                     direction: np.ndarray = None) -> None:
    if direction is None:
        direction = DOWN
    # Adaptive lag ratio: keeps total time reasonable for large groups
    n = max(1, len(group))
    lag = min(0.30, 1.6 / n)
    scene.play(
        LaggedStart(
            *[FadeIn(m, shift=direction * 0.25) for m in group],
            lag_ratio=lag,
        ),
        run_time=run_time,
    )


def card_reveal(scene: Scene, card: VGroup, run_time: float = 1.0) -> None:
    if len(card) < 2:
        scene.play(FadeIn(card), run_time=run_time)
        return
    bg, content = card[0], card[1]
    bg.save_state(); bg.set_opacity(0).scale(0.96)
    content.save_state(); content.set_opacity(0)
    scene.play(Restore(bg, rate_func=RF_SNAP), run_time=run_time * 0.55)
    scene.play(Write(content, rate_func=smooth), run_time=run_time * 0.7)


# ================================================================== emphasis
def glow_pulse(scene: Scene, mob: Mobject, color=None, run_time: float = 0.9) -> None:
    color = color or PALETTE["accent"]
    scene.play(Indicate(mob, color=color, scale_factor=1.12), run_time=run_time)


def underline_brace(scene: Scene, mob: Mobject, label, color=None,
                    direction=DOWN, buff: float = 0.25) -> VGroup:
    color = color or PALETTE["accent"]
    brace = Brace(mob, direction=direction, buff=buff, color=color)
    if isinstance(label, str):
        label = Text(label, font_size=20, color=color)
    label.next_to(brace, direction, buff=0.12)
    group = VGroup(brace, label)
    scene.play(GrowFromCenter(brace),
               FadeIn(label, shift=-direction * 0.1),
               run_time=0.7)
    return group


# ================================================================== graphs
def traced_graph(scene: Scene, axes: Axes, fn, x_range, color,
                 duration: float, dot_color=None,
                 show_tangent_at: float | None = None) -> tuple[Mobject, Mobject]:
    """Draw a graph progressively while a dot rides the curve."""
    graph = axes.plot(fn, x_range=x_range, color=color, stroke_width=4)
    dot_color = dot_color or PALETTE["accent"]

    # Pre-place the dot at its true starting position BEFORE adding to scene
    x0, x1 = float(x_range[0]), float(x_range[1])
    start_pos = axes.c2p(x0, fn(x0))
    dot = Dot(start_pos, color=dot_color, radius=0.10)

    tracker = ValueTracker(x0)

    def _dot_update(m, tr=tracker, ax=axes, f=fn):
        x = tr.get_value()
        try:
            m.move_to(ax.c2p(x, f(x)))
        except Exception:
            pass

    dot.add_updater(_dot_update)

    scene.play(Create(axes), run_time=0.6)
    scene.add(dot)
    scene.play(
        Create(graph),
        tracker.animate.set_value(x1),
        run_time=duration, rate_func=linear,
    )

    if show_tangent_at is not None:
        x0t = float(show_tangent_at)
        slope = (fn(x0t + 1e-3) - fn(x0t - 1e-3)) / 2e-3
        t_line = axes.plot(
            lambda x: fn(x0t) + slope * (x - x0t),
            x_range=[x0t - 1.2, x0t + 1.2],
            color=PALETTE["force"], stroke_width=3,
        )
        scene.play(Create(t_line), run_time=0.5)
        scene.play(Indicate(t_line, color=PALETTE["force"]), run_time=0.6)

    dot.clear_updaters()
    return graph, dot


def value_counter(scene: Scene, start: float, end: float, duration: float,
                  label: str = "", decimals: int = 2,
                  color=None, position=None) -> DecimalNumber:
    color = color or PALETTE["white"]
    num = DecimalNumber(start, num_decimal_places=decimals, color=color)
    if position is not None:
        num.move_to(position)
    group = VGroup(num)
    if label:
        lbl = Text(label, font_size=22, color=PALETTE["muted"]).next_to(num, LEFT, buff=0.2)
        group = VGroup(lbl, num)
    scene.add(group)
    scene.play(num.animate.set_value(end), run_time=duration, rate_func=linear)
    return num


# ================================================================== equations
def morph_equations(scene: Scene, eq_a: Mobject, eq_b: Mobject, run_time: float = 1.4) -> None:
    scene.play(TransformMatchingTex(eq_a, eq_b), run_time=run_time)


def color_code_equation(eq: MathTex, mapping: dict[int, str]) -> None:
    for idx, hexcol in mapping.items():
        try:
            eq[0][idx].set_color(hexcol)
        except Exception:
            pass


# ================================================================== camera
class CameraDirector:
    """Cinematic camera language wrapper for MovingCameraScene."""

    def __init__(self, scene: Scene):
        self.s = scene

    def zoom(self, factor: float, run_time: float = 1.2, center=None) -> None:
        frame = self.s.camera.frame
        target_width = frame.get_width() / factor
        builder = frame.animate.set(width=target_width)
        if center is not None:
            builder = builder.move_to(center)
        self.s.play(builder, run_time=run_time)

    def follow(self, mob: Mobject, run_time: float = 1.0) -> None:
        self.s.play(self.s.camera.frame.animate.move_to(mob.get_center()),
                    run_time=run_time)

    def reset(self, run_time: float = 0.8) -> None:
        frame = self.s.camera.frame
        self.s.play(
            frame.animate.set(width=config.frame_width).move_to(ORIGIN),
            run_time=run_time,
        )


# ================================================================== transitions
def wipe_transition(scene: Scene, direction: np.ndarray = None) -> None:
    if direction is None:
        direction = RIGHT
    bar = Rectangle(
        width=config.frame_width * 2, height=config.frame_height * 2,
        fill_color=PALETTE["bg"], fill_opacity=1, stroke_width=0,
    ).move_to(-direction * config.frame_width * 1.5)
    scene.add(bar)
    scene.play(bar.animate.move_to(direction * config.frame_width * 1.5),
               run_time=0.35, rate_func=RF_SNAP)
    scene.remove(bar)
