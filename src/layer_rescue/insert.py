"""Insert mode: print a holding wall, pause for the operator to seat a loose part, then print on top.

Output layout (all in one job, the printer is never power-cycled, so Z stays homed):

1. The source job's header and start G-code, untouched (homing and bed leveling run on an empty bed).
2. Layers 1..k_wall: each layer keeps its slicer frame (layer markers, progress, fans, timelapse) but its
   toolpaths are replaced by the holding wall.
3. Pause block: lift to Z_part + ``park_lift_mm``, park at a rear corner, nozzle to standby, machine pause.
4. Layers above the wall up to the part's top are dropped.
5. The retained-mode resume preamble (reheat, purge, wipe, travel above the part, descend) and the
   rest of the source job, every absolute Z shifted by ``delta = Z_part - z_k``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import geometry as geo
from ._version import __version__
from .flow import FlowSettings, flow_settings_from_config
from .gcode import (
    LAYER_MARKER_RE,
    Analysis,
    LayerInfo,
    ResumeError,
    _code,
    _command,
    _format_number,
    _next_extrusion_mode,
    _parameter,
    analyze_gcode,
    config_float,
)
from .machine_state import _scan_machine_state, _validate_supported_source
from .resume import ResumeOptions, ZReferenceMode, _resume_preamble
from .toolpath import LayerToolpaths, read_toolpaths
from .supports import SupportPlan, emit_support_layer, plan_supports
from .wall import EmitState, WallOptions, WallPlan, emit_wall_layer, footprint, plan_wall, section

# Safety limits (see the plan's "minimum part size" decision).
MIN_PART_HEIGHT_MM = 3.0
MIN_WALL_HEIGHT_MM = 2.0
MIN_GAP_ABOVE_WALL_MM = 1.0
MIN_BASE_MM = 5.0
RECOMMENDED_BASE_MM = 10.0
RECOMMENDED_PART_HEIGHT_MM = 5.0
MAX_Z_FINE_MM = 0.3
OVERHANG_TOLERANCE_MM = 0.5
OVERHANG_WARN_AREA_MM2 = 1.0
PAUSE_BLOCK_START = "; LAYER_RESCUE_INSERT_PAUSE_START"
PAUSE_BLOCK_END = "; LAYER_RESCUE_INSERT_PAUSE_END"
INSERT_MARKER = "; LAYER_RESCUE_INSERT_MODE"


@dataclass(frozen=True)
class InsertOptions:
    part_height_mm: float
    wall_height_mm: float | None = None  # None = recommended
    clearance_mm: float = 0.25
    wall_lines: int = 4
    brim_mm: float = 5.0
    chamfer: bool = True
    z_fine_mm: float = 0.0  # added to the measured height; negative = more squish on the first layer
    park_lift_mm: float = 15.0
    standby_temperature: int = 140  # nozzle temperature while paused; 0 keeps the print temperature
    adhesion_layers: int = 2
    adhesion_temp_boost: int = 10
    adhesion_speed_percent: int = 50
    adhesion_fan_off: bool = True
    purge_length_mm: float = 30.0
    z_lift_mm: float = 2.0
    nozzle_temperature: int | None = None
    bed_temperature: int | None = None
    reprint_supports: bool = True  # print the supports below the part height before the pause
    allow_untested: bool = False  # accept the risks of a printer / filament setup that has not been tested


@dataclass(frozen=True)
class InsertReport:
    part_layer: int  # last source layer that the physical part replaces
    resume_layer: int
    total_layers: int
    part_height_mm: float
    part_layer_z: float
    z_offset_mm: float
    first_layer_thickness_mm: float
    wall_layers: int
    wall_top_z: float
    wall_height_mm: float
    park_z: float
    nozzle_temperature: int
    bed_temperature: int
    wall_filament_mm: float
    support_layers: int
    last_printed_layer: int  # the pause comes after this layer
    silhouette_bounds: tuple[float, float, float, float]
    symmetric: bool
    source_sha256: str
    output_sha256: str
    backup_path: Path | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class InsertPlan:
    """Everything decided before G-code is written; also what the GUI previews."""

    analysis: Analysis
    options: InsertOptions
    flow: FlowSettings
    part_layer: LayerInfo
    resume_layer: LayerInfo
    wall_layers: list[LayerInfo]
    wall_height_mm: float
    z_offset: float
    wall: WallPlan
    top_section: geo.Region
    addition_section: geo.Region
    symmetric: bool
    park_xy: tuple[float, float]
    park_z: float
    warnings: list[str]
    supports: SupportPlan | None = None
    printed_layers: list[LayerInfo] = field(default_factory=list)  # layers printed before the pause


def recommended_wall_height(part_height_mm: float) -> float:
    """Half the part, at least 2 mm, at most 15 mm, and always 1 mm below the top."""
    value = min(max(part_height_mm * 0.5, 3.0), 15.0, part_height_mm - MIN_GAP_ABOVE_WALL_MM)
    return round(max(value, MIN_WALL_HEIGHT_MM), 1)


def _check_options(options: InsertOptions, wall_height: float) -> None:
    if options.part_height_mm < MIN_PART_HEIGHT_MM:
        raise ResumeError(f"The part must be at least {MIN_PART_HEIGHT_MM:g} mm tall for insert mode.")
    if wall_height < MIN_WALL_HEIGHT_MM:
        raise ResumeError(f"The holding wall must be at least {MIN_WALL_HEIGHT_MM:g} mm tall.")
    if wall_height > options.part_height_mm - MIN_GAP_ABOVE_WALL_MM + 1e-9:
        raise ResumeError(
            f"The holding wall must end at least {MIN_GAP_ABOVE_WALL_MM:g} mm below the top of the part "
            f"(at most {options.part_height_mm - MIN_GAP_ABOVE_WALL_MM:g} mm here), or the nozzle hits it."
        )
    if not 0.05 <= options.clearance_mm <= 1.0:
        raise ResumeError("The wall clearance must be between 0.05 and 1.0 mm.")
    if not 2 <= options.wall_lines <= 12:
        raise ResumeError("The wall must be 2 to 12 lines thick.")
    if not 0 <= options.brim_mm <= 15:
        raise ResumeError("The brim must be between 0 and 15 mm.")
    if abs(options.z_fine_mm) > MAX_Z_FINE_MM + 1e-9:
        raise ResumeError(f"The Z fine adjustment must be within ±{MAX_Z_FINE_MM:g} mm.")
    if not 5 <= options.park_lift_mm <= 50:
        raise ResumeError("The park lift must be between 5 and 50 mm.")
    if options.standby_temperature and not 100 <= options.standby_temperature <= 250:
        raise ResumeError("The standby temperature must be 0 (off) or between 100 and 250°C.")
    if not 0 <= options.adhesion_layers <= 10:
        raise ResumeError("Adhesion layers must be between 0 and 10.")
    if not 0 <= options.adhesion_temp_boost <= 30:
        raise ResumeError("The adhesion temperature boost must be between 0 and 30°C.")
    if not 20 <= options.adhesion_speed_percent <= 100:
        raise ResumeError("The adhesion speed must be between 20 and 100 %.")


def _nearest_layer(analysis: Analysis, z: float) -> LayerInfo:
    return min(analysis.layers, key=lambda layer: (abs(layer.z - z), layer.z))


def plan_insert(text_or_analysis: str | Analysis, options: InsertOptions) -> InsertPlan:
    analysis = text_or_analysis if isinstance(text_or_analysis, Analysis) else analyze_gcode(text_or_analysis)
    warnings: list[str] = list(analysis.warnings)
    wall_height = options.wall_height_mm if options.wall_height_mm is not None else recommended_wall_height(
        options.part_height_mm
    )
    _check_options(options, wall_height)

    layers = list(analysis.layers)
    if layers[0].number != 1:
        raise ResumeError("Insert mode needs the complete job starting at layer 1.")
    part_layer = _nearest_layer(analysis, options.part_height_mm)
    position = layers.index(part_layer)
    if position + 1 >= len(layers):
        raise ResumeError(
            f"The part is as tall as the whole model ({layers[-1].z:g} mm): there is nothing left to print on top."
        )
    resume_layer = layers[position + 1]
    if resume_layer.number != part_layer.number + 1:
        raise ResumeError("The layers around the part height are not contiguous.")
    delta = options.part_height_mm - part_layer.z + options.z_fine_mm
    first_thickness = resume_layer.z + delta - options.part_height_mm
    if first_thickness < 0.05:
        raise ResumeError("The Z fine adjustment leaves no room for the first layer on top of the part.")

    wall_layers = [layer for layer in layers if layer.z <= wall_height + 1e-6]
    if len(wall_layers) < 2:
        raise ResumeError("The holding wall must span at least two layers.")
    if wall_layers[-1].number >= part_layer.number:
        raise ResumeError("The holding wall must end below the top of the part.")

    state = _scan_machine_state(analysis, resume_layer.change_line)
    warnings.extend(_validate_supported_source(analysis, state, options.allow_untested))

    needed = [layer.number for layer in layers[: position + 2]]
    toolpaths = read_toolpaths(analysis, needed)
    _check_single_object(toolpaths, needed)

    flow = flow_settings_from_config(analysis.config)
    wall_options = WallOptions(
        clearance_mm=options.clearance_mm,
        wall_lines=options.wall_lines,
        brim_mm=options.brim_mm,
        chamfer_mm=0.6 if options.chamfer else 0.0,
    )
    for layer in wall_layers:
        if not toolpaths[layer.number].outline_extrusions():
            raise ResumeError(
                f"Layer {layer.number} has no printed outline to derive the holding wall from."
            )

    part_layers = layers[: position + 1]
    supports: SupportPlan | None = None
    has_support = any(toolpaths[layer.number].support_extrusions() for layer in layers[: position + 2])
    if has_support and options.reprint_supports:
        supports = plan_supports(part_layers, toolpaths, options.clearance_mm, resume_layer)
        if supports.source_mm > 0 and supports.dropped_mm / supports.source_mm > 0.02:
            warnings.append(
                f"{supports.dropped_mm / supports.source_mm:.0%} of the support below the part height lies where "
                "the part is lowered in (or stands on the part) and is not reprinted."
            )
        if supports.any:
            warnings.append(
                "Supports below the part height are printed again before the pause. Remove what is left of the "
                "old supports from the part so it slides over the new ones."
            )
        if supports.unsupported_above_mm2 > 2.0:
            warnings.append(
                f"About {supports.unsupported_above_mm2:.0f} mm² of support just above the part height has nothing "
                "under it and will start in the air."
            )
    elif has_support:
        warnings.append(
            "The job has supports but reprinting them is off: supports above the part height start in the air "
            "unless the old ones are still on the part."
        )
    keep_out = {number: layer.footprint for number, layer in supports.layers.items()} if supports else {}
    wall = plan_wall(wall_layers, toolpaths, flow, wall_options, keep_out, above=part_layers[len(wall_layers):])
    printed_layers = list(wall_layers)
    if supports and supports.last_layer_number is not None:
        printed_layers = [
            layer for layer in part_layers
            if layer.number <= max(supports.last_layer_number, wall_layers[-1].number)
        ]

    min_x, min_y, max_x, max_y = geo.bounds_mm(wall.silhouette)
    base = min(max_x - min_x, max_y - min_y)
    if base < MIN_BASE_MM:
        raise ResumeError(
            f"The part is too small to hold in a wall (narrowest side {base:.1f} mm, minimum {MIN_BASE_MM:g} mm)."
        )
    if base < RECOMMENDED_BASE_MM:
        warnings.append(
            f"The part's footprint is narrow ({base:.1f} mm); the wall may not hold it firmly. Seat it gently."
        )
    if options.part_height_mm < RECOMMENDED_PART_HEIGHT_MM:
        warnings.append("The part is shorter than 5 mm; the wall can only grip a small area.")

    _check_bed(analysis, wall)

    top_section = section(toolpaths[part_layer.number])
    addition_section = section(toolpaths[resume_layer.number])
    overhang = geo.difference(addition_section, geo.offset(top_section, OVERHANG_TOLERANCE_MM))
    if geo.area_mm2(overhang) > OVERHANG_WARN_AREA_MM2:
        warnings.append(
            f"The first layer on top reaches {geo.area_mm2(overhang):.0f} mm² beyond the part's top surface; "
            "that area is printed in the air."
        )

    symmetric = geo.symmetric_under_rotation(wall.silhouette)
    if symmetric:
        warnings.append(
            "The part looks the same when turned, so the wall cannot fix its orientation. Seat it facing the "
            "same way as in Bambu Studio (the plate's front edge is the front)."
        )

    max_z = config_float(analysis.config, "printable_height", default=250.0)
    park_z = min(options.part_height_mm + options.park_lift_mm, max_z - 1.0)
    if park_z < options.part_height_mm + 5.0:
        raise ResumeError("The part is too tall to park the toolhead safely above it.")
    center_x = (min_x + max_x) / 2
    park_xy = (236.0, 250.0) if center_x < 128 else (20.0, 250.0)

    return InsertPlan(
        analysis=analysis,
        options=options,
        flow=flow,
        part_layer=part_layer,
        resume_layer=resume_layer,
        wall_layers=wall_layers,
        wall_height_mm=wall_height,
        z_offset=delta,
        wall=wall,
        top_section=top_section,
        addition_section=addition_section,
        symmetric=symmetric,
        park_xy=park_xy,
        park_z=park_z,
        warnings=warnings,
        supports=supports,
        printed_layers=printed_layers,
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _check_single_object(toolpaths: dict[int, LayerToolpaths], numbers: list[int]) -> None:
    objects: set[str] = set()
    for number in numbers:
        layer_paths = toolpaths[number]
        objects |= layer_paths.object_ids
        for extrusion in layer_paths.extrusions:
            feature = extrusion.feature.lower()
            if "prime tower" in feature or "wipe tower" in feature:
                raise ResumeError("Insert mode does not support a prime tower. Disable it and slice again.")
    if len(objects) > 1:
        raise ResumeError(
            f"Insert mode supports a single object on the plate; this job prints {len(objects)} objects below the "
            "part height."
        )


def _check_bed(analysis: Analysis, wall: WallPlan) -> None:
    printed = footprint(wall)
    printable = geo.polygon_from_config(analysis.config.get("printable_area")) or geo.polygon_from_config(
        "0x0,256x0,256x256,0x256"
    )
    if geo.area_mm2(geo.difference(printed, printable)) > 0.01:
        raise ResumeError("The holding wall (with its brim) does not fit on the bed. Move the model inwards.")
    excluded = geo.polygon_from_config(analysis.config.get("bed_exclude_area"))
    if excluded and geo.area_mm2(geo.intersection(printed, excluded)) > 0.01:
        raise ResumeError("The holding wall would cross the bed's excluded area. Move the model away from it.")


# --------------------------------------------------------------------------------------------------
# G-code assembly


_BLOCK_OPEN = {"M622": "M623", "M624": "M625", "M620": "M621"}
OBJECT_START_RE = re.compile(r"^\s*;\s*start printing object", re.IGNORECASE)
FEATURE_LINE_RE = re.compile(r"^\s*;\s*(?:FEATURE|TYPE)\s*:", re.IGNORECASE)


def _is_block_open(code: str, command: str | None) -> bool:
    return command in _BLOCK_OPEN and re.search(r"(?:^|\s)[SJ]?\d", code[len(command):]) is not None


def _layer_frame(analysis: Analysis, layer: LayerInfo) -> list[str]:
    """The slicer's per-layer frame without its toolpaths.

    Kept: markers, comments, progress, fan/acceleration commands, Z-only moves and complete firmware
    conditional blocks (timelapse). Dropped: everything from the first feature or object section on,
    and any stray XY/E move before it (the wall code positions and primes the nozzle itself).
    """
    frame: list[str] = []
    depth: list[str] = []
    for raw in analysis.lines[layer.change_line : layer.end_line]:
        code = _code(raw)
        command = _command(code) if code else None
        if not depth and (FEATURE_LINE_RE.match(raw) or OBJECT_START_RE.match(raw) or command == "M624"):
            break
        if command and _is_block_open(code, command):
            depth.append(_BLOCK_OPEN[command])
            frame.append(raw)
            continue
        if depth:
            frame.append(raw)
            if command == depth[-1]:
                depth.pop()
            continue
        if command in {"G0", "G1", "G2", "G3"}:
            has_xy_or_e = any(_parameter(code, axis) is not None for axis in ("X", "Y", "E"))
            if command in {"G2", "G3"} or has_xy_or_e:
                if command in {"G1", "G2", "G3"} and (_parameter(code, "E") or 0) > 0 and (
                    _parameter(code, "X") is not None or _parameter(code, "Y") is not None
                ):
                    break
                continue
        frame.append(raw)
    if depth:
        # A conditional block that spans into the toolpaths: keep the layer's frame up to before it.
        raise ResumeError(f"Layer {layer.number}: a firmware conditional block runs into the toolpaths.")
    return frame


def _pending_retraction(analysis: Analysis, stop_line: int) -> float:
    """Filament pulled back (positive mm) at ``stop_line``: E-only moves since the last printing move."""
    net = 0.0
    relative = True
    for raw in analysis.lines[analysis.executable_start_line : stop_line]:
        code = _code(raw)
        if not code:
            continue
        command = _command(code)
        if command in {"M83", "G91"}:
            relative = True
        elif command in {"M82", "G90"}:
            relative = False
        elif command == "G92" and _parameter(code, "E") is not None:
            continue
        if command not in {"G0", "G1", "G2", "G3"} or not relative:
            continue
        e = _parameter(code, "E")
        if e is None:
            continue
        moves_xy = _parameter(code, "X") is not None or _parameter(code, "Y") is not None or command in {"G2", "G3"}
        if moves_xy and e > 0:
            net = 0.0
        elif not moves_xy:
            net += e
    return max(0.0, -net)


def _is_part_fan(code: str) -> bool:
    fan = _parameter(code, "P")
    return fan is None or int(fan) in {0, 1}


def _offset_z(body: list[str], delta: float, max_z: float) -> list[str]:
    """Shift every absolute Z coordinate in ``body`` by ``delta``."""
    if abs(delta) < 1e-9:
        return list(body)
    output: list[str] = []
    positioning = "G90"
    for raw in body:
        code = _code(raw)
        command = _command(code) if code else None
        if command in {"G90", "G91"}:
            positioning = command
        if command == "G92" and _parameter(code, "Z") is not None:
            raise ResumeError("Insert mode cannot shift a source that reassigns Z with G92.")
        if command in {"G0", "G1", "G2", "G3"} and positioning == "G90":
            z_value = _parameter(code, "Z")
            if z_value is not None and z_value + delta <= max_z:
                comment = raw.split(";", 1)[1] if ";" in raw else None
                new_code = re.sub(
                    r"(?<=\s)Z-?(?:\d+(?:\.\d*)?|\.\d+)(?=\s|$)",
                    f"Z{_format_number(z_value + delta)}",
                    " " + code,
                    count=1,
                    flags=re.IGNORECASE,
                ).strip()
                raw = new_code + (f" ;{comment}" if comment is not None else "")
        output.append(raw)
    return output


def _adhesion_body(
    analysis: Analysis,
    plan: InsertPlan,
    body_start: int,
    nozzle: int,
    boost_nozzle: int,
    speed_restore: str,
    fallback_fan: str | None,
) -> list[str]:
    """The retained body with the first ``adhesion_layers`` layers printed hotter, slower and without part fan."""
    options = plan.options
    body = list(analysis.lines[body_start:])
    if options.adhesion_layers <= 0:
        return body
    layers_after = [layer for layer in analysis.layers if layer.number >= plan.resume_layer.number]
    restore_layer = layers_after[options.adhesion_layers] if len(layers_after) > options.adhesion_layers else None
    restore_at = (restore_layer.change_line - body_start) if restore_layer else len(body)

    output: list[str] = []
    last_fan = fallback_fan
    for index, raw in enumerate(body):
        if index == restore_at:
            output.append("; Layer Rescue: end of adhesion layers, back to normal settings")
            if boost_nozzle != nozzle:
                output.append(f"M104 S{nozzle}")
            if options.adhesion_speed_percent != 100:
                output.append(speed_restore)
            if options.adhesion_fan_off and last_fan:
                output.append(last_fan)
        if index < restore_at:
            code = _code(raw)
            command = _command(code) if code else None
            if options.adhesion_fan_off and command == "M106" and _is_part_fan(code):
                last_fan = code
                output.append(f"; Layer Rescue adhesion: part fan held off (was: {code})")
                continue
            if options.adhesion_fan_off and command == "M107":
                last_fan = "M106 S0"
                continue
            if command in {"M104", "M109"} and boost_nozzle != nozzle and (_parameter(code, "S") or 0) > 0:
                output.append(f"; Layer Rescue adhesion: keep {boost_nozzle}°C (was: {code})")
                continue
        output.append(raw)
    return output


def build_insert_gcode(
    text: str, options: InsertOptions, plan: InsertPlan | None = None
) -> tuple[str, InsertReport]:
    """``plan``: a plan already made for this text and these options (the GUI preview), to save time."""
    if plan is None or plan.options != options or plan.analysis.source_sha256 != _sha256(text):
        plan = plan_insert(text, options)
    analysis = plan.analysis
    flow = plan.flow
    lines = analysis.lines

    state = _scan_machine_state(analysis, plan.resume_layer.change_line)
    nozzle = options.nozzle_temperature if options.nozzle_temperature is not None else state.nozzle_temperature
    bed = options.bed_temperature if options.bed_temperature is not None else state.bed_temperature
    assert nozzle is not None and bed is not None
    max_nozzle = min(300, int(config_float(analysis.config, "nozzle_temperature_range_high", default=300)))
    boost_nozzle = min(nozzle + (options.adhesion_temp_boost if options.adhesion_layers else 0), max(max_nozzle, nozzle))

    output: list[str] = list(lines[: plan.wall_layers[0].change_line])
    output.extend(
        [
            INSERT_MARKER,
            f"; Generated by Layer Rescue {__version__}: holding wall to {_format_number(plan.wall.top_z)} mm, "
            f"pause, then print from layer {plan.resume_layer.number} on a {_format_number(options.part_height_mm)} mm part",
        ]
    )

    emit = EmitState(retracted=_pending_retraction(analysis, plan.wall_layers[0].change_line))
    walls = {wall_layer.layer.number: wall_layer for wall_layer in plan.wall.layers}
    support_layers = 0
    for layer in plan.printed_layers:
        output.extend(_layer_frame(analysis, layer))
        if layer.number in walls:
            output.extend(emit_wall_layer(walls[layer.number], flow, emit))
        if plan.supports and plan.supports.layers[layer.number].pieces:
            output.extend(emit_support_layer(plan.supports.layers[layer.number], flow, emit))
            support_layers += 1
    wall_filament = emit.filament_mm

    park_x, park_y = plan.park_xy
    pause_gcode = [
        part.strip()
        for part in (analysis.config.get("machine_pause_gcode") or "").replace("\\n", "\n").splitlines()
        if part.strip()
    ] or ["M400 U1"]
    output.extend(
        [
            PAUSE_BLOCK_START,
            f"; Wall and supports are done. Park above {_format_number(plan.park_z)} mm and wait for the operator to seat "
            f"the part (height {_format_number(options.part_height_mm)} mm), then press Resume.",
            "M400",
            "G90",
            "M83",
            f"G1 Z{_format_number(plan.park_z)} F600 ; lift well above the part before any XY move",
            f"G1 X{_format_number(park_x)} Y{_format_number(park_y)} F{flow.travel_feed} ; park at a rear corner",
            "M106 S0",
        ]
    )
    if options.standby_temperature:
        output.append(f"M104 S{options.standby_temperature} ; standby while paused (reheated before printing)")
    output.append("M400")
    output.extend(pause_gcode)
    output.append(PAUSE_BLOCK_END)

    shifted = replace(plan.resume_layer, z=plan.resume_layer.z + plan.z_offset)
    preamble, _, bed_used, _ = _resume_preamble(
        analysis,
        shifted,
        state,
        ResumeOptions(
            start_layer=plan.resume_layer.number,
            z_reference_mode=ZReferenceMode.RETAINED,
            z_lift_mm=options.z_lift_mm,
            purge_length_mm=options.purge_length_mm,
            nozzle_temperature=boost_nozzle,
            bed_temperature=bed,
        ),
    )
    output.extend(preamble)
    speed_restore = state.speed_factor_command or "M220 S100"
    fallback_fan = next((cmd for cmd in state.fan_commands if _is_part_fan(cmd)), None)
    if options.adhesion_layers:
        output.append(f"; Layer Rescue adhesion: first {options.adhesion_layers} layer(s) on the old part")
        if options.adhesion_fan_off:
            output.append("M106 S0")
        if options.adhesion_speed_percent != 100:
            output.append(f"M220 S{options.adhesion_speed_percent}")

    body = _adhesion_body(
        analysis, plan, plan.resume_layer.change_line, nozzle, boost_nozzle, speed_restore, fallback_fan
    )
    max_z = config_float(analysis.config, "printable_height", default=250.0)
    output.extend(_offset_z(body, plan.z_offset, max_z))

    text_out = analysis.newline.join(output) + analysis.newline
    validate_insert_output(text_out, plan)

    report = InsertReport(
        part_layer=plan.part_layer.number,
        resume_layer=plan.resume_layer.number,
        total_layers=analysis.total_layers,
        part_height_mm=options.part_height_mm,
        part_layer_z=plan.part_layer.z,
        z_offset_mm=round(plan.z_offset, 4),
        first_layer_thickness_mm=round(plan.resume_layer.z + plan.z_offset - options.part_height_mm, 4),
        wall_layers=len(plan.wall_layers),
        wall_top_z=plan.wall.top_z,
        wall_height_mm=plan.wall_height_mm,
        park_z=plan.park_z,
        nozzle_temperature=nozzle,
        bed_temperature=bed_used,
        wall_filament_mm=round(wall_filament, 1),
        support_layers=support_layers,
        last_printed_layer=plan.printed_layers[-1].number,
        silhouette_bounds=geo.bounds_mm(plan.wall.silhouette),
        symmetric=plan.symmetric,
        source_sha256=analysis.source_sha256,
        output_sha256=hashlib.sha256(text_out.encode("utf-8")).hexdigest(),
        warnings=tuple(plan.warnings),
    )
    return text_out, report


# --------------------------------------------------------------------------------------------------
# Output validation (re-parses the text we are about to write)


def validate_insert_output(text: str, plan: InsertPlan) -> None:
    options = plan.options
    out_lines = text.splitlines()

    markers = [int(m.group(1)) for line in out_lines if (m := LAYER_MARKER_RE.match(line))]
    expected = [layer.number for layer in plan.printed_layers] + list(
        range(plan.resume_layer.number, plan.analysis.last_layer + 1)
    )
    if markers != expected:
        raise ResumeError(
            "Internal validation failed: the output layer sequence is not wall/support layers + remaining layers."
        )

    starts = [i for i, line in enumerate(out_lines) if line.strip() == PAUSE_BLOCK_START]
    ends = [i for i, line in enumerate(out_lines) if line.strip() == PAUSE_BLOCK_END]
    resume_end = [i for i, line in enumerate(out_lines) if line.strip() == "; LAYER_RESCUE_BLOCK_END"]
    if len(starts) != 1 or len(ends) != 1 or len(resume_end) != 1 or not starts[0] < ends[0] < resume_end[0]:
        raise ResumeError("Internal validation failed: expected exactly one pause block followed by the resume block.")
    pause_start, _, preamble_end = starts[0], ends[0], resume_end[0]

    first_wall = next(i for i, line in enumerate(out_lines) if line.strip() == INSERT_MARKER)
    safe_z = options.part_height_mm + 1.0
    clearance_rings = {
        wall_layer.layer.z: geo.offset(
            wall_layer.opening, options.clearance_mm + wall_layer.width / 2 - 0.04, tolerance_mm=geo.COARSE
        )
        for wall_layer in plan.wall.layers
    }

    extrusion_mode: str | None = None
    positioning = "G90"
    x = y = None
    z: float | None = None
    executable = False
    # E-mode is only checked in code Layer Rescue writes (wall toolpaths) and from the pause on (as in
    # resume mode). The start G-code and the slicer's layer frames are copied verbatim from a job that
    # prints fine, and the stock P1S start G-code legitimately extrudes after a G90.
    generated = False
    support_keep_out: dict[int, geo.Region] = {}
    section_kind: str | None = None  # "wall" or "support" while inside Layer Rescue's own toolpaths
    support_layer: int | None = None
    for index, raw in enumerate(out_lines):
        stripped = raw.strip()
        if stripped.upper() == "; EXECUTABLE_BLOCK_START":
            executable = True
        if stripped.startswith("; LAYER_RESCUE_WALL") or stripped == PAUSE_BLOCK_START:
            generated = True
            section_kind = "wall"
        elif stripped.startswith("; LAYER_RESCUE_SUPPORT"):
            generated = True
            section_kind = "support"
            support_layer = int(stripped.split()[3].rstrip(","))
        elif stripped.upper() == "; CHANGE_LAYER" and index < pause_start:
            generated = False
            section_kind = None
        code = _code(raw)
        if not code or not executable:
            continue
        command = _command(code)
        extrusion_mode = _next_extrusion_mode(command, extrusion_mode)
        if command in {"G90", "G91"}:
            positioning = command
        after_pause = index > pause_start
        if after_pause:
            if re.match(r"^G29(?:\.|\s|$)", code, re.IGNORECASE):
                raise ResumeError(f"Internal validation failed: bed leveling after the pause (line {index + 1}).")
            if re.match(r"^G28(?:\s|$)", code, re.IGNORECASE):
                params = code[3:].upper()
                if "Z" in params or not re.search(r"\b[XY]\b", params):
                    raise ResumeError(f"Internal validation failed: Z homing after the pause (line {index + 1}).")
        if command not in {"G0", "G1", "G2", "G3"}:
            continue
        px, py, pz, pe = (_parameter(code, axis) for axis in ("X", "Y", "Z", "E"))
        if pe is not None and extrusion_mode != "M83" and generated:
            raise ResumeError(
                f"Internal validation failed: extrusion at output line {index + 1} would run in absolute E mode."
            )
        if pz is not None:
            z = pz if positioning == "G90" else (z or 0.0) + pz
        moves_xy = px is not None or py is not None
        if positioning == "G90":
            x = px if px is not None else x
            y = py if py is not None else y

        prints = moves_xy and pe is not None and pe > 0
        if first_wall < index < pause_start and prints and section_kind is None:
            raise ResumeError(f"Internal validation failed: a source toolpath is left before the pause (line {index + 1}).")
        if first_wall < index < pause_start and prints and section_kind == "support":
            if z is None or z > plan.part_layer.z + 1e-6:
                raise ResumeError(f"Internal validation failed: support printed above the part (line {index + 1}).")
            assert plan.supports is not None and support_layer is not None
            if support_layer not in support_keep_out:
                support_keep_out[support_layer] = geo.offset(
                    plan.supports.layers[support_layer].keep_out, -0.08, tolerance_mm=geo.COARSE
                )
            keep_out = support_keep_out[support_layer]
            if x is not None and y is not None and geo.contains_point(keep_out, (x, y)):
                raise ResumeError(
                    f"Internal validation failed: support line where the part is lowered in (line {index + 1})."
                )
        if first_wall < index < pause_start and prints and section_kind == "wall":
            if z is None or z > plan.wall.top_z + 1e-6:
                raise ResumeError(f"Internal validation failed: wall extrusion above the wall top (line {index + 1}).")
            ring = clearance_rings.get(round(z, 6)) or clearance_rings.get(
                min(clearance_rings, key=lambda level: abs(level - z))
            )
            if ring and x is not None and y is not None and geo.contains_point(ring, (x, y)):
                raise ResumeError(
                    f"Internal validation failed: wall line inside the part's clearance at line {index + 1}."
                )
        if pause_start < index < preamble_end and moves_xy:
            if z is None or z < safe_z - 1e-6:
                raise ResumeError(
                    f"Internal validation failed: XY move below the part top + 1 mm after the pause (line {index + 1})."
                )
        if index > preamble_end and z is not None and z < options.part_height_mm + 0.05 - 1e-6:
            raise ResumeError(
                f"Internal validation failed: move at Z{z:g} would hit the seated part (line {index + 1})."
            )
