"""Small Tk helpers shared by the Layer Rescue windows."""

from __future__ import annotations

from typing import Any

from .i18n import LANGUAGES, Translator

WRAP = 560
HINT_COLOR = "#5f6670"
NOTE_COLOR = "#9a4d00"
OK_COLOR = "#166534"


def set_window_icon(root: Any) -> None:
    """Use the Layer Rescue icon instead of Tk's default feather (title bar, task bar, dialogs)."""
    import sys
    import tkinter as tk
    from pathlib import Path

    assets = Path(__file__).with_name("assets")
    try:
        if sys.platform == "win32":
            root.iconbitmap(default=str(assets / "icon.ico"))
        image = tk.PhotoImage(master=root, file=str(assets / "icon.png"))
        root.iconphoto(True, image)
        root._layer_rescue_icon = image  # Tk forgets images that Python no longer references
    except (tk.TclError, OSError):
        pass  # A missing icon is cosmetic; never block the window over it.


def text_label(tr: Translator, parent: Any, key: str, **options: Any) -> Any:
    """A ttk.Label whose text follows the selected language."""
    from tkinter import ttk

    label = ttk.Label(parent, **options)
    tr.on_change(lambda: label.configure(text=tr(key)))
    return label


def language_switch(tr: Translator, parent: Any) -> Any:
    """Toggle buttons for the window language (no restart needed)."""
    import tkinter as tk
    from tkinter import ttk

    frame = ttk.Frame(parent)
    text_label(tr, frame, "header.language").grid(row=0, column=0, padx=(0, 6))
    choice = tk.StringVar(value=tr.language)
    for column, (code, name) in enumerate(LANGUAGES.items(), start=1):
        ttk.Radiobutton(
            frame,
            text=name,
            value=code,
            variable=choice,
            style="Toolbutton",
            command=lambda: tr.set_language(choice.get()),
        ).grid(row=0, column=column, padx=1)
    return frame


def wrapped_check(tr: Translator, parent: Any, variable: Any, key: str, wraplength: int, **label_options: Any) -> Any:
    """A checkbox whose (translated) text wraps. Clicking the text toggles the box, like a normal checkbox."""
    from tkinter import ttk

    frame = ttk.Frame(parent)
    check = ttk.Checkbutton(frame, variable=variable)
    check.grid(row=0, column=0, sticky="nw")
    label = text_label(tr, frame, key, wraplength=wraplength, justify="left", **label_options)
    label.grid(row=0, column=1, sticky="w")
    label.bind("<Button-1>", lambda _event: check.invoke() if check.instate(["!disabled"]) else None)
    frame.check = check  # type: ignore[attr-defined]
    frame.label = label  # type: ignore[attr-defined]
    return frame


def frame_background() -> str:
    """The ttk frame background of the current theme (plain Tk widgets such as Canvas use it to blend in)."""
    from tkinter import ttk

    return ttk.Style().lookup("TFrame", "background") or "#d9d9d9"


# Widgets that take keyboard focus themselves (Tab); containers around them are ignored.
FOCUS_CLASSES = {"TEntry", "Entry", "TCheckbutton", "Checkbutton", "TRadiobutton", "TButton", "TCombobox", "TSpinbox"}


class ScrollArea:
    """A frame that scrolls vertically when its content is taller than the room on screen.

    The canvas asks for the content's full size, capped at ``max_height``; the scroll bar shows only when the
    content does not fit. The mouse wheel scrolls it wherever the pointer is inside the area, and a field that
    gets keyboard focus is scrolled into view.
    """

    def __init__(self, parent: Any) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.max_height: int | None = None
        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self.frame, highlightthickness=0, borderwidth=0, background=frame_background(), yscrollincrement=24
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _event: self.refresh())
        self.canvas.bind("<Configure>", self._view_changed)
        root = parent.winfo_toplevel()
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind_all(sequence, self._wheel, add="+")
        root.bind_all("<FocusIn>", self._focus, add="+")

    def refresh(self) -> None:
        width, height = self.inner.winfo_reqwidth(), self.inner.winfo_reqheight()
        visible = min(height, self.max_height) if self.max_height else height
        self.canvas.configure(scrollregion=(0, 0, width, height), width=width, height=visible)
        self._update_bar()

    def _view_changed(self, event: Any) -> None:
        self.canvas.itemconfigure(self._window, width=max(event.width, self.inner.winfo_reqwidth()))
        self._update_bar()

    def scrollable(self) -> bool:
        return self.inner.winfo_reqheight() > self.canvas.winfo_height() + 1

    def _update_bar(self) -> None:
        if self.scrollable():
            self.bar.grid(row=0, column=1, sticky="ns")
        else:
            self.bar.grid_remove()
            self.canvas.yview_moveto(0)

    def _inside(self, widget: Any) -> bool:
        return widget is not None and str(widget).startswith(str(self.canvas))

    def _wheel(self, event: Any) -> None:
        if not self.scrollable():
            return
        try:
            widget = self.canvas.winfo_containing(event.x_root, event.y_root)
        except (KeyError, RuntimeError):  # pointer over a menu or another window
            return
        if not self._inside(widget):
            return
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-1, "units")
        else:
            self.canvas.yview_scroll(1, "units")

    def _offset_in_content(self, widget: Any) -> int | None:
        """Top of ``widget`` measured from the top of the scrolled content, or None if it is not inside it."""
        y = 0
        while widget is not None and widget is not self.inner:
            y += widget.winfo_y()
            widget = widget.master
        return y if widget is self.inner else None

    def _focus(self, event: Any) -> None:
        """Scroll just enough to show a field that got keyboard focus (Tab) and is outside the view."""
        widget = event.widget
        if not self._inside(widget) or not hasattr(widget, "winfo_class") or not self.canvas.winfo_viewable():
            return
        if widget.winfo_class() not in FOCUS_CLASSES:  # FocusIn also reaches every frame around the field
            return
        if not self.scrollable():
            return
        top = self._offset_in_content(widget)
        if top is None:
            return
        bottom = top + widget.winfo_height()
        view_top = self.canvas.canvasy(0)
        view_height = self.canvas.winfo_height()
        total = max(self.inner.winfo_reqheight(), 1)
        if top < view_top:
            self.canvas.yview_moveto(max(top - 8, 0) / total)
        elif bottom > view_top + view_height:
            self.canvas.yview_moveto(max(bottom + 8 - view_height, 0) / total)


class Collapsible:
    """A titled section whose body opens and closes when the title is clicked (closed by default)."""

    def __init__(self, tr: Translator, parent: Any, key: str, suffix: Any = None) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tr = tr
        self.key = key
        self.suffix = suffix  # callable returning extra title text, e.g. "(2 on)"
        self.is_open = tk.BooleanVar(value=False)
        self.frame = ttk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.header = ttk.Label(self.frame, font=("TkDefaultFont", 10, "bold"), cursor="hand2")
        self.header.grid(row=0, column=0, sticky="w", pady=(2, 2))
        self.header.bind("<Button-1>", lambda _event: self.toggle())
        self.header.invoke = self.toggle  # type: ignore[attr-defined]  # keyboard-free tests and scripts
        ttk.Separator(self.frame).grid(row=1, column=0, sticky="ew")
        self.body = ttk.Frame(self.frame, padding=(14, 6, 0, 4))
        self.body.columnconfigure(0, weight=1)
        tr.on_change(self.update_title)

    def update_title(self) -> None:
        arrow = "▾" if self.is_open.get() else "▸"
        extra = self.suffix() if self.suffix else ""
        self.header.configure(text=f"{arrow} {self.tr(self.key)}{extra}")

    def toggle(self) -> None:
        self.is_open.set(not self.is_open.get())
        if self.is_open.get():
            self.body.grid(row=2, column=0, sticky="ew")
        else:
            self.body.grid_remove()
        self.update_title()
