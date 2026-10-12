from __future__ import annotations

from pathlib import Path
from typing import Any

from ._version import __version__
from .core import ResumeError, ResumeOptions, ZReferenceMode, analyze_gcode, rewrite_gcode_file
from .gui_insert import build_insert_tab
from .gui_widgets import (
    HINT_COLOR,
    Collapsible,
    NOTE_COLOR,
    OK_COLOR,
    WRAP,
    ScrollArea,
    language_switch,
    set_window_icon,
    text_label,
    wrapped_check,
)
from .i18n import Translator
from .machine_state import untested_setup


def _bring_to_front(root: Any) -> None:
    root.after(100, lambda: (root.lift(), root.attributes("-topmost", True), root.focus_force()))
    root.after(700, lambda: root.attributes("-topmost", False))


# Room kept free on screen for the title bar and the taskbar/dock.
SCREEN_MARGIN = 120


def _fit_to_screen(root: Any, area: ScrollArea) -> None:
    """Cap the scrolling part so the whole window fits on the screen; the window can still be resized."""
    root.update_idletasks()
    chrome = root.winfo_reqheight() - area.canvas.winfo_reqheight()
    area.max_height = max(220, root.winfo_screenheight() - SCREEN_MARGIN - chrome)
    area.refresh()
    root.update_idletasks()
    root.minsize(min(root.winfo_reqwidth(), root.winfo_screenwidth() - 40), min(root.winfo_reqheight(), 360))
    root.geometry("+{}+{}".format(max(0, (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2), 20))


def launch(path: Path, translator: Translator | None = None) -> int:
    tr = translator or Translator()
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        raise ResumeError(tr("error.tk_missing"))

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise ResumeError(tr("error.no_window", error=exc)) from exc
    set_window_icon(root)

    try:
        analysis = analyze_gcode(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ResumeError) as exc:
        root.withdraw()
        messagebox.showerror("Layer Rescue", tr.message(str(exc)))
        root.destroy()
        return 2

    root.title("Layer Rescue")
    result = {"code": 0}

    # Header and buttons stay put; everything between them scrolls when the window is taller than the screen.
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    outer = ttk.Frame(root, padding=(16, 14, 16, 12))
    outer.grid(row=0, column=0, sticky="nsew")
    outer.columnconfigure(0, weight=1)
    outer.rowconfigure(1, weight=1)

    # ---------------------------------------------------------------- header
    header = ttk.Frame(outer)
    header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    header.columnconfigure(1, weight=1)
    ttk.Label(header, text="Layer Rescue", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, sticky="w")
    version = ttk.Label(header, foreground=HINT_COLOR)
    version.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(5, 0))
    tr.on_change(lambda: version.configure(text=tr("header.version", version=__version__)))
    language_switch(tr, header).grid(row=0, column=2, sticky="e")

    area = ScrollArea(outer)
    area.frame.grid(row=1, column=0, sticky="nsew")
    content = area.inner
    content.columnconfigure(0, weight=1)

    info = ttk.LabelFrame(content, padding=(10, 6))
    tr.on_change(lambda: info.configure(text=tr("file.frame")))
    info.grid(row=1, column=0, sticky="ew", pady=(0, 10), padx=(0, 4))
    file_rows = [
        ("file.name", lambda: path.name),
        ("file.printer", lambda: analysis.printer_model),
        ("file.filament", lambda: analysis.filament_type),
        (
            "file.layers",
            lambda: tr(
                "file.layers_value",
                first=analysis.first_layer,
                last=analysis.last_layer,
                total=analysis.total_layers,
            ),
        ),
    ]
    for index, (key, value) in enumerate(file_rows):
        row, column = index % 2, (index // 2) * 2
        text_label(tr, info, key, foreground=HINT_COLOR).grid(row=row, column=column, sticky="w", padx=(0, 10))
        value_label = ttk.Label(info)
        value_label.grid(row=row, column=column + 1, sticky="w", padx=(0, 28))
        tr.on_change(lambda value_label=value_label, value=value: value_label.configure(text=value()))

    # A job outside what has been tested (other printer, several filaments): explain and let the user opt in.
    untested = untested_setup(analysis)
    untested_var = tk.BooleanVar(value=False)
    if untested:
        risk = ttk.LabelFrame(content, padding=(10, 6))
        tr.on_change(lambda: risk.configure(text=tr("untested.frame")))
        risk.grid(row=2, column=0, sticky="ew", pady=(0, 10), padx=(0, 4))
        text_label(tr, risk, "untested.intro", wraplength=WRAP, justify="left").grid(row=0, column=0, sticky="w")
        reasons = ttk.Label(risk, wraplength=WRAP, justify="left", foreground=NOTE_COLOR)
        reasons.grid(row=1, column=0, sticky="w", pady=(4, 4))
        tr.on_change(lambda: reasons.configure(text="\n".join("• " + tr.message(reason) for reason in untested)))
        wrapped_check(tr, risk, untested_var, "untested.check", WRAP - 20).grid(row=2, column=0, sticky="w")

    text_label(tr, content, "choose_mode", font=("TkDefaultFont", 10, "bold")).grid(
        row=3, column=0, sticky="w", pady=(0, 4)
    )
    notebook = ttk.Notebook(content)
    notebook.grid(row=4, column=0, sticky="nsew", padx=(0, 4))

    # ------------------------------------------------------------ resume tab
    tab = ttk.Frame(notebook, padding=12)
    notebook.add(tab, text="")
    tab.columnconfigure(0, weight=1)

    last_layer_var = tk.StringVar()
    nozzle_var = tk.StringVar()
    bed_var = tk.StringVar()
    home_var = tk.BooleanVar(value=True)
    z_mode_var = tk.StringVar(value=ZReferenceMode.RETAINED.value)
    retained_confirm_var = tk.BooleanVar(value=False)
    manual_confirm_var = tk.BooleanVar(value=False)
    attached_var = tk.BooleanVar(value=False)

    text_label(tr, tab, "resume.intro", wraplength=WRAP, justify="left").grid(
        row=0, column=0, sticky="w", pady=(0, 8)
    )

    def section(row: int, key: str) -> Any:
        frame = ttk.LabelFrame(tab, padding=(10, 6))
        tr.on_change(lambda: frame.configure(text=tr(key)))
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(2, weight=1)
        return frame

    # Step 1: where did it stop?
    step1 = section(1, "resume.step1")
    text_label(tr, step1, "resume.last_layer").grid(row=0, column=0, sticky="w", padx=(0, 8))
    last_entry = ttk.Entry(step1, width=10, textvariable=last_layer_var)
    last_entry.grid(row=0, column=1, sticky="w")
    text_label(tr, step1, "resume.last_layer_hint", wraplength=WRAP - 20, justify="left", foreground=HINT_COLOR).grid(
        row=1, column=0, columnspan=3, sticky="w", pady=(4, 0)
    )
    next_layer_label = ttk.Label(step1, wraplength=WRAP - 20, justify="left")
    next_layer_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def last_layer() -> int | None:
        try:
            number = int(last_layer_var.get().strip())
        except ValueError:
            return None
        return number if analysis.first_layer <= number < analysis.last_layer else None

    def update_next_layer(*_: object) -> None:
        number = last_layer()
        if number is not None:
            try:
                start = analysis.layer(number + 1)
            except ResumeError:
                start = None
            if start is not None:
                next_layer_label.configure(
                    text="→ " + tr("resume.next_layer", layer=start.number, total=analysis.total_layers, z=start.z),
                    foreground=OK_COLOR,
                )
                return
        if last_layer_var.get().strip():
            next_layer_label.configure(
                text=tr("resume.layer_range", first=analysis.first_layer, last=analysis.last_layer - 1),
                foreground=NOTE_COLOR,
            )
        else:
            next_layer_label.configure(text="")

    # Step 2: was the printer restarted?
    step2 = section(2, "resume.step2")
    mode_buttons = []
    for row, (mode, key) in enumerate(
        [(ZReferenceMode.RETAINED, "resume.mode_retained"), (ZReferenceMode.MANUAL, "resume.mode_manual")]
    ):
        button = ttk.Radiobutton(step2, variable=z_mode_var, value=mode.value)
        button.grid(row=row, column=0, columnspan=3, sticky="w", pady=1)
        tr.on_change(lambda button=button, key=key: button.configure(text=tr(key)))
        mode_buttons.append(button)
    mode_help = ttk.Label(step2, wraplength=WRAP - 20, justify="left", foreground=NOTE_COLOR)
    mode_help.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # Step 3: safety checks
    step3 = section(3, "resume.step3")
    text_label(tr, step3, "resume.checks_intro", wraplength=WRAP - 20, justify="left", foreground=HINT_COLOR).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
    )
    checks: dict[str, Any] = {}
    for row, (name, var, key) in enumerate(
        [
            ("attached", attached_var, "resume.check_attached"),
            ("retained", retained_confirm_var, "resume.check_retained"),
            ("manual", manual_confirm_var, "resume.check_manual"),
        ],
        start=1,
    ):
        check = wrapped_check(tr, step3, var, key, WRAP - 40)
        check.grid(row=row, column=0, columnspan=3, sticky="w", pady=1)
        checks[name] = check

    # Options
    options = section(4, "resume.options")
    for row, (key, var) in enumerate([("resume.nozzle", nozzle_var), ("resume.bed", bed_var)]):
        text_label(tr, options, key).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=1)
        ttk.Entry(options, width=8, textvariable=var).grid(row=row, column=1, sticky="w", pady=1)
        text_label(tr, options, "resume.temp_hint", foreground=HINT_COLOR).grid(
            row=row, column=2, sticky="w", padx=(8, 0)
        )
    home_check = ttk.Checkbutton(options, variable=home_var)
    home_check.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

    # Experimental features: folded and off by default; the title says how many are on.
    reheat_var = tk.BooleanVar(value=False)
    reheat_values = {
        "gap": tk.StringVar(value="0.2"),
        "speed": tk.StringVar(value="20"),
        "passes": tk.StringVar(value="1"),
        "temp": tk.StringVar(value=""),
    }
    experimental = Collapsible(
        tr, tab, "insert.experimental", suffix=lambda: tr("insert.experimental_on", n=1) if reheat_var.get() else ""
    )
    experimental.frame.grid(row=5, column=0, sticky="ew", pady=(2, 0))
    experimental.header._lr_action = "resume_experimental"  # type: ignore[attr-defined]
    text_label(
        tr, experimental.body, "insert.experimental_intro", wraplength=WRAP - 20, justify="left", foreground=NOTE_COLOR
    ).grid(row=0, column=0, sticky="w", pady=(0, 6))
    reheat_check = wrapped_check(tr, experimental.body, reheat_var, "resume.reheat", WRAP - 40)
    reheat_check.grid(row=1, column=0, sticky="w")
    reheat_check.check._lr_action = "resume_reheat"  # type: ignore[attr-defined]
    text_label(
        tr, experimental.body, "resume.reheat_hint", wraplength=WRAP - 50, justify="left", foreground=HINT_COLOR
    ).grid(row=2, column=0, sticky="w", padx=(24, 0))
    reheat_fields = ttk.Frame(experimental.body)
    reheat_fields.grid(row=3, column=0, sticky="w", padx=(24, 0), pady=(4, 0))
    reheat_entries = []
    for index, (name, key) in enumerate(
        [
            ("gap", "resume.reheat_gap"),
            ("speed", "insert.reheat_speed"),
            ("passes", "insert.reheat_passes"),
            ("temp", "resume.reheat_temp"),
        ]
    ):
        text_label(tr, reheat_fields, key).grid(row=index, column=0, sticky="w", pady=2)
        entry = ttk.Entry(reheat_fields, width=7, textvariable=reheat_values[name])
        entry.grid(row=index, column=1, sticky="w", pady=2, padx=(8, 0))
        entry.state(["disabled"])
        reheat_entries.append(entry)

    def reheat_changed(*_: object) -> None:
        for entry in reheat_entries:
            entry.state(["!disabled"] if reheat_var.get() else ["disabled"])
        experimental.update_title()

    reheat_var.trace_add("write", reheat_changed)

    def reheat_options() -> dict[str, Any]:
        if not reheat_var.get():
            return {}

        def number(name: str, key: str) -> float:
            try:
                return float(reheat_values[name].get().strip().replace(",", "."))
            except ValueError:
                raise ResumeError(tr("resume.err_number", field=tr(key).rstrip(":"))) from None

        def whole(name: str, key: str) -> int:
            value = number(name, key)
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
        # Show only the check that belongs to the chosen mode, so no box is left greyed out without reason.
        if manual:
            checks["retained"].grid_remove()
            checks["manual"].grid()
            home_var.set(True)
            home_check.configure(state="disabled", text=tr("resume.home_forced"))
            mode_help.configure(text=tr("resume.help_manual"))
        else:
            checks["manual"].grid_remove()
            checks["retained"].grid()
            home_check.configure(state="normal", text=tr("resume.home"))
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
                text = var.get().strip()
                if not text:
                    return None
                try:
                    return int(text)
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

    # ------------------------------------------------------------ insert tab
    insert = build_insert_tab(notebook, root, path, analysis, result, tr, untested_var if untested else None)
    notebook.add(insert.frame, text="")

    def update_tabs() -> None:
        notebook.tab(0, text="  " + tr("tab.resume") + "  ")
        notebook.tab(1, text="  " + tr("tab.insert") + "  ")

    tr.on_change(update_tabs)

    # --------------------------------------------------------------- buttons
    bottom = ttk.Frame(outer)
    bottom.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    bottom.columnconfigure(0, weight=1)
    status = ttk.Label(bottom, wraplength=440, justify="left")
    status.grid(row=0, column=0, sticky="w", padx=(0, 12))
    leave_button = ttk.Button(bottom, command=leave_unchanged)
    leave_button.grid(row=0, column=1, padx=(0, 8))
    create_button = ttk.Button(bottom, command=lambda: create())
    create_button.grid(row=0, column=2)
    tr.on_change(lambda: leave_button.configure(text=tr("button.leave")))
    tr.on_change(lambda: create_button.configure(text=tr("button.create")))

    def current_tab() -> int:
        try:
            return notebook.index(notebook.select())
        except tk.TclError:
            return 0

    def update_status(*_: object) -> None:
        missing = resume_ready() if current_tab() == 0 else insert.ready()
        if missing:
            status.configure(text=tr(missing), foreground=NOTE_COLOR)
            create_button.state(["disabled"])
        else:
            status.configure(text=tr("status.ready"), foreground=OK_COLOR)
            create_button.state(["!disabled"])

    def create() -> None:
        if current_tab() == 0:
            convert()
        else:
            insert.convert()

    for var in (
        last_layer_var, z_mode_var, retained_confirm_var, manual_confirm_var, attached_var, untested_var, *insert.watched
    ):
        var.trace_add("write", update_status)
    notebook.bind("<<NotebookTabChanged>>", update_status)
    tr.on_change(update_status)

    root.protocol("WM_DELETE_WINDOW", leave_unchanged)
    _fit_to_screen(root, area)
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
        from tkinter import ttk
    except ImportError:
        print(fallback)
        return 0

    try:
        root = tk.Tk()
    except tk.TclError:
        print(fallback)
        return 0
    set_window_icon(root)

    root.title("Layer Rescue")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid(row=0, column=0, sticky="nsew")
    frame.columnconfigure(0, weight=1)

    header = ttk.Frame(frame)
    header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
    header.columnconfigure(0, weight=1)
    ttk.Label(header, text=f"Layer Rescue {__version__}", font=("TkDefaultFont", 13, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    language_switch(tr, header).grid(row=0, column=1, sticky="e")

    text_label(tr, frame, "setup.text", wraplength=520, justify="left").grid(
        row=1, column=0, columnspan=2, sticky="w", pady=(0, 10)
    )

    command_var = tk.StringVar(value=command)
    entry = ttk.Entry(frame, textvariable=command_var, width=70, state="readonly")
    entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 12))

    copied = {"done": False}
    copy_button = ttk.Button(frame)

    def copy_text() -> None:
        copy_button.configure(text=tr("setup.copied" if copied["done"] else "setup.copy"))

    def copy() -> None:
        root.clipboard_clear()
        root.clipboard_append(command)
        copied["done"] = True
        copy_text()

    copy_button.configure(command=copy)
    copy_button.grid(row=3, column=0, sticky="e", padx=(0, 8))
    tr.on_change(copy_text)
    close_button = ttk.Button(frame, command=root.destroy)
    close_button.grid(row=3, column=1, sticky="e")
    tr.on_change(lambda: close_button.configure(text=tr("setup.close")))

    root.after(100, lambda: (root.lift(), root.focus_force()))
    root.mainloop()
    return 0

