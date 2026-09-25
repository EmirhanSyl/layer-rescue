from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from layer_rescue.core import (
    ResumeError,
    ResumeOptions,
    ZReferenceMode,
    analyze_gcode,
    build_resume_gcode,
    rewrite_gcode_file,
)


def sample_gcode(*, printer: str = "Bambu Lab P1S", second_tool: bool = False, absolute_e: bool = False) -> str:
    tool_change = "\nM620 S1A\nT1\nM621 S1A" if second_tool else ""
    e_mode = "M82" if absolute_e else "M83"
    return f"""; HEADER_BLOCK_START
; BambuStudio test
; total layer number: 4
; HEADER_BLOCK_END
; CONFIG_BLOCK_START
; printer_model = {printer}
; filament_type = PLA
; print_sequence = By layer
; spiral_mode = 0
; nozzle_temperature = 220
; textured_plate_temp = 55
; CONFIG_BLOCK_END
; EXECUTABLE_BLOCK_START
M201 X20000 Y20000 Z500 E5000
M203 X500 Y500 Z20 E30
M205 X9 Y9 Z3 E2.5
M140 S55
M104 S220
G90
{e_mode}
M220 S100
M221 S100
G28 X
M620 M
M620 S0A
M190 S55
M109 S220
T0
M621 S0A
M620.1 E F150 T250
T1000
M109 S220
M106 S128
; CHANGE_LAYER
; Z_HEIGHT: 0.2
; LAYER_HEIGHT: 0.2
G1 X10 Y10 Z0.2 F12000
; layer num/total_layer_count: 1/4
G1 X20 E1
; CHANGE_LAYER
; Z_HEIGHT: 0.4
; LAYER_HEIGHT: 0.2
G1 Z0.4
; layer num/total_layer_count: 2/4
G1 X30 E1{tool_change}
; CHANGE_LAYER
; Z_HEIGHT: 0.6
; LAYER_HEIGHT: 0.2
G1 Z0.6
; layer num/total_layer_count: 3/4
G1 X40 E1
; CHANGE_LAYER
; Z_HEIGHT: 0.8
; LAYER_HEIGHT: 0.2
G1 Z0.8
; layer num/total_layer_count: 4/4
G1 X50 E1
M104 S0
M140 S0
; EXECUTABLE_BLOCK_END
"""


class AnalyzeTests(unittest.TestCase):
    def test_detects_layers_and_z(self) -> None:
        analysis = analyze_gcode(sample_gcode())
        self.assertEqual(analysis.printer_model, "Bambu Lab P1S")
        self.assertEqual(analysis.total_layers, 4)
        self.assertEqual([layer.number for layer in analysis.layers], [1, 2, 3, 4])
        self.assertEqual(analysis.layer(3).z, 0.6)


class BuildTests(unittest.TestCase):
    def test_retains_selected_layer_through_end(self) -> None:
        output, report = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3))
        self.assertEqual(report.start_layer, 3)
        self.assertEqual(report.retained_layers, 2)
        self.assertNotIn("layer num/total_layer_count: 2/4", output)
        self.assertIn("layer num/total_layer_count: 3/4", output)
        self.assertIn("layer num/total_layer_count: 4/4", output)

    def test_never_emits_z_home_or_bed_leveling(self) -> None:
        output, _ = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3))
        active = [line.split(";", 1)[0].strip() for line in output.splitlines()]
        self.assertIn("G28 X", active)
        self.assertFalse(any(line == "G28" or line.startswith("G28 Z") for line in active))
        self.assertFalse(any(line.startswith("G29") for line in active))

    def test_retained_mode_does_not_rewrite_z_coordinate(self) -> None:
        output, report = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3))
        active = [line.split(";", 1)[0].strip() for line in output.splitlines()]
        self.assertEqual(report.z_reference_mode, ZReferenceMode.RETAINED)
        self.assertIsNone(report.reference_z)
        self.assertFalse(any(line.startswith("G92 Z") for line in active))

    def test_manual_mode_assigns_previous_layer_z_before_any_z_move(self) -> None:
        output, report = build_resume_gcode(
            sample_gcode(),
            ResumeOptions(start_layer=3, z_reference_mode=ZReferenceMode.MANUAL),
        )
        preamble = output.split("; LAYER_RESCUE_BLOCK_END", 1)[0]
        active = [line.split(";", 1)[0].strip() for line in preamble.splitlines()]
        assignment_index = active.index("G92 Z0.4")
        first_z_move = next(
            index
            for index, line in enumerate(active)
            if line.startswith(("G0 Z", "G1 Z"))
        )
        self.assertEqual(report.z_reference_mode, ZReferenceMode.MANUAL)
        self.assertEqual(report.reference_z, 0.4)
        self.assertLess(assignment_index, first_z_move)
        self.assertIn("G28 X", active)
        self.assertFalse(any(line == "G28" or line.startswith("G28 Z") for line in active))

    def test_manual_mode_emits_only_relative_z_moves(self) -> None:
        output, _ = build_resume_gcode(
            sample_gcode(),
            ResumeOptions(start_layer=3, z_reference_mode=ZReferenceMode.MANUAL),
        )
        body = output.split("; EXECUTABLE_BLOCK_START", 1)[1]
        positioning = "G90"
        for raw in body.splitlines():
            code = raw.split(";", 1)[0].strip()
            if code in {"G90", "G91"}:
                positioning = code
            elif code.startswith(("G0 ", "G1 ", "G2 ", "G3 ")) and " Z" in f" {code}":
                self.assertEqual(positioning, "G91", code)
        self.assertIn("M221 X0 Y0 Z0", output)

    def test_manual_mode_z_path_does_not_depend_on_firmware_z(self) -> None:
        output, _ = build_resume_gcode(
            sample_gcode(),
            ResumeOptions(start_layer=3, z_reference_mode=ZReferenceMode.MANUAL),
        )
        body = output.split("; LAYER_RESCUE_BLOCK_START", 1)[1]
        # Simulate firmware that ignores G92 Z and believes Z=0 at the aligned surface (physical 0.4).
        physical, relative, extrusion_z = 0.4, False, []
        for raw in body.splitlines():
            code = raw.split(";", 1)[0].strip()
            if code == "G91":
                relative = True
            elif code == "G90":
                relative = False
            elif code.startswith(("G0", "G1", "G2", "G3")):
                parts = {token[0]: float(token[1:]) for token in code.split()[1:] if token[1:]}
                if "Z" in parts:
                    self.assertTrue(relative, code)
                    physical += parts["Z"]
                if parts.get("E", 0) > 0 and "X" in parts:
                    extrusion_z.append(round(physical, 4))
        self.assertEqual(extrusion_z, [0.6, 0.8])

    def test_manual_mode_rejects_conditional_block_that_changes_z(self) -> None:
        source = sample_gcode().replace(
            "G1 X40 E1\n", "G1 X40 E1\nM622 J1\nG1 Z5\nM623\n", 1
        )
        with self.assertRaisesRegex(ResumeError, "conditional firmware block"):
            build_resume_gcode(source, ResumeOptions(start_layer=3, z_reference_mode=ZReferenceMode.MANUAL))

    def test_manual_mode_accepts_conditional_block_that_restores_z(self) -> None:
        source = sample_gcode().replace(
            "G1 X40 E1\n", "G1 X40 E1\nM622 J1\nG1 Z5\nG1 Z0.6\nM623\n", 1
        )
        build_resume_gcode(source, ResumeOptions(start_layer=3, z_reference_mode=ZReferenceMode.MANUAL))

    def test_manual_mode_rejects_extruding_z_move(self) -> None:
        source = sample_gcode().replace("G1 X40 E1\n", "G1 X40 Z0.7 E1\n", 1)
        with self.assertRaisesRegex(ResumeError, "extruding move that also changes Z"):
            build_resume_gcode(source, ResumeOptions(start_layer=3, z_reference_mode=ZReferenceMode.MANUAL))

    def test_retained_mode_keeps_absolute_z(self) -> None:
        output, _ = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3))
        self.assertIn("G1 Z0.8\n", output)
        self.assertNotIn("M221 X0 Y0 Z0", output)

    def test_manual_mode_requires_corexy_home(self) -> None:
        with self.assertRaisesRegex(ResumeError, "requires CoreXY homing"):
            build_resume_gcode(
                sample_gcode(),
                ResumeOptions(
                    start_layer=3,
                    z_reference_mode=ZReferenceMode.MANUAL,
                    home_corexy=False,
                ),
            )

    def test_reasserts_overridden_temperature_after_t1000(self) -> None:
        output, report = build_resume_gcode(
            sample_gcode(),
            ResumeOptions(start_layer=3, nozzle_temperature=225),
        )
        preamble = output.split("; LAYER_RESCUE_BLOCK_END", 1)[0]
        self.assertEqual(report.nozzle_temperature, 225)
        self.assertGreater(preamble.rfind("M109 S225"), preamble.rfind("T1000"))

    def test_relative_extrusion_is_reselected_after_every_g90(self) -> None:
        # Bambu firmware switches E to absolute on G90; M83 must follow the last G90.
        output, _ = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3))
        preamble = output.split("; LAYER_RESCUE_BLOCK_END", 1)[0]
        active = [line.split(";", 1)[0].strip() for line in preamble.splitlines()]
        active = [line for line in active if line]
        last_g90 = max(index for index, line in enumerate(active) if line == "G90")
        last_m83 = max(index for index, line in enumerate(active) if line == "M83")
        self.assertGreater(last_m83, last_g90)
        first_extrusion = next(
            index for index, line in enumerate(active) if line.startswith("G1") and " E" in f" {line}"
        )
        self.assertGreater(first_extrusion, last_g90)
        self.assertLess(
            max(index for index, line in enumerate(active[:first_extrusion]) if line == "M83"),
            first_extrusion,
        )

    def test_purges_before_returning_to_part(self) -> None:
        output, _ = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3))
        preamble = output.split("; LAYER_RESCUE_BLOCK_END", 1)[0]
        self.assertIn("G1 E30 F200", preamble)
        self.assertLess(preamble.find("G1 E30 F200"), preamble.find("G1 Z0.6"))

    def test_purge_can_be_disabled(self) -> None:
        output, _ = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3, purge_length_mm=0))
        preamble = output.split("; LAYER_RESCUE_BLOCK_END", 1)[0]
        self.assertNotIn("F200", preamble)

    def test_travels_to_layer_start_before_descending(self) -> None:
        source = sample_gcode().replace("G1 Z0.6\n", "G1 X12 Y34 Z0.6\n", 1)
        output, _ = build_resume_gcode(source, ResumeOptions(start_layer=3))
        preamble = output.split("; LAYER_RESCUE_BLOCK_END", 1)[0]
        travel = preamble.find("G1 X12 Y34 F12000")
        self.assertGreaterEqual(travel, 0)
        self.assertLess(travel, preamble.rfind("G1 Z0.6"))

    def test_g90_after_m83_in_source_counts_as_absolute(self) -> None:
        source = sample_gcode().replace("M106 S128\n", "M106 S128\nG90\n", 1)
        with self.assertRaisesRegex(ResumeError, "relative extrusion"):
            build_resume_gcode(source, ResumeOptions(start_layer=3))

    def test_rejects_absolute_extrusion(self) -> None:
        with self.assertRaisesRegex(ResumeError, "relative extrusion"):
            build_resume_gcode(sample_gcode(absolute_e=True), ResumeOptions(start_layer=3))

    def test_rejects_multi_filament(self) -> None:
        with self.assertRaisesRegex(ResumeError, "multi-filament"):
            build_resume_gcode(sample_gcode(second_tool=True), ResumeOptions(start_layer=3))

    def test_rejects_other_printer_for_mvp(self) -> None:
        with self.assertRaisesRegex(ResumeError, "only Bambu Lab P1S"):
            build_resume_gcode(sample_gcode(printer="Bambu Lab X1C"), ResumeOptions(start_layer=3))


class RewriteTests(unittest.TestCase):
    def test_atomic_rewrite_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "job.gcode"
            original = sample_gcode()
            path.write_text(original, encoding="utf-8")
            report = rewrite_gcode_file(path, ResumeOptions(start_layer=3))
            self.assertIsNotNone(report.backup_path)
            self.assertEqual(report.backup_path.read_text(encoding="utf-8"), original)
            self.assertIn("; LAYER_RESCUE_BLOCK_START", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
