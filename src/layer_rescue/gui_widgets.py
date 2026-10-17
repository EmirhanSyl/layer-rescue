"""CustomTkinter building blocks shared by the Layer Rescue windows.

Every text widget takes an i18n key and follows the selected language. Test scripts drive the window
through ``invoke()`` methods and the ``_lr_action`` names set on the main controls.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

from . import gui_theme as theme
from .i18n import LANGUAGES, Translator

WRAP = 600  # main column text width (CustomTkinter scales it)


def set_window_icon(root: Any) -> None:
    """Use the Layer Rescue icon in the title bar, task bar and dialogs.

    CustomTkinter sets its own icon on Windows about 200 ms after the window opens, so ours is set
    again after that.
    """
    import tkinter as tk

    assets = Path(__file__).with_name("assets")

    def apply() -> None:
        try:
            if sys.platform == "win32":
                root.iconbitmap(default=str(assets / "icon.ico"))
                root.iconbitmap(str(assets / "icon.ico"))
            image = tk.PhotoImage(master=root, file=str(assets / "icon.png"))
            root.iconphoto(True, image)
            root._layer_rescue_icon = image  # Tk forgets images that Python no longer references
        except (tk.TclError, OSError):
            pass  # A missing icon is cosmetic; never block the window over it.

    apply()
    try:
        root.after(300, apply)
    except tk.TclError:
        pass


def text(
    tr: Translator,
    parent: Any,
    key: str | None,
    font: Any = None,
    color: theme.Color = theme.INK,
    wrap: int | None = None,
    **values: Any,
) -> Any:
    """A label whose text follows the selected language (``key`` None: set the text yourself)."""
    import customtkinter as ctk

    label = ctk.CTkLabel(
        parent,
        text="",
        font=font,
        text_color=color,
        anchor="w",
        justify="left",
        wraplength=wrap or 0,
        fg_color="transparent",
    )
    if key is not None:
        tr.on_change(lambda: label.configure(text=tr(key, **values) if values else tr(key)))
    return label


def card(parent: Any, **options: Any) -> Any:
    import customtkinter as ctk

    settings = {
        "fg_color": theme.SURFACE,
        "corner_radius": theme.RADIUS,
        "border_width": 1,
        "border_color": theme.LINE,
    }
    settings.update(options)
    return ctk.CTkFrame(parent, **settings)


def field(parent: Any, variable: Any, width: int = 90) -> Any:
    import customtkinter as ctk

    return ctk.CTkEntry(
        parent,
        textvariable=variable,
        width=width,
        height=32,
        corner_radius=8,
        border_width=1,
        fg_color=theme.SURFACE_ALT,
        border_color=theme.LINE,
        text_color=theme.INK,
    )


def set_enabled(widget: Any, enabled: bool) -> None:
    widget.configure(state="normal" if enabled else "disabled")
    if hasattr(widget, "cget") and "CTkEntry" in type(widget).__name__:
        widget.configure(text_color=theme.INK if enabled else theme.FAINT)


_NUMBER_PREFIX = re.compile(r"^\s*\d+\.\s*")


def _ease_out(x: float) -> float:
    return 1 - (1 - x) ** 3


class Reveal:
    """Slide-open effect for ``container``, which is already laid out at its full size.

    Changing a section's height frame by frame makes every widget below it move on every frame, and on
    Windows CustomTkinter cannot redraw that fast (ghost copies of the moved widgets stay on screen). Here
    the layout changes once; a plain cover in the card's colour lies over the new content and slides down,
    uncovering it. Only the cover moves. ``cancel()`` removes the cover at once.
    """

    FRAME_MS = 16

    def __init__(self, container: Any, owner: Any, background: theme.Color, duration_ms: int = 220) -> None:
        import tkinter as tk

        self.owner = owner
        self.jobs: list[str] = []
        self.cover: Any = None
        self.frames = max(1, duration_ms // self.FRAME_MS)
        try:
            owner.update_idletasks()
            self.cover = tk.Frame(owner, background=theme.pick(background), borderwidth=0, highlightthickness=0)
            self.cover.place(in_=container, x=0, y=0, relwidth=1, relheight=1)
            self.cover.lift()
        except tk.TclError:
            self.cancel()
            return
        self.jobs.append(owner.after(self.FRAME_MS, lambda: self._step(1)))

    def _step(self, index: int) -> None:
        import tkinter as tk

        try:
            if index > self.frames or self.cover is None:
                self.cancel()
                return
            done = _ease_out(index / self.frames)
            self.cover.place_configure(rely=done, relheight=1 - done)
            self.jobs.append(self.owner.after(self.FRAME_MS, lambda: self._step(index + 1)))
        except tk.TclError:
            self.cancel()

    def cancel(self) -> None:
        for job in self.jobs:
            try:
                self.owner.after_cancel(job)
            except Exception:  # noqa: BLE001 - already ran
                pass
        self.jobs.clear()
        if self.cover is not None:
            try:
                self.cover.destroy()
            except Exception:  # noqa: BLE001 - window already gone
                pass
            self.cover = None


class StepCard:
    """A numbered step of the form: a header (badge, title, summary, arrow) and a body that opens and closes.

    Clicking the header opens or closes the step, so the user can go to any step. ``open`` slides the body
    open; ``set_done`` turns the badge into a check mark with a short pulse. While closed, the header shows a
    one-line summary of what was entered.
    """

    FRAME_MS = 16
    OPEN_MS = 200

    def __init__(self, tr: Translator, parent: Any, number: int, title_key: str, fonts: theme.Fonts) -> None:
        import customtkinter as ctk

        self.number = number
        self.is_open = False
        self.done = False
        self.visited = False
        self._summary = ""
        self._jobs: list[str] = []
        self._reveal: Reveal | None = None
        self.frame = card(parent)
        self.frame.columnconfigure(1, weight=1)
        import tkinter as tk

        self.fonts = fonts
        self._badge_scale = 1.0  # circle size during the pulse
        self._check = 1.0  # how much of the check mark is drawn
        scale = theme.widget_scaling(parent)
        self.badge = tk.Canvas(
            self.frame, width=int(34 * scale), height=int(34 * scale), highlightthickness=0, borderwidth=0
        )
        self.badge.grid(row=0, column=0, padx=(10, 6), pady=8, sticky="w")
        self.title = text(tr, self.frame, None, font=fonts.heading)
        self.title.grid(row=0, column=1, sticky="w", pady=12)
        tr.on_change(lambda: self.title.configure(text=_NUMBER_PREFIX.sub("", tr(title_key))))
        self.summary = text(tr, self.frame, None, font=fonts.small, color=theme.MUTED)
        self.summary.grid(row=0, column=2, sticky="e", padx=(12, 6))
        self.arrow = text(tr, self.frame, None, font=fonts.body, color=theme.FAINT)
        self.arrow.grid(row=0, column=3, sticky="e", padx=(0, 16))
        for widget in (self.frame, self.badge, self.title, self.summary, self.arrow):
            widget.bind("<Button-1>", lambda _event: self.toggle())
            for child in widget.winfo_children():
                child.bind("<Button-1>", lambda _event: self.toggle())
        # The body sits in a clip frame whose height is animated when the step opens.
        self.clip = ctk.CTkFrame(self.frame, fg_color="transparent", corner_radius=0)
        self.clip.columnconfigure(0, weight=1)
        self.body = ctk.CTkFrame(self.clip, fg_color="transparent", corner_radius=0)
        self.body.grid(row=0, column=0, sticky="ew")
        self.body.columnconfigure(0, weight=1)
        self._refresh()

    # -- appearance
    def _draw_badge(self) -> None:
        """A circle with the step number, or a check mark once the step is done (drawn on a canvas so the
        circle stays round and the check mark can be animated)."""
        scale = theme.widget_scaling(self.badge)
        c = self.badge
        c.configure(background=theme.pick(theme.SURFACE))
        c.delete("all")
        mid = 17 * scale
        radius = 13 * scale * self._badge_scale
        if self.done:
            fill, ink = theme.GREEN, theme.ON_GREEN
        elif self.is_open or self.visited:
            fill, ink = theme.GREEN_SOFT, theme.GREEN
        else:
            fill, ink = theme.SURFACE_ALT, theme.FAINT
        c.create_oval(mid - radius, mid - radius, mid + radius, mid + radius, fill=theme.pick(fill), outline="")
        if not self.done:
            c.create_text(mid, mid, text=str(self.number), fill=theme.pick(ink), font=self.fonts.badge)
            return
        # Check mark: short stroke down, long stroke up; drawn progressively while ``_check`` goes 0 → 1.
        points = [(-5.5, 0.2), (-1.6, 4.2), (6.0, -4.4)]
        first = ((points[1][0] - points[0][0]) ** 2 + (points[1][1] - points[0][1]) ** 2) ** 0.5
        second = ((points[2][0] - points[1][0]) ** 2 + (points[2][1] - points[1][1]) ** 2) ** 0.5
        length = (first + second) * self._check
        path = [points[0]]
        if length <= first:
            k = length / first
            path.append((points[0][0] + (points[1][0] - points[0][0]) * k, points[0][1] + (points[1][1] - points[0][1]) * k))
        else:
            k = min(1.0, (length - first) / second)
            path += [points[1], (points[1][0] + (points[2][0] - points[1][0]) * k, points[1][1] + (points[2][1] - points[1][1]) * k)]
        if len(path) >= 2 and self._check > 0:
            coords = [v for x, y in path for v in (mid + x * scale * self._badge_scale, mid + y * scale * self._badge_scale)]
            c.create_line(*coords, fill=theme.pick(ink), width=max(2.0, 2.4 * scale), capstyle="round", joinstyle="round")

    def repaint(self) -> None:
        """Light/dark changed."""
        self._refresh()

    def _refresh(self) -> None:
        self._draw_badge()
        self.title.configure(text_color=theme.INK if (self.is_open or self.done or self.visited) else theme.MUTED)
        self.summary.configure(text="" if self.is_open else self._summary)
        self.arrow.configure(text="▾" if self.is_open else "▸")

    def set_summary(self, value: str) -> None:
        self._summary = value
        self._refresh()

    def set_number(self, number: int) -> None:
        self.number = number
        self._refresh()

    # -- opening and closing
    def toggle(self) -> None:
        if self.is_open:
            self.close()
        else:
            self.open()

    def invoke(self) -> None:
        self.toggle()

    def open(self, animate: bool = True, after: Callable[[], None] | None = None) -> None:
        self._cancel()
        self.is_open = True
        self.visited = True
        self._refresh()
        # Kept clear of the card's rounded border, which the clip would otherwise paint over.
        self.clip.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, 16), pady=(0, 16))
        if animate:
            self._reveal = Reveal(self.clip, self.frame, theme.SURFACE, self.OPEN_MS)
        if after:
            # Scroll to the step right away, while it is being uncovered.
            self._jobs.append(self.frame.after(30, after))

    def close(self) -> None:
        self._cancel()
        self.is_open = False
        self.clip.grid_remove()
        self._refresh()

    def _cancel(self) -> None:
        for job in self._jobs:
            try:
                self.frame.after_cancel(job)
            except Exception:  # noqa: BLE001 - already ran
                pass
        self._jobs.clear()
        if self._reveal is not None:
            self._reveal.cancel()
            self._reveal = None
        self._badge_scale, self._check = 1.0, 1.0  # an interrupted pulse ends in its final state

    # -- completion
    def set_done(self, done: bool, animate: bool = True) -> None:
        if done == self.done:
            return
        self.done = done
        self._refresh()
        if not (done and animate):
            return
        # The circle pops (grows a little and settles) while the check mark is drawn, and the card border
        # flashes green.
        frames = 14

        def step(index: int) -> None:
            t = index / frames
            self._badge_scale = 1.0 + 0.22 * (1 - abs(2 * min(t, 0.7) / 0.7 - 1)) if t < 0.7 else 1.0
            self._check = min(1.0, max(0.0, (t - 0.15) / 0.65))
            self._draw_badge()
            if index < frames:
                self._jobs.append(self.frame.after(self.FRAME_MS, lambda: step(index + 1)))

        self._badge_scale, self._check = 0.85, 0.0
        step(0)
        self.frame.configure(border_color=theme.GREEN)
        self.frame.after(700, lambda: self.frame.configure(border_color=theme.LINE))


class StepFlow:
    """Opens the steps one after another as they are completed; the user can still open any step.

    ``update(index, complete, summary)`` is called whenever a step's input changes. A step counts as done
    once it has stayed complete for a moment (so typing "4" on the way to "461" does not jump ahead); then
    its badge turns into a check mark and the next step slides open.
    """

    SETTLE_MS = 550

    def __init__(self, steps: list[StepCard], reveal: Callable[[Any], None] | None = None) -> None:
        self.steps = steps
        self.reveal = reveal
        self._complete = [False] * len(steps)
        self._jobs: dict[int, str] = {}
        for index, step in enumerate(steps):
            if index == 0:
                step.open(animate=False)
            else:
                step.close()

    def update(self, index: int, complete: bool, summary: str = "") -> None:
        step = self.steps[index]
        step.set_summary(summary if complete else "")
        self._complete[index] = complete
        job = self._jobs.pop(index, None)
        if job is not None:
            step.frame.after_cancel(job)
        if not complete:
            step.set_done(False)
            return
        if step.done:
            return
        self._jobs[index] = step.frame.after(self.SETTLE_MS, lambda: self._settle(index))

    def _settle(self, index: int) -> None:
        self._jobs.pop(index, None)
        if not self._complete[index]:
            return
        self.steps[index].set_done(True)
        if index + 1 < len(self.steps):
            following = self.steps[index + 1]
            if not following.is_open and not following.visited:
                following.open(after=lambda: self.reveal(following.frame) if self.reveal else None)

    def settle_now(self) -> None:
        """Finish pending steps at once (tests, and before creating the G-code)."""
        for index in list(self._jobs):
            job = self._jobs.pop(index)
            self.steps[index].frame.after_cancel(job)
            self._settle(index)


class Collapsible:
    """A titled section whose body opens and closes when the title is clicked (closed by default)."""

    def __init__(
        self,
        tr: Translator,
        parent: Any,
        key: str,
        fonts: theme.Fonts,
        suffix: Callable[[], str] | None = None,
    ) -> None:
        import tkinter as tk

        import customtkinter as ctk

        self.tr = tr
        self.key = key
        self.suffix = suffix
        self.is_open = tk.BooleanVar(value=False)
        self._reveal: Reveal | None = None
        self.frame = card(parent)
        self.frame.columnconfigure(0, weight=1)
        self.header = ctk.CTkButton(
            self.frame,
            text="",
            anchor="w",
            height=44,
            corner_radius=theme.RADIUS,
            fg_color="transparent",
            hover_color=theme.SURFACE_ALT,
            text_color=theme.INK,
            font=fonts.body_bold,
            command=self.toggle,
        )
        self.header.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self.body = ctk.CTkFrame(self.frame, fg_color="transparent", corner_radius=0)
        self.body.columnconfigure(0, weight=1)
        tr.on_change(self.update_title)

    def update_title(self) -> None:
        arrow = "▾" if self.is_open.get() else "▸"
        extra = self.suffix() if self.suffix else ""
        self.header.configure(text=f"  {arrow}   {self.tr(self.key)}{extra}")

    def toggle(self) -> None:
        if self._reveal is not None:
            self._reveal.cancel()
            self._reveal = None
        self.is_open.set(not self.is_open.get())
        if self.is_open.get():
            self.body.grid(row=1, column=0, sticky="ew", padx=(42, 16), pady=(0, 14))
            self._reveal = Reveal(self.body, self.frame, theme.SURFACE)
        else:
            self.body.grid_remove()
        self.update_title()

    def invoke(self) -> None:
        self.toggle()


class WrappedCheck:
    """A checkbox whose translated text wraps; clicking the text toggles the box too."""

    def __init__(
        self,
        tr: Translator,
        parent: Any,
        variable: Any,
        key: str,
        fonts: theme.Fonts,
        wrap: int = WRAP - 60,
    ) -> None:
        import customtkinter as ctk

        self.frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        self.frame.columnconfigure(1, weight=1)
        self.check = ctk.CTkCheckBox(
            self.frame,
            text="",
            width=24,
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=5,
            border_width=2,
            variable=variable,
            fg_color=theme.GREEN,
            hover_color=theme.GREEN_HOVER,
            border_color=theme.FAINT,
            checkmark_color=theme.ON_GREEN,
        )
        self.check.grid(row=0, column=0, sticky="nw", pady=(2, 0))
        self.label = text(tr, self.frame, key, font=fonts.body, wrap=wrap)
        self.label.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.label.bind("<Button-1>", lambda _event: self.invoke())
        self.enabled = True

    def invoke(self) -> None:
        if self.enabled:
            self.check.toggle()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.check.configure(state="normal" if enabled else "disabled")
        self.label.configure(text_color=theme.INK if enabled else theme.FAINT)

    def grid(self, **options: Any) -> None:
        self.frame.grid(**options)

    def grid_remove(self) -> None:
        self.frame.grid_remove()


class ModeCard:
    """A selectable card in the sidebar: a small drawing, a title and one line of description."""

    def __init__(
        self,
        tr: Translator,
        parent: Any,
        title_key: str,
        description_key: str,
        draw_icon: Callable[[Any, float], None],
        command: Callable[[], None],
        fonts: theme.Fonts,
    ) -> None:
        import tkinter as tk

        self.command = command
        self.draw_icon = draw_icon
        self.selected = False
        self.frame = card(parent, border_width=2, fg_color=theme.SURFACE, cursor="hand2")
        self.frame.columnconfigure(1, weight=1)
        self.icon = tk.Canvas(self.frame, width=56, height=44, highlightthickness=0, borderwidth=0)
        self.icon.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=12, sticky="n")
        self.title = text(tr, self.frame, title_key, font=fonts.body_bold, wrap=150)
        self.title.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=(12, 0))
        self.description = text(tr, self.frame, description_key, font=fonts.small, color=theme.MUTED, wrap=150)
        self.description.grid(row=1, column=1, sticky="nw", padx=(0, 12), pady=(2, 12))
        for widget in (self.frame, self.icon, self.title, self.description):
            widget.bind("<Button-1>", lambda _event: self.invoke())
            for child in widget.winfo_children():
                child.bind("<Button-1>", lambda _event: self.invoke())
        self.refresh()

    def invoke(self) -> None:
        self.command()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.refresh()

    def refresh(self) -> None:
        self.frame.configure(
            border_color=theme.GREEN if self.selected else theme.LINE,
            fg_color=theme.GREEN_SOFT if self.selected else theme.SURFACE,
        )
        background = theme.pick(theme.GREEN_SOFT if self.selected else theme.SURFACE)
        scale = theme.widget_scaling(self.icon)
        self.icon.configure(background=background, width=int(56 * scale), height=int(44 * scale))
        self.icon.delete("all")
        self.draw_icon(self.icon, scale)


def segmented(parent: Any, values: list[str], command: Callable[[str], None], fonts: theme.Fonts) -> Any:
    import customtkinter as ctk

    return ctk.CTkSegmentedButton(
        parent,
        values=values,
        command=command,
        font=fonts.small,
        height=28,
        corner_radius=8,
        fg_color=theme.SURFACE_ALT,
        selected_color=theme.SURFACE,
        selected_hover_color=theme.SURFACE,
        unselected_color=theme.SURFACE_ALT,
        unselected_hover_color=theme.LINE,
        text_color=theme.INK,
    )


def language_switch(tr: Translator, parent: Any, fonts: theme.Fonts) -> Any:
    names = list(LANGUAGES.values())
    codes = {name: code for code, name in LANGUAGES.items()}
    switch = segmented(parent, names, lambda name: tr.set_language(codes[name]), fonts)
    switch.set(LANGUAGES[tr.language])
    return switch


def appearance_switch(
    tr: Translator, parent: Any, fonts: theme.Fonts, on_change: Callable[[], None], remember: bool = True
) -> Any:
    """System / light / dark. ``on_change`` repaints what CustomTkinter does not (canvases)."""
    current = {"value": theme.load_appearance() if remember else "system"}
    switch = segmented(parent, [tr(f"theme.{value}") for value in theme.APPEARANCES], lambda _label: None, fonts)

    def labels() -> dict[str, str]:
        return {tr(f"theme.{value}"): value for value in theme.APPEARANCES}

    def chosen(label: str) -> None:
        value = labels().get(label, "system")
        current["value"] = value
        theme.apply_appearance(value, remember)
        on_change()

    def relabel() -> None:
        names = list(labels())
        switch.configure(values=names, command=chosen)
        switch.set(next(name for name, value in labels().items() if value == current["value"]))

    tr.on_change(relabel)
    return switch


def swatch(parent: Any, fill: theme.Color | str, outline: theme.Color) -> Any:
    import customtkinter as ctk

    return ctk.CTkFrame(
        parent,
        width=14,
        height=14,
        corner_radius=4,
        border_width=2,
        border_color=outline,
        fg_color=fill if fill else "transparent",
    )


def primary_button(parent: Any, command: Callable[[], None], fonts: theme.Fonts) -> Any:
    import customtkinter as ctk

    return ctk.CTkButton(
        parent,
        text="",
        command=command,
        height=38,
        corner_radius=9,
        font=fonts.body_bold,
        fg_color=theme.GREEN,
        hover_color=theme.GREEN_HOVER,
        text_color=theme.ON_GREEN,
        text_color_disabled=theme.FAINT,
    )


def secondary_button(parent: Any, command: Callable[[], None], fonts: theme.Fonts, height: int = 38) -> Any:
    import customtkinter as ctk

    return ctk.CTkButton(
        parent,
        text="",
        command=command,
        height=height,
        corner_radius=9,
        font=fonts.body,
        fg_color="transparent",
        hover_color=theme.SURFACE_ALT,
        border_width=1,
        border_color=theme.LINE,
        text_color=theme.INK,
    )
