"""The insert panel ("part came off / print on a finished part") of the Layer Rescue window."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, NamedTuple

from . import gui_theme as theme
from .fileio import rewrite_with
from .gcode import Analysis, ResumeError
from .gui_art import Illustration
from .gui_widgets import (
    WRAP,
    Collapsible,
    StepCard,
    StepFlow,
    WrappedCheck,
    field,
    secondary_button,
    set_enabled,
    swatch,
    text,
)
from .i18n import Translator
from .insert import InsertOptions, InsertPlan, build_insert_gcode, plan_insert, recommended_wall_height
from .preview import plan_shapes, view_bounds

CANVAS_SIZE = 240
INFO_WRAP = 300
# (fill, outline) per shape kind; amber = the old part, green = the first new layer, as everywhere else.
COLORS: dict[str, tuple[theme.Color | None, theme.Color]] = {
    "silhouette": (theme.AMBER_SOFT, theme.AMBER),
    "addition": (None, theme.GREEN),
    "brim": (None, theme.LINE),
    "wall-bottom": (None, theme.FAINT),
    "wall-top": (None, theme.INK),
    "support": (("#E6DFF7", "#2D2742"), theme.SUPPORT),
}
LEGEND = ("silhouette", "wall-bottom", "wall-top", "addition", "support")


class InsertTab(NamedTuple):
    frame: Any
    convert: Callable[[], None]
    ready: Callable[[], str | None]  # None when the G-code can be created, else a status text key
    watched: tuple[Any, ...]  # Tk variables that change ready()
    controls: dict[str, Any]  # main controls, for test scripts
    repaint: Callable[[], None]  # light/dark changed


def _float(tr: Translator, value: str, field_key: str) -> float:
    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        raise ResumeError(tr("insert.err_number", field=tr(field_key).rstrip(":"))) from None


def _int(tr: Translator, value: str, field_key: str) -> int:
    number = _float(tr, value, field_key)
    if number != int(number):
        raise ResumeError(tr("insert.err_whole", field=tr(field_key).rstrip(":")))
    return int(number)


def build_insert_tab(
    parent: Any,
    root: Any,
    path: Path,
    analysis: Analysis,
    result: dict,
    tr: Translator,
    fonts: theme.Fonts,
    untested_var: Any = None,
    reveal: Callable[[Any], None] | None = None,
) -> InsertTab:
    import tkinter as tk
    from tkinter import messagebox

    import customtkinter as ctk

    panel = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
    panel.columnconfigure(0, weight=1)
    controls: dict[str, Any] = {}
    repaints: list[Callable[[], None]] = []

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

    # Step 1: part and wall
    step1 = StepCard(tr, panel, 1, "insert.step1", fonts)
    step1.frame.grid(row=0, column=0, sticky="ew", pady=(0, 12))
    grid1 = ctk.CTkFrame(step1.body, fg_color="transparent", corner_radius=0)
    grid1.grid(row=0, column=0, sticky="w")
    text(tr, grid1, "insert.part_height", font=fonts.body).grid(row=0, column=0, sticky="w", pady=4)
    part_entry = field(grid1, part_var)
    part_entry.grid(row=0, column=1, sticky="w", pady=4, padx=(10, 0))
    controls["part_height"] = part_entry
    text(tr, grid1, "insert.part_layer", font=fonts.body, color=theme.MUTED).grid(row=1, column=0, sticky="w", pady=4)
    part_layer_entry = field(grid1, part_layer_var)
    part_layer_entry.grid(row=1, column=1, sticky="w", pady=4, padx=(10, 0))
    controls["part_layer"] = part_layer_entry
    text(tr, grid1, "insert.wall_height", font=fonts.body).grid(row=2, column=0, sticky="w", pady=4)
    wall_entry = field(grid1, wall_var)
    wall_entry.grid(row=2, column=1, sticky="w", pady=4, padx=(10, 0))
    text(tr, grid1, "insert.wall_hint", font=fonts.small, color=theme.MUTED).grid(
        row=2, column=2, sticky="w", padx=(10, 0)
    )
    preview_button = secondary_button(grid1, lambda: preview(), fonts, height=34)
    preview_button.grid(row=0, column=2, rowspan=2, sticky="w", padx=(16, 0))
    tr.on_change(lambda: preview_button.configure(text=tr("insert.preview")))
    controls["preview"] = preview_button

    def part_layer_changed(*_: object) -> None:
        value = part_layer_var.get().strip()
        if not value:
            return
        try:
            part_var.set(f"{analysis.layer(int(value)).z:g}")
        except (ValueError, ResumeError):
            pass

    part_layer_var.trace_add("write", part_layer_changed)

    # Step 2: result of the preview, next to the top view
    step2 = StepCard(tr, panel, 2, "insert.step2", fonts)
    step2.frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
    step2.body.columnconfigure(0, weight=1)
    step2.body.rowconfigure(2, weight=1)  # the warnings sit right under the result, not halfway down the view
    info_label = text(tr, step2.body, None, font=fonts.body, wrap=INFO_WRAP)
    info_label.grid(row=0, column=0, sticky="nw")
    warn_label = text(tr, step2.body, None, font=fonts.small, color=theme.WARN, wrap=INFO_WRAP)
    warn_label.grid(row=1, column=0, sticky="nw", pady=(8, 0))
    view = ctk.CTkFrame(step2.body, fg_color="transparent", corner_radius=0)
    view.grid(row=0, column=1, rowspan=3, sticky="ne", padx=(16, 0))
    text(tr, view, "insert.legend_title", font=fonts.small, color=theme.MUTED, wrap=CANVAS_SIZE).grid(
        row=0, column=0, sticky="w", pady=(0, 6)
    )
    canvas = tk.Canvas(view, highlightthickness=0, borderwidth=0)
    canvas.grid(row=1, column=0, sticky="w")
    legend = ctk.CTkFrame(view, fg_color="transparent", corner_radius=0)
    legend.grid(row=2, column=0, sticky="w", pady=(8, 0))
    for index, kind in enumerate(LEGEND):
        row, column = index // 2, (index % 2) * 2
        fill, outline = COLORS[kind]
        swatch(legend, fill or "", outline).grid(row=row, column=column, padx=(0 if column == 0 else 14, 6), pady=2)
        text(tr, legend, f"legend.{kind}", font=fonts.small).grid(row=row, column=column + 1, sticky="w")

    # Step 3: safety check
    step3 = StepCard(tr, panel, 3, "insert.step3", fonts)
    step3.frame.grid(row=2, column=0, sticky="ew", pady=(0, 12))
    text(tr, step3.body, "insert.check_intro", font=fonts.small, color=theme.MUTED, wrap=WRAP).grid(
        row=0, column=0, sticky="w", pady=(0, 8)
    )
    attended = WrappedCheck(tr, step3.body, confirm_var, "insert.check_attended", fonts)
    attended.grid(row=1, column=0, sticky="w")
    controls["check_attended"] = attended

    # The steps open one after another: a valid part height previews the job by itself (step 2), and a
    # successful preview opens the safety check (step 3). Any step can still be opened by clicking it.
    flow = StepFlow([step1, step2, step3], reveal)
    repaints.extend([step1.repaint, step2.repaint, step3.repaint])
    controls["insert_steps"] = flow
    controls["insert_step_1"], controls["insert_step_2"], controls["insert_step_3"] = step1, step2, step3
    pending: dict[str, Any] = {}

    def part_height() -> float | None:
        try:
            value = _float(tr, part_var.get(), "insert.part_height")
        except ResumeError:
            return None
        return value if value > 0 else None

    def step1_changed(*_: object) -> None:
        height = part_height()
        flow.update(0, height is not None, tr("insert.step1_summary", part=height) if height else "")
        job = pending.pop("preview", None)
        if job is not None:
            panel.after_cancel(job)
        if height is not None:
            pending["preview"] = panel.after(StepFlow.SETTLE_MS + 50, auto_preview)

    def auto_preview() -> None:
        pending.pop("preview", None)
        if part_height() is not None:
            preview()

    for watched_var in (part_var, wall_var):
        watched_var.trace_add("write", step1_changed)
    confirm_var.trace_add("write", lambda *_: flow.update(2, confirm_var.get(), tr("step.checked")))
    tr.on_change(step1_changed)

    # Advanced settings: two columns of label + field, then the two options.
    advanced = Collapsible(tr, panel, "insert.advanced", fonts)
    advanced.frame.grid(row=3, column=0, sticky="ew", pady=(0, 12))
    controls["advanced"] = advanced
    fields = ctk.CTkFrame(advanced.body, fg_color="transparent", corner_radius=0)
    fields.grid(row=0, column=0, sticky="w")
    wall_only: list[Any] = [wall_entry]  # fields that mean nothing without the holding wall
    wall_only_checks: list[WrappedCheck] = []
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
        text(tr, fields, key, font=fonts.small, wrap=190).grid(
            row=row, column=column, sticky="w", pady=4, padx=(0 if column == 0 else 22, 0)
        )
        entry = field(fields, var, width=70)
        entry.grid(row=row, column=column + 1, sticky="w", pady=4, padx=(8, 0))
        controls[key.replace("insert.", "")] = entry
        if key in ("insert.lines", "insert.brim"):
            wall_only.append(entry)
    chamfer_check = WrappedCheck(tr, advanced.body, chamfer_var, "insert.chamfer", fonts)
    chamfer_check.grid(row=1, column=0, sticky="w", pady=(10, 3))
    wall_only_checks.append(chamfer_check)
    WrappedCheck(tr, advanced.body, supports_var, "insert.supports", fonts).grid(row=2, column=0, sticky="w", pady=3)

    # Experimental features: off by default; the section title says how many are on even when it is closed.
    def experimental_on() -> str:
        count = int(no_wall_var.get()) + int(reheat_var.get())
        return tr("insert.experimental_on", n=count) if count else ""

    experimental = Collapsible(tr, panel, "insert.experimental", fonts, suffix=experimental_on)
    experimental.frame.grid(row=4, column=0, sticky="ew")
    controls["experimental"] = experimental
    body = experimental.body
    side_wrap = WRAP - 330
    text(tr, body, "insert.experimental_intro", font=fonts.small, color=theme.WARN, wrap=WRAP - 40).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
    )
    no_wall_check = WrappedCheck(tr, body, no_wall_var, "insert.no_wall", fonts, wrap=side_wrap)
    no_wall_check.grid(row=1, column=0, sticky="nw")
    controls["no_wall"] = no_wall_check
    text(tr, body, "insert.no_wall_hint", font=fonts.small, color=theme.MUTED, wrap=side_wrap).grid(
        row=2, column=0, sticky="nw", padx=(32, 0), pady=(4, 16)
    )
    no_wall_art = Illustration(body, "no_wall", background=theme.SURFACE_ALT)
    no_wall_art.canvas.grid(row=1, column=1, rowspan=2, sticky="ne", padx=(12, 0), pady=(0, 16))
    repaints.append(no_wall_art.repaint)
    reheat_check = WrappedCheck(tr, body, reheat_var, "insert.reheat", fonts, wrap=side_wrap)
    reheat_check.grid(row=3, column=0, sticky="nw")
    controls["reheat"] = reheat_check
    text(tr, body, "insert.reheat_hint", font=fonts.small, color=theme.MUTED, wrap=side_wrap).grid(
        row=4, column=0, sticky="nw", padx=(32, 0), pady=(4, 0)
    )
    reheat_art = Illustration(body, "reheat", background=theme.SURFACE_ALT)
    reheat_art.canvas.grid(row=3, column=1, rowspan=3, sticky="ne", padx=(12, 0))
    repaints.append(reheat_art.repaint)
    reheat_fields = ctk.CTkFrame(body, fg_color="transparent", corner_radius=0)
    reheat_fields.grid(row=5, column=0, sticky="nw", padx=(32, 0), pady=(8, 0))
    reheat_entries: list[Any] = []
    for index, (key, var) in enumerate(
        [
            ("insert.reheat_gap", reheat_gap_var),
            ("insert.reheat_speed", reheat_speed_var),
            ("insert.reheat_passes", reheat_passes_var),
            ("insert.reheat_temp", reheat_temp_var),
        ]
    ):
        text(tr, reheat_fields, key, font=fonts.small, wrap=190).grid(row=index, column=0, sticky="w", pady=2, padx=(0, 10))
        entry = field(reheat_fields, var, width=70)
        entry.grid(row=index, column=1, sticky="w", pady=2)
        set_enabled(entry, False)
        reheat_entries.append(entry)
        controls[key.replace("insert.", "")] = entry

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
        scale = theme.widget_scaling(canvas)
        size = CANVAS_SIZE * scale
        canvas.configure(width=int(size), height=int(size), background=theme.pick(theme.SURFACE_ALT))
        canvas.delete("all")
        if plan is None:
            canvas.create_text(
                size / 2, size / 2, text="—", fill=theme.pick(theme.FAINT), font=fonts.heading
            )
            return
        shapes = plan_shapes(plan)
        min_x, min_y, max_x, max_y = view_bounds(shapes)
        factor = (size - 24 * scale) / max(max_x - min_x, max_y - min_y)

        def xy(point: tuple[float, float]) -> tuple[float, float]:
            return (12 * scale + (point[0] - min_x) * factor, size - 12 * scale - (point[1] - min_y) * factor)

        for kind in ("silhouette", "addition", "brim", "wall-bottom", "wall-top", "support"):
            fill, outline = COLORS[kind]
            for shape in shapes:
                if shape.kind == kind and len(shape.points) >= 3:
                    coords = [c for point in shape.points for c in xy(point)]
                    canvas.create_polygon(
                        *coords,
                        fill=theme.pick(fill) if fill else "",
                        outline=theme.pick(outline),
                        width=max(1.0, 1.4 * scale),
                    )
        canvas.create_text(
            size / 2, size - 3 * scale, text="▼ " + tr("insert.canvas_front"), fill=theme.pick(theme.MUTED),
            anchor="s", font=fonts.small,
        )
        if not plan.options.holding_wall:
            canvas.create_text(
                size / 2, 4 * scale, text=tr("insert.canvas_no_wall"), fill=theme.pick(theme.WARN), anchor="n",
                font=fonts.small,
            )

    def render() -> None:
        state = shown["state"]
        if state[0] == "start":
            info_label.configure(text=tr("insert.info_start"), text_color=theme.MUTED)
            warn_label.configure(text="")
            draw(None)
            flow.update(1, False)
            return
        if state[0] == "error":
            info_label.configure(text=tr.message(state[1]), text_color=theme.WARN)
            warn_label.configure(text="")
            draw(None)
            flow.update(1, False)
            return
        plan: InsertPlan = state[1]
        flow.update(1, True, tr("insert.step2_summary", layer=plan.resume_layer.number))
        o = plan.options
        message = tr(
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
            message += tr("insert.info_supports", layer=plan.printed_layers[-1].number)
        info_label.configure(text=message, text_color=theme.INK)
        warnings = [tr.message(warning) for warning in plan.warnings]
        warn_label.configure(text=(tr("warnings") + "\n• " + "\n• ".join(warnings)) if warnings else "")
        draw(plan)

    tr.on_change(render)
    repaints.append(render)

    def preview() -> InsertPlan | None:
        try:
            plan = plan_insert(analysis, options())
        except (ValueError, ResumeError) as exc:
            last_plan.pop("plan", None)
            shown["state"] = ("error", str(exc))
            render()
            return None
        last_plan["plan"] = plan
        shown["state"] = ("plan", plan)
        render()
        return plan

    def experimental_changed(*_: object) -> None:
        for widget in wall_only:
            set_enabled(widget, not no_wall_var.get())
        for check in wall_only_checks:
            check.set_enabled(not no_wall_var.get())
        for widget in reheat_entries:
            set_enabled(widget, reheat_var.get())
        experimental.update_title()
        # A preview made with other experimental settings no longer describes the job.
        if shown["state"][0] == "plan":
            preview()

    no_wall_var.trace_add("write", experimental_changed)
    reheat_var.trace_add("write", experimental_changed)
    no_wall_var.trace_add("write", lambda *_: no_wall_art.play() if no_wall_var.get() else None)
    reheat_var.trace_add("write", lambda *_: reheat_art.play() if reheat_var.get() else None)

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
                path, lambda source: build_insert_gcode(source, chosen, last_plan.get("plan"))
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

    def repaint() -> None:
        for callback in repaints:
            callback()

    return InsertTab(panel, convert, ready, (part_var, confirm_var), controls, repaint)
