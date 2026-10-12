"""Small side-view animations that show what each mode and experimental feature does.

They are drawn on a plain Tk canvas (no image files, no Pillow): sharp at any display scaling, in the
light or dark palette, and without text, so they need no translation. Amber layers are the old print,
green layers are what Layer Rescue prints. Each animation plays twice when it is shown and then stays on
its last frame; a click plays it again.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from . import gui_theme as theme

FRAME_MS = 33


def _ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _span(t: float, start: float, end: float) -> float:
    """0 before ``start``, 1 after ``end``, linear in between."""
    if t <= start:
        return 0.0
    if t >= end:
        return 1.0
    return (t - start) / (end - start)


class Pen:
    """Drawing helpers in logical units (multiplied by the window scaling)."""

    def __init__(self, canvas: Any, scale: float) -> None:
        self.c = canvas
        self.s = scale

    def rect(self, x0: float, y0: float, x1: float, y1: float, fill: theme.Color, outline: theme.Color | None = None, **kw: Any) -> None:
        s = self.s
        self.c.create_rectangle(
            x0 * s, y0 * s, x1 * s, y1 * s, fill=theme.pick(fill), outline=theme.pick(outline) if outline else "", **kw
        )

    def line(self, points: list[float], color: theme.Color, width: float = 1.5, **kw: Any) -> None:
        self.c.create_line(*[p * self.s for p in points], fill=theme.pick(color), width=max(1.0, width * self.s), **kw)

    def poly(self, points: list[float], fill: theme.Color, outline: theme.Color | None = None, **kw: Any) -> None:
        self.c.create_polygon(
            *[p * self.s for p in points], fill=theme.pick(fill), outline=theme.pick(outline) if outline else "", **kw
        )

    def oval(self, x0: float, y0: float, x1: float, y1: float, fill: theme.Color, outline: theme.Color | None = None, **kw: Any) -> None:
        s = self.s
        self.c.create_oval(
            x0 * s, y0 * s, x1 * s, y1 * s, fill=theme.pick(fill), outline=theme.pick(outline) if outline else "", **kw
        )

    # -- the things in every scene
    def bed(self, x0: float, x1: float, y: float) -> None:
        self.rect(x0, y, x1, y + 5, theme.NOZZLE)
        self.rect(x0 + 6, y + 5, x0 + 12, y + 9, theme.FAINT)
        self.rect(x1 - 12, y + 5, x1 - 6, y + 9, theme.FAINT)

    def layers(
        self,
        x0: float,
        x1: float,
        bottom: float,
        count: float,
        height: float,
        color: theme.Color,
        alternate: bool = False,
    ) -> float:
        """``count`` stacked layers; returns the top Y.

        A fraction draws the last layer partly: left to right, or with ``alternate`` in the direction the
        nozzle prints it (odd layers right to left, as in :func:`_printing_x`).
        """
        full = int(count)
        for index in range(full):
            y = bottom - (index + 1) * height
            self.rect(x0, y + 0.6, x1, y + height, color)
        part = count - full
        if part > 0:
            y = bottom - (full + 1) * height
            if alternate and full % 2 == 1:
                self.rect(x1 - (x1 - x0) * part, y + 0.6, x1, y + height, color)
            else:
                self.rect(x0, y + 0.6, x0 + (x1 - x0) * part, y + height, color)
        return bottom - full * height

    def nozzle(self, x: float, tip: float, faded: bool = False, hot: bool = False) -> None:
        body = theme.FAINT if faded else theme.NOZZLE
        self.line([x, 0, x, tip - 24], theme.FAINT, 2)
        self.rect(x - 13, tip - 26, x + 13, tip - 12, body)
        if hot:
            self.rect(x - 13, tip - 15, x + 13, tip - 12, theme.HEAT)
        self.poly([x - 7, tip - 12, x + 7, tip - 12, x + 2, tip, x - 2, tip], body)

    def pause_badge(self, x: float, y: float, alpha: float) -> None:
        if alpha <= 0:
            return
        size = 7 + 2 * alpha
        self.oval(x - size - 3, y - size - 3, x + size + 3, y + size + 3, theme.AMBER_SOFT)
        self.rect(x - 4.5, y - size + 2, x - 1.5, y + size - 2, theme.WARN)
        self.rect(x + 1.5, y - size + 2, x + 4.5, y + size - 2, theme.WARN)

    def bolt(self, x: float, y: float, k: float = 1.0) -> None:
        self.poly(
            [x + 2 * k, y, x - 7 * k, y + 13 * k, x - 1 * k, y + 13 * k, x - 4 * k, y + 24 * k, x + 7 * k, y + 9 * k, x + 1 * k, y + 9 * k],
            theme.AMBER,
        )


# ---------------------------------------------------------------- scenes
# Each scene draws one frame for t in [0, 1]. Sizes are in logical pixels.

W, H = 320, 150
BED_Y = 128
LAYER = 7.0
PART = (110.0, 210.0)


def _printing_x(progress: float, x0: float, x1: float) -> float:
    """Nozzle X while a layer is printed left to right, then right to left (boustrophedon)."""
    frac = progress - int(progress)
    return x0 + (x1 - x0) * (frac if int(progress) % 2 == 0 else 1 - frac)


def scene_retained(pen: Pen, t: float) -> None:
    x0, x1 = PART
    pen.bed(40, 280, BED_Y)
    old = 4 + 2 * _span(t, 0.0, 0.24)  # the last two old layers are printed, then the print stops
    top = pen.layers(x0, x1, BED_Y, old, LAYER, theme.AMBER)
    stop = _span(t, 0.24, 0.30)
    back = _ease(_span(t, 0.44, 0.56))
    new = 3 * _span(t, 0.58, 0.94)
    seam = BED_Y - 6 * LAYER
    if t >= 0.56:
        pen.layers(x0, x1, seam, new, LAYER, theme.GREEN, alternate=True)
    if t < 0.24:
        x = x0 + (x1 - x0) * ((old - int(old)) if old < 6 else 1)
        pen.nozzle(x, top - LAYER * (old - int(old) > 0))
    elif t < 0.56:
        lift = 26 * _ease(_span(t, 0.27, 0.38)) * (1 - back)
        x = x1 + 30 * _ease(_span(t, 0.27, 0.38)) * (1 - back)
        pen.nozzle(x, seam - lift)
        pen.pause_badge(x + 30, seam - lift - 30, stop * (1 - back))
    else:
        x = _printing_x(new, x0, x1) if new < 3 else x1
        layer_top = seam - LAYER * min(int(new) + 1, 3)
        pen.nozzle(x, layer_top - (6 * _span(t, 0.94, 1.0)))
    if t >= 0.56:
        pen.line([x0 - 8, seam, x0 - 2, seam], theme.GREEN, 2)
        pen.line([x1 + 2, seam, x1 + 8, seam], theme.GREEN, 2)


def scene_manual(pen: Pen, t: float) -> None:
    x0, x1 = PART
    pen.bed(40, 280, BED_Y)
    old = 5 + 0.55 * _span(t, 0.0, 0.16)
    cut = t >= 0.16
    pen.layers(x0, x1, BED_Y, 5, LAYER, theme.AMBER)
    seam = BED_Y - 5 * LAYER
    if cut:
        # The half-printed layer stays as it is; the job restarts on top of the last good layer.
        pen.layers(x0, x1, seam, 0.55, LAYER, theme.AMBER_SOFT)
    else:
        pen.layers(x0, x1, seam, old - 5, LAYER, theme.AMBER)
    if t < 0.16:
        pen.nozzle(x0 + (x1 - x0) * (old - 5), seam - LAYER)
    elif t < 0.58:
        pen.bolt(56, 22, 1.2 * (1 - _span(t, 0.30, 0.40)) if t < 0.40 else 0)
        # After the power cut the nozzle is moved up, then lowered by hand until it touches the layer.
        up = _ease(_span(t, 0.20, 0.32))
        down = _ease(_span(t, 0.36, 0.54))
        height = 40 * up * (1 - down)
        x = x0 + (x1 - x0) * 0.55 - 30 * up + 30 * down
        top = seam - 2 * (1 - down)
        pen.nozzle(x, top - height, faded=t < 0.36)
        if 0.36 <= t < 0.54:
            arrow_x = x + 30
            pen.line([arrow_x, top - height - 18, arrow_x, top - height + 2], theme.MUTED, 2, arrow="last")
        touch = _span(t, 0.52, 0.58)
        if 0 < touch < 1:
            pen.line([x - 14, seam - 1, x - 6, seam - 1], theme.GREEN, 2)
            pen.line([x + 6, seam - 1, x + 14, seam - 1], theme.GREEN, 2)
    else:
        new = 3 * _span(t, 0.60, 0.94)
        pen.layers(x0, x1, seam, new, LAYER, theme.GREEN, alternate=True)
        x = _printing_x(new, x0, x1) if new < 3 else x1
        pen.nozzle(x, seam - LAYER * min(int(new) + 1, 3) - 6 * _span(t, 0.94, 1.0))


def scene_insert(pen: Pen, t: float) -> None:
    x0, x1 = PART
    gap = 3
    post = 9
    pen.bed(40, 280, BED_Y)
    wall = 3 * _span(t, 0.0, 0.26)
    left = (x0 - gap - post, x0 - gap)
    right = (x1 + gap, x1 + gap + post)
    for a, b in (left, right):
        pen.layers(a, b, BED_Y, wall, LAYER, theme.FAINT)
    if t < 0.26:
        side = left if int(wall * 2) % 2 == 0 else right
        pen.nozzle((side[0] + side[1]) / 2, BED_Y - LAYER * (int(wall) + 1))
        return
    pause = _span(t, 0.26, 0.32)
    drop = _ease(_span(t, 0.34, 0.56))
    lift = 60 * (1 - drop)
    if t < 0.58:
        pen.nozzle(x1 + 46, BED_Y - 6 * LAYER - 34)
        pen.pause_badge(x1 + 76, BED_Y - 6 * LAYER - 64, pause * (1 - _span(t, 0.52, 0.58)))
    pen.layers(x0, x1, BED_Y - lift, 6, LAYER, theme.AMBER)
    if 0.34 <= t < 0.56:
        mid = (x0 + x1) / 2
        pen.line([mid, BED_Y - lift - 6 * LAYER - 22, mid, BED_Y - lift - 6 * LAYER - 6], theme.MUTED, 2, arrow="last")
    if t >= 0.58:
        top = BED_Y - 6 * LAYER
        new = 3 * _span(t, 0.60, 0.94)
        pen.layers(x0, x1, top, new, LAYER, theme.GREEN, alternate=True)
        x = _printing_x(new, x0, x1) if new < 3 else x1
        pen.nozzle(x, top - LAYER * min(int(new) + 1, 3) - 6 * _span(t, 0.94, 1.0))


SMALL_W, SMALL_H = 240, 96
SMALL_BED = 80
SMALL_PART = (70.0, 170.0)


def scene_reheat(pen: Pen, t: float) -> None:
    x0, x1 = SMALL_PART
    pen.bed(30, 210, SMALL_BED)
    top = pen.layers(x0, x1, SMALL_BED, 5, 6, theme.AMBER)
    sweep = _span(t, 0.05, 0.62)
    if t < 0.66:
        passes = sweep * 2  # there and back
        x = _printing_x(passes, x0, x1) if sweep < 1 else x0
        # Warm trail behind the nozzle, fading with distance.
        for step in range(12):
            d = step * 5
            trail = x - d if int(passes) % 2 == 0 else x + d
            if x0 <= trail <= x1 and sweep < 1:
                shade = theme.HEAT if step < 4 else theme.AMBER
                pen.rect(trail - 2.5, top - 1.6, trail + 2.5, top + 0.4, shade)
        pen.nozzle(x, top - 4, hot=True)
        glow = 0.6 + 0.4 * math.sin(t * 40)
        pen.oval(x - 6 * glow, top - 4, x + 6 * glow, top - 1, theme.HEAT)
    else:
        new = _span(t, 0.68, 0.94)
        pen.layers(x0, x1, top, new, 6, theme.GREEN, alternate=True)
        x = x0 + (x1 - x0) * new
        pen.nozzle(x, top - 6 - 5 * _span(t, 0.94, 1.0))


def scene_no_wall(pen: Pen, t: float) -> None:
    x0, x1 = SMALL_PART
    pen.bed(30, 210, SMALL_BED)
    drop = _ease(_span(t, 0.05, 0.36))
    if t < 0.36:
        pen.line([x0, SMALL_BED - 1, x1, SMALL_BED - 1], theme.GREEN, 1.5, dash=(4, 3))
    lift = 46 * (1 - drop)
    pen.layers(x0, x1, SMALL_BED - lift, 5, 6, theme.AMBER)
    tape = _span(t, 0.40, 0.50)
    if tape > 0:
        for side, sign in ((x0, -1), (x1, 1)):
            pen.poly(
                [side - 2 * sign, SMALL_BED - 10, side + 12 * sign * tape, SMALL_BED - 10,
                 side + 12 * sign * tape, SMALL_BED - 2, side - 2 * sign, SMALL_BED - 2],
                theme.MUTED,
            )
    top = SMALL_BED - 5 * 6
    if t >= 0.52:
        new = 2 * _span(t, 0.54, 0.94)
        pen.layers(x0, x1, top, new, 6, theme.GREEN, alternate=True)
        x = _printing_x(new, x0, x1) if new < 2 else x1
        pen.nozzle(x, top - 6 * min(int(new) + 1, 2) - 5 * _span(t, 0.94, 1.0))
    else:
        pen.nozzle(x1 + 30, top - 20)


SCENES: dict[str, tuple[Callable[[Pen, float], None], int, int, int]] = {
    # name: (draw, width, height, period ms)
    "retained": (scene_retained, W, H, 5600),
    "manual": (scene_manual, W, H, 6000),
    "insert": (scene_insert, W, H, 6000),
    "reheat": (scene_reheat, SMALL_W, SMALL_H, 4200),
    "no_wall": (scene_no_wall, SMALL_W, SMALL_H, 4200),
}


class Illustration:
    """A canvas that plays one scene: twice when shown, then its last frame; click to play again."""

    def __init__(self, parent: Any, scene: str, background: theme.Color = theme.SURFACE, loops: int = 2) -> None:
        import tkinter as tk

        self.scene = scene
        self.background = background
        self.loops = loops
        self.canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0, cursor="hand2")
        self.canvas.bind("<Button-1>", lambda _event: self.play())
        self._job: str | None = None
        self._elapsed = 0
        self.resize()
        self.draw(1.0)

    def resize(self) -> None:
        _, width, height, _ = SCENES[self.scene]
        scale = theme.widget_scaling(self.canvas)
        self.canvas.configure(width=int(width * scale), height=int(height * scale))

    def set_scene(self, scene: str, play: bool = True) -> None:
        self.stop()
        self.scene = scene
        self.resize()
        if play:
            self.play()
        else:
            self.draw(1.0)

    def draw(self, t: float) -> None:
        draw, _, _, _ = SCENES[self.scene]
        self.canvas.configure(background=theme.pick(self.background))
        self.canvas.delete("all")
        draw(Pen(self.canvas, theme.widget_scaling(self.canvas)), t)

    def play(self) -> None:
        self.stop()
        self._elapsed = 0
        self._tick()

    def stop(self) -> None:
        if self._job is not None:
            try:
                self.canvas.after_cancel(self._job)
            except Exception:  # noqa: BLE001 - the canvas may already be gone
                pass
            self._job = None

    def _tick(self) -> None:
        self._job = None
        try:
            if not self.canvas.winfo_exists():
                return
        except Exception:  # noqa: BLE001
            return
        _, _, _, period = SCENES[self.scene]
        total = period * self.loops
        if self._elapsed >= total:
            self.draw(1.0)
            return
        self.draw((self._elapsed % period) / period if self._elapsed < total else 1.0)
        self._elapsed += FRAME_MS
        self._job = self.canvas.after(FRAME_MS, self._tick)

    def repaint(self) -> None:
        """Light/dark changed: redraw the current (or last) frame."""
        if self._job is None:
            self.draw(1.0)


# ---------------------------------------------------------------- mode icons (56 x 44, static)


def icon_retained(canvas: Any, scale: float) -> None:
    pen = Pen(canvas, scale)
    pen.rect(6, 38, 50, 41, theme.NOZZLE)
    pen.layers(14, 42, 38, 4, 5, theme.AMBER)
    pen.layers(14, 42, 18, 2, 5, theme.GREEN)
    pen.rect(45, 4, 47.5, 13, theme.WARN)
    pen.rect(49.5, 4, 52, 13, theme.WARN)


def icon_manual(canvas: Any, scale: float) -> None:
    pen = Pen(canvas, scale)
    pen.rect(6, 38, 50, 41, theme.NOZZLE)
    pen.layers(14, 42, 38, 4, 5, theme.AMBER)
    pen.layers(14, 42, 18, 2, 5, theme.GREEN)
    pen.bolt(49, 2, 0.6)


def icon_insert(canvas: Any, scale: float) -> None:
    pen = Pen(canvas, scale)
    pen.rect(6, 38, 50, 41, theme.NOZZLE)
    pen.layers(10, 13, 38, 2, 5, theme.FAINT)
    pen.layers(43, 46, 38, 2, 5, theme.FAINT)
    pen.layers(15, 41, 38, 4, 5, theme.AMBER)
    pen.layers(15, 41, 18, 2, 5, theme.GREEN)
    pen.line([28, 0, 28, 6], theme.MUTED, 1.5, arrow="last")


MODE_ICONS = {"retained": icon_retained, "manual": icon_manual, "insert": icon_insert}
