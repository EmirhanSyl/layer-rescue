"""A tiny stand-in for Bambu Studio: writes P1S-style G-code for simple prismatic models.

The output mimics the structure Layer Rescue relies on (header/config/executable blocks, layer change
frames with timelapse blocks, object labels, FEATURE/LINE_WIDTH comments, relative extrusion, optional
arc-fitted walls). It is not a slicer: walls are the model outline and infill is a few straight lines.
"""

from __future__ import annotations

import math

LINE_WIDTH = 0.42
LAYER_HEIGHT = 0.2
E_PER_MM = 0.0333


def _square(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    h = size / 2
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def _l_shape(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    h = size / 2
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy), (cx, cy), (cx, cy + h), (cx - h, cy + h)]


def _inset(points: list[tuple[float, float]], d: float) -> list[tuple[float, float]]:
    """Crude inset toward the centroid; good enough for convex-ish test outlines."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    out = []
    for x, y in points:
        dx, dy = cx - x, cy - y
        length = math.hypot(dx, dy) or 1.0
        out.append((x + dx / length * d, y + dy / length * d))
    return out


def _loop(points: list[tuple[float, float]]) -> list[str]:
    lines = [f"G1 X{points[0][0]:.3f} Y{points[0][1]:.3f} F30000"]
    lines.append("G1 F3000")
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        e = math.hypot(bx - ax, by - ay) * E_PER_MM
        lines.append(f"G1 X{bx:.3f} Y{by:.3f} E{e:.5f}")
    return lines


def _circle_arc(cx: float, cy: float, r: float) -> list[str]:
    """A full circle as two G3 half arcs, like Bambu's arc fitting."""
    e = math.pi * r * E_PER_MM
    return [
        f"G1 X{cx + r:.3f} Y{cy:.3f} F30000",
        "G1 F3000",
        f"G3 X{cx - r:.3f} Y{cy:.3f} I{-r:.3f} J0 E{e:.5f}",
        f"G3 X{cx + r:.3f} Y{cy:.3f} I{r:.3f} J0 E{e:.5f}",
    ]


def bambu_like_gcode(
    *,
    shape: str = "square",
    part_size: float = 20.0,
    part_height: float = 10.0,
    addition_size: float = 10.0,
    addition_height: float = 4.0,
    center: tuple[float, float] = (128.0, 128.0),
    objects: int = 1,
    prime_tower: bool = False,
    hollow: bool = False,
    support_at: tuple[float, float] | None = None,
    support_top: float | None = None,
    printer: str = "Bambu Lab P1S",
    extra_config: dict[str, str] | None = None,
) -> str:
    cx, cy = center
    total_height = part_height + addition_height
    n_layers = int(round(total_height / LAYER_HEIGHT))
    config = {
        "printer_model": printer,
        "filament_type": "PLA",
        "print_sequence": "by layer",
        "spiral_mode": "0",
        "nozzle_diameter": "0.4",
        "nozzle_temperature": "220",
        "nozzle_temperature_range_high": "240",
        "textured_plate_temp": "55",
        "layer_height": "0.2",
        "initial_layer_print_height": "0.2",
        "line_width": "0.42",
        "outer_wall_line_width": "0.42",
        "initial_layer_line_width": "0.5",
        "filament_diameter": "1.75",
        "filament_flow_ratio": "0.98",
        "outer_wall_speed": "200",
        "initial_layer_speed": "50",
        "travel_speed": "500",
        "retraction_length": "0.8",
        "retraction_speed": "30",
        "z_hop": "0.4",
        "slow_down_layer_time": "4",
        "slow_down_min_speed": "20",
        "printable_area": "0x0,256x0,256x256,0x256",
        "printable_height": "250",
        "bed_exclude_area": "0x0,18x0,18x28,0x28",
        "machine_pause_gcode": "M400 U1",
    }
    config.update(extra_config or {})
    out = [
        "; HEADER_BLOCK_START",
        "; BambuStudio 02.02.00.85",
        f"; total layer number: {n_layers}",
        "; HEADER_BLOCK_END",
        "",
        "; CONFIG_BLOCK_START",
        *[f"; {key} = {value}" for key, value in config.items()],
        "; CONFIG_BLOCK_END",
        "",
        "; EXECUTABLE_BLOCK_START",
        "M73 P0 R20",
        "M201 X20000 Y20000 Z500 E5000",
        "M203 X500 Y500 Z20 E30",
        "M204 P20000 R5000 T20000",
        "M205 X9.00 Y9.00 Z3.00 E2.50",
        "M106 P3 S0",
        ";===== machine: P1S ========================",
        "M140 S55",
        "M104 S220",
        "G90",
        "M83",
        "M220 S100 ;Reset Feedrate",
        "M221 S100 ;Reset Flowrate",
        "G28",
        "G29 ; bed leveling",
        "M190 S55",
        "M109 S220",
        "M975 S1",
        "M620 M",
        "M620 S0A",
        "T0",
        "M621 S0A",
        "M620.1 E F523.843 T240",
        "T1000",
        "M109 S220",
        ";===== stock P1S start G-code extrudes after G90 (no M83 in between) ===",
        "G90",
        "G1 X67 Y1 F12000",
        "G1 E10 F300",
        "M83",
        ";===== prime line ===",
        "G1 X18 Y1 F18000",
        "G1 Z0.3",
        "G1 X240 Y1 E8 F3000",
        "G1 E-.2 F1800",
        "M1002 set_gcode_claim_speed_level : 5",
        "M106 S0",
    ]

    object_ids = [101 + 3 * i for i in range(objects)]
    progress_every = max(1, n_layers // 20)
    previous_z = 0.0
    for n in range(1, n_layers + 1):
        z = round(n * LAYER_HEIGHT, 4)
        in_part = z <= part_height + 1e-6
        size = part_size if in_part else addition_size
        out += [
            "; CHANGE_LAYER",
            f"; Z_HEIGHT: {z:g}",
            f"; LAYER_HEIGHT: {z - previous_z:g}",
            "G1 E-.8 F1800",
            f"; layer num/total_layer_count: {n}/{n_layers}",
            "; update layer progress",
            f"M73 L{n}",
            f"M991 S0 P{n - 1} ;notify layer change",
        ]
        if n % progress_every == 0:
            out.append(f"M73 P{int(n / n_layers * 100)} R{max(0, 20 - n // 5)}")
        if n == 3:
            out.append("M106 S255")
        out += [
            "; SKIPPABLE_START",
            "; SKIPTYPE: timelapse",
            "M622.1 S1 ; for prev firmware, default turned on",
            "M1002 judge_flag timelapse_record_flag",
            "M622 J1",
            f"G1 Z{z + 0.4:g} F900",
            "M971 S11 C10 O0",
            "M623",
            "; SKIPPABLE_END",
        ]
        if n == 1:
            out.append(f"G1 Z{z:g} F900")
        else:
            out.append(f"G1 X{cx:.3f} Y{cy:.3f} F30000")
            out.append(f"G1 Z{z:g}")
        for index, object_id in enumerate(object_ids):
            ox = cx + index * (part_size + 15)
            out += [
                f"; start printing object, unique label id: {object_id}",
                "M624 AQAAAAAAAAA=",
                "G1 E.8 F1800",
                "; FEATURE: Outer wall",
                f"; LINE_WIDTH: {0.5 if n == 1 else LINE_WIDTH}",
            ]
            if shape == "circle":
                out += _circle_arc(ox, cy, size / 2 - LINE_WIDTH / 2)
                outline = [
                    (ox + (size / 2) * math.cos(a / 16 * math.pi), cy + (size / 2) * math.sin(a / 16 * math.pi))
                    for a in range(32)
                ]
            else:
                make = _l_shape if (shape == "L" and in_part) else _square
                outline = make(ox, cy, size - LINE_WIDTH)
                out += _loop(outline)
            out += ["; FEATURE: Inner wall", f"; LINE_WIDTH: {LINE_WIDTH}"]
            out += _loop(_inset(outline, LINE_WIDTH * 1.5)) if shape != "circle" else _circle_arc(
                ox, cy, size / 2 - LINE_WIDTH * 1.5
            )
            if not hollow or not in_part:
                out += ["; FEATURE: Sparse infill", "; LINE_WIDTH: 0.45"]
                half = size / 2 - 1.5
                for k in range(-2, 3):
                    out.append(f"G1 X{ox - half:.3f} Y{cy + k * half / 3:.3f} F30000")
                    out.append(f"G1 X{ox + half:.3f} Y{cy + k * half / 3:.3f} E{2 * half * E_PER_MM:.5f} F6000")
            if support_at is not None and z <= (support_top if support_top is not None else total_height) + 1e-6:
                # A 3 mm square support column (tree trunk stand-in), inside the object block like Bambu.
                out += ["; FEATURE: Support", f"; LINE_WIDTH: {LINE_WIDTH}"]
                out += _loop(_square(support_at[0], support_at[1], 3.0))
            out += [
                "; WIPE_START",
                f"G1 X{ox:.3f} Y{cy:.3f} E-.4 F24000",
                "; WIPE_END",
                f"; stop printing object, unique label id: {object_id}",
                "M625",
            ]
        if prime_tower:
            out += ["; FEATURE: Prime tower", "G1 X230 Y230 F30000", "G1 X240 Y230 E.5"]
        previous_z = z

    out += [
        "; EXECUTABLE_BLOCK_END",
        "M400",
        "G92 E0",
        "G1 E-0.8 F1800",
        f"G1 Z{total_height + 0.5:g} F900",
        "G1 X65 Y245 F12000",
        "G1 Y265 F3000",
        "M140 S0",
        "M104 S0",
        "M106 S0",
        "M84",
    ]
    return "\n".join(out) + "\n"
