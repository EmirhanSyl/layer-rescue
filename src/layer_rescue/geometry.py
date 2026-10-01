"""2D polygon operations for the insert mode, on top of pyclipper (Clipper 1, integer coordinates).

A *region* is a list of closed integer paths in Clipper's convention: outer contours are
counter-clockwise (positive area), holes clockwise. Coordinates are micrometres (``SCALE``).
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import pyclipper

SCALE = 1000  # 1 unit = 1 µm
ARC_TOLERANCE = 0.01 * SCALE  # 10 µm chord error for rounded offsets
COARSE = 0.03  # mm, for keep-out areas that are only tested against, never printed

Point = tuple[float, float]
IntPath = list[list[int]]
Region = list[IntPath]


def to_int(points: Iterable[Point]) -> IntPath:
    return [[int(round(px * SCALE)), int(round(py * SCALE))] for px, py in points]


def to_float(path: Sequence[Sequence[int]]) -> list[Point]:
    return [(px / SCALE, py / SCALE) for px, py in path]


def _offsetter(tolerance_mm: float | None = None) -> pyclipper.PyclipperOffset:
    tolerance = ARC_TOLERANCE if tolerance_mm is None else tolerance_mm * SCALE
    return pyclipper.PyclipperOffset(miter_limit=2.0, arc_tolerance=tolerance)


def buffer_polylines(polylines: Iterable[tuple[Sequence[Point], float]]) -> Region:
    """Footprint of printed lines: every polyline grown by half its width, unioned."""
    groups: dict[int, list[IntPath]] = {}
    for points, width in polylines:
        path = to_int(points)
        if len(path) < 2:
            continue
        groups.setdefault(int(round(width * SCALE / 2)), []).append(path)
    pieces: Region = []
    for half_width, paths in groups.items():
        offsetter = _offsetter()
        offsetter.AddPaths(paths, pyclipper.JT_ROUND, pyclipper.ET_OPENROUND)
        pieces.extend(offsetter.Execute(half_width))
    return union(pieces)


def union(*regions: Region) -> Region:
    paths = [path for region in regions for path in region if len(path) >= 3]
    if not paths:
        return []
    clipper = pyclipper.Pyclipper()
    clipper.AddPaths(paths, pyclipper.PT_SUBJECT, True)
    return clipper.Execute(pyclipper.CT_UNION, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)


def difference(subject: Region, clip: Region) -> Region:
    if not subject:
        return []
    if not clip:
        return [list(path) for path in subject]
    clipper = pyclipper.Pyclipper()
    clipper.AddPaths(subject, pyclipper.PT_SUBJECT, True)
    clipper.AddPaths(clip, pyclipper.PT_CLIP, True)
    return clipper.Execute(pyclipper.CT_DIFFERENCE, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)


def intersection(subject: Region, clip: Region) -> Region:
    if not subject or not clip:
        return []
    clipper = pyclipper.Pyclipper()
    clipper.AddPaths(subject, pyclipper.PT_SUBJECT, True)
    clipper.AddPaths(clip, pyclipper.PT_CLIP, True)
    return clipper.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)


def fill_holes(region: Region) -> Region:
    """Outer contours only (islands inside holes are covered by their outer contour)."""
    return union([path for path in region if pyclipper.Orientation(path)])


def offset(region: Region, delta_mm: float, *, round_joins: bool = True, tolerance_mm: float | None = None) -> Region:
    if not region:
        return []
    if abs(delta_mm) < 1e-9:
        return [list(path) for path in region]
    offsetter = _offsetter(tolerance_mm)
    offsetter.AddPaths(region, pyclipper.JT_ROUND if round_joins else pyclipper.JT_MITER, pyclipper.ET_CLOSEDPOLYGON)
    return offsetter.Execute(delta_mm * SCALE)


def closing(region: Region, distance_mm: float, tolerance_mm: float | None = None) -> Region:
    """Grow then shrink: merges islands and fills notches narrower than ``2 * distance_mm``."""
    return offset(offset(region, distance_mm, tolerance_mm=tolerance_mm), -distance_mm, tolerance_mm=tolerance_mm)


def area_mm2(region: Region) -> float:
    return sum(pyclipper.Area(path) for path in region) / (SCALE * SCALE)


def bounds_mm(region: Region) -> tuple[float, float, float, float]:
    xs = [px for path in region for px, _ in path]
    ys = [py for path in region for _, py in path]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs) / SCALE, min(ys) / SCALE, max(xs) / SCALE, max(ys) / SCALE)


def centroid_mm(region: Region) -> Point:
    total = 0.0
    cx = cy = 0.0
    for path in region:
        n = len(path)
        for i in range(n):
            x0, y0 = path[i]
            x1, y1 = path[(i + 1) % n]
            cross = x0 * y1 - x1 * y0
            total += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
    if abs(total) < 1e-9:
        min_x, min_y, max_x, max_y = bounds_mm(region)
        return ((min_x + max_x) / 2, (min_y + max_y) / 2)
    return (cx / (3 * total) / SCALE, cy / (3 * total) / SCALE)


def rotate(region: Region, angle_deg: float, center: Point) -> Region:
    angle = math.radians(angle_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    ox, oy = center[0] * SCALE, center[1] * SCALE
    return [
        [
            [int(round(ox + (px - ox) * cos_a - (py - oy) * sin_a)), int(round(oy + (px - ox) * sin_a + (py - oy) * cos_a))]
            for px, py in path
        ]
        for path in region
    ]


def symmetric_under_rotation(region: Region, angles: Sequence[float] = (90.0, 180.0), tolerance: float = 0.03) -> bool:
    """True when rotating the region about its centroid by one of ``angles`` barely changes it."""
    base = area_mm2(region)
    if base <= 0:
        return False
    center = centroid_mm(region)
    for angle in angles:
        turned = rotate(region, angle, center)
        changed = area_mm2(difference(region, turned)) + area_mm2(difference(turned, region))
        if changed / base < tolerance:
            return True
    return False


def outer_and_holes(region: Region) -> list[IntPath]:
    """All closed contours of a region (outer and holes), for printing as perimeters."""
    return [list(path) for path in region if len(path) >= 3]


def simplify(region: Region, distance_mm: float = 0.01) -> Region:
    return [path for path in pyclipper.CleanPolygons(region, distance_mm * SCALE) if len(path) >= 3]


def contains_point(region: Region, point: Point) -> bool:
    """Non-zero winding test over the whole region."""
    p = [int(round(point[0] * SCALE)), int(round(point[1] * SCALE))]
    winding = 0
    for path in region:
        inside = pyclipper.PointInPolygon(p, path)
        if inside == -1:
            return True
        if inside:
            winding += 1 if pyclipper.Orientation(path) else -1
    return winding != 0


def polygon_from_config(value: str | None) -> Region:
    """Parse Bambu ``printable_area`` / ``bed_exclude_area`` values like ``0x0,256x0,256x256,0x256``."""
    if not value:
        return []
    points: list[Point] = []
    for token in value.replace(";", ",").split(","):
        token = token.strip().strip('"')
        if "x" not in token:
            continue
        sx, sy = token.split("x", 1)
        try:
            points.append((float(sx), float(sy)))
        except ValueError:
            continue
    if len(points) < 3:
        return []
    path = to_int(points)
    if not pyclipper.Orientation(path):
        path.reverse()
    return union([path])


def clip_polylines(polylines: Sequence[Sequence[Point]], region: Region) -> list[list[Point]]:
    """The parts of open polylines that lie inside ``region``."""
    paths = [to_int(points) for points in polylines if len(points) >= 2]
    if not paths or not region:
        return []
    clipper = pyclipper.Pyclipper()
    for path in paths:
        clipper.AddPath(path, pyclipper.PT_SUBJECT, False)
    clipper.AddPaths(region, pyclipper.PT_CLIP, True)
    tree = clipper.Execute2(pyclipper.CT_INTERSECTION, pyclipper.PFT_NONZERO, pyclipper.PFT_NONZERO)
    return [to_float(path) for path in pyclipper.OpenPathsFromPolyTree(tree) if len(path) >= 2]


def polyline_length(points: Sequence[Point]) -> float:
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))
