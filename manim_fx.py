"""
manim_fx.py — Motion vocabulary for cinematic physics shorts.

Every helper guarantees continuous motion; no scene should ever sit frozen.
Compatible with manim==0.18.1, numpy==1.26.4, Python 3.11.

Public API:
    Palette          : PALETTE, SEMANTIC, resolve_color
    Rate functions   : RF_SOFT, RF_SPRING, RF_SNAP, RF_LINEAR
    Motion primitives: live_wait, idle_float, pulse_loop
    Entrances        : pop_in, staggered_reveal, card_reveal, grow_in
    Emphasis         : glow_pulse, underline_brace, highlight_bound
    Graphs           : traced_graph, value_counter
    Equations        : morph_equations, color_code_equation, color_code_terms
    Camera           : CameraDirector
    Transitions      : wipe_transition
"""

from __future__ import annotations

import numpy as np
from manim import *


# =================================================================== PALETTE
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

# Semantic palette — a concept gets the SAME color across all videos.
# JSON elements declare `"semantic": "force"` instead of a hard-coded hex.
SEMANTIC = {
    "force":    PALETTE["field"],     # blue    → force / field
    "energy":   PALETTE["accent"],    # yellow  → energy / work / heat
    "mass":     PALETTE["white"],
    "charge":   PALETTE["pos"],       # red     → positive charge
    "field":    PALETTE["field"],
    "velocity": PALETTE["force"],     # green   → velocity / momentum flow
    "position": PALETTE["accent"],
    "momentum": PALETTE["warn"],
    "accent":   PALETTE["accent"],
    "muted":    PALETTE["muted"],
}


def resolve_color(item: dict | None) -> str:
    """Resolve a JSON element's color. Prefers `semantic`, falls back to `color`."""
    if not isinstance(item, dict):
        return PALETTE["accent"]
    if "semantic" in item:
        key = str(item["semantic"]).lower().strip()
        if key in SEMANTIC:
            return SEMANTIC[key]
    return item.get("color", PALETTE["accent"])


# =================================================================== RATE FUNCTIONS
RF_SOFT   = rate_functions.ease_in_out_sine
RF_SPRING = rate_functions.ease_out_back
RF_SNAP   = rate_functions.ease_out_cubic
RF_LINEAR = linear


# =================================================================== INTERNAL
def _has_updater(mob: Mobject) -> bool:
    """Recursively check if mob or any descendant owns an updater."""
    if getattr(mob, "updaters", None):
        return True
    if hasattr(mob, "submobjects"):
        for sub in mob.submobjects:
            if _has_updater(sub):
                return True
    return False


def _safe_remove_updaters(mob: Mobject) -> None:
    try:
        mob.clear_updaters()
    except Exception:
        pass
    if hasattr(mob, "submobjects"):
        for sub in mob.submobjects:
            _safe_remove_updaters(sub)


def _attach_semantic(mob: Mobject, color_hex: str) -> None:
    """Attach a metadata attribute for later binding-based coloring."""
    try:
        mob._semantic_color = color_hex
    except Exception:
        pass


# =================================================================== MOTION
def live_wait(scene: Scene, duration: float,
              mobs: list[Mobject] | None = None,
              breathe_scale: float = 0.012,
              max_targets: int = 6) -> None:
    """
    Replacement for scene.wait(N). Keeps `mobs` (or everything currently in
    the scene) subtly breathing while time passes. Automatically skips mobs
    that own their own updaters (always_redraw etc.).
    """
    if duration <= 0.05:
        return

    if mobs is None:
        candidates = [m for m in scene.mobjects if isinstance(m, VMobject)]
    else:
        candidates = [m for m in mobs if isinstance(m, VMobject)]

    targets = [m for m in candidates if not _has_updater(m)][:max_targets]

    if not targets:
        scene.wait(duration)
        return

    cycles = max(1, int(duration / 2.4))
    per_cycle = duration / cycles

    for _ in range(cycles):
        anims = []
        for m in targets:
            try:
                anims.append(
                    m.animate(rate_func=there_and_back, run_time=per_cycle)
                     .scale(1 + breathe_scale)
                )
            except Exception:
                continue
        if anims:
            try:
                scene.play(*anims, run_time=per_cycle)
            except Exception:
                scene.wait(per_cycle)
        else:
            scene.wait(per_cycle)


def idle_float(scene: Scene, mob: Mobject, duration: float,
               amp: float = 0.06) -> None:
    """Slow vertical drift + return. For isolated focal objects."""
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
                   run_time=duration, rate_func=RF_LINEAR)
    finally:
        _safe_remove_updaters(mob)
        mob.move_to(start)


def pulse_loop(scene: Scene, mob: Mobject, cycles: int = 2,
               scale: float = 1.05, cycle_time: float = 0.6) -> None:
    """Discrete scale pulses — emphasis without freezing."""
    for _ in range(max(1, cycles)):
        scene.play(mob.animate.scale(scale),
                   run_time=cycle_time / 2, rate_func=RF_SOFT)
        scene.play(mob.animate.scale(1 / scale),
                   run_time=cycle_time / 2, rate_func=RF_SOFT)


# =================================================================== ENTRANCES
def pop_in(scene: Scene, mob: Mobject, run_time: float = 0.55) -> None:
    """Springy entrance — scale from 0 with slight overshoot."""
    mob.save_state()
    mob.scale(0.001).set_opacity(0)
    scene.play(Restore(mob, rate_func=RF_SPRING), run_time=run_time)


def staggered_reveal(scene: Scene, group: VGroup, run_time: float = 1.2,
                     direction: np.ndarray | None = None,
                     shift_amount: float = 0.25) -> None:
    """Lagged fade-in. Adaptive lag keeps large groups within time budget."""
    if direction is None:
        direction = DOWN
    if len(group) == 0:
        return
    n = max(1, len(group))
    lag = min(0.30, 1.6 / n)
    scene.play(
        LaggedStart(
            *[FadeIn(m, shift=direction * shift_amount) for m in group],
            lag_ratio=lag,
        ),
        run_time=run_time,
    )


def card_reveal(scene: Scene, card: VGroup, run_time: float = 1.0) -> None:
    """Elegant equation card: bg wipes in, then content writes on."""
    if len(card) < 2:
        scene.play(FadeIn(card, scale=0.96), run_time=run_time)
        return
    bg, content = card[0], card[1]
    bg.save_state()
    bg.set_opacity(0).scale(0.96)
    content.save_state()
    content.set_opacity(0)
    scene.play(Restore(bg, rate_func=RF_SNAP), run_time=run_time * 0.55)
    scene.play(Write(content, rate_func=smooth), run_time=run_time * 0.70)


def grow_in(scene: Scene, mob: Mobject,
            direction: np.ndarray | None = None,
            run_time: float = 0.5) -> None:
    """Directional entrance for arrows / lines."""
    if direction is None:
        direction = DOWN
    mob.save_state()
    mob.set_opacity(0).shift(-direction * 0.3)
    scene.play(Restore(mob, rate_func=RF_SNAP), run_time=run_time)


# =================================================================== EMPHASIS
def glow_pulse(scene: Scene, mob: Mobject, color=None,
               run_time: float = 0.9) -> None:
    color = color or PALETTE["accent"]
    scene.play(Indicate(mob, color=color, scale_factor=1.12), run_time=run_time)


def underline_brace(scene: Scene, mob: Mobject, label,
                    color=None, direction=DOWN, buff: float = 0.25) -> VGroup:
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


def highlight_bound(scene: Scene, eq_submob, visual_mob, color=None,
                    run_time: float = 0.9) -> None:
    """
    3b1b's signature move: when the narrator says a word, BOTH the equation
    term AND its visual counterpart pulse in sync. Binds abstract symbols
    to concrete pictures.
    """
    color = color or PALETTE["accent"]
    anims = []
    if eq_submob is not None:
        try:
            anims.append(Indicate(eq_submob, color=color, scale_factor=1.20))
        except Exception:
            pass
    if visual_mob is not None:
        try:
            anims.append(Indicate(visual_mob, color=color, scale_factor=1.15))
        except Exception:
            pass
    if anims:
        scene.play(*anims, run_time=run_time)


# =================================================================== GRAPHS
def traced_graph(scene: Scene, axes: Axes, fn, x_range,
                 color=None, duration: float = 2.4,
                 dot_color=None,
                 show_tangent_at: float | None = None,
                 show_axes: bool = True
                 ) -> tuple[Mobject, Mobject, ValueTracker]:
    """
    Draw a graph progressively while a dot rides the curve.
    Returns (graph, dot, tracker) so caller can keep the tracker alive.
    """
    color = color or PALETTE["accent"]
    dot_color = dot_color or PALETTE["accent"]

    graph = axes.plot(fn, x_range=x_range, color=color, stroke_width=4)

    x0, x1 = float(x_range[0]), float(x_range[1])
    try:
        start_pos = axes.c2p(x0, fn(x0))
    except Exception:
        start_pos = axes.c2p(x0, 0.0)

    dot = Dot(start_pos, color=dot_color, radius=0.10)
    tracker = ValueTracker(x0)

    def _dot_update(m, tr=tracker, ax=axes, f=fn):
        try:
            x = tr.get_value()
            m.move_to(ax.c2p(x, f(x)))
        except Exception:
            pass

    dot.add_updater(_dot_update)

    if show_axes:
        scene.play(Create(axes), run_time=0.6)
    scene.add(dot)
    scene.play(
        Create(graph),
        tracker.animate.set_value(x1),
        run_time=duration, rate_func=RF_LINEAR,
    )

    if show_tangent_at is not None:
        x0t = float(show_tangent_at)
        try:
            slope = (fn(x0t + 1e-3) - fn(x0t - 1e-3)) / 2e-3
            t_line = axes.plot(
                lambda x: fn(x0t) + slope * (x - x0t),
                x_range=[x0t - 1.2, x0t + 1.2],
                color=PALETTE["force"], stroke_width=3,
            )
            scene.play(Create(t_line), run_time=0.5)
            scene.play(Indicate(t_line, color=PALETTE["force"]), run_time=0.6)
        except Exception:
            pass

    dot.clear_updaters()
    return graph, dot, tracker


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
    scene.play(num.animate.set_value(end), run_time=duration, rate_func=RF_LINEAR)
    return num


# =================================================================== EQUATIONS
def morph_equations(scene: Scene, eq_a: Mobject, eq_b: Mobject,
                    run_time: float = 1.4) -> None:
    """3b1b's signature equation morph."""
    scene.play(TransformMatchingTex(eq_a, eq_b), run_time=run_time)


def color_code_equation(eq: MathTex, mapping: dict[int, str]) -> None:
    """Color specific submobjects of a MathTex by index."""
    for idx, hexcol in mapping.items():
        try:
            eq[0][idx].set_color(hexcol)
        except Exception:
            pass


def color_code_terms(equation_mobs: list, bindings: dict,
                     visuals_by_id: dict) -> None:
    """
    Permanently color equation sub-terms to match their bound visual's
    semantic color. Call once at `law` beat reveal.
    """
    for visual_id, terms in bindings.items():
        vis = visuals_by_id.get(visual_id)
        vis_color = getattr(vis, "_semantic_color", PALETTE["accent"])
        for eq_idx, term_idx in terms:
            try:
                equation_mobs[eq_idx][0][term_idx].set_color(vis_color)
            except Exception:
                pass


# =================================================================== CAMERA
class CameraDirector:
    """Cinematic camera language for MovingCameraScene."""

    def __init__(self, scene: Scene):
        self.s = scene

    def zoom(self, factor: float, run_time: float = 1.2,
             center=None) -> None:
        """Chain set(width) + move_to on a single builder."""
        frame = self.s.camera.frame
        target_width = frame.get_width() / factor
        builder = frame.animate.set(width=target_width)
        if center is not None:
            builder = builder.move_to(center)
        self.s.play(builder, run_time=run_time, rate_func=RF_SOFT)

    def follow(self, mob: Mobject, run_time: float = 1.0) -> None:
        self.s.play(self.s.camera.frame.animate.move_to(mob.get_center()),
                    run_time=run_time, rate_func=RF_SOFT)

    def reset(self, run_time: float = 0.8) -> None:
        frame = self.s.camera.frame
        self.s.play(
            frame.animate.set(width=config.frame_width).move_to(ORIGIN),
            run_time=run_time, rate_func=RF_SOFT,
        )


# =================================================================== TRANSITIONS
def wipe_transition(scene: Scene,
                    direction: np.ndarray | None = None,
                    run_time: float = 0.35) -> None:
    """Quick visual wipe between narrative beats."""
    if direction is None:
        direction = RIGHT
    bar = Rectangle(
        width=config.frame_width * 2,
        height=config.frame_height * 2,
        fill_color=PALETTE["bg"], fill_opacity=1, stroke_width=0,
    ).move_to(-direction * config.frame_width * 1.5)
    scene.add(bar)
    scene.play(bar.animate.move_to(direction * config.frame_width * 1.5),
               run_time=run_time, rate_func=RF_SNAP)
    scene.remove(bar)
