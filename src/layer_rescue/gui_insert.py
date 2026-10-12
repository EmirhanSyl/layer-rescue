"""The insert tab ("part came off / print on a finished part") of the Layer Rescue window."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, NamedTuple

from .fileio import rewrite_with
from .gcode import Analysis, ResumeError
from .gui_widgets import HINT_COLOR, NOTE_COLOR, Collapsible, frame_background, text_label, wrapped_check
from .i18n import Translator
from .insert import InsertOptions, InsertPlan, build_insert_gcode, plan_insert, recommended_wall_height
from .preview import plan_shapes, view_bounds

CANVAS_SIZE = 260
LEFT_WRAP = 400
FULL_WRAP = 680
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
    tab.columnconfigure(0, weight=1)
    left = ttk.Frame(tab)
    left.grid(row=0, column=0, sticky="nw")
    left.columnconfigure(0, weight=1)
    right = ttk.Frame(tab)
    right.grid(row=0, column=1, sticky="n", padx=(16, 0))
    # Settings most people never touch: closed sections across the full width, under the steps, so opening
    # them makes the tab a little taller instead of a lot taller.
    settings = ttk.Frame(tab)
    settings.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
    settings.columnconfigure(0, weight=1)

    part_var = tk.StringVar()
    part_layer_var = tk.StringVar()
    wall_var = tk.StringVar()
    confirm_var = tk.BooleanVar(value=False)
    clearance_var = tk.StringVar(value="0.25")
    lines_var = tk.StringVar(value="4")
    brim_var = tk.StringVar(value="5")
    fine_var = tk.StringVar(value="0")
    standby_var = tk.StringVar(value="140")
    adhesion_var = tk.StringVar(value="2")
    chamfer_var = tk.BooleanVar(value=True)
    supports_var = tk.BooleanVar(value=True)
    no_wall_var = tk.BooleanVar(value=False)
    reheat_var = tk.BooleanVar(value=False)
    reheat_gap_var = tk.StringVar(value="0.2")
    reheat_speed_var = tk.StringVar(value="20")
    reheat_passes_var = tk.StringVar(value="1")
    reheat_temp_var = tk.StringVar(value="")
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
    wall_entry = ttk.Entry(step1, width=9, textvariable=wall_var)
    wall_entry.grid(row=2, column=1, sticky="w", pady=2, padx=(8, 0))
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

    # Right: top view and a two-column legend
    legend_title = text_label(tr, right, "insert.legend_title", foreground=HINT_COLOR)
    legend_title.grid(row=0, column=0, sticky="w", pady=(0, 4))
    canvas = tk.Canvas(right, width=CANVAS_SIZE, height=CANVAS_SIZE, background="white", highlightthickness=1)
    canvas.grid(row=1, column=0)
    legend = ttk.Frame(right)
    legend.grid(row=2, column=0, sticky="w", pady=(6, 0))
    for index, kind in enumerate(LEGEND):
        row, column = index // 2, (index % 2) * 2
        fill, outline = COLORS[kind]
        swatch = tk.Canvas(legend, width=14, height=14, highlightthickness=0, background=frame_background())
        swatch.create_rectangle(1, 1, 13, 13, fill=fill or "white", outline=outline, width=2)
        swatch.grid(row=row, column=column, padx=(0 if column == 0 else 12, 6), pady=1)
        text_label(tr, legend, f"legend.{kind}").grid(row=row, column=column + 1, sticky="w")

    # Advanced settings: two columns of label + field, then the two options.
    advanced = Collapsible(tr, settings, "insert.advanced")
    advanced.frame.grid(row=0, column=0, sticky="ew")
    advanced.header._lr_action = "advanced"  # type: ignore[attr-defined]
    advanced.body.columnconfigure(0, weight=0)
    wall_only: list[Any] = [wall_entry]  # fields that mean nothing without the holding wall
    for index, (key, var) in enumerate(
        [
            ("insert.clearance", clearance_var),
            ("insert.lines", lines_var),
            ("insert.brim", brim_var),
            ("insert.fine", fine_var),
            ("insert.standby", standby_var),
            ("insert.adhesion", adhesion_var),
        ]
    ):
        row, column = index // 2, (index % 2) * 2
        text_label(tr, advanced.body, key, wraplength=230, justify="left").grid(
            row=row, column=column, sticky="w", pady=2, padx=(0 if column == 0 else 24, 0)
        )
        entry = ttk.Entry(advanced.body, width=7, textvariable=var)
        entry.grid(row=row, column=column + 1, sticky="w", pady=2, padx=(8, 0))
        if key in ("insert.lines", "insert.brim"):
            wall_only.append(entry)
    chamfer_check = wrapped_check(tr, advanced.body, chamfer_var, "insert.chamfer", FULL_WRAP - 40)
    chamfer_check.grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 1))
    wall_only.append(chamfer_check.check)
    wrapped_check(tr, advanced.body, supports_var, "insert.supports", FULL_WRAP - 40).grid(
        row=4, column=0, columnspan=4, sticky="w", pady=1
    )

    # Experimental features: off by default; the section title says how many are on even when it is closed.
    def experimental_on() -> str:
        count = int(no_wall_var.get()) + int(reheat_var.get())
        return tr("insert.experimental_on", n=count) if count else ""

    experimental = Collapsible(tr, settings, "insert.experimental", suffix=experimental_on)
    experimental.frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
    experimental.header._lr_action = "experimental"  # type: ignore[attr-defined]
    body = experimental.body
    text_label(tr, body, "insert.experimental_intro", wraplength=FULL_WRAP, justify="left", foreground=NOTE_COLOR).grid(
        row=0, column=0, sticky="w", pady=(0, 6)
    )
    no_wall_check = wrapped_check(tr, body, no_wall_var, "insert.no_wall", FULL_WRAP - 40)
    no_wall_check.grid(row=1, column=0, sticky="w")
    no_wall_check.check._lr_action = "no_wall"  # type: ignore[attr-defined]
    text_label(tr, body, "insert.no_wall_hint", wraplength=FULL_WRAP - 30, justify="left", foreground=HINT_COLOR).grid(
        row=2, column=0, sticky="w", padx=(24, 0), pady=(0, 6)
    )
    reheat_check = wrapped_check(tr, body, reheat_var, "insert.reheat", FULL_WRAP - 40)
    reheat_check.grid(row=3, column=0, sticky="w")
    reheat_check.check._lr_action = "reheat"  # type: ignore[attr-defined]
    text_label(tr, body, "insert.reheat_hint", wraplength=FULL_WRAP - 30, justify="left", foreground=HINT_COLOR).grid(
        row=4, column=0, sticky="w", padx=(24, 0)
    )
    reheat_fields = ttk.Frame(body)
    reheat_fields.grid(row=5, column=0, sticky="w", padx=(24, 0), pady=(4, 0))
    reheat_entries: list[Any] = []
    for index, (key, var) in enumerate(
        [
            ("insert.reheat_gap", reheat_gap_var),
            ("insert.reheat_speed", reheat_speed_var),
            ("insert.reheat_passes", reheat_passes_var),
            ("insert.reheat_temp", reheat_temp_var),
        ]
    ):
        text_label(tr, reheat_fields, key).grid(row=index, column=0, sticky="w", pady=2)
        entry = ttk.Entry(reheat_fields, width=7, textvariable=var)
        entry.grid(row=index, column=1, sticky="w", pady=2, padx=(8, 0))
        entry.state(["disabled"])
        reheat_entries.append(entry)

    def options() -> InsertOptions:
        wall_text = wall_var.get().strip()
        reheat = reheat_var.get()
        temperature_text = reheat_temp_var.get().strip()
        return InsertOptions(
            part_height_mm=_float(tr, part_var.get(), "insert.part_height"),
            wall_height_mm=_float(tr, wall_text, "insert.wall_height") if wall_text and not no_wall_var.get() else None,
            clearance_mm=_float(tr, clearance_var.get(), "insert.clearance"),
            wall_lines=_int(tr, lines_var.get(), "insert.lines"),
            brim_mm=_float(tr, brim_var.get(), "insert.brim"),
            chamfer=chamfer_var.get(),
            z_fine_mm=_float(tr, fine_var.get() or "0", "insert.fine"),
            standby_temperature=_int(tr, standby_var.get() or "0", "insert.standby"),
            adhesion_layers=_int(tr, adhesion_var.get() or "0", "insert.adhesion"),
            reprint_supports=supports_var.get(),
            allow_untested=bool(untested_var and untested_var.get()),
            holding_wall=not no_wall_var.get(),
            reheat_pass=reheat,
            reheat_gap_mm=_float(tr, reheat_gap_var.get(), "insert.reheat_gap") if reheat else 0.2,
            reheat_speed_mm_s=_float(tr, reheat_speed_var.get(), "insert.reheat_speed") if reheat else 20.0,
            reheat_passes=_int(tr, reheat_passes_var.get(), "insert.reheat_passes") if reheat else 1,
            reheat_temperature=(
                _int(tr, temperature_text, "insert.reheat_temp") if reheat and temperature_text else None
            ),
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
        if not plan.options.holding_wall:
            canvas.create_text(CANVAS_SIZE / 2, 6, text=tr("insert.canvas_no_wall"), fill=NOTE_COLOR, anchor="n")

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
            "insert.info" if o.holding_wall else "insert.info_bare",
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

    def experimental_changed(*_: object) -> None:
        for widget in wall_only:
            widget.state(["disabled"] if no_wall_var.get() else ["!disabled"])
        for widget in reheat_entries:
            widget.state(["!disabled"] if reheat_var.get() else ["disabled"])
        experimental.update_title()
        # A preview made with other experimental settings no longer describes the job.
        if shown["state"][0] == "plan":
            preview()

    no_wall_var.trace_add("write", experimental_changed)
    reheat_var.trace_add("write", experimental_changed)

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
            reheat = (
                tr("insert.done_reheat", seconds=report.reheat_seconds, gap=chosen.reheat_gap_mm, resume=report.resume_layer)
                if report.reheat_hover_z is not None
                else ""
            )
            messagebox.showinfo(
                "Layer Rescue",
                tr(
                    "insert.done" if report.holding_wall else "insert.done_no_wall",
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
                + reheat
                + (("\n\n" + tr("warnings") + "\n- " + "\n- ".join(warnings)) if warnings else ""),
                parent=root,
            )
            result["code"] = 0
            root.destroy()
        except (ValueError, OSError, ResumeError) as exc:
            messagebox.showerror("Layer Rescue", tr.message(str(exc)), parent=root)

    return InsertTab(tab, convert, ready, (part_var, confirm_var))
