from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import ResumeError, ResumeOptions, ZReferenceMode, analyze_gcode, rewrite_gcode_file
from .fileio import rewrite_with


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="layer-rescue",
        description="Create conservative layer-resume G-code for interrupted Bambu Lab P1S prints.",
    )
    parser.add_argument("gcode", nargs="?", help="G-code path; Bambu Studio appends this automatically")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--start-layer", type=int, help="first layer to print")
    selection.add_argument("--last-layer", type=int, help="last successfully printed layer")
    selection.add_argument(
        "--part-height",
        type=float,
        help="insert mode: measured height (mm) of a loose part to seat in a printed wall and print on top of",
    )
    selection.add_argument("--part-layer", type=int, help="insert mode: last source layer the loose part contains")
    parser.add_argument("--gui", action="store_true", help="open the graphical layer selector")
    parser.add_argument("--analyze", action="store_true", help="print source information without modifying it")
    parser.add_argument(
        "--z-mode",
        choices=[mode.value for mode in ZReferenceMode],
        help="Z reference: retained after uninterrupted power, or manual after a restart",
    )
    parser.add_argument(
        "--confirm-manual-z-aligned",
        action="store_true",
        help="confirm that the nozzle was aligned to touch the last successful layer",
    )
    parser.add_argument(
        "--assume-z-known",
        action="store_true",
        help="deprecated alias for --z-mode retained",
    )
    parser.add_argument(
        "--allow-untested",
        action="store_true",
        help="accept the risks and continue with a printer or multi-filament job Layer Rescue has not been tested on",
    )
    parser.add_argument("--no-home-corexy", action="store_true", help="do not emit the P1S G28 X CoreXY home")
    parser.add_argument("--no-backup", action="store_true", help="do not create a sibling .bak file")
    parser.add_argument("--nozzle-temp", type=int, help="override detected nozzle temperature")
    parser.add_argument("--bed-temp", type=int, help="override detected bed temperature")
    parser.add_argument("--z-lift", type=float, default=2.0, help="relative safety lift before CoreXY motion (default: 2.0)")
    insert = parser.add_argument_group("insert mode (a loose part seated in a printed wall)")
    insert.add_argument("--wall-height", type=float, help="holding wall height in mm (default: recommended)")
    insert.add_argument("--clearance", type=float, default=0.25, help="gap between part and wall in mm (default: 0.25)")
    insert.add_argument("--wall-lines", type=int, default=4, help="wall thickness in lines (default: 4)")
    insert.add_argument("--brim", type=float, default=5.0, help="brim width around the wall in mm (default: 5)")
    insert.add_argument("--no-chamfer", action="store_true", help="no lead-in chamfer at the wall rim")
    insert.add_argument("--z-fine", type=float, default=0.0, help="added to the part height; negative squishes more")
    insert.add_argument("--standby-temp", type=int, default=140, help="nozzle °C while paused, 0 = keep (default: 140)")
    insert.add_argument("--adhesion-layers", type=int, default=2, help="hotter/slower/no-fan layers on the part (default: 2)")
    insert.add_argument(
        "--confirm-attended",
        action="store_true",
        help="confirm you will seat the part when the printer pauses and watch the first layers",
    )
    insert.add_argument(
        "--no-reprint-supports",
        action="store_true",
        help="do not print the supports below the part height before the pause",
    )
    insert.add_argument("--preview-svg", help="insert mode: also write a top-view SVG of the wall to this path")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _analysis_json(path: Path) -> str:
    from .machine_state import untested_setup

    analysis = analyze_gcode(path.read_text(encoding="utf-8", errors="replace"))
    return json.dumps(
        {
            "file": str(path),
            "printer_model": analysis.printer_model,
            "filament_type": analysis.filament_type,
            "first_layer": analysis.first_layer,
            "last_layer": analysis.last_layer,
            "total_layers": analysis.total_layers,
            "first_z": analysis.layers[0].z,
            "last_z": analysis.layers[-1].z,
            "sha256": analysis.source_sha256,
            "warnings": analysis.warnings,
            "untested_setup": untested_setup(analysis),
        },
        indent=2,
    )


def _run_insert(args: argparse.Namespace, path: Path) -> int:
    from .insert import InsertOptions, build_insert_gcode, plan_insert

    if not args.confirm_attended:
        raise ResumeError(
            "Insert mode requires --confirm-attended: you must seat the part when the printer pauses "
            "and watch the first layers."
        )
    part_height = args.part_height
    if part_height is None:
        analysis = analyze_gcode(path.read_text(encoding="utf-8", errors="replace"))
        part_height = analysis.layer(args.part_layer).z
    options = InsertOptions(
        part_height_mm=part_height,
        wall_height_mm=args.wall_height,
        clearance_mm=args.clearance,
        wall_lines=args.wall_lines,
        brim_mm=args.brim,
        chamfer=not args.no_chamfer,
        z_fine_mm=args.z_fine,
        standby_temperature=args.standby_temp,
        adhesion_layers=args.adhesion_layers,
        reprint_supports=not args.no_reprint_supports,
        allow_untested=args.allow_untested,
        z_lift_mm=args.z_lift,
        nozzle_temperature=args.nozzle_temp,
        bed_temperature=args.bed_temp,
    )
    if args.preview_svg:
        from .preview import plan_svg

        plan = plan_insert(path.read_text(encoding="utf-8", errors="replace"), options)
        Path(args.preview_svg).write_text(plan_svg(plan), encoding="utf-8")
    report, backup = rewrite_with(
        path, lambda text: build_insert_gcode(text, options), create_backup=not args.no_backup
    )
    print(
        json.dumps(
            {
                "status": "converted",
                "mode": "insert",
                "part_height_mm": report.part_height_mm,
                "part_layer": report.part_layer,
                "resume_layer": report.resume_layer,
                "total_layers": report.total_layers,
                "z_offset_mm": report.z_offset_mm,
                "first_layer_thickness_mm": report.first_layer_thickness_mm,
                "wall_layers": report.wall_layers,
                "wall_top_z": report.wall_top_z,
                "park_z": report.park_z,
                "wall_filament_mm": report.wall_filament_mm,
                "support_layers": report.support_layers,
                "last_printed_layer": report.last_printed_layer,
                "nozzle_temperature": report.nozzle_temperature,
                "bed_temperature": report.bed_temperature,
                "backup": str(backup) if backup else None,
                "output_sha256": report.output_sha256,
                "warnings": report.warnings,
            },
            indent=2,
        )
    )
    return 0


def post_processing_command() -> str:
    """The command to paste into Bambu Studio's Post-processing Scripts field."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m layer_rescue'


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.gcode:
        if getattr(sys, "frozen", False):
            # Opened directly (double-click) instead of from Bambu Studio: explain the setup.
            from .gui import show_setup_info

            return show_setup_info(post_processing_command())
        _parser().error("a G-code path is required")
    path = Path(args.gcode).expanduser().resolve()

    try:
        if args.analyze:
            print(_analysis_json(path))
            return 0

        if args.part_height is not None or args.part_layer is not None:
            return _run_insert(args, path)

        if args.gui or (args.start_layer is None and args.last_layer is None):
            from .gui import launch

            return launch(path)

        if args.assume_z_known and args.z_mode not in {None, ZReferenceMode.RETAINED.value}:
            raise ResumeError(
                "--assume-z-known is an alias for --z-mode retained and cannot be combined with manual mode."
            )
        z_mode_value = args.z_mode or (ZReferenceMode.RETAINED.value if args.assume_z_known else None)
        if z_mode_value is None:
            raise ResumeError("Batch conversion requires --z-mode retained or --z-mode manual.")
        z_mode = ZReferenceMode(z_mode_value)
        if z_mode is ZReferenceMode.MANUAL and not args.confirm_manual_z_aligned:
            raise ResumeError(
                "Manual mode requires --confirm-manual-z-aligned after the nozzle touches the last successful layer."
            )

        start_layer = args.start_layer if args.start_layer is not None else args.last_layer + 1
        report = rewrite_gcode_file(
            path,
            ResumeOptions(
                start_layer=start_layer,
                z_reference_mode=z_mode,
                home_corexy=not args.no_home_corexy,
                z_lift_mm=args.z_lift,
                nozzle_temperature=args.nozzle_temp,
                bed_temperature=args.bed_temp,
                allow_untested=args.allow_untested,
            ),
            create_backup=not args.no_backup,
        )
        print(
            json.dumps(
                {
                    "status": "converted",
                    "start_layer": report.start_layer,
                    "total_layers": report.total_layers,
                    "start_z": report.start_z,
                    "nozzle_temperature": report.nozzle_temperature,
                    "bed_temperature": report.bed_temperature,
                    "z_reference_mode": report.z_reference_mode.value,
                    "reference_z": report.reference_z,
                    "backup": str(report.backup_path) if report.backup_path else None,
                    "output_sha256": report.output_sha256,
                    "warnings": report.warnings,
                },
                indent=2,
            )
        )
        return 0
    except (OSError, ResumeError) as exc:
        print(f"layer-rescue: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
