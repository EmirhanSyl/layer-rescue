"""Extrusion amounts and print speeds for toolpaths Layer Rescue generates itself."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from .gcode import NUMBER_RE


def extrusion_per_mm(width: float, height: float, filament_diameter: float, flow_ratio: float = 1.0) -> float:
    """Filament length per mm of path for a rounded-rectangle bead (the Slic3r/Bambu flow model)."""
    if width <= 0 or height <= 0 or filament_diameter <= 0:
        raise ValueError("width, height and filament diameter must be positive")
    width = max(width, height)
    bead_area = (width - height) * height + math.pi * (height / 2) ** 2
    filament_area = math.pi * (filament_diameter / 2) ** 2
    return bead_area / filament_area * flow_ratio


def _number(config: Mapping[str, str], key: str, *, relative_to: float | None = None) -> float | None:
    value = config.get(key)
    if not value:
        return None
    match = NUMBER_RE.search(value)
    if not match:
        return None
    number = float(match.group(0))
    if "%" in value.split(",")[0] and relative_to is not None:
        return number / 100 * relative_to
    return number


def _first(config: Mapping[str, str], *keys: str, default: float, relative_to: float | None = None) -> float:
    for key in keys:
        value = _number(config, key, relative_to=relative_to)
        if value is not None and value > 0:
            return value
    return default


@dataclass(frozen=True)
class FlowSettings:
    nozzle_diameter: float = 0.4
    line_width: float = 0.42
    first_layer_line_width: float = 0.5
    filament_diameter: float = 1.75
    flow_ratio: float = 0.98
    wall_speed: float = 60.0  # mm/s
    first_layer_speed: float = 30.0
    travel_speed: float = 200.0
    support_speed: float = 60.0
    retraction_length: float = 0.8
    retraction_speed: float = 30.0
    z_hop: float = 0.4
    min_layer_time: float = 8.0  # s
    min_speed: float = 20.0

    @property
    def wall_feed(self) -> int:
        return int(round(self.wall_speed * 60))

    @property
    def first_layer_feed(self) -> int:
        return int(round(self.first_layer_speed * 60))

    @property
    def support_feed(self) -> int:
        return int(round(self.support_speed * 60))

    @property
    def travel_feed(self) -> int:
        return int(round(self.travel_speed * 60))

    @property
    def retraction_feed(self) -> int:
        return int(round(self.retraction_speed * 60))


# The wall is a fixture, not a show piece: print it at moderate speeds whatever the profile says.
MAX_WALL_SPEED = 100.0
MAX_FIRST_LAYER_SPEED = 40.0
MAX_TRAVEL_SPEED = 300.0


def flow_settings_from_config(config: Mapping[str, str]) -> FlowSettings:
    nozzle = _first(config, "nozzle_diameter", default=0.4)
    return FlowSettings(
        nozzle_diameter=nozzle,
        line_width=_first(config, "outer_wall_line_width", "line_width", default=nozzle * 1.05, relative_to=nozzle),
        first_layer_line_width=_first(
            config, "initial_layer_line_width", "first_layer_extrusion_width", default=nozzle * 1.25, relative_to=nozzle
        ),
        filament_diameter=_first(config, "filament_diameter", default=1.75),
        flow_ratio=min(max(_first(config, "filament_flow_ratio", "extrusion_multiplier", default=1.0), 0.5), 1.5),
        wall_speed=min(_first(config, "outer_wall_speed", "external_perimeter_speed", default=60.0), MAX_WALL_SPEED),
        first_layer_speed=min(
            _first(config, "initial_layer_speed", "first_layer_speed", default=30.0), MAX_FIRST_LAYER_SPEED
        ),
        travel_speed=min(_first(config, "travel_speed", default=200.0), MAX_TRAVEL_SPEED),
        support_speed=min(_first(config, "support_speed", default=60.0), MAX_WALL_SPEED),
        retraction_length=min(_first(config, "retraction_length", default=0.8), 5.0),
        retraction_speed=min(_first(config, "retraction_speed", default=30.0), 60.0),
        z_hop=min(_first(config, "z_hop", "retract_lift_above", default=0.4), 2.0),
        min_layer_time=_first(config, "slow_down_layer_time", "slowdown_below_layer_time", default=8.0),
        min_speed=_first(config, "slow_down_min_speed", "min_print_speed", default=20.0),
    )
