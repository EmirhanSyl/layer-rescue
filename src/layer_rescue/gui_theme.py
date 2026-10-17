"""Colours, fonts and the light/dark setting of the Layer Rescue window.

The palette comes from the app icon: amber is what is already printed (the old part), green is what
Layer Rescue adds (the new layers, the main button, the chosen mode). Every colour is a (light, dark)
pair, which CustomTkinter widgets switch by themselves; plain Tk canvases ask :func:`pick`.
"""

from __future__ import annotations

import sys
from typing import Any

from .i18n import load_setting, save_setting

Color = tuple[str, str]

BG: Color = ("#ECEFF2", "#14171B")  # window
SIDEBAR: Color = ("#E2E6EB", "#1A1E23")
SURFACE: Color = ("#FFFFFF", "#20252B")  # cards
SURFACE_ALT: Color = ("#F3F5F7", "#272D34")  # fields, hover
LINE: Color = ("#D3D9E0", "#333A42")
INK: Color = ("#1C2228", "#E8EBEE")
MUTED: Color = ("#5A6470", "#9BA5B0")
FAINT: Color = ("#8A939D", "#6E7882")

AMBER: Color = ("#D98E1F", "#E5A43C")  # printed layers
AMBER_SOFT: Color = ("#F6E3C4", "#4A3A22")
WARN: Color = ("#8F5300", "#F0B455")  # warning text
WARN_SOFT: Color = ("#FBF0DF", "#2E271C")  # warning banner

GREEN: Color = ("#1E8656", "#33B077")  # new layers, main action, chosen mode
GREEN_HOVER: Color = ("#176B45", "#2B9666")
GREEN_SOFT: Color = ("#E4F3EA", "#1B2E25")
ON_GREEN: Color = ("#FFFFFF", "#0E1A14")

RED: Color = ("#C2372B", "#EE6A5E")
SUPPORT: Color = ("#6E55B8", "#A28BE8")  # reprinted supports in the top view
NOZZLE: Color = ("#39424C", "#C9D0D7")
HEAT: Color = ("#F07A22", "#FF9440")

APPEARANCES = ("system", "light", "dark")
RADIUS = 10
PAD = 16  # outer padding; inner spacing is 8 or 12


def font_family() -> str:
    if sys.platform == "win32":
        return "Segoe UI"
    if sys.platform == "darwin":
        return "Helvetica Neue"
    return "DejaVu Sans"


class Fonts:
    """CustomTkinter fonts (they follow the window scaling). Create after the root window."""

    def __init__(self) -> None:
        import customtkinter as ctk

        family = font_family()
        self.title = ctk.CTkFont(family=family, size=21, weight="bold")
        self.heading = ctk.CTkFont(family=family, size=15, weight="bold")
        self.body = ctk.CTkFont(family=family, size=13)
        self.body_bold = ctk.CTkFont(family=family, size=13, weight="bold")
        self.small = ctk.CTkFont(family=family, size=12)
        self.small_bold = ctk.CTkFont(family=family, size=12, weight="bold")
        self.badge = ctk.CTkFont(family=family, size=12, weight="bold")


def is_dark() -> bool:
    import customtkinter as ctk

    return ctk.get_appearance_mode().lower() == "dark"


def pick(color: Color) -> str:
    """The light or dark half of ``color`` for plain Tk widgets such as canvases."""
    return color[1] if is_dark() else color[0]


def load_appearance() -> str:
    value = load_setting("appearance")
    return value if value in APPEARANCES else "system"


def apply_appearance(value: str, remember: bool = True) -> None:
    import customtkinter as ctk

    ctk.set_appearance_mode(value if value in APPEARANCES else "system")
    if remember:
        save_setting("appearance", value)


def widget_scaling(widget: Any) -> float:
    """CustomTkinter's scaling for ``widget`` (Windows display scaling); canvases draw with it."""
    try:
        from customtkinter import ScalingTracker

        return float(ScalingTracker.get_widget_scaling(widget))
    except Exception:  # noqa: BLE001 - older/newer CustomTkinter internals: draw unscaled
        return 1.0
