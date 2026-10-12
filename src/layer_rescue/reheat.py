"""Experimental: a non-extruding reheat pass over the old surface before the first new layer.

Used by both modes:

* resume: after the resume preamble the hot nozzle traces the resumed layer once, a small gap above the
  last printed layer. In restarted (power-cut) mode the pass's Z moves are made relative, like the rest
  of the job.
* insert: after the preamble, it traces the first layer on top, a small gap above the seated part.

The idea is to warm the old surface so the first new layer bonds better (interlayer strength depends
on the temperature of the previous layer; see the reheating effect reported by Sinha et al., Rapid
Prototyping Journal 2018). Whether it helps on a given printer and filament is what the experimental
flag is for.

Safety: the nozzle never goes below ``old surface + gap`` (gap >= 0.05 mm, checked again by each mode's
output validator), the filament is retracted for the dry pass and restored after it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .gcode import ResumeError, _code, _command, _format_number, _parameter
from .toolpath import LayerToolpaths

if TYPE_CHECKING:  # pragma: no cover
    from .insert import InsertPlan

REHEAT_START = "; LAYER_RESCUE_REHEAT_START"
REHEAT_END = "; LAYER_RESCUE_REHEAT_END"

MIN_GAP_MM = 0.05
MAX_GAP_MM = 1.0
MIN_SPEED_MM_S = 2.0
MAX_SPEED_MM_S = 150.0
MAX_PASSES = 10
TRAVEL_MM_S = 150.0

Polyline = list[tuple[float, float]]


def check_reheat_options(gap_mm: float, speed_mm_s: float, passes: int, temperature: int | None) -> None:
    if not MIN_GAP_MM <= gap_mm <= MAX_GAP_MM:
        raise ResumeError(f"The reheat gap must be between {MIN_GAP_MM:g} and {MAX_GAP_MM:g} mm.")
    if not MIN_SPEED_MM_S <= speed_mm_s <= MAX_SPEED_MM_S:
        raise ResumeError(f"The reheat speed must be between {MIN_SPEED_MM_S:g} and {MAX_SPEED_MM_S:g} mm/s.")
    if not 1 <= passes <= MAX_PASSES:
        raise ResumeError(f"Reheat passes must be between 1 and {MAX_PASSES}.")
    if temperature is not None and not 150 <= temperature <= 300:
        raise ResumeError("The reheat temperature must be between 150 and 300°C.")


def reheat_paths(layer: LayerToolpaths) -> list[Polyline]:
    """The part toolpaths (no support, brim, purge) of the first repair layer, as XY polylines."""
    return [list(extrusion.points) for extrusion in layer.part_extrusions() if len(extrusion.points) >= 2]


def path_length_mm(paths: list[Polyline]) -> float:
    total = 0.0
    for points in paths:
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            total += ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    return total


def estimated_seconds(path_mm: float, speed_mm_s: float, passes: int) -> float:
    return path_mm * passes / speed_mm_s


def _last_value(lines: list[str], commands: set[str], axis: str) -> float | None:
    value = None
    for raw in lines:
        code = _code(raw)
        if code and _command(code) in commands:
            found = _parameter(code, axis)
            if found is not None:
                value = found
    return value


def _travel_target(preamble: list[str]) -> tuple[float, float] | None:
    """XY of the preamble's "travel above the part" move (the start of the first repair layer)."""
    for raw in reversed(preamble):
        if "travel above the part" in raw:
            code = _code(raw)
            x, y = _parameter(code, "X"), _parameter(code, "Y")
            if x is not None and y is not None:
                return (x, y)
    return None


def _last_part_fan(lines: list[str]) -> str | None:
    fan = None
    for raw in lines:
        code = _code(raw)
        if not code:
            continue
        command = _command(code)
        if command == "M106":
            p = _parameter(code, "P")
            if p is None or int(p) in {0, 1}:
                fan = code
        elif command == "M107":
            fan = "M106 S0"
    return fan


def reheat_block(plan: InsertPlan, preamble: list[str], retract_mm: float, extruder: str = "") -> tuple[list[str], float]:
    """Insert mode: G-code for the reheat pass, placed right after the resume preamble. Returns (lines, hover Z)."""
    options = plan.options
    if not plan.reheat_paths:
        raise ResumeError("The first layer on top has no part toolpaths to trace for the reheat pass.")
    hover_z = round(options.part_height_mm + options.reheat_gap_mm, 3)
    lines = reheat_lines(
        paths=plan.reheat_paths,
        hover_z=hover_z,
        layer_z=round(plan.resume_layer.z + plan.z_offset, 3),
        layer_number=plan.resume_layer.number,
        surface="the part top",
        gap_mm=options.reheat_gap_mm,
        speed_mm_s=options.reheat_speed_mm_s,
        passes=options.reheat_passes,
        temperature=options.reheat_temperature,
        preamble=preamble,
        retract_mm=retract_mm,
        extruder=extruder,
        restore_note="back to the adhesion-layer temperature",
        layer_note="back to the first repair layer height",
    )
    return lines, hover_z


def reheat_lines(
    *,
    paths: list[Polyline],
    hover_z: float,
    layer_z: float,
    layer_number: int,
    surface: str,
    gap_mm: float,
    speed_mm_s: float,
    passes: int,
    temperature: int | None,
    preamble: list[str],
    retract_mm: float,
    extruder: str = "",
    restore_note: str = "back to the print temperature",
    layer_note: str = "back to the layer height",
) -> list[str]:
    """The reheat pass in absolute Z: hover at ``hover_z``, trace ``paths``, then return to ``layer_z``.

    Called right after a resume preamble, which leaves the nozzle at ``layer_z`` above the start of the
    layer with the filament un-retracted. Restarted (power-cut) jobs convert the Z moves to relative ones.
    """
    if not paths:
        raise ResumeError("The resumed layer has no part toolpaths to trace for the reheat pass.")
    first_xy = _travel_target(preamble)
    current = _last_value(preamble, {"M109", "M104"}, "S")
    current_temp = int(current) if current is not None else None
    fan_before = _last_part_fan(preamble)
    feed = int(round(speed_mm_s * 60))
    travel = int(round(TRAVEL_MM_S * 60))

    block = [
        REHEAT_START,
        f"; Layer Rescue (experimental): non-extruding reheat pass over the toolpaths of layer "
        f"{layer_number}, {_format_number(gap_mm)} mm above {surface} "
        f"(Z={_format_number(hover_z)}), {_format_number(speed_mm_s)} mm/s, "
        f"{passes} pass(es)",
        "G90",
        "M83",
        "M106 S0 ; part fan off while reheating",
    ]
    if temperature is not None and temperature != current_temp:
        block.append(f"M109 S{temperature}{extruder} ; reheat temperature")
    if retract_mm > 0:
        block.append(f"G1 E-{_format_number(retract_mm)} F1800 ; retract before the dry pass")
    block.append(f"G1 Z{_format_number(hover_z)} F600 ; reheat height")

    last: tuple[float, float] | None = None
    for _ in range(passes):
        for points in paths:
            sx, sy = points[0]
            if last is None or abs(last[0] - sx) > 1e-6 or abs(last[1] - sy) > 1e-6:
                block.append(f"G1 X{sx:.3f} Y{sy:.3f} F{travel}")
            block.append(f"G1 F{feed}")
            for (ax, ay), (bx, by) in zip(points, points[1:]):
                if ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 < 1e-4:
                    continue
                block.append(f"G1 X{bx:.3f} Y{by:.3f}")
            last = points[-1]

    if first_xy is not None:
        block.append(
            f"G1 X{_format_number(first_xy[0])} Y{_format_number(first_xy[1])} F{travel} ; back to the layer start"
        )
    block.append(f"G1 Z{_format_number(layer_z)} F600 ; {layer_note}")
    if retract_mm > 0:
        block.append(f"G1 E{_format_number(retract_mm)} F1800 ; undo the retraction")
    block.append("G92 E0")
    if temperature is not None and current_temp is not None and temperature != current_temp:
        block.append(f"M109 S{current_temp}{extruder} ; {restore_note}")
    if fan_before:
        block.append(f"{fan_before} ; part fan as before the pass")
    block.append(REHEAT_END)
    return block


def reheat_z_values(block: list[str], start_z: float) -> list[float]:
    """Nominal nozzle Z after every Z move of ``block`` (absolute or relative), starting at ``start_z``."""
    z = start_z
    relative = False
    values: list[float] = []
    for raw in block:
        code = _code(raw)
        command = _command(code) if code else None
        if command == "G90":
            relative = False
        elif command == "G91":
            relative = True
        elif command in {"G0", "G1", "G2", "G3"}:
            value = _parameter(code, "Z")
            if value is not None:
                z = z + value if relative else value
                values.append(round(z, 4))
    return values


def check_reheat_block(lines: list[str], start: int, lowest_z: float, start_z: float) -> int:
    """Validate the reheat block that must start at ``lines[start]``; returns the index of its end marker."""
    if start >= len(lines) or lines[start].strip() != REHEAT_START:
        raise ResumeError("Internal validation failed: the reheat pass must follow the resume block.")
    try:
        end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == REHEAT_END)
    except StopIteration:
        raise ResumeError("Internal validation failed: the reheat pass is not terminated.") from None
    block = lines[start : end + 1]
    for raw in block:
        code = _code(raw)
        if code and _command(code) in {"G0", "G1", "G2", "G3"}:
            moves_xy = _parameter(code, "X") is not None or _parameter(code, "Y") is not None
            if moves_xy and _parameter(code, "E") is not None:
                raise ResumeError("Internal validation failed: the reheat pass must not extrude.")
    z_values = [start_z, *reheat_z_values(block, start_z)]  # a relative move of 0 is left out
    if min(z_values) < lowest_z - 1e-6:
        raise ResumeError("Internal validation failed: the reheat pass goes below its safe height.")
    if abs(z_values[-1] - start_z) > 1e-6:
        raise ResumeError("Internal validation failed: the reheat pass does not return to the layer height.")
    return end
