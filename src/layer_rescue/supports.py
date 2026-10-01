"""Reprint the supports that stand below the part height, where the seated part will not hit them.

Supports that hold features above the part height usually start on the bed. When the part was
removed they are gone (or broken), so the part of each support below the part height must be
printed again before the pause, next to the wall or inside a hollow part.

The part is lowered in from above, so its material at height ``H`` sweeps every level above ``H``.
A support line at level ``h`` is kept only if it is clear of every part section at ``H <= h``
(walls only, holes NOT filled: a hollow part may be lowered over supports inside it). A kept line
must also stand on something: the bed on the first layer, kept support below it otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import geometry as geo
from .gcode import LayerInfo
from .toolpath import Extrusion, LayerToolpaths

SUPPORT_CLEARANCE_EXTRA_MM = 0.2  # on top of the wall clearance, between the part and reprinted support
STACK_TOLERANCE_MM = 0.6  # how far a support line may step sideways from the support below it
MIN_PIECE_MM = 1.0
BED_FOOT_MM = 5.0  # support foot on the bed kept this far around the support that is needed


@dataclass(frozen=True)
class SupportPiece:
    points: tuple[tuple[float, float], ...]
    width: float
    z: float
    e_per_mm: float
    feature: str


@dataclass
class SupportLayer:
    layer: LayerInfo
    pieces: list[SupportPiece] = field(default_factory=list)
    footprint: geo.Region = field(default_factory=list)  # printed support at this layer (for the wall to avoid)
    source_mm: float = 0.0  # support path length in the source layer
    kept_mm: float = 0.0
    previous_z: float | None = None
    keep_out: geo.Region = field(default_factory=list)  # where the lowered part passes (support must stay out)


@dataclass
class SupportPlan:
    layers: dict[int, SupportLayer]
    dropped_mm: float
    source_mm: float
    unsupported_above_mm2: float  # support area just above the part with nothing under it

    @property
    def kept_mm(self) -> float:
        return sum(layer.kept_mm for layer in self.layers.values())

    @property
    def any(self) -> bool:
        return any(layer.pieces for layer in self.layers.values())

    @property
    def last_layer_number(self) -> int | None:
        numbers = [number for number, layer in self.layers.items() if layer.pieces]
        return max(numbers) if numbers else None


MATERIAL_CLOSING_MM = 3.0  # infill gaps narrower than twice this count as solid part


def _material(toolpaths: LayerToolpaths) -> geo.Region:
    """Part material at one layer. Infill gaps are closed; real cavities (a hollow part) stay open."""
    lines = [(e.points, e.width) for e in toolpaths.part_extrusions()]
    return geo.closing(geo.buffer_polylines(lines), MATERIAL_CLOSING_MM, geo.COARSE)


def plan_supports(
    layers: list[LayerInfo],
    toolpaths: dict[int, LayerToolpaths],
    clearance_mm: float,
    next_layer: LayerInfo | None = None,
) -> SupportPlan:
    """Supports of ``layers`` (the part's layers, bottom up) that can be printed before the part is seated."""
    swept: geo.Region = []  # part material at or below the current level
    below: geo.Region = []  # where kept support can carry the next layer
    result: dict[int, SupportLayer] = {}
    dropped = 0.0
    total = 0.0
    previous_z = 0.0
    for layer in layers:
        paths = toolpaths[layer.number]
        swept = geo.union(swept, _material(paths))
        supports = paths.support_extrusions()
        plan_layer = SupportLayer(layer, previous_z=previous_z)
        previous_z = layer.z
        result[layer.number] = plan_layer
        if not supports:
            continue
        plan_layer.source_mm = sum(geo.polyline_length(e.points) for e in supports)
        total += plan_layer.source_mm
        keep_out = geo.offset(swept, clearance_mm + SUPPORT_CLEARANCE_EXTRA_MM, tolerance_mm=geo.COARSE)
        plan_layer.keep_out = keep_out
        if layer is layers[0]:
            base = geo.polygon_from_config("-1000x-1000,1000x-1000,1000x1000,-1000x1000")  # the bed
        else:
            base = geo.offset(below, STACK_TOLERANCE_MM)  # only on top of support printed below
        allowed = geo.difference(base, keep_out)
        pieces: list[SupportPiece] = []
        for extrusion in supports:
            for clipped in geo.clip_polylines([extrusion.points], allowed):
                if geo.polyline_length(clipped) < MIN_PIECE_MM:
                    continue
                pieces.append(_piece(extrusion, clipped, layer))
        plan_layer.pieces = pieces
        plan_layer.kept_mm = sum(geo.polyline_length(p.points) for p in pieces)
        dropped += plan_layer.source_mm - plan_layer.kept_mm
        plan_layer.footprint = geo.buffer_polylines([(p.points, p.width) for p in pieces]) if pieces else []
        below = plan_layer.footprint

    unsupported = 0.0
    above_region: geo.Region = []
    if next_layer is not None and next_layer.number in toolpaths:
        above = toolpaths[next_layer.number].support_extrusions()
        if above:
            above_region = geo.buffer_polylines([(e.points, e.width) for e in above])
            carried = geo.union(geo.offset(below, STACK_TOLERANCE_MM), geo.offset(swept, STACK_TOLERANCE_MM))
            unsupported = geo.area_mm2(geo.difference(above_region, carried))

    # Top-down: only support that carries support above the part height is needed. The rest held the
    # part's own overhangs, which are already printed (and its top could lift the seated part).
    needed = geo.offset(above_region, STACK_TOLERANCE_MM)
    first_support_layer = next((layer for layer in layers if result[layer.number].pieces), None)
    for layer in reversed(layers):
        plan_layer = result[layer.number]
        if not plan_layer.pieces:
            if plan_layer.source_mm > 0:
                needed = []  # support existed here but none is printed: nothing below can be needed
            continue
        pruned: list[SupportPiece] = []
        # The first support layer is the foot on the bed: keep its full width around what is needed.
        region = geo.offset(needed, BED_FOOT_MM) if layer is first_support_layer else needed
        for piece in plan_layer.pieces:
            for clipped in geo.clip_polylines([piece.points], region):
                if geo.polyline_length(clipped) >= MIN_PIECE_MM:
                    pruned.append(replace(piece, points=tuple(clipped)))
        plan_layer.pieces = pruned
        plan_layer.kept_mm = sum(geo.polyline_length(p.points) for p in pruned)
        plan_layer.footprint = geo.buffer_polylines([(p.points, p.width) for p in pruned]) if pruned else []
        needed = geo.offset(plan_layer.footprint, STACK_TOLERANCE_MM) if pruned else []
    return SupportPlan(result, max(0.0, dropped), total, unsupported)


def _piece(extrusion: Extrusion, points: list[tuple[float, float]], layer: LayerInfo) -> SupportPiece:
    return SupportPiece(
        points=tuple(points),
        width=extrusion.width,
        z=extrusion.z if extrusion.z is not None else layer.z,
        e_per_mm=extrusion.e_per_mm,
        feature=extrusion.feature,
    )


def emit_support_layer(layer: SupportLayer, flow, state) -> list[str]:
    """G-code for the kept support of one layer. Leaves filament retracted, like the wall emitter."""
    from .flow import extrusion_per_mm
    from .gcode import _format_number

    if not layer.pieces:
        return []
    lines = [
        f"; LAYER_RESCUE_SUPPORT layer {layer.layer.number}, {len(layer.pieces)} pieces",
        "; FEATURE: Support",
        "G90",
        "M83 ; relative extrusion (G90 also switches E to absolute on Bambu firmware)",
    ]
    height = max(layer.layer.z - _previous_z(layer), 0.08)

    def retract() -> None:
        if state.retracted <= 0 and flow.retraction_length > 0:
            lines.append(f"G1 E-{_format_number(flow.retraction_length)} F{flow.retraction_feed}")
            state.retracted = flow.retraction_length

    remaining = list(layer.pieces)
    while remaining:
        # Nearest piece next, entered from whichever end is closer.
        def distance(piece: SupportPiece) -> float:
            if state.x is None:
                return 0.0
            return min(
                (piece.points[0][0] - state.x) ** 2 + (piece.points[0][1] - state.y) ** 2,
                (piece.points[-1][0] - state.x) ** 2 + (piece.points[-1][1] - state.y) ** 2,
            )

        piece = min(remaining, key=distance)
        remaining.remove(piece)
        points = list(piece.points)
        if state.x is not None and (
            (points[-1][0] - state.x) ** 2 + (points[-1][1] - state.y) ** 2
            < (points[0][0] - state.x) ** 2 + (points[0][1] - state.y) ** 2
        ):
            points.reverse()
        epm = piece.e_per_mm if piece.e_per_mm > 0 else extrusion_per_mm(
            piece.width, height, flow.filament_diameter, flow.flow_ratio
        )
        sx, sy = points[0]
        retract()
        lines.append(f"G1 Z{_format_number(piece.z + flow.z_hop)} F600")
        lines.append(f"G1 X{sx:.3f} Y{sy:.3f} F{flow.travel_feed}")
        lines.append(f"G1 Z{_format_number(piece.z)} F600")
        if state.retracted > 0:
            lines.append(f"G1 E{_format_number(state.retracted)} F{flow.retraction_feed}")
            state.retracted = 0.0
        lines.append(f"G1 F{flow.support_feed}")
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
            if length < 1e-4:
                continue
            e = length * epm
            state.filament_mm += e
            lines.append(f"G1 X{bx:.3f} Y{by:.3f} E{e:.5f}")
        state.x, state.y = points[-1]
    retract()
    return lines


def _previous_z(layer: SupportLayer) -> float:
    return layer.previous_z if layer.previous_z is not None else 0.0
