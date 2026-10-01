"""Top-view drawing of an insert plan, as SVG (debugging, bug reports) or as shapes for the Tk preview."""

from __future__ import annotations

from dataclasses import dataclass

from . import geometry as geo
from .insert import InsertPlan


@dataclass(frozen=True)
class Shape:
    kind: str  # "silhouette", "addition", "wall-bottom", "wall-top", "brim"
    points: tuple[tuple[float, float], ...]


def plan_shapes(plan: InsertPlan) -> list[Shape]:
    shapes: list[Shape] = []
    for path in plan.wall.silhouette:
        shapes.append(Shape("silhouette", tuple(geo.to_float(path))))
    for path in plan.addition_section:
        shapes.append(Shape("addition", tuple(geo.to_float(path))))
    first, last = plan.wall.layers[0], plan.wall.layers[-1]
    for path in first.brim:
        shapes.append(Shape("brim", tuple(geo.to_float(path))))
    for path in first.loops:
        shapes.append(Shape("wall-bottom", tuple(geo.to_float(path))))
    for path in last.loops:
        shapes.append(Shape("wall-top", tuple(geo.to_float(path))))
    if plan.supports:
        for layer in plan.supports.layers.values():
            if layer.pieces:
                for path in layer.footprint:
                    shapes.append(Shape("support", tuple(geo.to_float(path))))
                break
    return shapes


def view_bounds(shapes: list[Shape], margin: float = 3.0) -> tuple[float, float, float, float]:
    xs = [x for shape in shapes for x, _ in shape.points]
    ys = [y for shape in shapes for _, y in shape.points]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


STYLES = {
    "silhouette": 'fill="#d9d4c7" stroke="#8a8272" stroke-width="0.15"',
    "addition": 'fill="#3b82f6" fill-opacity="0.25" stroke="#2563eb" stroke-width="0.15"',
    "brim": 'fill="none" stroke="#9ca3af" stroke-width="0.1"',
    "wall-bottom": 'fill="none" stroke="#6b7280" stroke-width="0.12"',
    "wall-top": 'fill="none" stroke="#dc2626" stroke-width="0.12"',
    "support": 'fill="#16a34a" fill-opacity="0.35" stroke="#15803d" stroke-width="0.1"',
}


def plan_svg(plan: InsertPlan) -> str:
    shapes = plan_shapes(plan)
    min_x, min_y, max_x, max_y = view_bounds(shapes)
    width, height = max_x - min_x, max_y - min_y
    body = []
    for kind in ("silhouette", "addition", "brim", "wall-bottom", "wall-top", "support"):
        for shape in shapes:
            if shape.kind != kind:
                continue
            # SVG y grows downwards; the bed's Y grows away from the front edge.
            points = " ".join(f"{x - min_x:.3f},{max_y - y:.3f}" for x, y in shape.points)
            body.append(f'<polygon points="{points}" {STYLES[kind]}/>')
    label = (
        f"part {plan.options.part_height_mm:g} mm, wall to {plan.wall.top_z:g} mm, "
        f"resume at layer {plan.resume_layer.number}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} {height + 4:.3f}" '
        f'width="{width * 20:.0f}" height="{(height + 4) * 20:.0f}">'
        f'<rect width="100%" height="100%" fill="white"/>'
        + "".join(body)
        + f'<text x="1" y="{height + 3:.3f}" font-size="1.1" font-family="sans-serif">{label} (front edge at the bottom)</text>'
        + "</svg>"
    )
