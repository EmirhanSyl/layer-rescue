"""Resume-from-layer conversion (the original Layer Rescue mode)."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ._version import __version__
from .gcode import (
    LAYER_MARKER_RE,
    NUMBER_RE,
    Analysis,
    LayerInfo,
    ResumeError,
    _code,
    _command,
    _format_number,
    _next_extrusion_mode,
    _parameter,
    analyze_gcode,
)
from .machine_state import MachineState, _scan_machine_state, _validate_supported_source
from .printers import (
    H2,
    H2_CLEARANCE_LIMITED,
    POWER_CUT_CLEARANCE_MM,
    POWER_CUT_HEIGHT_MARGIN_MM,
    StationContext,
    extruder_for_filament,
    heat_commands,
    home_command,
    power_cut_clearance,
    printer_profile,
    station_block,
)


class ZReferenceMode(str, Enum):
    """How the recovery job establishes its absolute Z coordinate."""

    RETAINED = "retained"
    MANUAL = "manual"



@dataclass(frozen=True)
class ResumeOptions:
    start_layer: int
    z_reference_mode: ZReferenceMode = ZReferenceMode.RETAINED
    home_corexy: bool = True
    z_lift_mm: float = 2.0
    purge_length_mm: float = 30.0
    nozzle_temperature: int | None = None
    bed_temperature: int | None = None
    allow_untested: bool = False  # accept the risks of a printer / filament setup that has not been tested


@dataclass(frozen=True)
class ResumeReport:
    start_layer: int
    total_layers: int
    start_z: float
    nozzle_temperature: int
    bed_temperature: int
    retained_layers: int
    z_reference_mode: ZReferenceMode
    reference_z: float | None
    source_sha256: str
    output_sha256: str
    backup_path: Path | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _z_reference_mode(value: ZReferenceMode | str) -> ZReferenceMode:
    try:
        return ZReferenceMode(value)
    except ValueError as exc:
        choices = ", ".join(mode.value for mode in ZReferenceMode)
        raise ResumeError(f"Unknown Z reference mode '{value}'; choose one of: {choices}.") from exc


def _previous_layer(analysis: Analysis, layer: LayerInfo) -> LayerInfo:
    try:
        position = analysis.layers.index(layer)
    except ValueError as exc:  # pragma: no cover - internal consistency guard
        raise ResumeError("Selected layer is missing from the analyzed layer table.") from exc
    if position == 0:
        raise ResumeError("Manual Z reference requires a preceding successfully printed layer.")
    previous = analysis.layers[position - 1]
    if previous.number != layer.number - 1:
        raise ResumeError("Manual Z reference requires contiguous selected and preceding layers.")
    return previous


def _first_layer_xy(analysis: Analysis, layer: LayerInfo) -> tuple[float, float] | None:
    """Return the first absolute XY target of the resumed layer, if one precedes any extrusion."""
    for raw_line in analysis.lines[layer.change_line : layer.end_line]:
        code = _code(raw_line)
        command = _command(code)
        if command not in {"G0", "G1", "G2", "G3"}:
            continue
        x_value = _parameter(code, "X")
        y_value = _parameter(code, "Y")
        e_value = _parameter(code, "E")
        if command in {"G0", "G1"} and x_value is not None and y_value is not None:
            return x_value, y_value
        if e_value is not None and e_value > 0:
            return None
    return None


FILAMENT_AREA_175 = math.pi * (1.75 / 2) ** 2
MAX_PURGE_FEED = 200.0  # mm/min of filament: the original fixed rate, about 8 mm³/s with 1.75 mm filament
MIN_PURGE_FEED = 10.0
PURGE_VOLUMETRIC_FACTOR = 0.8  # stay below the filament's max volumetric speed, like the stock start G-code


def _config_at(analysis: Analysis, key: str, index: int) -> float | None:
    """Per-filament config value (comma separated) for ``index``, falling back to the first entry."""
    value = analysis.config.get(key)
    if not value:
        return None
    entries = [entry for entry in value.split(",") if entry.strip()]
    if not entries:
        return None
    match = NUMBER_RE.search(entries[index] if 0 <= index < len(entries) else entries[0])
    return float(match.group(0)) if match else None


def _purge_feed(analysis: Analysis, tool: int) -> int:
    """Filament feed (mm/min) for the purge that respects the filament's max volumetric speed.

    A fixed F200 is ~8 mm³/s; a 0.2 mm nozzle profile allows ~2 mm³/s, so the extruder would skip.
    """
    max_volumetric = _config_at(analysis, "filament_max_volumetric_speed", tool)
    if max_volumetric is None or max_volumetric <= 0:
        return int(MAX_PURGE_FEED)
    diameter = _config_at(analysis, "filament_diameter", tool) or 1.75
    area = math.pi * (diameter / 2) ** 2 if diameter > 0 else FILAMENT_AREA_175
    feed = max_volumetric * PURGE_VOLUMETRIC_FACTOR / area * 60
    return int(max(MIN_PURGE_FEED, min(MAX_PURGE_FEED, math.floor(feed))))


def _retraction_length(analysis: Analysis) -> float:
    value = analysis.config.get("retraction_length")
    match = NUMBER_RE.search(value) if value else None
    length = float(match.group(0)) if match else 0.8
    return min(max(length, 0.0), 5.0)


Z_DECIMALS = 4
_BLOCK_OPENERS = {"M620": "M621", "M622": "M623", "M624": "M625"}


def _format_z_delta(value: float) -> str:
    text = f"{value:.{Z_DECIMALS}f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _relative_z_move(delta: float, feed: str | None, note: str | None = None) -> list[str]:
    """Emit a Z-only move relative to the current physical position (Bambu: G90 resets E, so M83 follows)."""
    move = f"G1 Z{_format_z_delta(delta)}"
    if feed:
        move += f" {feed}"
    if note:
        move += f" ; {note}"
    return ["G91", move, "G90", "M83"]


def _relativize_z(body: list[str], start_z: float) -> list[str]:
    """Rewrite every absolute Z move in ``body`` as a relative move.

    After a power cycle the P1S has not homed Z, and its absolute Z coordinate cannot be trusted
    (an unhomed axis, soft limits and ``G92`` handling are firmware-specific). The operator aligns
    the nozzle physically, so the only reliable reference is that physical position. Tracking the
    slicer's absolute Z and emitting only differences keeps the nozzle exactly where the slicer
    intended, whatever the firmware believes its absolute Z to be.
    """
    output: list[str] = []
    positioning = "G90"
    nominal_z = start_z  # where the slicer believes the nozzle is
    emitted_z = start_z  # where the emitted relative moves put the nozzle (after rounding)
    blocks: list[tuple[str, float, int]] = []

    for index, raw_line in enumerate(body):
        code = _code(raw_line)
        command = _command(code)
        if command is None:
            output.append(raw_line)
            continue

        if command in _BLOCK_OPENERS and re.search(r"(?:^|\s)[SJ]?\d", code[len(command):]):
            blocks.append((_BLOCK_OPENERS[command], emitted_z, index))
        elif blocks and command == blocks[-1][0]:
            _, entry_z, opened_at = blocks.pop()
            if abs(entry_z - emitted_z) > 1e-6:
                raise ResumeError(
                    "Restarted mode cannot convert a conditional firmware block that changes Z "
                    f"(source body lines {opened_at + 1}-{index + 1}); the result would depend on whether "
                    "the printer executes it."
                )

        if command == "G92" and _parameter(code, "Z") is not None:
            raise ResumeError("Restarted mode cannot convert a source that reassigns Z with G92.")
        if command in {"G90", "G91"}:
            positioning = command
            output.append(raw_line)
            continue
        if command not in {"G0", "G1", "G2", "G3"}:
            output.append(raw_line)
            continue

        z_value = _parameter(code, "Z")
        if z_value is None:
            output.append(raw_line)
            continue
        if positioning == "G91":
            nominal_z += z_value
            emitted_z += z_value
            output.append(raw_line)
            continue

        e_value = _parameter(code, "E")
        if e_value is not None and e_value > 0:
            raise ResumeError(
                f"Restarted mode cannot convert an extruding move that also changes Z: {code}"
            )

        nominal_z = z_value
        delta = round(nominal_z - emitted_z, Z_DECIMALS)
        emitted_z += delta

        tokens = code.split()
        rest_tokens = [tokens[0]] + [token for token in tokens[1:] if not token.upper().startswith("Z")]
        feed = next((token for token in rest_tokens[1:] if token.upper().startswith("F")), None)
        has_xy = any(token[:1].upper() in {"X", "Y"} for token in rest_tokens[1:])
        has_e = any(token[:1].upper() == "E" for token in rest_tokens[1:])
        is_arc = command in {"G2", "G3"}
        comment = raw_line.split(";", 1)[1].strip() if ";" in raw_line else ""

        planar: list[str] = []
        if has_xy or (has_e and not is_arc):
            planar = [" ".join(rest_tokens) + (f" ; {comment}" if comment else "")]
        elif feed:
            # Keep the modal feedrate the original move would have set.
            planar = [f"G1 {feed}"]

        z_lines = _relative_z_move(delta, feed, f"abs Z{_format_number(nominal_z)}") if delta else []
        # Rising: lift first, then move. Descending: move first, then lower (never drag across the part).
        output.extend(z_lines + planar if delta > 0 else planar + z_lines)

    if blocks:
        raise ResumeError("Restarted mode found an unterminated conditional firmware block.")
    return output


END_GCODE_MARKER = "; MACHINE_END_GCODE_START"


def _lower_bed_before_end_macros(body: list[str], analysis: Analysis) -> tuple[list[str], float]:
    """H2 power-cut mode: give the end G-code's G150.x macros the same clearance as the preamble.

    The stock H2 end G-code runs G150.3 0.4 mm above the finished part. With an unhomed Z that is the
    same open question as in the preamble, so the bed is lowered first (relative) and every absolute
    Z of the end G-code is raised by the same amount, keeping its own moves unchanged relative to it.
    """
    try:
        start = body.index(END_GCODE_MARKER)
    except ValueError:
        return body, 0.0
    end_codes = [_code(line) for line in body[start:]]
    if not any(code.upper().startswith("G150") for code in end_codes):
        return body, 0.0
    highest = max(
        (z for code in end_codes if _command(code) in {"G0", "G1", "G2", "G3"} and (z := _parameter(code, "Z")) is not None),
        default=0.0,
    )
    height = analysis.config.get("printable_height")
    match = NUMBER_RE.search(height) if height else None
    max_z = float(match.group(0)) if match else 250.0
    clearance = round(max(0.0, min(POWER_CUT_CLEARANCE_MM, max_z - POWER_CUT_HEIGHT_MARGIN_MM - highest)), 3)
    if clearance <= 0:
        return body, 0.0

    shifted = body[: start + 1] + [
        "G91",
        f"G1 Z{_format_number(clearance)} F600 ; lower the bed before the H2 end-G-code macros (power-cut mode)",
        "G90",
    ]
    positioning = "G90"
    for raw in body[start + 1 :]:
        code = _code(raw)
        command = _command(code)
        if command in {"G90", "G91"}:
            positioning = command
        z_value = _parameter(code, "Z") if command in {"G0", "G1", "G2", "G3"} else None
        if z_value is None or positioning == "G91":
            shifted.append(raw)
            continue
        comment = raw.split(";", 1)[1] if ";" in raw else ""
        tokens = [
            f"Z{_format_number(z_value + clearance)}" if token.upper().startswith("Z") else token
            for token in code.split()
        ]
        shifted.append(" ".join(tokens) + (f" ;{comment}" if comment else ""))
    return shifted, clearance


def _resume_preamble(
    analysis: Analysis,
    layer: LayerInfo,
    state: MachineState,
    options: ResumeOptions,
) -> tuple[list[str], int, int, float | None]:
    nozzle = options.nozzle_temperature if options.nozzle_temperature is not None else state.nozzle_temperature
    bed = options.bed_temperature if options.bed_temperature is not None else state.bed_temperature
    assert nozzle is not None
    assert bed is not None
    if not 150 <= nozzle <= 300:
        raise ResumeError(f"Nozzle temperature {nozzle}°C is outside the allowed 150–300°C range.")
    if not 0 <= bed <= 120:
        raise ResumeError(f"Bed temperature {bed}°C is outside the allowed 0–120°C range.")
    if not 0.5 <= options.z_lift_mm <= 10:
        raise ResumeError("The relative Z safety lift must be between 0.5 and 10 mm.")
    if not 0 <= options.purge_length_mm <= 100:
        raise ResumeError("The purge length must be between 0 and 100 mm of filament.")

    tool = state.active_tool or 0  # the filament slot that was printing when the selected layer starts
    profile = printer_profile(analysis)
    station = StationContext(
        tool=tool,
        nozzle=nozzle,
        bed=bed,
        purge_length=options.purge_length_mm,
        purge_feed=_purge_feed(analysis, tool),
        retract=_retraction_length(analysis),
        hotend=state.active_hotend,
        extruder=state.active_extruder if state.active_extruder is not None else extruder_for_filament(analysis, tool),
        flush_setup=state.flush_setup_command,
        toolchange_setup=state.toolchange_setup,
        hotend_remap=state.hotend_remap,
    )

    mode = _z_reference_mode(options.z_reference_mode)
    reference_z: float | None = None
    if mode is ZReferenceMode.MANUAL:
        if not options.home_corexy:
            raise ResumeError("Manual Z reference mode requires CoreXY homing after the safety lift.")
        reference_z = _previous_layer(analysis, layer).z
    clearance = power_cut_clearance(analysis, profile, mode, reference_z, options.z_lift_mm)

    progress = max(0, min(100, round((layer.number - 1) / layer.total * 100)))
    safety_note = (
        "requires retained printer Z coordinates and a firmly attached original part."
        if mode is ZReferenceMode.RETAINED
        else (
            "before job start, the nozzle must just touch the top of the last successful layer; "
            "all Z moves are relative to that position; Z is never homed."
        )
    )
    lines = [
        "; LAYER_RESCUE_BLOCK_START",
        f"; Generated by Layer Rescue {__version__}",
        f"; Resume at layer {layer.number}/{layer.total}, Z={_format_number(layer.z)} mm",
        f"; Z reference mode: {mode.value}",
        f"; SAFETY: {safety_note}",
        f"M73 P{progress}",
    ]
    lines.extend(state.motion_commands)
    lines.extend(heat_commands(profile, station))
    lines.extend(
        [
            "G90",
            "G21",
            "M83",
            state.speed_factor_command or "M220 S100",
            state.flow_factor_command or "M221 S100",
            "M73.2 R1.0",
            "M1002 set_gcode_claim_speed_level : 5",
        ]
    )
    if mode is ZReferenceMode.MANUAL:
        assert reference_z is not None
        lines.extend(
            [
                # Same as the stock P1S start G-code: after a power cycle Z is not homed, so the
                # firmware's soft limits must not clamp or reinterpret Z moves.
                f"{profile.soft_endstops_off} ; turn off soft endstops (as the stock start G-code does for an unhomed Z)",
                f"G92 Z{_format_number(reference_z)} ; nominal Z of the aligned last-layer surface",
                "; Restarted mode: every Z move below is relative to the aligned nozzle position,",
                "; so the job does not depend on the firmware's absolute Z after a power cycle.",
            ]
        )
    lines.extend(
        [
            "G91",
            f"G1 Z{_format_number(options.z_lift_mm)} F600 ; relative safety lift; no Z homing",
            "G90",
        ]
    )
    if clearance > 0:
        # H2 after a power cut: the stock start G-code lowers the bed ~30 mm (relative) before it runs
        # G28 X T300 and the G150.x purge/wipe macros on an unhomed Z. Do the same, so these
        # firmware commands run with the clearance they are designed for.
        lines.extend(
            [
                "G91",
                f"G1 Z{_format_number(clearance)} F600 ; lower the bed for the H2 macros, like the stock start",
                "G90",
            ]
        )
    if options.home_corexy:
        lines.append(home_command(profile))
    lines.extend(station_block(profile, station))
    lines.extend(state.fan_commands)
    for command in state.auxiliary_commands:
        if not command.startswith("M975"):
            lines.append(command)

    retract = station.retract
    first_xy = _first_layer_xy(analysis, layer)
    if first_xy is not None:
        lines.append(
            f"G1 X{_format_number(first_xy[0])} Y{_format_number(first_xy[1])} F12000"
            " ; travel above the part at the lifted Z"
        )
        approach_note = "descend onto the recovered layer start"
    else:
        approach_note = "approach the recovered layer at the rear station"
    if mode is ZReferenceMode.MANUAL:
        assert reference_z is not None
        approach = layer.z - (reference_z + options.z_lift_mm + clearance)
        lines.extend(_relative_z_move(approach, "F600", approach_note))
    else:
        lines.append(f"G1 Z{_format_number(layer.z)} F600 ; {approach_note}")
    if options.purge_length_mm > 0 and retract > 0:
        lines.append(f"G1 E{_format_number(retract)} F1800 ; undo the post-purge retraction")
    lines.extend(
        [
            "G92 E0",
            "M83",
            "M1002 gcode_claim_action : 0",
            "; LAYER_RESCUE_BLOCK_END",
        ]
    )
    return lines, nozzle, bed, reference_z


def _validate_output(
    text: str,
    start_layer: int,
    last_layer: int,
    z_reference_mode: ZReferenceMode,
    reference_z: float | None,
) -> None:
    layers = [
        int(match.group(1))
        for line in text.splitlines()
        if (match := LAYER_MARKER_RE.match(line))
    ]
    if not layers or layers[0] != start_layer:
        raise ResumeError("Internal validation failed: the first retained layer is incorrect.")
    # The last layer number can be below the markers' "total" (Bambu counts independent support
    # layers in the total), so compare against the last layer actually present in the source.
    expected = list(range(start_layer, last_layer + 1))
    if layers != expected:
        raise ResumeError("Internal validation failed: retained layers are not contiguous through the end.")

    preamble_end = text.find("; LAYER_RESCUE_BLOCK_END")
    if preamble_end < 0:
        raise ResumeError("Internal validation failed: resume block terminator is missing.")
    preamble = text[:preamble_end]
    # The last tool selection (T1000 on the P1 series, T<n> H<h> on the H2) can change the nozzle
    # temperature, so the print temperature must be waited for again after it.
    preamble_codes = [_code(line) for line in preamble.splitlines()]
    tool_lines = [index for index, code in enumerate(preamble_codes) if re.match(r"^T\d+(?:\s|$)", code)]
    heat_lines = [index for index, code in enumerate(preamble_codes) if re.match(r"^M109\s+S", code)]
    if not tool_lines or not heat_lines or heat_lines[-1] < tool_lines[-1]:
        raise ResumeError("Internal validation failed: print temperature is not reasserted after the tool selection.")

    preamble_lines = preamble.splitlines()
    z_assignments: list[tuple[int, float]] = []
    first_z_move: int | None = None
    for index, raw_line in enumerate(preamble_lines):
        code = _code(raw_line)
        command = _command(code)
        if command == "G92" and (value := _parameter(code, "Z")) is not None:
            z_assignments.append((index, value))
        if command in {"G0", "G1"} and _parameter(code, "Z") is not None and first_z_move is None:
            first_z_move = index

    if z_reference_mode is ZReferenceMode.MANUAL:
        if reference_z is None or len(z_assignments) != 1:
            raise ResumeError("Internal validation failed: manual mode must emit exactly one G92 Z assignment.")
        assignment_line, assignment_z = z_assignments[0]
        if abs(assignment_z - reference_z) > 1e-6:
            raise ResumeError("Internal validation failed: the manual Z assignment is incorrect.")
        if first_z_move is None or assignment_line >= first_z_move:
            raise ResumeError("Internal validation failed: G92 Z must precede every Z movement.")
    elif z_assignments:
        raise ResumeError("Internal validation failed: retained-Z mode must not rewrite the Z coordinate.")

    extrusion_mode: str | None = None
    positioning: str | None = None
    executable = False
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        if raw_line.strip().upper() == "; EXECUTABLE_BLOCK_START":
            executable = True
        code = _code(raw_line)
        if not code or not executable:
            continue
        command = _command(code)
        extrusion_mode = _next_extrusion_mode(command, extrusion_mode)
        if command in {"G90", "G91"}:
            positioning = command
        if (
            z_reference_mode is ZReferenceMode.MANUAL
            and command in {"G0", "G1", "G2", "G3"}
            and _parameter(code, "Z") is not None
            and positioning != "G91"
        ):
            raise ResumeError(
                f"Internal validation failed: restarted mode emitted an absolute Z move at output line "
                f"{line_number}: {code}"
            )
        if command in {"G0", "G1", "G2", "G3"} and _parameter(code, "E") is not None and extrusion_mode != "M83":
            raise ResumeError(
                f"Internal validation failed: extrusion at output line {line_number} would run in absolute "
                "E mode (missing M83 after G90/M82)."
            )
        if re.match(r"^G29(?:\.|\s|$)", code, re.IGNORECASE):
            raise ResumeError(f"Unsafe bed-leveling command remains at output line {line_number}: {code}")
        if re.match(r"^G28(?:\s|$)", code, re.IGNORECASE):
            parameters = code[3:].upper()
            if "Z" in parameters or not re.search(r"\b[XY]\b", parameters):
                raise ResumeError(f"Unsafe Z/all-axis homing command remains at output line {line_number}: {code}")


def build_resume_gcode(text: str, options: ResumeOptions) -> tuple[str, ResumeReport]:
    analysis = analyze_gcode(text)
    layer = analysis.layer(options.start_layer)
    if options.start_layer <= analysis.first_layer:
        raise ResumeError("Choose a start layer after the first layer; a normal print should be used instead.")
    if options.start_layer > analysis.last_layer:
        raise ResumeError("The selected start layer is beyond the end of the print.")

    state = _scan_machine_state(analysis, layer.change_line)
    accepted_risks = _validate_supported_source(analysis, state, options.allow_untested)
    mode = _z_reference_mode(options.z_reference_mode)
    preamble, nozzle, bed, reference_z = _resume_preamble(analysis, layer, state, options)

    prefix = list(analysis.lines[: analysis.config_end_line + 1])
    body = list(analysis.lines[layer.change_line :])
    if mode is ZReferenceMode.MANUAL:
        if printer_profile(analysis) is H2:
            body, _ = _lower_bed_before_end_macros(body, analysis)
        body = _relativize_z(body, layer.z)
    output_lines = prefix + ["", "; EXECUTABLE_BLOCK_START"] + preamble + body
    output = analysis.newline.join(output_lines) + analysis.newline
    _validate_output(output, options.start_layer, analysis.last_layer, mode, reference_z)

    warnings = list(analysis.warnings) + accepted_risks
    if mode is ZReferenceMode.MANUAL:
        warnings.append(
            "Manual Z mode depends on the operator aligning the nozzle to the last successful layer before job start."
        )
        profile = printer_profile(analysis)
        clearance = power_cut_clearance(analysis, profile, mode, reference_z, options.z_lift_mm)
        if profile.experimental and clearance < POWER_CUT_CLEARANCE_MM:
            warnings.append(H2_CLEARANCE_LIMITED.format(clearance=_format_number(clearance)))

    report = ResumeReport(
        start_layer=options.start_layer,
        total_layers=analysis.total_layers,
        start_z=layer.z,
        nozzle_temperature=nozzle,
        bed_temperature=bed,
        retained_layers=analysis.last_layer - options.start_layer + 1,
        z_reference_mode=mode,
        reference_z=reference_z,
        source_sha256=analysis.source_sha256,
        output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
        warnings=tuple(warnings),
    )
    return output, report

