from __future__ import annotations

from pathlib import Path

from .core import ResumeError, ResumeOptions, ZReferenceMode, analyze_gcode, rewrite_gcode_file


def launch(path: Path) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        raise ResumeError("Tkinter is unavailable; use --start-layer/--last-layer from the CLI.")

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise ResumeError(f"Could not open the graphical selector: {exc}") from exc

    try:
        analysis = analyze_gcode(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ResumeError) as exc:
        root.withdraw()
        messagebox.showerror("Layer Rescue", str(exc))
        root.destroy()
        return 2

    root.title("Layer Rescue")
    root.resizable(False, False)
    result = {"code": 0}

    frame = ttk.Frame(root, padding=18)
    frame.grid(row=0, column=0, sticky="nsew")
    ttk.Label(frame, text="Recover an interrupted print", font=("TkDefaultFont", 15, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )

    summary = (
        f"File: {path.name}\n"
        f"Printer: {analysis.printer_model}\n"
        f"Filament: {analysis.filament_type}\n"
        f"Layers: {analysis.first_layer}–{analysis.last_layer} / {analysis.total_layers}"
    )
    ttk.Label(frame, text=summary, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))

    last_layer_var = tk.StringVar()
    nozzle_var = tk.StringVar()
    bed_var = tk.StringVar()
    home_var = tk.BooleanVar(value=True)
    z_mode_var = tk.StringVar(value=ZReferenceMode.RETAINED.value)
    retained_confirm_var = tk.BooleanVar(value=False)
    manual_confirm_var = tk.BooleanVar(value=False)
    attached_var = tk.BooleanVar(value=False)
    mode_help_var = tk.StringVar()

    ttk.Label(frame, text="Last successfully printed layer").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)
    last_entry = ttk.Entry(frame, width=12, textvariable=last_layer_var)
    last_entry.grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Label(frame, text="Nozzle °C (blank = detect)").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=4)
    ttk.Entry(frame, width=12, textvariable=nozzle_var).grid(row=3, column=1, sticky="ew", pady=4)
    ttk.Label(frame, text="Bed °C (blank = detect)").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=4)
    ttk.Entry(frame, width=12, textvariable=bed_var).grid(row=4, column=1, sticky="ew", pady=4)

    ttk.Label(frame, text="Z reference mode", font=("TkDefaultFont", 10, "bold")).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(12, 2)
    )
    ttk.Radiobutton(
        frame,
        text="Printer stayed powered on (retain Z)",
        variable=z_mode_var,
        value=ZReferenceMode.RETAINED.value,
    ).grid(row=6, column=0, columnspan=2, sticky="w", pady=2)
    ttk.Radiobutton(
        frame,
        text="Printer was restarted (manual Z reference)",
        variable=z_mode_var,
        value=ZReferenceMode.MANUAL.value,
    ).grid(row=7, column=0, columnspan=2, sticky="w", pady=2)

    home_check = ttk.Checkbutton(frame, text="Re-home CoreXY with G28 X (never Z)", variable=home_var)
    home_check.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 2))
    retained_check = ttk.Checkbutton(
        frame,
        text="The printer never lost power or its Z motor position",
        variable=retained_confirm_var,
    )
    retained_check.grid(row=9, column=0, columnspan=2, sticky="w", pady=2)
    manual_check = ttk.Checkbutton(
        frame,
        text="Before job start, I will align the clean nozzle to touch the last printed layer",
        variable=manual_confirm_var,
    )
    manual_check.grid(row=10, column=0, columnspan=2, sticky="w", pady=2)
    ttk.Checkbutton(
        frame,
        text="The original part is still firmly attached to the same plate",
        variable=attached_var,
    ).grid(row=11, column=0, columnspan=2, sticky="w", pady=2)

    ttk.Label(frame, textvariable=mode_help_var, wraplength=500, foreground="#9a4d00", justify="left").grid(
        row=12, column=0, columnspan=2, sticky="w", pady=(12, 14)
    )

    def update_mode() -> None:
        manual = z_mode_var.get() == ZReferenceMode.MANUAL.value
        retained_check.configure(state="disabled" if manual else "normal")
        manual_check.configure(state="normal" if manual else "disabled")
        if manual:
            home_var.set(True)
            home_check.configure(state="disabled")
            mode_help_var.set(
                "Put the clean nozzle over a flat area of the last successful layer and adjust it until it "
                "just touches that surface before sending. Every Z move in the job is relative to that "
                "position, so it does not depend on the printer's Z coordinate after a restart. The job "
                "lifts 2 mm and homes CoreXY only. It never homes Z or levels the bed."
            )
        else:
            home_check.configure(state="normal")
            mode_help_var.set(
                "Retained mode uses the printer's existing absolute Z coordinate. Use it only when power and "
                "the Z motor position were preserved. The job never homes Z or levels the bed."
            )

    for child in frame.winfo_children():
        if isinstance(child, ttk.Radiobutton):
            child.configure(command=update_mode)
    update_mode()

    def leave_unchanged() -> None:
        result["code"] = 0
        root.destroy()

    def convert() -> None:
        try:
            z_mode = ZReferenceMode(z_mode_var.get())
            if not attached_var.get():
                raise ResumeError("Confirm that the original part is still firmly attached.")
            if z_mode is ZReferenceMode.RETAINED and not retained_confirm_var.get():
                raise ResumeError("Retained mode requires confirmation that the printer never lost its Z position.")
            if z_mode is ZReferenceMode.MANUAL and not manual_confirm_var.get():
                raise ResumeError("Restarted mode requires the manual nozzle-alignment confirmation.")
            last_layer = int(last_layer_var.get().strip())
            start_layer = last_layer + 1
            nozzle = int(nozzle_var.get()) if nozzle_var.get().strip() else None
            bed = int(bed_var.get()) if bed_var.get().strip() else None
            report = rewrite_gcode_file(
                path,
                ResumeOptions(
                    start_layer=start_layer,
                    z_reference_mode=z_mode,
                    home_corexy=home_var.get(),
                    nozzle_temperature=nozzle,
                    bed_temperature=bed,
                ),
            )
            z_summary = (
                "Retained printer Z coordinate"
                if report.z_reference_mode is ZReferenceMode.RETAINED
                else f"Manual reference: nozzle touching Z={report.reference_z:g} mm surface"
            )
            manual_reminder = (
                "\n\nBefore sending: align the clean nozzle so it just touches the top of the last "
                "successful layer. Do not start unless this is exact."
                if report.z_reference_mode is ZReferenceMode.MANUAL
                else ""
            )
            messagebox.showinfo(
                "Layer Rescue",
                (
                    f"Recovery G-code created.\n\n"
                    f"Starts at layer {report.start_layer}/{report.total_layers}\n"
                    f"Z: {report.start_z:g} mm\n"
                    f"Z mode: {z_summary}\n"
                    f"Nozzle: {report.nozzle_temperature}°C\n"
                    f"Bed: {report.bed_temperature}°C\n\n"
                    "Inspect Bambu Studio Preview before sending."
                    f"{manual_reminder}"
                ),
                parent=root,
            )
            result["code"] = 0
            root.destroy()
        except (ValueError, OSError, ResumeError) as exc:
            messagebox.showerror("Layer Rescue", str(exc), parent=root)

    buttons = ttk.Frame(frame)
    buttons.grid(row=13, column=0, columnspan=2, sticky="e")
    ttk.Button(buttons, text="Leave unchanged", command=leave_unchanged).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Create recovery G-code", command=convert).grid(row=0, column=1)

    root.protocol("WM_DELETE_WINDOW", leave_unchanged)
    root.after(100, lambda: (root.lift(), root.attributes("-topmost", True)))
    root.after(700, lambda: root.attributes("-topmost", False))
    last_entry.focus_set()
    root.mainloop()
    return result["code"]
