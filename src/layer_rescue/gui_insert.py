"""The insert tab ("part came off / print on a finished part") of the Layer Rescue window."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, NamedTuple

from .fileio import rewrite_with
from .gcode import Analysis, ResumeError
from .gui_widgets import HINT_COLOR, NOTE_COLOR, text_label, wrapped_check
from .i18n import Translator
from .insert import InsertOptions, InsertPlan, build_insert_gcode, plan_insert, recommended_wall_height
from .preview import plan_shapes, view_bounds

CANVAS_SIZE = 280
LEFT_WRAP = 400
COLORS = {
    "silhouette": ("#d9d4c7", "#8a8272"),
    "addition": ("", "#2563eb"),
    "brim": ("", "#b0b5bd"),
    "wall-bottom": ("", "#6b7280"),
    "wall-top": ("", "#dc2626"),
    "support": ("#86efac", "#15803d"),
}
LEGEND = ("silhouette", "wall-bottom", "wall-top", "addition", "support")


class InsertTab(NamedTuple):
    frame: Any
    convert: Callable[[], None]
    ready: Callable[[], str | None]  # None when the G-code can be created, else a status text key
    watched: tuple[Any, ...]  # Tk variables that change ready()


def _float(tr: Translator, text: str, field_key: str) -> float:
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        raise ResumeError(tr("insert.err_number", field=tr(field_key).rstrip(":"))) from None


def _int(tr: Translator, text: str, field_key: str) -> int:
    value = _float(tr, text, field_key)
    if value != int(value):
        raise ResumeError(tr("insert.err_whole", field=tr(field_key).rstrip(":")))
    return int(value)


def build_insert_tab(
    notebook: Any, root: Any, path: Path, analysis: Analysis, result: dict, tr: Translator, untested_var: Any = None
) -> InsertTab:
    import tkinter as tk
    from tkinter import messagebox, ttk

    tab = ttk.Frame(notebook, padding=12)
    left = ttk.Frame(tab)
    left.grid(row=0, column=0, sticky="nw")
    left.columnconfigure(0, weight=1)
    right = ttk.Frame(tab)
    right.grid(row=0, column=1, sticky="n", padx=(16, 0))

    part_var = tk.StringVar()
    part_layer_var = tk.StringVar()
    wall_var = tk.StringVar()
    confirm_var = tk.BooleanVar(value=False)
    advanced_var = tk.BooleanVar(value=False)
    clearance_var = tk.StringVar(value="0.25")
    lines_var = tk.StringVar(value="4")
    brim_var = tk.StringVar(value="5")
    fine_var = tk.StringVar(value="0")
    standby_var = tk.StringVar(value="140")
    adhesion_var = tk.StringVar(value="2")
    chamfer_var = tk.BooleanVar(value=True)
    supports_var = tk.BooleanVar(value=True)
    last_plan: dict[str, InsertPlan] = {}
    # What the result area shows: ("start",), ("plan", plan) or ("error", message). Re-rendered on language change.
    shown: dict[str, Any] = {"state": ("start",)}

    text_label(tr, left, "insert.intro", wraplength=LEFT_WRAP, justify="left").grid(
        row=0, column=0, sticky="w", pady=(0, 8)
    )

    def section(row: int, key: str) -> Any:
        frame = ttk.LabelFrame(left, padding=(10, 6))
        tr.on_change(lambda: frame.configure(text=tr(key)))
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        return frame

    # Step 1: part and wall
    step1 = section(1, "insert.step1")
    text_label(tr, step1, "insert.part_height").grid(row=0, column=0, sticky="w", pady=2)
    part_entry = ttk.Entry(step1, width=9, textvariable=part_var)
    part_entry.grid(row=0, column=1, sticky="w", pady=2, padx=(8, 0))
    text_label(tr, step1, "insert.part_layer", foreground=HINT_COLOR).grid(row=1, column=0, sticky="w", pady=2)
    ttk.Entry(step1, width=9, textvariable=part_layer_var).grid(row=1, column=1, sticky="w", pady=2, padx=(8, 0))
    text_label(tr, step1, "insert.wall_height").grid(row=2, column=0, sticky="w", pady=2)
    ttk.Entry(step1, width=9, textvariable=wall_var).grid(row=2, column=1, sticky="w", pady=2, padx=(8, 0))
    text_label(tr, step1, "insert.wall_hint", foreground=HINT_COLOR).grid(row=2, column=2, sticky="w", padx=(8, 0))
    preview_button = ttk.Button(step1, command=lambda: preview())
    preview_button.grid(row=0, column=2, rowspan=2, sticky="w", padx=(10, 0))
    tr.on_change(lambda: preview_button.configure(text=tr("insert.preview")))

    def part_layer_changed(*_: object) -> None:
        text = part_layer_var.get().strip()
        if not text:
            return
        try:
            part_var.set(f"{analysis.layer(int(text)).z:g}")
        except (ValueError, ResumeError):
            pass

    part_layer_var.trace_add("write", part_layer_changed)

    advanced_toggle = ttk.Checkbutton(right, variable=advanced_var, command=lambda: toggle_advanced())
    advanced_toggle.grid(row=3, column=0, sticky="w", pady=(10, 0))
    tr.on_change(lambda: advanced_toggle.configure(text=tr("insert.show_advanced")))

    advanced = ttk.LabelFrame(right, padding=8)
    tr.on_change(lambda: advanced.configure(text=tr("insert.advanced")))
    fields = [
        ("insert.clearance", clearance_var),
        ("insert.lines", lines_var),
        ("insert.brim", brim_var),
        ("insert.fine", fine_var),
        ("insert.standby", standby_var),
        ("insert.adhesion", adhesion_var),
    ]
    for row, (key, var) in enumerate(fields):
        text_label(tr, advanced, key, wraplength=CANVAS_SIZE - 80, justify="left").grid(
            row=row, column=0, sticky="w", pady=2
        )
        ttk.Entry(advanced, width=8, textvariable=var).grid(row=row, column=1, sticky="w", pady=2, padx=(8, 0))
    for row, (key, var) in enumerate([("insert.chamfer", chamfer_var), ("insert.supports", supports_var)]):
        wrapped_check(tr, advanced, var, key, CANVAS_SIZE - 40).grid(
            row=len(fields) + row, column=0, columnspan=2, sticky="w", pady=2
        )

    def toggle_advanced() -> None:
        if advanced_var.get():
            advanced.grid(row=4, column=0, sticky="ew", pady=(4, 0))
        else:
            advanced.grid_remove()

    # Step 2: result of the preview
    step2 = section(2, "insert.step2")
    info_label = ttk.Label(step2, justify="left", wraplength=LEFT_WRAP - 20)
    info_label.grid(row=0, column=0, sticky="w")
    warn_label = ttk.Label(step2, justify="left", wraplength=LEFT_WRAP - 20, foreground=NOTE_COLOR)
    warn_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

    # Step 3: safety check
    step3 = section(3, "insert.step3")
    text_label(tr, step3, "insert.check_intro", wraplength=LEFT_WRAP - 20, justify="left", foreground=HINT_COLOR).grid(
        row=0, column=0, sticky="w", pady=(0, 4)
    )
    wrapped_check(tr, step3, confirm_var, "insert.check_attended", LEFT_WRAP - 40).grid(row=1, column=0, sticky="w")

    # Right: top view and legend
    legend_title = text_label(tr, right, "insert.legend_title", foreground=HINT_COLOR)
    legend_title.grid(row=0, column=0, sticky="w", pady=(0, 4))
    canvas = tk.Canvas(right, width=CANVAS_SIZE, height=CANVAS_SIZE, background="white", highlightthickness=1)
    canvas.grid(row=1, column=0)
    legend = ttk.Frame(right)
    legend.grid(row=2, column=0, sticky="w", pady=(6, 0))
    for row, kind in enumerate(LEGEND):
        fill, outline = COLORS[kind]
        swatch = tk.Canvas(legend, width=14, height=14, highlightthickness=0, background=root.cget("background"))
        swatch.create_rectangle(1, 1, 13, 13, fill=fill or "white", outline=outline, width=2)
        swatch.grid(row=row, column=0, padx=(0, 6), pady=1)
        text_label(tr, legend, f"legend.{kind}").grid(row=row, column=1, sticky="w")

    def options() -> InsertOptions:
        wall_text = wall_var.get().strip()
        return InsertOptions(
            part_height_mm=_float(tr, part_var.get(), "insert.part_height"),
            wall_height_mm=_float(tr, wall_text, "insert.wall_height") if wall_text else None,
            clearance_mm=_float(tr, clearance_var.get(), "insert.clearance"),
            wall_lines=_int(tr, lines_var.get(), "insert.lines"),
            brim_mm=_float(tr, brim_var.get(), "insert.brim"),
            chamfer=chamfer_var.get(),
            z_fine_mm=_float(tr, fine_var.get() or "0", "insert.fine"),
            standby_temperature=_int(tr, standby_var.get() or "0", "insert.standby"),
            adhesion_layers=_int(tr, adhesion_var.get() or "0", "insert.adhesion"),
            reprint_supports=supports_var.get(),
            allow_untested=bool(untested_var and untested_var.get()),
        )

    def draw(plan: InsertPlan | None) -> None:
        canvas.delete("all")
        if plan is None:
            return
        shapes = plan_shapes(plan)
        min_x, min_y, max_x, max_y = view_bounds(shapes)
        scale = (CANVAS_SIZE - 20) / max(max_x - min_x, max_y - min_y)

        def xy(point: tuple[float, float]) -> tuple[float, float]:
            return (10 + (point[0] - min_x) * scale, CANVAS_SIZE - 10 - (point[1] - min_y) * scale)

        for kind in ("silhouette", "addition", "brim", "wall-bottom", "wall-top", "support"):
            fill, outline = COLORS[kind]
            for shape in shapes:
                if shape.kind == kind and len(shape.points) >= 3:
                    coords = [c for point in shape.points for c in xy(point)]
                    canvas.create_polygon(*coords, fill=fill, outline=outline, width=1)
        canvas.create_text(
            CANVAS_SIZE / 2, CANVAS_SIZE - 4, text="▼ " + tr("insert.canvas_front"), fill="#6b7280", anchor="s"
        )

    def render() -> None:
        state = shown["state"]
        if state[0] == "start":
            info_label.configure(text=tr("insert.info_start"), foreground=HINT_COLOR)
            warn_label.configure(text="")
            return
        if state[0] == "error":
            info_label.configure(text=tr.message(state[1]), foreground=NOTE_COLOR)
            warn_label.configure(text="")
            return
        plan: InsertPlan = state[1]
        o = plan.options
        text = tr(
            "insert.info",
            wall_last=plan.wall_layers[-1].number,
            wall_top=plan.wall.top_z,
            recommended=recommended_wall_height(o.part_height_mm),
            resume=plan.resume_layer.number,
            total=plan.analysis.total_layers,
            model_z=plan.part_layer.z,
            part=o.part_height_mm,
            offset=plan.z_offset,
            first=plan.resume_layer.z + plan.z_offset - o.part_height_mm,
        )
        if plan.supports and plan.supports.any:
            text += tr("insert.info_supports", layer=plan.printed_layers[-1].number)
        info_label.configure(text=text, foreground="")
        warnings = [tr.message(warning) for warning in plan.warnings]
        warn_label.configure(text=(tr("warnings") + "\n• " + "\n• ".join(warnings)) if warnings else "")
        draw(plan)

    tr.on_change(render)

    def preview() -> InsertPlan | None:
        try:
            plan = plan_insert(analysis, options())
        except (ValueError, ResumeError) as exc:
            last_plan.pop("plan", None)
            shown["state"] = ("error", str(exc))
            draw(None)
            render()
            return None
        last_plan["plan"] = plan
        shown["state"] = ("plan", plan)
        render()
        return plan

    def ready() -> str | None:
        if untested_var is not None and not untested_var.get():
            return "status.untested"
        try:
            _float(tr, part_var.get(), "insert.part_height")
        except ResumeError:
            return "status.insert_height"
        if not confirm_var.get():
            return "status.insert_check"
        return None

    def convert() -> None:
        try:
            if not confirm_var.get():
                raise ResumeError(tr("insert.err_attended"))
            chosen = options()
            report, _backup = rewrite_with(
                path, lambda text: build_insert_gcode(text, chosen, last_plan.get("plan"))
            )
            warnings = [tr.message(warning) for warning in report.warnings]
            messagebox.showinfo(
                "Layer Rescue",
                tr(
                    "insert.done",
                    wall_top=report.wall_top_z,
                    wall_layers=report.wall_layers,
                    supports=(
                        tr("insert.done_supports", layer=report.last_printed_layer) if report.support_layers else ""
                    ),
                    park_z=report.park_z,
                    supports_hint=tr("insert.done_supports_hint") if report.support_layers else "",
                    resume=report.resume_layer,
                    first=report.first_layer_thickness_mm,
                )
                + (("\n\n" + tr("warnings") + "\n- " + "\n- ".join(warnings)) if warnings else ""),
                parent=root,
            )
            result["code"] = 0
            root.destroy()
        except (ValueError, OSError, ResumeError) as exc:
            messagebox.showerror("Layer Rescue", tr.message(str(exc)), parent=root)

    return InsertTab(tab, convert, ready, (part_var, confirm_var))
