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
