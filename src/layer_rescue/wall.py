"""Plan and emit the holding wall that keeps a re-seated part in place.

The wall is derived from the part's own toolpaths below the wall height:

* ``S(h)``: footprint of the outline extrusions of layer ``h`` (lines grown by half their width,
  holes filled) = the outside of the part at that height.
* ``O(z) = union of S(h) for h <= z``: the part is lowered into the wall from above, so the opening
  at height ``z`` must let every section below ``z`` pass. The opening only grows with height.
* The outside of the wall is fixed (from the largest opening), so the wall is thickest at the bottom
  and never overhangs outwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import geometry as geo
from .flow import FlowSettings, extrusion_per_mm
from .gcode import LayerInfo, _format_number
from .toolpath import LayerToolpaths

WALL_GAP_TO_SUPPORT_MM = 1.0  # the wall keeps this far from reprinted support on the same layer


@dataclass(frozen=True)
class WallOptions:
    clearance_mm: float = 0.25
    wall_lines: int = 4
    brim_mm: float = 5.0
    chamfer_mm: float = 0.6  # extra opening at the rim, a lead-in for seating the part
    chamfer_height_mm: float = 1.2
    max_loops: int = 30
    cradle_depth_mm: float = 3.0  # how far the wall may reach in under the part's outline (never deeper)
    vertical_clearance_mm: float = 0.4  # gap under overhangs: the opening at z already includes sections up to z + this


@dataclass
class WallLayer:
    layer: LayerInfo
    height: float
    width: float
    opening: geo.Region  # O(z): union of part sections up to this layer
    loops: list[geo.IntPath] = field(default_factory=list)
    brim: list[geo.IntPath] = field(default_factory=list)


@dataclass
class WallPlan:
    layers: list[WallLayer]
    silhouette: geo.Region  # O at the top of the wall
    outer_boundary: geo.Region
    spacing: float

    @property
    def top_z(self) -> float:
        return self.layers[-1].layer.z


def spacing_for(width: float, height: float) -> float:
    """Centre-to-centre distance of adjacent beads (Slic3r/Bambu flow spacing)."""
    return max(width - height * (1 - math.pi / 4), width * 0.5)


def section(toolpaths: LayerToolpaths) -> geo.Region:
    """Outside of the part at one layer (holes filled)."""
    lines = [(e.points, e.width) for e in toolpaths.outline_extrusions()]
    return geo.fill_holes(geo.buffer_polylines(lines))


def _contours_ccw(region: geo.Region) -> list[geo.IntPath]:
    """Contours to print, hole contours first (they touch the part), all counter-clockwise."""
    holes = [list(reversed(path)) for path in region if not geo.pyclipper.Orientation(path)]
    outers = [list(path) for path in region if geo.pyclipper.Orientation(path)]
    return holes + outers


def plan_wall(
    layers: list[LayerInfo],
    toolpaths: dict[int, LayerToolpaths],
    flow: FlowSettings,
    options: WallOptions,
    keep_out: dict[int, geo.Region] | None = None,
    above: list[LayerInfo] | None = None,
) -> WallPlan:
    """``keep_out``: per layer number, areas the wall must stay out of (reprinted support).
    ``above``: the part's layers above the wall, for the vertical clearance under overhangs."""
    keep_out = keep_out or {}
    if not layers:
        raise ValueError("the wall needs at least one layer")
    sequence = list(layers) + [layer for layer in (above or []) if layer.number in toolpaths]
    sections = {}
    openings: list[geo.Region] = []
    opening: geo.Region = []
    cursor = 0
    for layer in layers:
        # Everything the part has up to z + vertical clearance, so its overhangs never rest on the wall.
        while cursor < len(sequence) and sequence[cursor].z <= layer.z + options.vertical_clearance_mm + 1e-6:
            number = sequence[cursor].number
            sections[number] = section(toolpaths[number])
            opening = geo.fill_holes(geo.union(opening, sections[number]))
            cursor += 1
        openings.append(opening)
    silhouette = opening

    top_height = layers[-1].z - (layers[-2].z if len(layers) > 1 else 0.0)
    top_width = flow.line_width
    spacing = spacing_for(top_width, top_height)
    thickness = options.wall_lines * spacing
    outer_boundary = geo.offset(silhouette, options.clearance_mm + thickness)

    # Keep at least two beads at the rim even with the chamfer.
    max_chamfer = max(0.0, thickness - 2 * spacing)
    chamfer = min(options.chamfer_mm, max_chamfer)
    chamfer_start = layers[-1].z - options.chamfer_height_mm
    # Deep inside the outline there is nothing to hold (e.g. the hollow of a part standing on legs),
    # and reprinted support may stand there.
    interior = geo.offset(silhouette, -(options.clearance_mm + options.cradle_depth_mm))

    planned: list[WallLayer] = []
    previous_z = 0.0
    for index, layer in enumerate(layers):
        height = layer.z - previous_z
        previous_z = layer.z
        first = index == 0
        width = flow.first_layer_line_width if first else flow.line_width
        layer_spacing = spacing_for(width, height)
        extra = 0.0
        if chamfer > 0 and layer.z > chamfer_start:
            extra = chamfer * min(1.0, (layer.z - chamfer_start) / options.chamfer_height_mm)
        hole = geo.offset(openings[index], options.clearance_mm + extra)
        avoid = geo.offset(keep_out.get(layer.number, []), WALL_GAP_TO_SUPPORT_MM)
        region = geo.difference(outer_boundary, geo.union(hole, interior, avoid))

        loops: list[geo.IntPath] = []
        for ring in range(options.max_loops):
            inset = geo.offset(region, -(width / 2 + ring * layer_spacing))
            inset = geo.simplify(inset)
            if not inset:
                break
            loops.extend(_contours_ccw(inset))

        brim: list[geo.IntPath] = []
        if first and options.brim_mm > 0:
            if avoid:
                # Brim as insets of the free band around the wall, so it stops short of support.
                band = geo.difference(
                    geo.offset(outer_boundary, options.brim_mm + layer_spacing - width / 2), geo.union(outer_boundary, avoid)
                )
                for ring in range(options.max_loops):
                    inset = geo.simplify(geo.offset(band, -(width / 2 + ring * layer_spacing)))
                    if not inset:
                        break
                    brim.extend(_contours_ccw(inset))
            else:
                rings = max(1, int(options.brim_mm / layer_spacing))
                for ring in range(rings):
                    grown = geo.offset(outer_boundary, layer_spacing * (ring + 1) - width / 2)
                    brim.extend(_contours_ccw([path for path in geo.simplify(grown) if geo.pyclipper.Orientation(path)]))
        planned.append(WallLayer(layer, height, width, openings[index], loops, brim))

    return WallPlan(planned, silhouette, outer_boundary, spacing)


def footprint(plan: WallPlan) -> geo.Region:
    """Everything the wall prints on the bed, including the brim, as a region."""
    first = plan.layers[0]
    reach = first.width / 2
    if first.brim:
        return geo.offset(geo.union([path for path in first.brim if geo.pyclipper.Orientation(path)], plan.outer_boundary), reach)
    return geo.offset(plan.outer_boundary, reach)


@dataclass
class EmitState:
    x: float | None = None
    y: float | None = None
    retracted: float = 0.0  # filament currently pulled back, mm
    filament_mm: float = 0.0  # total extruded by the wall


def _path_length(points: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def _rotate_to_nearest(path: list[tuple[float, float]], x: float | None, y: float | None) -> list[tuple[float, float]]:
    if x is None or y is None or not path:
        return path
    start = min(range(len(path)), key=lambda i: (path[i][0] - x) ** 2 + (path[i][1] - y) ** 2)
    return path[start:] + path[:start]


def emit_wall_layer(
    wall_layer: WallLayer,
    flow: FlowSettings,
    state: EmitState,
) -> list[str]:
    """G-code for one wall layer. Assumes nothing about the head position; leaves filament retracted."""
    z = wall_layer.layer.z
    first = wall_layer.layer.number == 1 or wall_layer.height >= z - 1e-9
    loops = [geo.to_float(path) for path in wall_layer.loops] + [geo.to_float(path) for path in wall_layer.brim]
    loops = [path + [path[0]] for path in loops if len(path) >= 3]
    epm = extrusion_per_mm(wall_layer.width, wall_layer.height, flow.filament_diameter, flow.flow_ratio)

    total = sum(_path_length(path) for path in loops)
    speed = flow.first_layer_speed if first else flow.wall_speed
    if total > 0 and flow.min_layer_time > 0 and total / speed < flow.min_layer_time:
        speed = max(flow.min_speed, total / flow.min_layer_time)
    feed = int(round(speed * 60))
    travel = flow.travel_feed
    hop = flow.z_hop

    lines = [
        f"; LAYER_RESCUE_WALL layer {wall_layer.layer.number}, Z={_format_number(z)}, "
        f"{len(wall_layer.loops)} loops, {len(wall_layer.brim)} brim loops",
        "; FEATURE: Layer Rescue wall",
        f"; LINE_WIDTH: {_format_number(wall_layer.width)}",
        "G90",
        "M83 ; relative extrusion (G90 also switches E to absolute on Bambu firmware)",
    ]

    def retract() -> None:
        if state.retracted <= 0 and flow.retraction_length > 0:
            lines.append(f"G1 E-{_format_number(flow.retraction_length)} F{flow.retraction_feed}")
            state.retracted = flow.retraction_length

    def unretract() -> None:
        if state.retracted > 0:
            lines.append(f"G1 E{_format_number(state.retracted)} F{flow.retraction_feed}")
            state.retracted = 0.0

    first_loop = True
    for path in loops:
        path = _rotate_to_nearest(path[:-1], state.x, state.y)
        path = path + [path[0]]
        sx, sy = path[0]
        far = state.x is None or math.dist((state.x, state.y), (sx, sy)) > 2.0
        if first_loop or far:
            retract()
            lines.append(f"G1 Z{_format_number(z + hop)} F600")
            lines.append(f"G1 X{sx:.3f} Y{sy:.3f} F{travel}")
            lines.append(f"G1 Z{_format_number(z)} F600")
        else:
            lines.append(f"G1 X{sx:.3f} Y{sy:.3f} F{travel}")
        unretract()
        lines.append(f"G1 F{feed}")
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            length = math.hypot(bx - ax, by - ay)
            if length < 1e-4:
                continue
            e = length * epm
            state.filament_mm += e
            lines.append(f"G1 X{bx:.3f} Y{by:.3f} E{e:.5f}")
        state.x, state.y = path[-1]
        first_loop = False
    retract()
    return lines
