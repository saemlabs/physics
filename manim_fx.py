"""
manim_fx.py — Motion vocabulary for cinematic physics shorts.
Every helper guarantees *continuous* motion; no frozen frames.
"""

from __future__ import annotations

import numpy as np
from manim import *

# ------------------------------------------------------------------ palette
PALETTE = {
    "bg":      "#0B0C10",
    "card":    "#15161D",
    "border":  "#2A2C36",
    "white":   "#F2F3F5",
    "muted":   "#8A8F9C",
    "field":   "#3498DB",
    "pos":     "#FF4B4B",
    "neg":     "#00D2FF",
    "accent":  "#F1C40F",
    "force":   "#2ECC71",
    "warn":    "#E67E22",
}

# rate functions
RF_SOFT   = rate_functions.ease_in_out_sine
RF_SPRING = rate_functions.ease_out_back
RF_SNAP   = rate_functions.ease_out_cubic


# ================================================================== motion primitives
def breathe(mob: Mobject, scale: float = 0.015, period: float = 2.4) -> Animation:
    """Endless, subtle scale pulse. Chain with .become or use in a loop."""
    return mob.animate(rate_func=there_and_back, run_time=period).scale(1 + scale)


def live_wait(scene: Scene, duration: float, mobs: list[Mobject] | None = None,
              breathe_scale: float = 0.012):
    """
    Replace scene.wait(N). Keeps `mobs` breathing while time passes.
    If mobs is None, uses everything currently in the scene.
    """
    if duration <= 0.05:
        return
    targets = mobs if mobs is not None else [m for m in scene.mobjects if isinstance(m, VMobject)]
    if not targets:
        scene.wait(duration); return

    cycles = max(1, int(duration / 2.4))
    per_cycle = duration / cycles
    # Parallel breathing on all targets, one cycle at a time
    for _ in range(cycles):
        anims = [breathe(m, breathe_scale, per_cycle) for m in targets[:8]]  # cap for perf
        if anims:
            scene.play(*anims, run_time=per_cycle)


def idle_float(scene: Scene, mob: Mobject, duration: float, amp: float = 0.06):
    """Slow vertical drift + breathe. For isolated focal objects."""
    start = mob.get_center().copy()
    tracker = ValueTracker(0.0)

    def upd(m):
        t = tracker.get_value()
        m.move_to(start + UP * amp * np.sin(t * TAU))

    mob.add_updater(upd)
    scene.play(tracker.animate.set_value(duration / 2.0), run_time=duration, rate_func=linear)
    mob.clear_updaters()
    mob.move_to(start)


# ================================================================== entrances
def pop_in(scene: Scene, mob: Mobject, run_time: float = 0.55, lag: float = 0.04):
    """Springy entrance — scale from 0 with slight overshoot."""
    mob.save_state()
    mob.scale(0.001).set_opacity(0)
    scene.play(Restore(mob, rate_func=RF_SPRING), run_time=run_time)


def staggered_reveal(scene: Scene, group: VGroup, run_time: float = 1.2,
                     direction: np.ndarray = DOWN):
    """Lagged fade + shift; feels hand-crafted."""
    scene.play(
        LaggedStart(
            *[FadeIn(m, shift=direction * 0.25) for m in group],
            lag_ratio=0.18,
        ),
        run_time=run_time,
    )


def card_reveal(scene: Scene, card: VGroup, run_time: float = 1.0):
    """Elegant equation card: bg wipes in, then content writes on."""
    bg, content = card[0], card[1]
    bg.save_state(); bg.set_opacity(0).scale(0.96)
    content.save_state(); content.set_opacity(0)
    scene.play(Restore(bg, rate_func=RF_SNAP), run_time=run_time * 0.55)
    scene.play(Write(content, rate_func=smooth), run_time=run_time * 0.7)


# ================================================================== emphasis
def glow_pulse(scene: Scene, mob: Mobject, color=None, run_time: float = 0.9):
    color = color or PALETTE["accent"]
    scene.play(Indicate(mob, color=color, scale_factor=1.12), run_time=run_time)


def underline_brace(scene: Scene, mob: Mobject, label: str | Mobject,
                    color=None, direction=DOWN, buff: float = 0.25) -> VGroup:
    color = color or PALETTE["accent"]
    brace = Brace(mob, direction=direction, buff=buff, color=color)
    if isinstance(label, str):
        label = Text(label, font_size=20, color=color)
    label.next_to(brace, direction, buff=0.12)
    group = VGroup(brace, label)
    scene.play(GrowFromCenter(brace), FadeIn(label, shift=-direction * 0.1),
               run_time=0.7)
    return group


# ================================================================== graphs
def traced_graph(scene: Scene, axes: Axes, fn, x_range, color,
                 duration: float, dot_color=None, show_tangent_at: float | None = None):
    """
    Draw a graph progressively while a dot rides the curve.
    Optional tangent line at parameter `show_tangent_at`.
    """
    graph = axes.plot(fn, x_range=x_range, color=color, stroke_width=4)
    dot_color = dot_color or PALETTE["accent"]
    dot = Dot(color=dot_color, radius=0.10)
    tracker = ValueTracker(x_range[0])

    def dot_pos():
        x = tracker.get_value()
        return axes.c2p(x, fn(x))

    dot.add_updater(lambda m: m.move_to(dot_pos()))

    # Reveal axes first
    scene.play(Create(axes), run_time=0.6)
    scene.add(dot)
    scene.play(
        Create(graph),
        tracker.animate.set_value(x_range[1]),
        run_time=duration, rate_func=linear,
    )

    if show_tangent_at is not None:
        x0 = show_tangent_at
        slope = (fn(x0 + 1e-3) - fn(x0 - 1e-3)) / 2e-3
        t_line = axes.plot(lambda x: fn(x0) + slope * (x - x0),
                           x_range=[x0 - 1.2, x0 + 1.2],
                           color=PALETTE["force"], stroke_width=3)
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
def morph_equations(scene: Scene, eq_a: Mobject, eq_b: Mobject, run_time: float = 1.4):
    """TransformMatchingTex — 3b1b's signature equation morph."""
    scene.play(TransformMatchingTex(eq_a, eq_b), run_time=run_time)


def color_code_equation(eq: MathTex, mapping: dict[int, str]):
    """
    mapping: {substring_index: color_hex}
    Colors specific submobjects of a MathTex. Index into eq[0][i].
    """
    for idx, hexcol in mapping.items():
        try:
            eq[0][idx].set_color(hexcol)
        except Exception:
            pass


# ================================================================== camera
class CameraDirector:
    """Wrapper for MovingCameraScene camera language."""
    def __init__(self, scene):
        self.s = scene

    def zoom(self, factor: float, run_time: float = 1.2, center=None):
        target = self.s.camera.frame.get_width() / factor
        anims = [self.s.camera.frame.animate.set(width=target)]
        if center is not None:
            anims.append(self.s.camera.frame.animate.move_to(center))
        self.s.play(*anims, run_time=run_time)

    def follow(self, mob: Mobject, run_time: float = 1.0):
        self.s.play(self.s.camera.frame.animate.move_to(mob.get_center()), run_time=run_time)

    def reset(self, run_time: float = 0.8):
        self.s.play(
            self.s.camera.frame.animate.set(width=config.frame_width).move_to(ORIGIN),
            run_time=run_time,
        )


# ================================================================== scene transition
def wipe_transition(scene: Scene, direction: np.ndarray = RIGHT):
    """Quick visual wipe between narrative beats."""
    bar = Rectangle(
        width=config.frame_width * 2, height=config.frame_height * 2,
        fill_color=PALETTE["bg"], fill_opacity=1, stroke_width=0,
    ).move_to(-direction * config.frame_width * 1.5)
    scene.add(bar)
    scene.play(bar.animate.move_to(direction * config.frame_width * 1.5),
               run_time=0.35, rate_func=RF_SNAP)
    scene.remove(bar)
