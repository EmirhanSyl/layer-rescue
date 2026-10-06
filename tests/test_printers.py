from __future__ import annotations

import math
import re
import unittest

from layer_rescue.gcode import ResumeError, analyze_gcode
from layer_rescue.machine_state import untested_setup
from layer_rescue.printers import H2, P1, park_position, printer_profile, reachable_bounds
from layer_rescue.resume import ResumeOptions, ZReferenceMode, build_resume_gcode
from test_core import sample_gcode


def h2_gcode(*, model: str = "Bambu Lab H2C", hotend: bool = True) -> str:
    """A small H2C-style job: two extruders, 0.2 mm nozzles, the filament on extruder 2 (physical 0)."""
    select = "M620 S0A H1\nM109 S220 T0\nT0 H1\nM621 S0A" if hotend else "M620 S0A\nM109 S220 T0\nT0\nM621 S0A"
    return f"""; HEADER_BLOCK_START
; BambuStudio 02.08.02.61
; total layer number: 4
; HEADER_BLOCK_END
; CONFIG_BLOCK_START
; printer_model = {model}
; filament_type = PLA
; print_sequence = By layer
; spiral_mode = 0
; nozzle_diameter = 0.2,0.2
; nozzle_temperature = 220
; hot_plate_temp = 55
; filament_diameter = 1.75
; filament_max_volumetric_speed = 2
; filament_map = 2
; physical_extruder_map = 1,0
; retraction_length = 0.4,0.4
; printable_area = 0x0,330x0,330x320,0x320
; extruder_printable_area = 0x0,325x0,325x320,0x320#25x0,330x0,330x320,25x320
; CONFIG_BLOCK_END
; EXECUTABLE_BLOCK_START
M201 X20000 Y20000 Z500 E5000
M140 S55
M104 S220 T0
G90
M83
M620 M
M620 N
G28 X T300
T1000
M620.10 A0 F74.8347 H0.2 T220 P220 S1
M620.10 A1 F74.8347 H0.2 T220 P220 S1
M620.11 P1 I0 B1 E0
M620.11 K0 I0 B1 R0
{select}
M620.10 R0
G150.3
M109 S220
G1 E45 F49
G1 E-3 F1800
G150.2
G150.1
G91
G1 Y-16 F12000
G90
M83
M106 S128
; CHANGE_LAYER
; Z_HEIGHT: 0.2
; LAYER_HEIGHT: 0.2
G1 X150 Y150 Z0.2 F12000
; layer num/total_layer_count: 1/4
G1 X160 E1
; CHANGE_LAYER
; Z_HEIGHT: 0.4
; LAYER_HEIGHT: 0.2
G1 Z0.4
; layer num/total_layer_count: 2/4
G1 X170 E1
; CHANGE_LAYER
; Z_HEIGHT: 0.6
; LAYER_HEIGHT: 0.2
G1 X154 Y147 Z0.6
; layer num/total_layer_count: 3/4
G1 X180 E1
; CHANGE_LAYER
; Z_HEIGHT: 0.8
; LAYER_HEIGHT: 0.2
G1 Z0.8
; layer num/total_layer_count: 4/4
G1 X190 E1
M104 S0 T0
M104 S0 T1
M140 S0
; EXECUTABLE_BLOCK_END
"""


def _preamble(output: str) -> list[str]:
    block = output.split("; LAYER_RESCUE_BLOCK_START", 1)[1].split("; LAYER_RESCUE_BLOCK_END", 1)[0]
    return [line.split(";", 1)[0].strip() for line in block.splitlines() if line.split(";", 1)[0].strip()]


class ProfileTests(unittest.TestCase):
    def test_families(self) -> None:
        for model, profile in [
            ("Bambu Lab P1S", P1),
            ("Bambu Lab P1P", P1),
            ("Bambu Lab X1 Carbon", P1),
            ("Bambu Lab X1C", P1),
            ("Bambu Lab X1E", P1),
            ("Bambu Lab H2D", H2),
            ("Bambu Lab H2S", H2),
            ("Bambu Lab H2C", H2),
        ]:
            with self.subTest(model=model):
                self.assertIs(printer_profile(analyze_gcode(sample_gcode(printer=model))), profile)

    def test_unknown_printers_are_refused(self) -> None:
        for model in ("Bambu Lab A1", "Bambu Lab A1 mini", "Prusa MK4"):
            with self.subTest(model=model):
                with self.assertRaisesRegex(ResumeError, "No resume sequence"):
                    build_resume_gcode(sample_gcode(printer=model), ResumeOptions(start_layer=3, allow_untested=True))

    def test_park_position_on_a_p1s_is_unchanged(self) -> None:
        analysis = analyze_gcode(sample_gcode().replace(
            "; spiral_mode = 0\n", "; spiral_mode = 0\n; printable_area = 0x0,256x0,256x256,0x256\n"
        ))
        self.assertEqual(park_position(analysis, 100), (236.0, 250.0))
        self.assertEqual(park_position(analysis, 200), (20.0, 250.0))

    def test_park_position_stays_where_both_h2_nozzles_reach(self) -> None:
        analysis = analyze_gcode(h2_gcode())
        self.assertEqual(reachable_bounds(analysis), (25.0, 0.0, 325.0, 320.0))
        self.assertEqual(park_position(analysis, 100), (305.0, 314.0))
        self.assertEqual(park_position(analysis, 250), (45.0, 314.0))


class P1SequenceTests(unittest.TestCase):
    def test_p1s_keeps_the_stock_station_moves(self) -> None:
        output, _ = build_resume_gcode(sample_gcode(), ResumeOptions(start_layer=3))
        preamble = _preamble(output)
        for line in ("G28 X", "G1 Y265 F3000", "G1 Y-3", "T0", "T1000", "M620.1 E F150 T250"):
            self.assertIn(line, preamble)
        self.assertFalse(any(line.startswith("G150") for line in preamble))


class H2SequenceTests(unittest.TestCase):
    def build(self, source: str | None = None, **options: object):
        return build_resume_gcode(source or h2_gcode(), ResumeOptions(start_layer=3, allow_untested=True, **options))

    def test_requires_accepting_the_risks(self) -> None:
        with self.assertRaisesRegex(ResumeError, "Untested printer"):
            build_resume_gcode(h2_gcode(), ResumeOptions(start_layer=3))
        reasons = untested_setup(analyze_gcode(h2_gcode()))
        self.assertTrue(any(reason.startswith("Experimental H2 sequence") for reason in reasons))

    def test_no_p1s_station_moves(self) -> None:
        output, report = self.build()
        preamble = _preamble(output)
        for line in preamble:
            self.assertNotRegex(line, r"\bY(265|245|-3)\b", line)
            self.assertNotIn("M620.1 E", line)
            self.assertNotEqual(line, "T1000")
        self.assertTrue(any(w.startswith("Experimental H2 sequence") for w in report.warnings))

    def test_selects_the_hotend_with_the_tool(self) -> None:
        preamble = _preamble(self.build()[0])
        self.assertIn("M620 S0A H1", preamble)
        self.assertIn("T0 H1", preamble)
        self.assertIn("M621 S0A", preamble)
        self.assertLess(preamble.index("M620 S0A H1"), preamble.index("T0 H1"))
        self.assertLess(preamble.index("T0 H1"), preamble.index("M621 S0A"))

    def test_copies_the_flush_and_cut_setup_before_the_tool_change(self) -> None:
        preamble = _preamble(self.build()[0])
        select = preamble.index("M620 S0A H1")
        for line in (
            "M620.10 A0 F74.8347 H0.2 T220 P220 S1",
            "M620.10 A1 F74.8347 H0.2 T220 P220 S1",
            "M620.11 P1 I0 B1 E0",
            "M620.11 K0 I0 B1 R0",
        ):
            self.assertIn(line, preamble)
            self.assertLess(preamble.index(line), select)
        self.assertNotIn("M620.10 R0", preamble)

    def test_temperatures_address_the_extruder(self) -> None:
        preamble = _preamble(self.build()[0])
        nozzle = [line for line in preamble if re.match(r"^M10[49] S[1-9]", line)]
        self.assertTrue(nozzle)
        for line in nozzle:
            self.assertTrue(line.endswith(" T0"), line)
        self.assertGreater(
            max(i for i, line in enumerate(preamble) if line.startswith("M109 S220 T0")), preamble.index("T0 H1")
        )

    def test_extruder_falls_back_to_the_filament_map(self) -> None:
        source = h2_gcode().replace("M104 S220 T0\n", "M104 S220\n").replace("M109 S220 T0\n", "M109 S220\n")
        preamble = _preamble(self.build(source)[0])
        self.assertIn("M104 S220 T0", preamble)  # filament_map 2 -> physical_extruder_map[1] = 0

    def test_homes_x_like_the_stock_h2_start(self) -> None:
        preamble = _preamble(self.build()[0])
        self.assertIn("G28 X T300", preamble)
        self.assertNotIn("G28 X", preamble)

    def test_purges_at_the_bin_within_the_volumetric_limit(self) -> None:
        preamble = _preamble(self.build()[0])
        purge = next(line for line in preamble if line.startswith("G1 E30 "))
        index = preamble.index(purge)
        self.assertEqual(preamble[index - 3], "G150.3")
        feed = float(purge.split(" F", 1)[1])
        self.assertLessEqual(feed / 60 * math.pi * (1.75 / 2) ** 2, 2.0)
        self.assertIn("G150.2", preamble[index:])
        self.assertIn("G150.1", preamble[index:])
        last_g90 = max(i for i, line in enumerate(preamble) if line == "G90")
        self.assertGreater(max(i for i, line in enumerate(preamble) if line == "M83"), last_g90)

    def test_then_travels_above_the_part_and_descends(self) -> None:
        preamble = _preamble(self.build()[0])
        travel = preamble.index("G1 X154 Y147 F12000")
        self.assertGreater(travel, preamble.index("G150.1"))
        self.assertEqual(preamble[travel + 1], "G1 Z0.6 F600")

    def test_missing_hotend_is_refused(self) -> None:
        with self.assertRaisesRegex(ResumeError, "hotend"):
            self.build(h2_gcode(hotend=False))

    def test_manual_z_mode_is_not_offered(self) -> None:
        with self.assertRaisesRegex(ResumeError, "Restarted \\(manual Z\\) mode is not available"):
            self.build(z_reference_mode=ZReferenceMode.MANUAL, home_corexy=True)


if __name__ == "__main__":
    unittest.main()
