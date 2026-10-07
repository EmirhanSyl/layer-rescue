"""Build an insert-mode G-code for one benchmark run, with every InsertOptions field exposed.

The layer-rescue CLI does not expose the adhesion-layer recipe (temperature boost, speed,
part fan), which the T4 parameter sweep changes. This wrapper calls the same library
functions as the CLI and writes the result to a NEW file, so the sliced source stays as is.

Example (T4 run 5: +20 °C, 100 % speed, fan on):
    python benchmark/run_insert.py M2.gcode -o T4-r05-PLA-01.gcode --part-layer 200 \
        --temp-boost 20 --speed 100 --fan-on
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from layer_rescue.gcode import analyze_gcode
from layer_rescue.insert import InsertOptions, build_insert_gcode


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("gcode", type=Path, help="sliced source G-code (left unchanged)")
    p.add_argument("-o", "--output", type=Path, required=True, help="output G-code")
    h = p.add_mutually_exclusive_group(required=True)
    h.add_argument("--part-layer", type=int, help="last source layer the loose part contains")
    h.add_argument("--part-height", type=float, help="part height in mm")
    p.add_argument("--clearance", type=float, default=0.25)
    p.add_argument("--wall-height", type=float, help="default: recommended")
    p.add_argument("--wall-lines", type=int, default=4)
    p.add_argument("--brim", type=float, default=5.0)
    p.add_argument("--z-fine", type=float, default=0.0)
    p.add_argument("--standby-temp", type=int, default=140)
    p.add_argument("--adhesion-layers", type=int, default=2)
    p.add_argument("--temp-boost", type=int, default=10, help="adhesion layers: °C added (0-30)")
    p.add_argument("--speed", type=int, default=50, help="adhesion layers: speed in %% (20-100)")
    fan = p.add_mutually_exclusive_group()
    fan.add_argument("--fan-on", action="store_true", help="keep the part fan as sliced on adhesion layers")
    fan.add_argument("--fan-off", action="store_true", help="part fan off on adhesion layers (default)")
    p.add_argument("--no-reprint-supports", action="store_true")
    p.add_argument("--allow-untested", action="store_true")
    a = p.parse_args(argv)

    text = a.gcode.read_text(encoding="utf-8", errors="replace")
    height = a.part_height
    if height is None:
        height = analyze_gcode(text).layer(a.part_layer).z
    options = InsertOptions(
        part_height_mm=height,
        wall_height_mm=a.wall_height,
        clearance_mm=a.clearance,
        wall_lines=a.wall_lines,
        brim_mm=a.brim,
        z_fine_mm=a.z_fine,
        standby_temperature=a.standby_temp,
        adhesion_layers=a.adhesion_layers,
        adhesion_temp_boost=a.temp_boost,
        adhesion_speed_percent=a.speed,
        adhesion_fan_off=not a.fan_on,
        reprint_supports=not a.no_reprint_supports,
        allow_untested=a.allow_untested,
    )
    out, report = build_insert_gcode(text, options)
    a.output.write_text(out, encoding="utf-8")
    print(json.dumps({
        "output": str(a.output),
        "part_height_mm": report.part_height_mm,
        "part_layer": report.part_layer,
        "resume_layer": report.resume_layer,
        "wall_height_mm": report.wall_height_mm,
        "nozzle_temperature": report.nozzle_temperature,
        "bed_temperature": report.bed_temperature,
        "wall_filament_mm": round(report.wall_filament_mm, 1),
        "support_layers": report.support_layers,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
