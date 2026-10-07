"""Bambu Studio G-code parsing: markers, layers, config and small command helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Mapping


LAYER_MARKER_RE = re.compile(
    r"^\s*;\s*layer num/total_layer_count:\s*(\d+)\s*/\s*(\d+)\s*$",
    re.IGNORECASE,
)
PROGRESS_LAYER_RE = re.compile(r"^\s*M73\s+L(\d+)\b", re.IGNORECASE)
TOTAL_LAYERS_RE = re.compile(r"^\s*;\s*total layer number:\s*(\d+)\s*$", re.IGNORECASE)
Z_HEIGHT_RE = re.compile(r"^\s*;\s*Z_HEIGHT:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*$", re.IGNORECASE)
CONFIG_RE = re.compile(r"^\s*;\s*([^=]+?)\s*=\s*(.*?)\s*$")
COMMAND_RE = re.compile(r"^\s*([GMT]\d+(?:\.\d+)?)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"-?(?:\d+(?:\.\d*)?|\.\d+)")



class ResumeError(ValueError):
    """Raised when a source file cannot be converted conservatively."""



@dataclass(frozen=True)
class LayerInfo:
    number: int
    total: int
    z: float
    change_line: int
    marker_line: int
    end_line: int



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


def _code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _command(line: str) -> str | None:
    match = COMMAND_RE.match(_code(line))
    return match.group(1).upper() if match else None


_PARAMETER_RES: dict[str, re.Pattern[str]] = {}


def _parameter(code: str, letter: str) -> float | None:
    pattern = _PARAMETER_RES.get(letter)
    if pattern is None:
        pattern = re.compile(rf"(?:^|\s){re.escape(letter)}(-?(?:\d+(?:\.\d*)?|\.\d+))(?=\s|$)", re.IGNORECASE)
        _PARAMETER_RES[letter] = pattern
    match = pattern.search(code)
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


def layer_markers(lines: list[str] | tuple[str, ...], start: int = 0) -> list[tuple[int, int, int]]:
    """(line index, layer number, total) for every layer.

    Most Bambu printer templates write ``; layer num/total_layer_count: N/T`` in the layer-change
    G-code. The A2L's does not; there the layer number is the first ``M73 L<n>`` after each
    ``; CHANGE_LAYER`` and the total comes from the header's ``; total layer number: T``.
    """
    markers: list[tuple[int, int, int]] = []
    for index in range(start, len(lines)):
        match = LAYER_MARKER_RE.match(lines[index])
        if match:
            markers.append((index, int(match.group(1)), int(match.group(2))))
    if markers:
        return markers

    total = 0
    for line in lines[: min(len(lines), 200)]:
        match = TOTAL_LAYERS_RE.match(line)
        if match:
            total = int(match.group(1))
            break
    waiting = False
    for index in range(start, len(lines)):
        line = lines[index]
        if line.strip().upper() == "; CHANGE_LAYER":
            waiting = True
            continue
        if waiting:
            match = PROGRESS_LAYER_RE.match(line)
            if match:
                markers.append((index, int(match.group(1)), total))
                waiting = False
    if markers and total == 0:
        total = markers[-1][1]
        markers = [(index, number, total) for index, number, _ in markers]
    return markers


def layer_numbers(lines: list[str] | tuple[str, ...]) -> list[int]:
    return [number for _, number, _ in layer_markers(lines)]


def _find_layers(lines: list[str], executable_start: int) -> tuple[LayerInfo, ...]:
    raw_markers = layer_markers(lines, executable_start)

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



def _format_number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def config_float(config: Mapping[str, str], *keys: str, default: float) -> float:
    """First number of the first present config key (Bambu lists per-extruder values as 'a,b')."""
    for key in keys:
        value = config.get(key)
        if value:
            match = NUMBER_RE.search(value)
            if match:
                return float(match.group(0))
    return default
