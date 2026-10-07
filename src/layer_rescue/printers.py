"""Printer families and the machine-specific parts of the resume sequence.

Everything that depends on where things are inside a particular printer lives here: the filament
station and purge moves, X homing, tool and hotend selection, extruder-indexed temperatures and the
insert-mode park position. The rest of the resume sequence (Z handling, extrusion mode, fans, travel
and descent) is shared.

Families:

* ``p1``: Bambu Lab P1S / P1P / X1 / X1C / X1E. Same 256 mm CoreXY frame, purge chute at the rear,
  filament cutter at the front left. The P1S is the printer Layer Rescue was developed and tested on.
* ``h2``: Bambu Lab H2D / H2S / H2C. Larger bed with two extruders (and on the H2C a hotend rack).
  Purge and wipe are firmware macros (``G150.x``), tools are selected together with a hotend
  (``T<n> H<h>``) and temperatures are addressed per extruder (``M104 S.. T<e>``). This sequence is
  derived from Bambu Studio's stock H2 G-code and has not been run on a printer yet.

Any other printer (A1, A1 mini, other brands) gets the P1 sequence, as before printer profiles existed.
It is an untested setup, so the user has to accept the risks first (``--allow-untested``).

Sources for the H2 sequence (Bambu does not publish documentation for these commands, so the H2
sequence mirrors what their own templates do):

* Bambu Studio printer profiles, ``resources/profiles/BBL/machine/Bambu Lab H2C 0.4 nozzle template
  machine_start_gcode.json`` / ``... change_filament_gcode.json`` / ``... machine_end_gcode.json``
  (https://github.com/bambulab/BambuStudio). The same templates are embedded in every sliced file's
  CONFIG_BLOCK as ``machine_start_gcode`` and ``change_filament_gcode``.
* ``G150.3`` / ``G150.2`` / ``G150.1``: the start template purges after ``G150.3`` and then runs
  ``G150.2`` / ``G150.1`` followed by ``G1 Y-16 ; move away from the trash bin``; the end template
  calls ``G150.3`` above the finished part. Their exact firmware behaviour is inferred, not documented.
* ``M620.10`` / ``M620.11`` / ``M628 S1 … M629`` / ``T<n> H<h>`` / ``M628 S0`` / ``M629``: order taken
  from the start template's initial filament load.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .gcode import NUMBER_RE, Analysis, ResumeError, _format_number


@dataclass(frozen=True)
class PrinterProfile:
    key: str
    description: str
    experimental: bool = False  # the sequence has never run on a real printer


P1 = PrinterProfile("p1", "Bambu Lab P1/X1 series")
H2 = PrinterProfile("h2", "Bambu Lab H2 series", experimental=True)

_H2_MODELS = re.compile(r"\bh2[a-z]?\b", re.IGNORECASE)

H2_EXPERIMENTAL_WARNING = (
    "Experimental H2 sequence: purge, wipe, hotend selection and X homing follow Bambu Studio's stock H2 "
    "G-code but have not been run on a printer yet. Watch the printer until it is printing on the part."
)


def printer_profile(analysis: Analysis) -> PrinterProfile:
    """The profile for the job's printer. Printers without their own profile fall back to the P1 sequence."""
    model = analysis.printer_model or ""
    if _H2_MODELS.search(model):
        return H2
    return P1


# ----------------------------------------------------------------------------- config helpers


def config_list(analysis: Analysis, key: str) -> list[float]:
    value = analysis.config.get(key) or ""
    numbers: list[float] = []
    for entry in value.split(","):
        match = NUMBER_RE.search(entry)
        if match:
            numbers.append(float(match.group(0)))
    return numbers


def _bounds(area: str) -> tuple[float, float, float, float] | None:
    points = []
    for token in area.replace(";", ",").split(","):
        token = token.strip().strip('"')
        if "x" not in token:
            continue
        sx, sy = token.split("x", 1)
        try:
            points.append((float(sx), float(sy)))
        except ValueError:
            continue
    if len(points) < 3:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def reachable_bounds(analysis: Analysis) -> tuple[float, float, float, float]:
    """XY box every nozzle can reach: the printable area intersected with each extruder's area."""
    box = _bounds(analysis.config.get("printable_area") or "") or (0.0, 0.0, 256.0, 256.0)
    min_x, min_y, max_x, max_y = box
    for area in (analysis.config.get("extruder_printable_area") or "").split("#"):
        extruder = _bounds(area)
        if extruder is None:
            continue
        min_x, min_y = max(min_x, extruder[0]), max(min_y, extruder[1])
        max_x, max_y = min(max_x, extruder[2]), min(max_y, extruder[3])
    if min_x >= max_x or min_y >= max_y:
        return box
    return min_x, min_y, max_x, max_y


def park_position(analysis: Analysis, part_center_x: float) -> tuple[float, float]:
    """A rear corner away from the part (insert mode). On the P1S this is (236, 250) or (20, 250)."""
    min_x, _, max_x, max_y = reachable_bounds(analysis)
    y = max_y - 6.0
    if part_center_x < (min_x + max_x) / 2:
        return max_x - 20.0, y
    return min_x + 20.0, y


# ----------------------------------------------------------------------------- tools and hotends

TOOL_SELECT_RE = re.compile(r"^T(\d+)(?:\s+H(-?\d+))?\s*$", re.IGNORECASE)
AMS_SELECT_RE = re.compile(r"^M620\s+S(\d+)A(?:\s+H(-?\d+))?\b", re.IGNORECASE)


def extruder_for_filament(analysis: Analysis, tool: int) -> int:
    """Physical extruder index (the ``T`` of ``M104``) that prints filament ``tool`` on an H2."""
    filament_map = config_list(analysis, "filament_map")
    logical = int(filament_map[tool]) if 0 <= tool < len(filament_map) else 1
    physical = config_list(analysis, "physical_extruder_map")
    if 1 <= logical <= len(physical):
        return int(physical[logical - 1])
    return logical % 2  # what the stock H2 start G-code uses


# ----------------------------------------------------------------------------- sequences


@dataclass(frozen=True)
class StationContext:
    tool: int
    nozzle: int
    bed: int
    purge_length: float
    purge_feed: int
    retract: float
    hotend: int | None = None
    extruder: int | None = None
    flush_setup: str | None = None
    toolchange_setup: tuple[str, ...] = ()


def heat_commands(profile: PrinterProfile, ctx: StationContext) -> list[str]:
    if profile is H2:
        return [f"M140 S{ctx.bed}", f"M104 S{ctx.nozzle} T{ctx.extruder}"]
    return [f"M140 S{ctx.bed}", f"M104 S{ctx.nozzle}"]


def home_command(profile: PrinterProfile) -> str:
    if profile is H2:
        return "G28 X T300 ; CoreXY X re-home as in the stock H2 start G-code; never home Z"
    return "G28 X ; Bambu CoreXY re-home only; never home Z"


def station_block(profile: PrinterProfile, ctx: StationContext) -> list[str]:
    """Select the filament, reach print temperature and purge/wipe, ending with ``G90`` + ``M83``."""
    if profile is H2:
        return _h2_station(ctx)
    return _p1_station(ctx)


def _purge(ctx: StationContext) -> list[str]:
    lines = [
        "M400",
        "G92 E0",
        f"G1 E{_format_number(ctx.purge_length)} F{ctx.purge_feed} ; purge within the filament's max volumetric speed",
        "M400",
    ]
    if ctx.retract > 0:
        lines.append(f"G1 E-{_format_number(ctx.retract)} F1800 ; retract before wiping and travel")
    return lines


def _p1_station(ctx: StationContext) -> list[str]:
    lines = [
        "M975 S1",
        "; Move to the stock P1S filament-change station at the lifted Z position.",
        "G1 X60 F12000",
        "G1 Y245",
        "G1 Y265 F3000",
        "M620 M",
        f"M620 S{ctx.tool}A",
        f"M190 S{ctx.bed}",
        f"M109 S{ctx.nozzle}",
        "G1 X120 F12000",
        "G1 X20 Y50 F12000",
        "G1 Y-3",
        f"T{ctx.tool}",
        "G1 X54 F12000",
        "G1 Y265",
        "M400",
        f"M621 S{ctx.tool}A",
        ctx.flush_setup or "M620.1 E F149.669 T270",
        "T1000",
        f"M109 S{ctx.nozzle} ; reassert print temperature after tool/AMS selection",
        "M412 S1",
        # Bambu firmware: G90 (issued above for the Z lift) also switches E to
        # absolute. Without this M83 every relative E value in the retained body
        # is executed as an absolute position and no filament is extruded.
        "G90",
        "M83 ; relative extrusion must be re-selected after G90 on Bambu firmware",
    ]
    if ctx.purge_length > 0:
        lines.append("; Refill the melt zone over the rear purge chute (nozzle may have oozed or been retracted).")
        lines.extend(_purge(ctx))
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
    return lines


def _is_cut_sequence(line: str) -> bool:
    """``M620.11 S<n> ...``: the filament cut + retraction, recorded between ``M628 S1`` and ``M629``."""
    tokens = line.split()
    return len(tokens) > 1 and tokens[0].upper() == "M620.11" and tokens[1][:1].upper() == "S"


def _h2_station(ctx: StationContext) -> list[str]:
    if ctx.hotend is None or ctx.extruder is None:
        raise ResumeError(
            "Could not determine the hotend (T<n> H<h>) or extruder used by the selected layer; "
            "the H2 sequence needs both."
        )
    hotend, extruder = ctx.hotend, ctx.extruder
    # Same structure as the stock H2 start G-code: flush (M620.10) and cut-retraction (M620.11 P/K)
    # settings, the cut sequence recorded between M628 S1 and M629, the tool change, then an empty
    # M628 S0 / M629 block. The cut lines are only ever sent inside that block.
    cut = [line for line in ctx.toolchange_setup if _is_cut_sequence(line)]
    settings = [line for line in ctx.toolchange_setup if not _is_cut_sequence(line)]
    lines = [
        "M975 S1",
        "; H2: tool/hotend selection, purge and wipe use the firmware's own moves (stock H2 G-code).",
        "M620 M ; enable remap (stock H2 start)",
        "M620 N ; enable hotend remap (stock H2 start)",
        *settings,
    ]
    if cut:
        lines.extend(["M628 S1", *cut, "M629"])
    lines += [
        f"M620 S{ctx.tool}A H{hotend}",
        f"M190 S{ctx.bed}",
        f"M109 S{ctx.nozzle} T{extruder}",
        "M400",
        f"T{ctx.tool} H{hotend}",
        "M400",
        "M628 S0",
        "M629",
        "M400",
        f"M621 S{ctx.tool}A",
        f"M109 S{ctx.nozzle} T{extruder} ; reassert print temperature after tool/hotend selection",
        "G90",
        "M83 ; relative extrusion must be re-selected after G90 on Bambu firmware",
    ]
    if ctx.purge_length > 0:
        lines.extend(["; Refill the melt zone over the purge bin.", "G150.3 ; firmware: move to the purge bin"])
        lines.extend(_purge(ctx))
        lines.extend(
            [
                "M106 P1 S255",
                "M400 S3",
                "M106 P1 S0",
                "G150.2 ; firmware: wipe",
                "G150.1 ; firmware: wipe",
                "G91",
                "G1 Y-16 F12000 ; move away from the purge bin (stock H2)",
                "G90",
                "M83",
            ]
        )
    return lines
