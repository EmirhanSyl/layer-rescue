from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Mapping


LAYER_MARKER_RE = re.compile(
    r"^\s*;\s*layer num/total_layer_count:\s*(\d+)\s*/\s*(\d+)\s*$",
    re.IGNORECASE,
)
Z_HEIGHT_RE = re.compile(r"^\s*;\s*Z_HEIGHT:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*$", re.IGNORECASE)
CONFIG_RE = re.compile(r"^\s*;\s*([^=]+?)\s*=\s*(.*?)\s*$")
COMMAND_RE = re.compile(r"^\s*([GMT]\d+(?:\.\d+)?)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?(?:\d+(?:\.\d*)?|\.\d+)")


class ResumeError(ValueError):
    """Raised when a source file cannot be converted conservatively."""


class ZReferenceMode(str, Enum):
    """How the recovery job establishes its absolute Z coordinate."""

    RETAINED = "retained"
    MANUAL = "manual"


@dataclass(frozen=True)
class LayerInfo:
    number: int
    total: int
    z: float
    change_line: int
    marker_line: int
    end_line: int


@dataclass(frozen=True)
class MachineState:
    nozzle_temperature: int | None
    bed_temperature: int | None
    extrusion_mode: str | None
    positioning_mode: str | None
    fan_commands: tuple[str, ...] = ()
    motion_commands: tuple[str, ...] = ()
    speed_factor_command: str | None = None
    flow_factor_command: str | None = None
    flush_setup_command: str | None = None
    auxiliary_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class Analysis:
    lines: tuple[str, ...]
    newline: str
    config: Mapping[str, str]
    layers: tuple[LayerInfo, ...]
    config_end_line: int
    executable_start_line: int
    printer_model: str
    filament_type: str
    source_sha256: str
    warnings: tuple[str, ...] = ()

    @property
    def first_layer(self) -> int:
        return self.layers[0].number

    @property
    def last_layer(self) -> int:
        return self.layers[-1].number

    @property
    def total_layers(self) -> int:
        return self.layers[0].total

    def layer(self, number: int) -> LayerInfo:
        for layer in self.layers:
            if layer.number == number:
                return layer
        raise ResumeError(f"Layer {number} is not present in this G-code file.")


@dataclass(frozen=True)
class ResumeOptions:
    start_layer: int
    z_reference_mode: ZReferenceMode = ZReferenceMode.RETAINED
    home_corexy: bool = True
    z_lift_mm: float = 2.0
    purge_length_mm: float = 30.0
    nozzle_temperature: int | None = None
    bed_temperature: int | None = None


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


def _code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _command(line: str) -> str | None:
    match = COMMAND_RE.match(_code(line))
    return match.group(1).upper() if match else None


def _parameter(code: str, letter: str) -> float | None:
    match = re.search(
        rf"(?:^|\s){re.escape(letter)}(-?(?:\d+(?:\.\d*)?|\.\d+))(?=\s|$)",
        code,
        re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def _next_extrusion_mode(command: str | None, current: str | None) -> str | None:
    """Track the extruder distance mode the way Bambu (Marlin-derived) firmware does.

    ``G90``/``G91`` switch *all* axes, including E. That is why every stock Bambu
    template re-issues ``M83`` right after ``G90``. A ``G90`` that is not followed by
    ``M83`` silently turns the relative E values of a Bambu Studio job into absolute
    positions, so the extruder only oscillates around zero and nothing is printed.
    """
    if command == "M83" or command == "G91":
        return "M83"
    if command == "M82" or command == "G90":
        return "M82"
    return current


def _first_number(value: str | None) -> int | None:
    if not value:
        return None
    match = NUMBER_RE.search(value)
    return int(round(float(match.group(0)))) if match else None


def _parse_config(lines: list[str], start: int, end: int) -> dict[str, str]:
    config: dict[str, str] = {}
    for line in lines[start : end + 1]:
        match = CONFIG_RE.match(line)
        if match:
            config[match.group(1).strip().lower()] = match.group(2).strip()
    return config


def _find_marker(lines: list[str], marker: str) -> int:
    for index, line in enumerate(lines):
        if line.strip().upper() == marker:
            return index
    raise ResumeError(f"Required Bambu Studio marker is missing: {marker}")


def _find_layers(lines: list[str], executable_start: int) -> tuple[LayerInfo, ...]:
    raw_markers: list[tuple[int, int, int]] = []
    for index in range(executable_start, len(lines)):
        match = LAYER_MARKER_RE.match(lines[index])
        if match:
            raw_markers.append((index, int(match.group(1)), int(match.group(2))))

    if not raw_markers:
        raise ResumeError("No Bambu Studio layer markers were found.")

    seen: set[int] = set()
    layers: list[LayerInfo] = []
    previous_marker = executable_start
    for marker_position, (marker_line, number, total) in enumerate(raw_markers):
        if number in seen:
            raise ResumeError(f"Duplicate layer marker found for layer {number}.")
        seen.add(number)

        change_line = marker_line
        for index in range(marker_line, previous_marker - 1, -1):
            if lines[index].strip().upper() == "; CHANGE_LAYER":
                change_line = index
                break

        z_value: float | None = None
        for index in range(change_line, min(marker_line + 1, len(lines))):
            z_match = Z_HEIGHT_RE.match(lines[index])
            if z_match:
                z_value = float(z_match.group(1))
        if z_value is None:
            raise ResumeError(f"Layer {number} has no '; Z_HEIGHT:' marker.")

        next_change = len(lines)
        if marker_position + 1 < len(raw_markers):
            next_marker = raw_markers[marker_position + 1][0]
            next_change = next_marker
            for index in range(next_marker, marker_line, -1):
                if lines[index].strip().upper() == "; CHANGE_LAYER":
                    next_change = index
                    break

        layers.append(
            LayerInfo(
                number=number,
                total=total,
                z=z_value,
                change_line=change_line,
                marker_line=marker_line,
                end_line=next_change,
            )
        )
        previous_marker = marker_line + 1

    totals = {layer.total for layer in layers}
    if len(totals) != 1:
        raise ResumeError("Layer markers disagree about the total layer count.")
    if any(right.number <= left.number for left, right in zip(layers, layers[1:])):
        raise ResumeError("Layer markers are not strictly increasing.")
    return tuple(layers)


def analyze_gcode(text: str) -> Analysis:
    if not text.strip():
        raise ResumeError("The G-code file is empty.")
    if "; LAYER_RESCUE_BLOCK_START" in text:
        raise ResumeError("This G-code has already been processed by Layer Rescue.")

    newline = "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"
    lines = text.splitlines()
    config_start = _find_marker(lines, "; CONFIG_BLOCK_START")
    config_end = _find_marker(lines, "; CONFIG_BLOCK_END")
    executable_start = _find_marker(lines, "; EXECUTABLE_BLOCK_START")
    if not config_start < config_end < executable_start:
        raise ResumeError("The Bambu Studio header/config/executable blocks are out of order.")

    config = _parse_config(lines, config_start, config_end)
    layers = _find_layers(lines, executable_start)
    printer_model = config.get("printer_model", "Unknown")
    filament_type = config.get("filament_type", "Unknown")

    warnings: list[str] = []
    numbers = [layer.number for layer in layers]
    if numbers != list(range(numbers[0], numbers[-1] + 1)):
        warnings.append("The source contains non-contiguous layer numbers.")

    return Analysis(
        lines=tuple(lines),
        newline=newline,
        config=config,
        layers=layers,
        config_end_line=config_end,
        executable_start_line=executable_start,
        printer_model=printer_model,
        filament_type=filament_type,
        source_sha256=hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
        warnings=tuple(warnings),
    )


def _scan_machine_state(analysis: Analysis, stop_line: int) -> MachineState:
    nozzle_temperature: int | None = None
    bed_temperature: int | None = None
    extrusion_mode: str | None = None
    positioning_mode: str | None = None
    fan_commands: dict[int, str] = {}
    motion_commands: dict[str, str] = {}
    speed_factor: str | None = None
    flow_factor: str | None = None
    flush_setup: str | None = None
    auxiliary_commands: dict[str, str] = {}

    for raw_line in analysis.lines[analysis.executable_start_line : stop_line]:
        code = _code(raw_line)
        if not code:
            continue
        command = _command(code)
        if command in {"M104", "M109"}:
            value = _parameter(code, "S")
            if value is not None and value > 0:
                nozzle_temperature = int(round(value))
        elif command in {"M140", "M190"}:
            value = _parameter(code, "S")
            if value is not None and value > 0:
                bed_temperature = int(round(value))
        elif command == "M106":
            fan = int(_parameter(code, "P") or 0)
            if _parameter(code, "S") is not None:
                fan_commands[fan] = code
        elif command == "M107":
            fan_commands[0] = "M106 S0"
        elif command in {"M201", "M203", "M204", "M205"}:
            motion_commands[command] = code
        elif command == "M220" and _parameter(code, "S") is not None:
            speed_factor = code
        elif command == "M221" and _parameter(code, "S") is not None:
            flow_factor = code
        elif command == "M620.1" and re.search(r"(?:^|\s)E(?:\s|$)", code, re.IGNORECASE):
            flush_setup = code
        elif command in {"M900", "M975", "M1003"}:
            auxiliary_commands[command] = code
        elif command == "G90":
            positioning_mode = "G90"
        elif command == "G91":
            positioning_mode = "G91"
        extrusion_mode = _next_extrusion_mode(command, extrusion_mode)

    nozzle_temperature = nozzle_temperature or _first_number(
        analysis.config.get("nozzle_temperature")
        or analysis.config.get("nozzle_temperature_initial_layer")
    )
    bed_temperature = bed_temperature or _first_number(
        analysis.config.get("hot_plate_temp")
        or analysis.config.get("textured_plate_temp")
        or analysis.config.get("bed_temperature")
    )

    return MachineState(
        nozzle_temperature=nozzle_temperature,
        bed_temperature=bed_temperature,
        extrusion_mode=extrusion_mode,
        positioning_mode=positioning_mode,
        fan_commands=tuple(fan_commands[key] for key in sorted(fan_commands)),
        motion_commands=tuple(motion_commands[key] for key in ("M201", "M203", "M205", "M204") if key in motion_commands),
        speed_factor_command=speed_factor,
        flow_factor_command=flow_factor,
        flush_setup_command=flush_setup,
        auxiliary_commands=tuple(auxiliary_commands[key] for key in sorted(auxiliary_commands)),
    )


def _validate_supported_source(analysis: Analysis, state: MachineState) -> None:
    model = analysis.printer_model.lower()
    if "p1s" not in model:
        raise ResumeError(
            f"MVP safety guard: only Bambu Lab P1S G-code is supported; source reports '{analysis.printer_model}'."
        )

    sequence = analysis.config.get("print_sequence", "by layer").strip().lower().replace("_", " ")
    if sequence not in {"by layer", "bylayer"}:
        raise ResumeError("MVP safety guard: sequential/by-object printing is not supported.")

    spiral = analysis.config.get("spiral_mode", "0").strip().lower()
    if spiral not in {"0", "false", "off", ""}:
        raise ResumeError("MVP safety guard: spiral-vase G-code is not supported.")

    tools: set[int] = set()
    for raw_line in analysis.lines[analysis.executable_start_line :]:
        code = _code(raw_line)
        tool_match = re.match(r"^T(\d+)\s*$", code, re.IGNORECASE)
        if tool_match:
            tool = int(tool_match.group(1))
            if 0 <= tool < 255:
                tools.add(tool)
        ams_match = re.match(r"^M620\s+S(\d+)A\b", code, re.IGNORECASE)
        if ams_match:
            tool = int(ams_match.group(1))
            if 0 <= tool < 255:
                tools.add(tool)
    if any(tool > 0 for tool in tools):
        raise ResumeError("MVP safety guard: multi-filament/AMS tool changes are not supported yet.")

    if state.positioning_mode != "G90":
        raise ResumeError("MVP safety guard: the selected layer must begin from known absolute positioning (G90).")
    if state.extrusion_mode != "M83":
        raise ResumeError("MVP safety guard: only known relative extrusion (M83) is supported.")
    if state.nozzle_temperature is None:
        raise ResumeError("Could not determine the active nozzle temperature at the selected layer.")
    if state.bed_temperature is None:
        raise ResumeError("Could not determine the active bed temperature at the selected layer.")


def _format_number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


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


def _retraction_length(analysis: Analysis) -> float:
    value = analysis.config.get("retraction_length")
    match = NUMBER_RE.search(value) if value else None
    length = float(match.group(0)) if match else 0.8
    return min(max(length, 0.0), 5.0)


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

    mode = _z_reference_mode(options.z_reference_mode)
    reference_z: float | None = None
    if mode is ZReferenceMode.MANUAL:
        if not options.home_corexy:
            raise ResumeError("Manual Z reference mode requires CoreXY homing after the safety lift.")
        reference_z = _previous_layer(analysis, layer).z

    progress = max(0, min(100, round((layer.number - 1) / layer.total * 100)))
    safety_note = (
        "requires retained printer Z coordinates and a firmly attached original part."
        if mode is ZReferenceMode.RETAINED
        else (
            "before job start, the nozzle must just touch the top of the last successful layer; "
            "G92 assigns that position without Z homing."
        )
    )
    lines = [
        "; LAYER_RESCUE_BLOCK_START",
        "; Generated by Layer Rescue 0.2.1",
        f"; Resume at layer {layer.number}/{layer.total}, Z={_format_number(layer.z)} mm",
        f"; Z reference mode: {mode.value}",
        f"; SAFETY: {safety_note}",
        f"M73 P{progress}",
    ]
    lines.extend(state.motion_commands)
    lines.extend(
        [
            f"M140 S{bed}",
            f"M104 S{nozzle}",
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
        lines.append(
            f"G92 Z{_format_number(reference_z)} ; assign manually aligned last-layer surface as absolute Z"
        )
    lines.extend(
        [
            "G91",
            f"G1 Z{_format_number(options.z_lift_mm)} F600 ; relative safety lift; no Z homing",
            "G90",
        ]
    )
    if options.home_corexy:
        lines.append("G28 X ; Bambu CoreXY re-home only; never home Z")
    lines.extend(
        [
            "M975 S1",
            "; Move to the stock P1S filament-change station at the lifted Z position.",
            "G1 X60 F12000",
            "G1 Y245",
            "G1 Y265 F3000",
            "M620 M",
            "M620 S0A",
            f"M190 S{bed}",
            f"M109 S{nozzle}",
            "G1 X120 F12000",
            "G1 X20 Y50 F12000",
            "G1 Y-3",
            "T0",
            "G1 X54 F12000",
            "G1 Y265",
            "M400",
            "M621 S0A",
            state.flush_setup_command or "M620.1 E F149.669 T270",
            "T1000",
            f"M109 S{nozzle} ; reassert print temperature after tool/AMS selection",
            "M412 S1",
            # Bambu firmware: G90 (issued above for the Z lift) also switches E to
            # absolute. Without this M83 every relative E value in the retained body
            # is executed as an absolute position and no filament is extruded.
            "G90",
            "M83 ; relative extrusion must be re-selected after G90 on Bambu firmware",
        ]
    )
    retract = _retraction_length(analysis)
    if options.purge_length_mm > 0:
        lines.extend(
            [
                "; Refill the melt zone over the rear purge chute (nozzle may have oozed or been retracted).",
                "M400",
                "G92 E0",
                f"G1 E{_format_number(options.purge_length_mm)} F200",
                "M400",
            ]
        )
        if retract > 0:
            lines.append(f"G1 E-{_format_number(retract)} F1800 ; retract before wiping and travel")
        lines.extend(
            [
                "M106 P1 S255",
                "M400 S3",
                "G1 X70 F9000",
                "G1 X76 F15000",
                "G1 X65 F15000",
                "G1 X76 F15000",
                "G1 X65 F15000 ; shake off purged filament",
                "G1 X80 F6000",
                "G1 X95 F15000",
                "G1 X80 F15000",
                "G1 X165 F15000 ; wipe",
                "M400",
                "M106 P1 S0",
            ]
        )
    lines.extend(state.fan_commands)
    for command in state.auxiliary_commands:
        if not command.startswith("M975"):
            lines.append(command)

    first_xy = _first_layer_xy(analysis, layer)
    if first_xy is not None:
        lines.append(
            f"G1 X{_format_number(first_xy[0])} Y{_format_number(first_xy[1])} F12000"
            " ; travel above the part at the lifted Z"
        )
        approach_note = "descend onto the recovered layer start"
    else:
        approach_note = "approach the recovered layer at the rear station"
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
    total_layers: int,
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
    expected = list(range(start_layer, total_layers + 1))
    if layers != expected:
        raise ResumeError("Internal validation failed: retained layers are not contiguous through the end.")

    preamble_end = text.find("; LAYER_RESCUE_BLOCK_END")
    if preamble_end < 0:
        raise ResumeError("Internal validation failed: resume block terminator is missing.")
    preamble = text[:preamble_end]
    tool_index = preamble.rfind("T1000")
    final_heat_index = preamble.rfind("M109 S")
    if tool_index < 0 or final_heat_index < tool_index:
        raise ResumeError("Internal validation failed: print temperature is not reasserted after T1000.")

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
    executable = False
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        if raw_line.strip().upper() == "; EXECUTABLE_BLOCK_START":
            executable = True
        code = _code(raw_line)
        if not code or not executable:
            continue
        command = _command(code)
        extrusion_mode = _next_extrusion_mode(command, extrusion_mode)
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
    if options.start_layer > analysis.total_layers:
        raise ResumeError("The selected start layer is beyond the end of the print.")

    state = _scan_machine_state(analysis, layer.change_line)
    _validate_supported_source(analysis, state)
    mode = _z_reference_mode(options.z_reference_mode)
    preamble, nozzle, bed, reference_z = _resume_preamble(analysis, layer, state, options)

    prefix = list(analysis.lines[: analysis.config_end_line + 1])
    body = list(analysis.lines[layer.change_line :])
    output_lines = prefix + ["", "; EXECUTABLE_BLOCK_START"] + preamble + body
    output = analysis.newline.join(output_lines) + analysis.newline
    _validate_output(output, options.start_layer, analysis.total_layers, mode, reference_z)

    warnings = list(analysis.warnings)
    if mode is ZReferenceMode.MANUAL:
        warnings.append(
            "Manual Z mode depends on the operator aligning the nozzle to the last successful layer before job start."
        )

    report = ResumeReport(
        start_layer=options.start_layer,
        total_layers=analysis.total_layers,
        start_z=layer.z,
        nozzle_temperature=nozzle,
        bed_temperature=bed,
        retained_layers=analysis.total_layers - options.start_layer + 1,
        z_reference_mode=mode,
        reference_z=reference_z,
        source_sha256=analysis.source_sha256,
        output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
        warnings=tuple(warnings),
    )
    return output, report


def _available_backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".layer-rescue.bak")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".layer-rescue.{counter}.bak")
        counter += 1
    return candidate


def rewrite_gcode_file(
    path: str | os.PathLike[str],
    options: ResumeOptions,
    *,
    create_backup: bool = True,
) -> ResumeReport:
    source_path = Path(path).expanduser().resolve()
    if not source_path.is_file():
        raise ResumeError(f"G-code file does not exist: {source_path}")
    if source_path.suffix.lower() not in {".gcode", ".gco"}:
        raise ResumeError("Post-processing MVP accepts raw .gcode files only.")

    text = source_path.read_text(encoding="utf-8", errors="replace")
    output, report = build_resume_gcode(text, options)
    backup_path: Path | None = None
    if create_backup:
        backup_path = _available_backup_path(source_path)
        shutil.copy2(source_path, backup_path)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=source_path.parent,
            prefix=source_path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, source_path)
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()

    return replace(report, backup_path=backup_path)
