from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import ResumeError, ResumeOptions, ZReferenceMode, analyze_gcode, rewrite_gcode_file


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="layer-rescue",
        description="Create conservative layer-resume G-code for interrupted Bambu Lab P1S prints.",
    )
    parser.add_argument("gcode", nargs="?", help="G-code path; Bambu Studio appends this automatically")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--start-layer", type=int, help="first layer to print")
    selection.add_argument("--last-layer", type=int, help="last successfully printed layer")
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
    parser.add_argument("--no-home-corexy", action="store_true", help="do not emit the P1S G28 X CoreXY home")
    parser.add_argument("--no-backup", action="store_true", help="do not create a sibling .bak file")
    parser.add_argument("--nozzle-temp", type=int, help="override detected nozzle temperature")
    parser.add_argument("--bed-temp", type=int, help="override detected bed temperature")
    parser.add_argument("--z-lift", type=float, default=2.0, help="relative safety lift before CoreXY motion (default: 2.0)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _analysis_json(path: Path) -> str:
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
        },
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.gcode:
        _parser().error("a G-code path is required")
    path = Path(args.gcode).expanduser().resolve()

    try:
        if args.analyze:
            print(_analysis_json(path))
            return 0

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
