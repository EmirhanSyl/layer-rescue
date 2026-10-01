"""Machine state reconstruction and source-support guards."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .gcode import Analysis, ResumeError, _code, _command, _first_number, _next_extrusion_mode, _parameter


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
    active_tool: int | None = None  # filament slot (T/M620 S<n>A) in use when the selected layer starts


TOOL_RE = re.compile(r"^T(\d+)\s*$", re.IGNORECASE)
AMS_SELECT_RE = re.compile(r"^M620\s+S(\d+)A\b", re.IGNORECASE)
TESTED_PRINTERS = ("p1s",)
UNTESTED_HINT = " To try it anyway, accept the risks (CLI: --allow-untested)."


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
    active_tool: int | None = None

    for raw_line in analysis.lines[analysis.executable_start_line : stop_line]:
        code = _code(raw_line)
        if not code:
            continue
        command = _command(code)
        tool_match = TOOL_RE.match(code) or AMS_SELECT_RE.match(code)
        if tool_match and 0 <= int(tool_match.group(1)) < 255:
            active_tool = int(tool_match.group(1))
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
        active_tool=active_tool,
    )


def filament_slots(analysis: Analysis) -> set[int]:
    """Filament slots the job selects (T<n> or AMS M620 S<n>A), ignoring Bambu's special T255/T1000."""
    tools: set[int] = set()
    for raw_line in analysis.lines[analysis.executable_start_line :]:
        code = _code(raw_line)
        match = TOOL_RE.match(code) or AMS_SELECT_RE.match(code)
        if match and 0 <= int(match.group(1)) < 255:
            tools.add(int(match.group(1)))
    return tools


def untested_setup(analysis: Analysis) -> list[str]:
    """Reasons this job is outside what Layer Rescue has been tested on (empty when it is a tested setup).

    These are not hard limits: the user can accept the risks and continue.
    """
    reasons: list[str] = []
    model = analysis.printer_model
    if not any(name in model.lower() for name in TESTED_PRINTERS):
        reasons.append(
            f"Untested printer: this G-code is for '{model}', and Layer Rescue has only been tested on the "
            "Bambu Lab P1S. Parking, purging and homing positions may not fit this printer."
        )
    slots = filament_slots(analysis)
    if any(slot > 0 for slot in slots):
        reasons.append(
            f"Untested setup: this job uses {len(slots)} filaments (AMS/tool changes), and Layer Rescue has only "
            "been tested with a single filament. It loads the filament that was active at the selected layer."
        )
    return reasons


def _validate_supported_source(analysis: Analysis, state: MachineState, allow_untested: bool = False) -> list[str]:
    """Reject sources Layer Rescue cannot convert safely. Returns the untested-setup warnings that were accepted."""
    sequence = analysis.config.get("print_sequence", "by layer").strip().lower().replace("_", " ")
    if sequence not in {"by layer", "bylayer"}:
        raise ResumeError("MVP safety guard: sequential/by-object printing is not supported.")

    spiral = analysis.config.get("spiral_mode", "0").strip().lower()
    if spiral not in {"0", "false", "off", ""}:
        raise ResumeError("MVP safety guard: spiral-vase G-code is not supported.")

    untested = untested_setup(analysis)
    if untested and not allow_untested:
        raise ResumeError(untested[0] + UNTESTED_HINT)

    if state.positioning_mode != "G90":
        raise ResumeError("MVP safety guard: the selected layer must begin from known absolute positioning (G90).")
    if state.extrusion_mode != "M83":
        raise ResumeError("MVP safety guard: only known relative extrusion (M83) is supported.")
    if state.nozzle_temperature is None:
        raise ResumeError("Could not determine the active nozzle temperature at the selected layer.")
    if state.bed_temperature is None:
        raise ResumeError("Could not determine the active bed temperature at the selected layer.")
    return untested
