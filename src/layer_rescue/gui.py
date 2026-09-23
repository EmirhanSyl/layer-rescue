from __future__ import annotations

from pathlib import Path

from .core import ResumeError, ResumeOptions, analyze_gcode, rewrite_gcode_file


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
    powered_var = tk.BooleanVar(value=False)
    attached_var = tk.BooleanVar(value=False)

    ttk.Label(frame, text="Last successfully printed layer").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)
    last_entry = ttk.Entry(frame, width=12, textvariable=last_layer_var)
    last_entry.grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Label(frame, text="Nozzle °C (blank = detect)").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=4)
    ttk.Entry(frame, width=12, textvariable=nozzle_var).grid(row=3, column=1, sticky="ew", pady=4)
    ttk.Label(frame, text="Bed °C (blank = detect)").grid(row=4, column=0, sticky="w", padx=(0, 12), pady=4)
    ttk.Entry(frame, width=12, textvariable=bed_var).grid(row=4, column=1, sticky="ew", pady=4)

    ttk.Checkbutton(frame, text="Re-home CoreXY with G28 X (never Z)", variable=home_var).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(10, 2)
    )
    ttk.Checkbutton(
        frame,
        text="The printer stayed powered on and its Z position is still valid",
        variable=powered_var,
    ).grid(row=6, column=0, columnspan=2, sticky="w", pady=2)
    ttk.Checkbutton(
        frame,
        text="The original part is still firmly attached to the same plate",
        variable=attached_var,
    ).grid(row=7, column=0, columnspan=2, sticky="w", pady=2)

    warning = (
        "The tool starts at the layer after the number above. It does not home Z or level the bed. "
        "Clean the nozzle and inspect the Preview before sending."
    )
    ttk.Label(frame, text=warning, wraplength=470, foreground="#9a4d00", justify="left").grid(
        row=8, column=0, columnspan=2, sticky="w", pady=(12, 14)
    )

    def leave_unchanged() -> None:
        result["code"] = 0
        root.destroy()

    def convert() -> None:
        try:
            if not powered_var.get() or not attached_var.get():
                raise ResumeError("Both safety confirmations are required.")
            last_layer = int(last_layer_var.get().strip())
            start_layer = last_layer + 1
            nozzle = int(nozzle_var.get()) if nozzle_var.get().strip() else None
            bed = int(bed_var.get()) if bed_var.get().strip() else None
            report = rewrite_gcode_file(
                path,
                ResumeOptions(
                    start_layer=start_layer,
                    home_corexy=home_var.get(),
                    nozzle_temperature=nozzle,
                    bed_temperature=bed,
                ),
            )
            messagebox.showinfo(
                "Layer Rescue",
                (
                    f"Recovery G-code created.\n\n"
                    f"Starts at layer {report.start_layer}/{report.total_layers}\n"
                    f"Z: {report.start_z:g} mm\n"
                    f"Nozzle: {report.nozzle_temperature}°C\n"
                    f"Bed: {report.bed_temperature}°C\n\n"
                    "Inspect Bambu Studio Preview before sending."
                ),
                parent=root,
            )
            result["code"] = 0
            root.destroy()
        except (ValueError, OSError, ResumeError) as exc:
            messagebox.showerror("Layer Rescue", str(exc), parent=root)

    buttons = ttk.Frame(frame)
    buttons.grid(row=9, column=0, columnspan=2, sticky="e")
    ttk.Button(buttons, text="Leave unchanged", command=leave_unchanged).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Create recovery G-code", command=convert).grid(row=0, column=1)

    root.protocol("WM_DELETE_WINDOW", leave_unchanged)
    root.after(100, lambda: (root.lift(), root.attributes("-topmost", True)))
    root.after(700, lambda: root.attributes("-topmost", False))
    last_entry.focus_set()
    root.mainloop()
    return result["code"]
