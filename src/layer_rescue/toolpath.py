"""Read the printed toolpaths of selected layers back out of Bambu Studio G-code.

Only what the insert mode needs is modelled: XY polylines that extrude filament, with their line
width, feature type and object label. Arcs (``G2``/``G3`` from arc fitting) are flattened.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable

from .gcode import Analysis, LayerInfo, ResumeError, _code, _command, _parameter, config_float

FEATURE_RE = re.compile(r"^\s*;\s*(?:FEATURE|TYPE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
WIDTH_RE = re.compile(r"^\s*;\s*(?:LINE_)?WIDTH\s*:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", re.IGNORECASE)
OBJECT_START_RE = re.compile(r"^\s*;\s*start printing object, unique label id:\s*(\S+)", re.IGNORECASE)
OBJECT_STOP_RE = re.compile(r"^\s*;\s*stop printing object", re.IGNORECASE)

# Things the operator removes from the part (or that never belong to it).
EXCLUDED_FEATURE_WORDS = ("skirt", "brim", "support", "prime tower", "wipe tower", "purge")
# Features that trace the part outline. The union of their footprints, holes filled, is the silhouette.
OUTLINE_FEATURE_WORDS = ("wall", "perimeter", "gap")

ARC_TOLERANCE_MM = 0.01
MIN_WIDTH_MM = 0.1
MAX_WIDTH_MM = 1.5  # Arachne can emit absurd LINE_WIDTH values; never trust more than this


@dataclass(frozen=True)
class Extrusion:
    points: tuple[tuple[float, float], ...]
    width: float
    feature: str
    object_id: str | None
    z: float | None = None  # nozzle Z while printing it (support can have its own layer height)
    e_per_mm: float = 0.0  # filament per mm of path, as the slicer extruded it

    @property
    def is_support(self) -> bool:
        return "support" in self.feature.lower()


@dataclass
class LayerToolpaths:
    layer: LayerInfo
    extrusions: list[Extrusion] = field(default_factory=list)
    object_ids: set[str] = field(default_factory=set)

    def outline_extrusions(self) -> list[Extrusion]:
        """Extrusions that describe the outside of the part; falls back to everything that is part of it."""
        part = self.part_extrusions()
        outline = [e for e in part if any(word in e.feature.lower() for word in OUTLINE_FEATURE_WORDS)]
        return outline or part

    def part_extrusions(self) -> list[Extrusion]:
        return [e for e in self.extrusions if not is_excluded_feature(e.feature)]

    def support_extrusions(self) -> list[Extrusion]:
        return [e for e in self.extrusions if e.is_support]


def is_excluded_feature(feature: str) -> bool:
    lowered = feature.lower()
    return any(word in lowered for word in EXCLUDED_FEATURE_WORDS)


def arc_points(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float],
    clockwise: bool,
    tolerance: float = ARC_TOLERANCE_MM,
) -> list[tuple[float, float]]:
    """Points along a G2 (clockwise) / G3 arc, excluding ``start`` and including ``end``."""
    cx, cy = center
    radius = math.hypot(start[0] - cx, start[1] - cy)
    if radius < 1e-6:
        return [end]
    a0 = math.atan2(start[1] - cy, start[0] - cx)
    a1 = math.atan2(end[1] - cy, end[0] - cx)
    sweep = a1 - a0
    if clockwise:
        if sweep >= -1e-9:
            sweep -= 2 * math.pi
    elif sweep <= 1e-9:
        sweep += 2 * math.pi
    ratio = max(-1.0, min(1.0, 1 - tolerance / radius))
    step = 2 * math.acos(ratio) if ratio < 1 else math.pi / 36
    step = max(step, 1e-3)
    count = max(1, math.ceil(abs(sweep) / step))
    points = [
        (cx + radius * math.cos(a0 + sweep * i / count), cy + radius * math.sin(a0 + sweep * i / count))
        for i in range(1, count)
    ]
    points.append(end)
    return points


def default_line_width(analysis: Analysis) -> float:
    nozzle = config_float(analysis.config, "nozzle_diameter", default=0.4)
    return config_float(analysis.config, "outer_wall_line_width", "line_width", default=nozzle * 1.05)


def read_toolpaths(analysis: Analysis, layer_numbers: Iterable[int]) -> dict[int, LayerToolpaths]:
    """Parse the extruding XY moves of the requested layers.

    The whole executable block up to the last requested layer is scanned so that positions,
    positioning mode, feature and object labels are known when each requested layer starts.
    """
    wanted = set(layer_numbers)
    if not wanted:
        return {}
    by_number = {layer.number: layer for layer in analysis.layers}
    missing = wanted - set(by_number)
    if missing:
        raise ResumeError(f"Layer(s) {sorted(missing)} are not present in this G-code file.")
    result = {number: LayerToolpaths(by_number[number]) for number in wanted}
    last_line = max(by_number[number].end_line for number in wanted)

    ordered = sorted(analysis.layers, key=lambda layer: layer.change_line)

    x = y = 0.0
    z: float | None = None
    absolute_xy = True
    relative_e = True
    feature = ""
    width = default_line_width(analysis)
    object_id: str | None = None
    current: list[tuple[float, float]] = []
    current_key: tuple[str, float, str | None, float | None] | None = None
    current_e = 0.0
    current_layer: int | None = None

    def flush() -> None:
        nonlocal current, current_key, current_e
        if current_layer in result and current_key is not None and len(current) >= 2:
            feat, w, obj, cz = current_key
            length = sum(math.dist(a, b) for a, b in zip(current, current[1:]))
            epm = current_e / length if length > 1e-6 else 0.0
            result[current_layer].extrusions.append(Extrusion(tuple(current), w, feat, obj, cz, epm))
            if obj is not None:
                result[current_layer].object_ids.add(obj)
        current = []
        current_key = None
        current_e = 0.0

    layer_index = 0
    for index in range(analysis.executable_start_line, last_line):
        while layer_index < len(ordered) and ordered[layer_index].change_line <= index:
            flush()
            current_layer = ordered[layer_index].number
            layer_index += 1
        raw = analysis.lines[index]
        stripped = raw.strip()
        if stripped.startswith(";"):
            if match := FEATURE_RE.match(raw):
                flush()
                feature = match.group(1)
            elif match := WIDTH_RE.match(raw):
                value = float(match.group(1))
                width = min(max(value, MIN_WIDTH_MM), MAX_WIDTH_MM)
            elif match := OBJECT_START_RE.match(raw):
                flush()
                object_id = match.group(1)
            elif OBJECT_STOP_RE.match(raw):
                flush()
                object_id = None
            continue
        code = _code(raw)
        if not code:
            continue
        command = _command(code)
        if command == "G90":
            absolute_xy = True
            relative_e = False
            continue
        if command == "G91":
            absolute_xy = False
            relative_e = True
            continue
        if command == "M83":
            relative_e = True
            continue
        if command == "M82":
            relative_e = False
            continue
        if command == "G92":
            px, py, pz = _parameter(code, "X"), _parameter(code, "Y"), _parameter(code, "Z")
            if px is not None:
                x = px
            if py is not None:
                y = py
            if pz is not None:
                z = pz
            continue
        if command not in {"G0", "G1", "G2", "G3"}:
            continue

        px, py, pe = _parameter(code, "X"), _parameter(code, "Y"), _parameter(code, "E")
        pz = _parameter(code, "Z")
        nx = (px if absolute_xy else x + px) if px is not None else x
        ny = (py if absolute_xy else y + py) if py is not None else y
        if pz is not None:
            new_z = pz if absolute_xy else (z or 0.0) + pz
            if new_z != z:
                flush()
            z = new_z
        extruding = pe is not None and pe > 0 and relative_e and command != "G0"
        moved = (nx, ny) != (x, y)
        if command in {"G2", "G3"}:
            i_off, j_off = _parameter(code, "I"), _parameter(code, "J")
            if i_off is not None or j_off is not None:
                segment = arc_points((x, y), (nx, ny), (x + (i_off or 0.0), y + (j_off or 0.0)), command == "G2")
            else:
                segment = [(nx, ny)]
            moved = True
        else:
            segment = [(nx, ny)]

        if extruding and moved:
            key = (feature, width, object_id, z)
            if current_key != key or not current or current[-1] != (x, y):
                flush()
                current = [(x, y)]
                current_key = key
            current.extend(segment)
            current_e += pe
        elif moved or (pe is not None and pe < 0):
            flush()
        x, y = nx, ny
    flush()
    return result
