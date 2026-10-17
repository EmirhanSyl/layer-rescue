"""The Layer Rescue window (CustomTkinter).

Layout: a sidebar with the three "what happened?" cards, the sliced file and the language/theme switches;
a scrolling main column with an animated drawing of the chosen mode and its steps; a bar at the bottom
with the status and the buttons. Test scripts find the main controls in ``root._lr``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import gui_theme as theme
from ._version import __version__
from .core import ResumeError, ResumeOptions, ZReferenceMode, analyze_gcode, rewrite_gcode_file
from .gui_art import MODE_ICONS, Illustration
from .gui_insert import build_insert_tab
from .gui_widgets import (
    WRAP,
    Collapsible,
    ModeCard,
    StepCard,
    StepFlow,
    WrappedCheck,
    appearance_switch,
    card,
    field,
    language_switch,
    primary_button,
    secondary_button,
    set_enabled,
    set_window_icon,
    text,
)
from .i18n import Translator
from .machine_state import untested_setup

MODES = ("retained", "manual", "insert")
SIDEBAR_WIDTH = 270
MAIN_WIDTH = 720
SCREEN_MARGIN = 110  # room for the title bar and the task bar / dock


def _bring_to_front(root: Any) -> None:
    root.after(100, lambda: (root.lift(), root.attributes("-topmost", True), root.focus_force()))
    root.after(700, lambda: root.attributes("-topmost", False))


def _fit_to_screen(root: Any) -> None:
    """Open as large as the content wants, but never larger than the screen; the main column scrolls."""
    root.update_idletasks()
    scaling = theme.widget_scaling(root) or 1.0
    screen_w = root.winfo_screenwidth() / scaling
    screen_h = root.winfo_screenheight() / scaling
    width = int(min(SIDEBAR_WIDTH + MAIN_WIDTH + 60, screen_w - 40))
    height = int(min(820, screen_h - SCREEN_MARGIN))
    x = int(max(0, (screen_w - width) / 2) * scaling)
    root.geometry(f"{width}x{height}+{x}+{int(16 * scaling)}")
    root.minsize(min(760, width), min(520, height))


def _brand(parent: Any, fonts: theme.Fonts, tr: Translator, background: theme.Color = theme.SIDEBAR) -> Any:
    import tkinter as tk

    import customtkinter as ctk

    frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
    icon_path = Path(__file__).with_name("assets") / "icon.png"
    try:
        image = tk.PhotoImage(master=parent, file=str(icon_path))
        factor = max(1, round(image.width() / (36 * theme.widget_scaling(parent))))
        image = image.subsample(factor)
        logo = tk.Label(frame, image=image, borderwidth=0, background=theme.pick(background))
        logo.image = image  # type: ignore[attr-defined]
        logo.grid(row=0, column=0, rowspan=2, padx=(0, 10))
        frame._logo = (logo, background)  # type: ignore[attr-defined]
    except (tk.TclError, OSError):
        pass
    text(tr, frame, "app.title", font=fonts.heading).grid(row=0, column=1, sticky="sw")
    text(tr, frame, "header.version", font=fonts.small, color=theme.MUTED, version=__version__).grid(
        row=1, column=1, sticky="nw"
    )
    return frame


def _repaint_logo(brand: Any) -> None:
    logo = getattr(brand, "_logo", None)
    if logo is not None:
        label, background = logo
        label.configure(background=theme.pick(background))


def launch(path: Path, translator: Translator | None = None) -> int:
    tr = translator or Translator()
    try:
        import tkinter as tk
        from tkinter import messagebox

        import customtkinter as ctk
    except ImportError:
        raise ResumeError(tr("error.tk_missing"))

    remember = tr.remember
    theme.apply_appearance(theme.load_appearance() if remember else "system", remember=False)
    try:
        root = ctk.CTk(fg_color=theme.BG)
    except tk.TclError as exc:
        raise ResumeError(tr("error.no_window", error=exc)) from exc
    set_window_icon(root)
    fonts = theme.Fonts()

    try:
        analysis = analyze_gcode(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ResumeError) as exc:
        root.withdraw()
        messagebox.showerror("Layer Rescue", tr.message(str(exc)))
        root.destroy()
        return 2

    root.title("Layer Rescue")
    result = {"code": 0}
    controls: dict[str, Any] = {}
    root._lr = controls  # type: ignore[attr-defined]
    repaints: list[Any] = []

    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    # ------------------------------------------------------------- sidebar
    sidebar = ctk.CTkFrame(root, width=SIDEBAR_WIDTH, corner_radius=0, fg_color=theme.SIDEBAR)
    sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
    sidebar.grid_propagate(False)
    sidebar.columnconfigure(0, weight=1)
    brand = _brand(sidebar, fonts, tr)
    brand.grid(row=0, column=0, sticky="w", padx=theme.PAD, pady=(18, 18))
    text(tr, sidebar, "mode.heading", font=fonts.small_bold, color=theme.MUTED).grid(
        row=1, column=0, sticky="w", padx=theme.PAD, pady=(0, 8)
    )

    mode_var = tk.StringVar(value="retained")
    cards: dict[str, ModeCard] = {}
    for index, mode in enumerate(MODES):
        mode_card = ModeCard(
            tr,
            sidebar,
            f"mode.{mode}",
            f"mode.{mode}_desc",
            MODE_ICONS[mode],
            lambda mode=mode: select_mode(mode),
            fonts,
        )
        mode_card.frame.grid(row=2 + index, column=0, sticky="ew", padx=(12, 12), pady=(0, 8))
        cards[mode] = mode_card
        controls[f"mode_{mode}"] = mode_card
    sidebar.rowconfigure(5, weight=1)

    file_box = ctk.CTkFrame(sidebar, fg_color="transparent", corner_radius=0)
    file_box.grid(row=6, column=0, sticky="ew", padx=theme.PAD, pady=(8, 10))
    file_box.columnconfigure(1, weight=1)
    file_name = text(tr, file_box, None, font=fonts.small_bold, wrap=SIDEBAR_WIDTH - 40)
    file_name.configure(text=path.name)
    file_name.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
    rows = [
        ("file.printer", lambda: analysis.printer_model),
        ("file.filament", lambda: analysis.filament_type),
        (
            "file.layers",
            lambda: tr(
                "file.layers_value", first=analysis.first_layer, last=analysis.last_layer, total=analysis.total_layers
            ),
        ),
    ]
    for row, (key, value) in enumerate(rows, start=1):
        text(tr, file_box, key, font=fonts.small, color=theme.MUTED).grid(row=row, column=0, sticky="w", padx=(0, 10))
        value_label = text(tr, file_box, None, font=fonts.small, wrap=150)
        value_label.grid(row=row, column=1, sticky="w")
        tr.on_change(lambda value_label=value_label, value=value: value_label.configure(text=value()))

    switches = ctk.CTkFrame(sidebar, fg_color="transparent", corner_radius=0)
    switches.grid(row=7, column=0, sticky="ew", padx=theme.PAD, pady=(4, 18))
    switches.columnconfigure(0, weight=1)
    language_switch(tr, switches, fonts).grid(row=0, column=0, sticky="ew", pady=(0, 6))
    appearance = appearance_switch(tr, switches, fonts, lambda: repaint_all(), remember=remember)
    appearance.grid(row=1, column=0, sticky="ew")
    controls["appearance"] = appearance

    # ---------------------------------------------------------- main column
    main = ctk.CTkScrollableFrame(
        root,
        corner_radius=0,
        fg_color=theme.BG,
        scrollbar_button_color=theme.LINE,
        scrollbar_button_hover_color=theme.FAINT,
    )
    main.grid(row=0, column=1, sticky="nsew")
    main.columnconfigure(0, weight=1)
    content = ctk.CTkFrame(main, fg_color="transparent", corner_radius=0)
    content.grid(row=0, column=0, sticky="nsew", padx=(22, 14), pady=(18, 12))
    content.columnconfigure(0, weight=1)
    controls["main"] = main

    # A job outside what has been tested (other printer, several filaments): explain and let the user opt in.
    untested = untested_setup(analysis)
    untested_var = tk.BooleanVar(value=False)
    if untested:
        banner = card(content, fg_color=theme.WARN_SOFT, border_color=theme.AMBER)
        banner.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        banner.columnconfigure(0, weight=1)
        text(tr, banner, "untested.frame", font=fonts.body_bold, color=theme.WARN).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 2)
        )
        text(tr, banner, "untested.intro", font=fonts.body, wrap=WRAP).grid(row=1, column=0, sticky="w", padx=16)
        reasons = text(tr, banner, None, font=fonts.small, color=theme.WARN, wrap=WRAP)
        reasons.grid(row=2, column=0, sticky="w", padx=16, pady=(6, 6))
        tr.on_change(lambda: reasons.configure(text="\n".join("• " + tr.message(reason) for reason in untested)))
        untested_check = WrappedCheck(tr, banner, untested_var, "untested.check", fonts, wrap=WRAP - 40)
        untested_check.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 14))
        controls["untested"] = untested_check

    # Hero: what this mode does, with its drawing.
    hero = ctk.CTkFrame(content, fg_color="transparent", corner_radius=0)
    hero.grid(row=1, column=0, sticky="ew", pady=(0, 16))
    hero.columnconfigure(0, weight=1)
    hero_title = text(tr, hero, None, font=fonts.title, wrap=340)
    hero_title.grid(row=0, column=0, sticky="nw", pady=(4, 6))
    hero_lead = text(tr, hero, None, font=fonts.body, color=theme.MUTED, wrap=340)
    hero_lead.grid(row=1, column=0, sticky="nw")
    art_box = card(hero, fg_color=theme.SURFACE)
    art_box.grid(row=0, column=1, rowspan=3, sticky="ne", padx=(18, 0))
    illustration = Illustration(art_box, "retained")
    illustration.canvas.grid(row=0, column=0, padx=8, pady=8)
    repaints.append(illustration.repaint)
    controls["illustration"] = illustration
    text(tr, hero, "mode.replay", font=fonts.small, color=theme.FAINT, wrap=340).grid(
        row=2, column=0, sticky="sw", pady=(8, 0)
    )

    # ------------------------------------------------------------ resume panel
    resume = ctk.CTkFrame(content, fg_color="transparent", corner_radius=0)
    resume.columnconfigure(0, weight=1)

    last_layer_var = tk.StringVar()
    height_var = tk.StringVar()
    nozzle_var = tk.StringVar()
    bed_var = tk.StringVar()
    home_var = tk.BooleanVar(value=True)
    z_mode_var = tk.StringVar(value=ZReferenceMode.RETAINED.value)
    retained_confirm_var = tk.BooleanVar(value=False)
    manual_confirm_var = tk.BooleanVar(value=False)
    attached_var = tk.BooleanVar(value=False)

    # Step 1: where did it stop?
    step1 = StepCard(tr, resume, 1, "resume.step1", fonts)
    step1.frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    # Either the last good layer or the part's measured height (the nearest layer is used), as in insert mode.
    row1 = ctk.CTkFrame(step1.body, fg_color="transparent", corner_radius=0)
    row1.grid(row=0, column=0, sticky="w")
    text(tr, row1, "resume.last_layer", font=fonts.body).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=3)
    last_entry = field(row1, last_layer_var, width=100)
    last_entry.grid(row=0, column=1, sticky="w", pady=3)
    controls["last_layer"] = last_entry
    text(tr, row1, "resume.part_height", font=fonts.body, color=theme.MUTED).grid(
        row=1, column=0, sticky="w", padx=(0, 10), pady=3
    )
    height_entry = field(row1, height_var, width=100)
    height_entry.grid(row=1, column=1, sticky="w", pady=3)
    controls["resume_height"] = height_entry
    next_layer_label = text(tr, step1.body, None, font=fonts.body_bold, color=theme.GREEN, wrap=WRAP)
    next_layer_label.grid(row=1, column=0, sticky="w", pady=(8, 0))
    text(tr, step1.body, "resume.last_layer_hint", font=fonts.small, color=theme.MUTED, wrap=WRAP).grid(
        row=2, column=0, sticky="w", pady=(6, 0)
    )

    # Layers a resume can start after, and the heights a measured part can map to.
    candidates = [layer for layer in analysis.layers if analysis.first_layer <= layer.number < analysis.last_layer]
    filling = {"active": False, "from_height": None}

    def last_layer() -> int | None:
        try:
            number = int(last_layer_var.get().strip())
        except ValueError:
            return None
        return number if analysis.first_layer <= number < analysis.last_layer else None

    def nearest_layer(height: float) -> Any:
        """The layer whose top is closest to a measured height, or None outside the printable range."""
        if not candidates:
            return None
        best = min(candidates, key=lambda layer: abs(layer.z - height))
        thickness = max(0.05, candidates[1].z - candidates[0].z) if len(candidates) > 1 else 0.2
        return best if abs(best.z - height) <= thickness else None

    def height_changed(*_: object) -> None:
        if filling["active"]:
            return
        value = height_var.get().strip().replace(",", ".")
        filling["from_height"] = None
        layer = None
        if value:
            try:
                layer = nearest_layer(float(value))
            except ValueError:
                layer = None
            filling["from_height"] = value
        filling["active"] = True
        last_layer_var.set(str(layer.number) if layer is not None else "")
        filling["active"] = False

    def layer_changed(*_: object) -> None:
        if filling["active"]:
            return
        filling["from_height"] = None
        number = last_layer()
        filling["active"] = True
        height_var.set(f"{analysis.layer(number).z:g}" if number is not None else "")
        filling["active"] = False

    height_var.trace_add("write", height_changed)
    last_layer_var.trace_add("write", layer_changed)

    def update_next_layer(*_: object) -> None:
        number = last_layer()
        complete = False
        lines: list[str] = []
        color = theme.GREEN
        if number is not None:
            try:
                start = analysis.layer(number + 1)
            except ResumeError:
                start = None
            if start is not None:
                if filling["from_height"]:
                    lines.append(
                        tr(
                            "resume.nearest_layer",
                            height=float(filling["from_height"]),
                            layer=number,
                            z=analysis.layer(number).z,
                        )
                    )
                lines.append(tr("resume.next_layer", layer=start.number, total=analysis.total_layers, z=start.z))
                complete = True
                flow.update(0, True, tr("resume.step1_summary", last=number, layer=start.number))
        if not complete:
            color = theme.WARN
            if filling["from_height"]:
                low, high = (candidates[0].z, candidates[-1].z) if candidates else (0.0, 0.0)
                lines.append(tr("resume.height_range", low=low, high=high))
            elif last_layer_var.get().strip():
                lines.append(tr("resume.layer_range", first=analysis.first_layer, last=analysis.last_layer - 1))
            flow.update(0, False)
        next_layer_label.configure(text="\n".join(lines), text_color=color)
        if lines:
            next_layer_label.grid()
        else:
            next_layer_label.grid_remove()  # no empty gap above the hint

    # Step 2: safety checks (what to do before sending depends on the mode)
    step2 = StepCard(tr, resume, 2, "resume.step3", fonts)
    step2.frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
    mode_help = text(tr, step2.body, None, font=fonts.body, wrap=WRAP)
    mode_help.grid(row=0, column=0, sticky="w", pady=(0, 10))
    text(tr, step2.body, "resume.checks_intro", font=fonts.small, color=theme.MUTED, wrap=WRAP).grid(
        row=1, column=0, sticky="w", pady=(0, 8)
    )
    checks = {
        "attached": WrappedCheck(tr, step2.body, attached_var, "resume.check_attached", fonts),
        "retained": WrappedCheck(tr, step2.body, retained_confirm_var, "resume.check_retained", fonts),
        "manual": WrappedCheck(tr, step2.body, manual_confirm_var, "resume.check_manual", fonts),
    }
    for row, (check_name, check) in enumerate(checks.items(), start=2):
        check.grid(row=row, column=0, sticky="w", pady=3)
        controls[f"check_{check_name}"] = check

    def reveal(widget: Any) -> None:
        """Scroll the main column just enough to show ``widget`` (a step that has just opened)."""
        try:
            root.update_idletasks()
            canvas = main._parent_canvas
            total = max(main.winfo_height(), 1)
            top = widget.winfo_rooty() - main.winfo_rooty()
            bottom = top + widget.winfo_height()
            view_top = canvas.canvasy(0)
            view_height = canvas.winfo_height()
            if bottom > view_top + view_height:
                target = max(0.0, min(top - 12, bottom + 16 - view_height))
            elif top < view_top:
                target = max(0.0, top - 12)
            else:
                return
        except (AttributeError, tk.TclError):
            return
        # Glide there in a few frames instead of jumping.
        start = view_top
        frames = 10

        def glide(index: int) -> None:
            try:
                t = index / frames
                eased = 1 - (1 - t) ** 3
                canvas.yview_moveto((start + (target - start) * eased) / total)
                if index < frames:
                    root.after(16, lambda: glide(index + 1))
            except tk.TclError:
                pass

        glide(1)

    flow = StepFlow([step1, step2], reveal)
    repaints.extend([step1.repaint, step2.repaint])
    controls["resume_steps"] = flow
    controls["resume_step_1"], controls["resume_step_2"] = step1, step2

    def update_checks(*_: object) -> None:
        manual = z_mode_var.get() == ZReferenceMode.MANUAL.value
        confirmed = manual_confirm_var.get() if manual else retained_confirm_var.get()
        flow.update(1, bool(attached_var.get() and confirmed), tr("step.checked"))

    for var in (attached_var, retained_confirm_var, manual_confirm_var, z_mode_var):
        var.trace_add("write", update_checks)
    tr.on_change(update_checks)

    # Options (folded)
    options = Collapsible(tr, resume, "resume.options", fonts)
    options.frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
    controls["resume_options"] = options
    temps = ctk.CTkFrame(options.body, fg_color="transparent", corner_radius=0)
    temps.grid(row=0, column=0, sticky="w")
    for row, (key, var) in enumerate([("resume.nozzle", nozzle_var), ("resume.bed", bed_var)]):
        text(tr, temps, key, font=fonts.body).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
        field(temps, var, width=80).grid(row=row, column=1, sticky="w", pady=3)
        text(tr, temps, "resume.temp_hint", font=fonts.small, color=theme.MUTED).grid(
            row=row, column=2, sticky="w", padx=(10, 0)
        )
    home_check = WrappedCheck(tr, options.body, home_var, "resume.home", fonts)
    home_check.grid(row=1, column=0, sticky="w", pady=(8, 0))

    # Experimental features (folded); the title says how many are on.
    reheat_var = tk.BooleanVar(value=False)
    reheat_values = {
        "gap": tk.StringVar(value="0.2"),
        "speed": tk.StringVar(value="20"),
        "passes": tk.StringVar(value="1"),
        "temp": tk.StringVar(value=""),
    }
    experimental = Collapsible(
        tr,
        resume,
        "insert.experimental",
        fonts,
        suffix=lambda: tr("insert.experimental_on", n=1) if reheat_var.get() else "",
    )
    experimental.frame.grid(row=3, column=0, sticky="ew")
    controls["resume_experimental"] = experimental
    text(tr, experimental.body, "insert.experimental_intro", font=fonts.small, color=theme.WARN, wrap=WRAP - 40).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
    )
    reheat_check = WrappedCheck(tr, experimental.body, reheat_var, "resume.reheat", fonts, wrap=WRAP - 330)
    reheat_check.grid(row=1, column=0, sticky="nw")
    controls["resume_reheat"] = reheat_check
    reheat_art = Illustration(experimental.body, "reheat", background=theme.SURFACE_ALT)
    reheat_art.canvas.grid(row=1, column=1, rowspan=3, sticky="ne", padx=(12, 0))
    repaints.append(reheat_art.repaint)
    text(tr, experimental.body, "resume.reheat_hint", font=fonts.small, color=theme.MUTED, wrap=WRAP - 330).grid(
        row=2, column=0, sticky="nw", padx=(32, 0), pady=(4, 0)
    )
    reheat_fields = ctk.CTkFrame(experimental.body, fg_color="transparent", corner_radius=0)
    reheat_fields.grid(row=3, column=0, sticky="nw", padx=(32, 0), pady=(8, 0))
    reheat_entries = []
    for index, (value_name, key) in enumerate(
        [
            ("gap", "resume.reheat_gap"),
            ("speed", "insert.reheat_speed"),
            ("passes", "insert.reheat_passes"),
            ("temp", "resume.reheat_temp"),
        ]
    ):
        text(tr, reheat_fields, key, font=fonts.small, wrap=190).grid(row=index, column=0, sticky="w", pady=2, padx=(0, 10))
        entry = field(reheat_fields, reheat_values[value_name], width=70)
        entry.grid(row=index, column=1, sticky="w", pady=2)
        set_enabled(entry, False)
        reheat_entries.append(entry)
        controls[f"reheat_{value_name}"] = entry

    def reheat_changed(*_: object) -> None:
        for entry in reheat_entries:
            set_enabled(entry, reheat_var.get())
        experimental.update_title()
        if reheat_var.get():
            reheat_art.play()

    reheat_var.trace_add("write", reheat_changed)

    def reheat_options() -> dict[str, Any]:
        if not reheat_var.get():
            return {}

        def number(value_name: str, key: str) -> float:
            try:
                return float(reheat_values[value_name].get().strip().replace(",", "."))
            except ValueError:
                raise ResumeError(tr("resume.err_number", field=tr(key).rstrip(":"))) from None

        def whole(value_name: str, key: str) -> int:
            value = number(value_name, key)
            if value != int(value):
                raise ResumeError(tr("resume.err_whole", field=tr(key).rstrip(":")))
            return int(value)

        return {
            "reheat_pass": True,
            "reheat_gap_mm": number("gap", "resume.reheat_gap"),
            "reheat_speed_mm_s": number("speed", "insert.reheat_speed"),
            "reheat_passes": whole("passes", "insert.reheat_passes"),
            "reheat_temperature": whole("temp", "resume.reheat_temp") if reheat_values["temp"].get().strip() else None,
        }

    def update_mode(*_: object) -> None:
        manual = z_mode_var.get() == ZReferenceMode.MANUAL.value
        # Only the check that belongs to the chosen mode is shown, so no box is left without a reason.
        if manual:
            checks["retained"].grid_remove()
            checks["manual"].grid(row=4, column=0, sticky="w", pady=3)
            home_var.set(True)
            home_check.set_enabled(False)
            home_check.label.configure(text=tr("resume.home_forced"))
            mode_help.configure(text=tr("resume.help_manual"))
        else:
            checks["manual"].grid_remove()
            checks["retained"].grid(row=3, column=0, sticky="w", pady=3)
            home_check.set_enabled(True)
            home_check.label.configure(text=tr("resume.home"))
            mode_help.configure(text=tr("resume.help_retained"))

    z_mode_var.trace_add("write", update_mode)
    last_layer_var.trace_add("write", update_next_layer)
    tr.on_change(update_mode)
    tr.on_change(update_next_layer)

    def resume_ready() -> str | None:
        """None when the resume G-code can be created, else the status key to show."""
        if untested and not untested_var.get():
            return "status.untested"
        if last_layer() is None:
            return "status.resume_layer"
        manual = z_mode_var.get() == ZReferenceMode.MANUAL.value
        confirmed = manual_confirm_var.get() if manual else retained_confirm_var.get()
        if not (attached_var.get() and confirmed):
            return "status.resume_checks"
        return None

    def leave_unchanged() -> None:
        result["code"] = 0
        root.destroy()

    def convert() -> None:
        try:
            z_mode = ZReferenceMode(z_mode_var.get())
            if not attached_var.get():
                raise ResumeError(tr("resume.err_attached"))
            if z_mode is ZReferenceMode.RETAINED and not retained_confirm_var.get():
                raise ResumeError(tr("resume.err_retained"))
            if z_mode is ZReferenceMode.MANUAL and not manual_confirm_var.get():
                raise ResumeError(tr("resume.err_manual"))
            try:
                last = int(last_layer_var.get().strip())
            except ValueError:
                raise ResumeError(tr("resume.err_layer")) from None

            def temperature(var: Any, key: str) -> int | None:
                value = var.get().strip()
                if not value:
                    return None
                try:
                    return int(value)
                except ValueError:
                    raise ResumeError(tr("resume.err_temperature", field=tr(key).rstrip(":"))) from None

            reheat = reheat_options()
            report = rewrite_gcode_file(
                path,
                ResumeOptions(
                    start_layer=last + 1,
                    z_reference_mode=z_mode,
                    allow_untested=untested_var.get(),
                    home_corexy=home_var.get(),
                    nozzle_temperature=temperature(nozzle_var, "resume.nozzle"),
                    bed_temperature=temperature(bed_var, "resume.bed"),
                    **reheat,
                ),
            )
            manual = report.z_reference_mode is ZReferenceMode.MANUAL
            mode_text = tr("resume.done_manual", z=report.reference_z) if manual else tr("resume.done_retained")
            messagebox.showinfo(
                "Layer Rescue",
                tr(
                    "resume.done",
                    layer=report.start_layer,
                    total=report.total_layers,
                    z=report.start_z,
                    mode=mode_text,
                    nozzle=report.nozzle_temperature,
                    bed=report.bed_temperature,
                )
                + (tr("resume.done_manual_reminder") if manual else "")
                + (
                    tr(
                        "resume.done_reheat",
                        seconds=report.reheat_seconds,
                        gap=reheat["reheat_gap_mm"],
                        layer=report.start_layer,
                    )
                    if report.reheat_hover_z is not None
                    else ""
                )
                + (
                    "\n\n" + tr("warnings") + "\n- " + "\n- ".join(tr.message(w) for w in report.warnings)
                    if report.warnings
                    else ""
                ),
                parent=root,
            )
            result["code"] = 0
            root.destroy()
        except (ValueError, OSError, ResumeError) as exc:
            messagebox.showerror("Layer Rescue", tr.message(str(exc)), parent=root)

    # ------------------------------------------------------------ insert panel
    # Built the first time its card is chosen: most jobs are resumes, and the window opens faster without it.
    built: dict[str, Any] = {}

    def insert_panel() -> Any:
        if "insert" not in built:
            panel = build_insert_tab(
                content, root, path, analysis, result, tr, fonts, untested_var if untested else None, reveal
            )
            built["insert"] = panel
            controls.update(panel.controls)
            repaints.append(panel.repaint)
            for watched in panel.watched:
                watched.trace_add("write", update_status)
        return built["insert"]

    # ------------------------------------------------------------- bottom bar
    bottom = ctk.CTkFrame(root, fg_color=theme.SURFACE, corner_radius=0)
    bottom.grid(row=1, column=1, sticky="ew")
    bottom.columnconfigure(0, weight=1)
    ctk.CTkFrame(bottom, height=1, corner_radius=0, fg_color=theme.LINE).grid(
        row=0, column=0, columnspan=3, sticky="ew"
    )
    status = text(tr, bottom, None, font=fonts.small, wrap=360)
    status.grid(row=1, column=0, sticky="w", padx=(22, 12), pady=12)
    leave_button = secondary_button(bottom, leave_unchanged, fonts)
    leave_button.grid(row=1, column=1, padx=(0, 10), pady=12)
    create_button = primary_button(bottom, lambda: create(), fonts)
    create_button.grid(row=1, column=2, padx=(0, 18), pady=12)
    tr.on_change(lambda: leave_button.configure(text=tr("button.leave")))
    tr.on_change(lambda: create_button.configure(text=tr("button.create")))
    controls["create"] = create_button
    controls["leave"] = leave_button
    controls["status"] = status

    def update_status(*_: object) -> None:
        missing = insert_panel().ready() if mode_var.get() == "insert" else resume_ready()
        if missing:
            status.configure(text=tr(missing), text_color=theme.WARN)
            create_button.configure(state="disabled", fg_color=theme.LINE)
        else:
            status.configure(text=tr("status.ready"), text_color=theme.GREEN)
            create_button.configure(state="normal", fg_color=theme.GREEN)

    def create() -> None:
        if mode_var.get() == "insert":
            insert_panel().convert()
        else:
            convert()

    # ------------------------------------------------------------- modes
    def show_hero() -> None:
        mode = mode_var.get()
        hero_title.configure(text=tr(f"mode.{mode}_title"))
        hero_lead.configure(text=tr("insert.intro") if mode == "insert" else tr(f"mode.{mode}_lead"))

    def select_mode(mode: str) -> None:
        mode_var.set(mode)
        for key, mode_card in cards.items():
            mode_card.set_selected(key == mode)
        if mode == "insert":
            resume.grid_remove()
            insert_panel().frame.grid(row=2, column=0, sticky="ew")
        else:
            if "insert" in built:
                built["insert"].frame.grid_remove()
            resume.grid(row=2, column=0, sticky="ew")
            z_mode_var.set(ZReferenceMode.MANUAL.value if mode == "manual" else ZReferenceMode.RETAINED.value)
        show_hero()
        illustration.set_scene(mode)
        try:
            main._parent_canvas.yview_moveto(0)
        except (AttributeError, tk.TclError):
            pass
        update_status()

    tr.on_change(show_hero)

    def repaint_all() -> None:
        root.update_idletasks()
        for mode_card in cards.values():
            mode_card.refresh()
        for repaint in repaints:
            repaint()
        _repaint_logo(brand)

    # Follow a system light/dark switch while the window is open.
    seen = {"dark": theme.is_dark()}

    def watch_appearance() -> None:
        if theme.is_dark() != seen["dark"]:
            seen["dark"] = theme.is_dark()
            repaint_all()
        root.after(1500, watch_appearance)

    root.after(1500, watch_appearance)

    for var in (
        last_layer_var, z_mode_var, retained_confirm_var, manual_confirm_var, attached_var, untested_var
    ):
        var.trace_add("write", update_status)
    tr.on_change(update_status)

    select_mode("retained")
    root.protocol("WM_DELETE_WINDOW", leave_unchanged)
    _fit_to_screen(root)
    _bring_to_front(root)
    last_entry.focus_set()
    root.mainloop()
    return result["code"]


def show_setup_info(command: str, translator: Translator | None = None) -> int:
    """Shown when the app is opened directly instead of by Bambu Studio."""
    tr = translator or Translator()
    fallback = f"Add this to Bambu Studio > Post-processing Scripts:\n{command}"
    try:
        import tkinter as tk

        import customtkinter as ctk
    except ImportError:
        print(fallback)
        return 0

    theme.apply_appearance(theme.load_appearance() if tr.remember else "system", remember=False)
    try:
        root = ctk.CTk(fg_color=theme.BG)
    except tk.TclError:
        print(fallback)
        return 0
    set_window_icon(root)
    fonts = theme.Fonts()
    root.title("Layer Rescue")
    root.resizable(False, False)
    frame = card(root)
    frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
    frame.columnconfigure(0, weight=1)

    header = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=0)
    header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
    header.columnconfigure(0, weight=1)
    _brand(header, fonts, tr, background=theme.SURFACE).grid(row=0, column=0, sticky="w")
    language_switch(tr, header, fonts).grid(row=0, column=1, sticky="e")

    text(tr, frame, "setup.text", font=fonts.body, wrap=540).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 12))
    command_var = tk.StringVar(value=command)
    entry = field(frame, command_var, width=560)
    entry.configure(state="readonly")
    entry.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 14))

    copied = {"done": False}
    buttons = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=0)
    buttons.grid(row=3, column=0, sticky="e", padx=18, pady=(0, 16))

    def copy_text() -> None:
        copy_button.configure(text=tr("setup.copied" if copied["done"] else "setup.copy"))

    def copy() -> None:
        root.clipboard_clear()
        root.clipboard_append(command)
        copied["done"] = True
        copy_text()

    copy_button = primary_button(buttons, copy, fonts)
    copy_button.grid(row=0, column=0, padx=(0, 8))
    tr.on_change(copy_text)
    close_button = secondary_button(buttons, root.destroy, fonts)
    close_button.grid(row=0, column=1)
    tr.on_change(lambda: close_button.configure(text=tr("setup.close")))

    root.after(100, lambda: (root.lift(), root.focus_force()))
    root.mainloop()
    return 0
