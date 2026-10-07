from __future__ import annotations

import math
import re
import unittest

from layer_rescue.gcode import ResumeError, analyze_gcode
from layer_rescue.machine_state import untested_setup
from layer_rescue.printers import A1, A1_MINI, H2, P1, park_position, printer_profile, reachable_bounds
from layer_rescue.resume import ResumeOptions, ZReferenceMode, build_resume_gcode
from test_core import sample_gcode


def h2_gcode(*, model: str = "Bambu Lab H2C", hotend: bool = True) -> str:
    """A small H2C-style job: two extruders, 0.2 mm nozzles, the filament on extruder 2 (physical 0)."""
    # Bambu Studio 2.08 resolves the hotend to -1 (no particular hotend) for a plain H2C job.
    select = (
        "M620 S0A H-1\nM400\nT0 H-1\nM400\nM628 S0\nM629\nM400\nM621 S0A\nM104 S220"
        if hotend
        else "M620 S0A\nM400\nT0\nM400\nM621 S0A\nM104 S220"
    )
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
M620.11 P1 I0 B-1 E0
M620.11 K1 I0 B-1 R10 F623.623
M628 S1
M620.11 S1 L0 I0 B-1 R10 D8 E-14 F623.623
M629
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
            ("Bambu Lab A1", A1),
            ("Bambu Lab A1 mini", A1_MINI),
        ]:
            with self.subTest(model=model):
                self.assertIs(printer_profile(analyze_gcode(sample_gcode(printer=model))), profile)

    def test_other_printers_use_the_p1_sequence_after_accepting_the_risks(self) -> None:
        for model in ("Creality K1", "Prusa MK4"):
            with self.subTest(model=model):
                self.assertIs(printer_profile(analyze_gcode(sample_gcode(printer=model))), P1)
                with self.assertRaisesRegex(ResumeError, "Untested printer.*--allow-untested"):
                    build_resume_gcode(sample_gcode(printer=model), ResumeOptions(start_layer=3))
                output, report = build_resume_gcode(
                    sample_gcode(printer=model), ResumeOptions(start_layer=3, allow_untested=True)
                )
                self.assertIn("G1 Y265 F3000", _preamble(output))
                self.assertTrue(any(warning.startswith("Untested printer") for warning in report.warnings))

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


class A1SequenceTests(unittest.TestCase):
    def build(self, **options: object):
        return build_resume_gcode(
            sample_gcode(printer="Bambu Lab A1"), ResumeOptions(start_layer=3, allow_untested=True, **options)
        )

    def test_still_requires_accepting_the_risks(self) -> None:
        with self.assertRaisesRegex(ResumeError, "Untested printer"):
            build_resume_gcode(sample_gcode(printer="Bambu Lab A1"), ResumeOptions(start_layer=3))

    def test_no_p1s_station_or_cutter_moves(self) -> None:
        for line in _preamble(self.build()[0]):
            self.assertNotRegex(line, r"\bY(265|245|-3)\b", line)
            self.assertNotRegex(line, r"^G1 X(60|20|54|120)\b", line)
            self.assertNotEqual(line, "T1000")

    def test_purges_and_wipes_off_the_bed_on_the_left(self) -> None:
        preamble = _preamble(self.build()[0])
        purge = next(i for i, line in enumerate(preamble) if line.startswith("G1 E30 "))
        moves = [line for line in preamble[:purge] if re.match(r"^G1 X", line)]
        self.assertEqual(moves[-1], "G1 X-48.2 F3000")
        after = preamble[purge:]
        self.assertEqual(after.count("G1 X-28.5 F30000"), 3)
        self.assertEqual(after.count("G1 X-48.2 F3000"), 3)

    def test_loads_the_filament_like_the_stock_a1_start(self) -> None:
        preamble = _preamble(self.build()[0])
        for line in ("M620 M", "M620 S0A", "T0", "M620.1 E F150 T250", "M621 S0A"):
            self.assertIn(line, preamble)
        order = [preamble.index(line) for line in ("M620 S0A", "T0", "M620.1 E F150 T250", "M621 S0A")]
        self.assertEqual(order, sorted(order))
        last_heat = max(i for i, line in enumerate(preamble) if line.startswith("M109 S220"))
        self.assertGreater(last_heat, preamble.index("T0"))

    def test_homes_x_and_returns_to_the_part_after_the_wipe(self) -> None:
        source = sample_gcode(printer="Bambu Lab A1").replace("G1 Z0.6\n", "G1 X128 Y113 Z0.6\n", 1)
        preamble = _preamble(build_resume_gcode(source, ResumeOptions(start_layer=3, allow_untested=True))[0])
        self.assertIn("G28 X", preamble)
        travel = preamble.index("G1 X128 Y113 F12000")
        wipe_end = max(i for i, line in enumerate(preamble) if line == "G1 X-48.2 F3000")
        self.assertGreater(travel, wipe_end)
        self.assertEqual(preamble[travel + 1], "G1 Z0.6 F600")

    def test_manual_z_mode_is_still_available(self) -> None:
        output, report = self.build(z_reference_mode=ZReferenceMode.MANUAL, home_corexy=True)
        self.assertIn("G1 X-48.2 F3000", _preamble(output))
        self.assertEqual(report.z_reference_mode, ZReferenceMode.MANUAL)


class H2SequenceTests(unittest.TestCase):
    def build(self, source: str | None = None, **options: object):
        return build_resume_gcode(source or h2_gcode(), ResumeOptions(start_layer=3, allow_untested=True, **options))

    def test_requires_accepting_the_risks(self) -> None:
        with self.assertRaisesRegex(ResumeError, "Untested printer"):
            build_resume_gcode(h2_gcode(), ResumeOptions(start_layer=3))
        reasons = untested_setup(analyze_gcode(h2_gcode()))
        self.assertTrue(any(reason.startswith("Experimental H2 sequence") for reason in reasons))
        self.assertTrue(any(reason.startswith("Experimental power-cut mode on the H2") for reason in reasons))

    def test_power_cut_messages_are_translated(self) -> None:
        from layer_rescue.i18n import translate_message

        tall = h2_gcode().replace("; CONFIG_BLOCK_END", "; printable_height = 20\n; CONFIG_BLOCK_END")
        _, report = self.build(tall, z_reference_mode=ZReferenceMode.MANUAL, home_corexy=True)
        limited = [w for w in report.warnings if w.startswith("Power-cut mode on the H2: the bed can only be lowered")]
        self.assertEqual(len(limited), 1)
        self.assertIn("12.6 mm", limited[0])
        messages = [*limited, *untested_setup(analyze_gcode(h2_gcode()))]
        for message in messages:
            self.assertNotEqual(translate_message(message, "tr"), message, message)

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
        self.assertIn("M620 S0A H-1", preamble)
        self.assertIn("T0 H-1", preamble)
        self.assertIn("M621 S0A", preamble)
        self.assertLess(preamble.index("M620 S0A H-1"), preamble.index("T0 H-1"))
        self.assertLess(preamble.index("T0 H-1"), preamble.index("M621 S0A"))

    def test_copies_the_flush_and_cut_setup_before_the_tool_change(self) -> None:
        preamble = _preamble(self.build()[0])
        select = preamble.index("M620 S0A H-1")
        for line in (
            "M620.10 A0 F74.8347 H0.2 T220 P220 S1",
            "M620.10 A1 F74.8347 H0.2 T220 P220 S1",
            "M620.11 P1 I0 B-1 E0",
            "M620.11 K1 I0 B-1 R10 F623.623",
        ):
            self.assertIn(line, preamble)
            self.assertLess(preamble.index(line), select)
        self.assertNotIn("M620.10 R0", preamble)

    def test_cut_sequence_is_only_sent_inside_m628_m629(self) -> None:
        preamble = _preamble(self.build()[0])
        cut = preamble.index("M620.11 S1 L0 I0 B-1 R10 D8 E-14 F623.623")
        self.assertEqual(preamble[cut - 1], "M628 S1")
        self.assertEqual(preamble[cut + 1], "M629")
        self.assertLess(cut, preamble.index("M620 S0A H-1"))
        self.assertEqual(sum(1 for line in preamble if line.startswith("M620.11 S")), 1)

    def test_tool_change_follows_the_stock_h2_structure(self) -> None:
        preamble = _preamble(self.build()[0])
        for line in ("M620 M", "M620 N"):
            self.assertLess(preamble.index(line), preamble.index("M620 S0A H-1"))
        tool = preamble.index("T0 H-1")
        self.assertEqual(preamble[tool + 1 : tool + 5], ["M400", "M628 S0", "M629", "M400"])
        self.assertLess(tool + 4, preamble.index("M621 S0A"))

    def test_temperatures_address_the_extruder(self) -> None:
        preamble = _preamble(self.build()[0])
        nozzle = [line for line in preamble if re.match(r"^M10[49] S[1-9]", line)]
        self.assertTrue(nozzle)
        for line in nozzle:
            self.assertTrue(line.endswith(" T0"), line)
        self.assertGreater(
            max(i for i, line in enumerate(preamble) if line.startswith("M109 S220 T0")), preamble.index("T0 H-1")
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

    def test_power_cut_mode_lowers_the_bed_before_the_macros(self) -> None:
        output, report = self.build(z_reference_mode=ZReferenceMode.MANUAL, home_corexy=True)
        preamble = _preamble(output)
        self.assertIn("M211 X0 Y0 Z0", preamble)
        self.assertNotIn("M221 X0 Y0 Z0", preamble)
        self.assertIn("G92 Z0.4", preamble)
        clearance = preamble.index("G1 Z30 F600")
        self.assertEqual(preamble[clearance - 1], "G91")
        self.assertEqual(preamble[clearance + 1], "G90")
        for macro in ("G28 X T300", "G150.3", "G150.2", "G150.1"):
            self.assertGreater(preamble.index(macro), clearance, macro)
        # back down by lift + clearance - layer step: 0.6 - (0.4 + 2 + 30)
        descend = preamble.index("G1 Z-31.8 F600")
        self.assertEqual(preamble[descend - 1], "G91")
        self.assertGreater(descend, preamble.index("G1 X154 Y147 F12000"))
        self.assertTrue(any(w.startswith("Experimental power-cut mode on the H2") for w in report.warnings))
        self.assertFalse(any("can only be lowered" in w for w in report.warnings))

    def test_power_cut_mode_also_lowers_the_bed_before_the_end_macros(self) -> None:
        # Stock H2 end G-code: lift 0.4 mm, then G150.3 right above the finished part.
        source = h2_gcode().replace(
            "M104 S0 T0\n", "; MACHINE_END_GCODE_START\nG90\nG1 Z1.2 F900\nG150.3\nG1 Z10 F900\nG150.2\nM104 S0 T0\n"
        )
        output, _ = self.build(source, z_reference_mode=ZReferenceMode.MANUAL, home_corexy=True)
        end = output.split("; MACHINE_END_GCODE_START", 1)[1]
        codes = [line.split(";", 1)[0].strip() for line in end.splitlines() if line.split(";", 1)[0].strip()]
        self.assertEqual(codes[:3], ["G91", "G1 Z30 F600", "G90"])
        self.assertGreater(codes.index("G150.3"), 2)
        # the end G-code's own moves keep their size: +0.4 mm, then +8.8 mm
        self.assertIn("G1 Z0.4 F900", codes)
        self.assertIn("G1 Z8.8 F900", codes)

    def test_power_cut_clearance_respects_the_maximum_height(self) -> None:
        tall = h2_gcode().replace("; CONFIG_BLOCK_END", "; printable_height = 20\n; CONFIG_BLOCK_END")
        preamble = _preamble(self.build(tall, z_reference_mode=ZReferenceMode.MANUAL, home_corexy=True)[0])
        self.assertIn("G1 Z12.6 F600", preamble)  # 20 - 5 - (0.4 + 2)
        self.assertIn("G1 Z-14.4 F600", preamble)

    def test_printer_stayed_on_mode_has_no_extra_clearance(self) -> None:
        preamble = _preamble(self.build()[0])
        self.assertNotIn("G1 Z30 F600", preamble)


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------------- every mode on every profile

from fake_slicer import (  # noqa: E402
    A1_CONFIG,
    A1_MINI_CONFIG,
    A1_MINI_START,
    A1_START,
    H2C_CONFIG,
    H2C_START,
    H2D_CONFIG,
    H2D_START,
    bambu_like_gcode,
)
from layer_rescue.insert import PAUSE_BLOCK_END, PAUSE_BLOCK_START, InsertOptions, build_insert_gcode  # noqa: E402
from layer_rescue.printers import reachable_bounds as _reachable  # noqa: E402

PRINTERS = {
    # model: (start G-code, config, part centre, lines that must appear in the station block)
    "Bambu Lab P1S": (None, {}, (128.0, 128.0), ["G1 Y265 F3000", "T1000"]),
    "Bambu Lab H2C": (H2C_START, H2C_CONFIG, (165.0, 160.0), ["G150.3", "T0 H-1", "G28 X T300", "M620 N"]),
    "Bambu Lab H2D": (H2D_START, H2D_CONFIG, (175.0, 160.0), ["G150.3", "T0 H-1", "G28 X T300"]),
    "Bambu Lab A1": (A1_START, A1_CONFIG, (128.0, 128.0), ["G1 X-48.2 F3000", "G1 X-28.5 F30000"]),
    "Bambu Lab A1 mini": (A1_MINI_START, A1_MINI_CONFIG, (90.0, 90.0), ["G1 X-13.5 F3000", "G1 X0 F30000"]),
}
P1S_ONLY = [r"\bY265\b", r"\bY245\b", r"\bY-3\b", r"^G1 X20 Y50\b", r"^T1000$"]


def _job(model: str, **kwargs: object) -> str:
    start, config, center, _ = PRINTERS[model]
    return bambu_like_gcode(
        printer=model,
        machine_start=start,
        extra_config={"filament_max_volumetric_speed": "21", **config},
        center=center,
        **kwargs,
    )


def _block(output: str, start: str = "; LAYER_RESCUE_BLOCK_START", end: str = "; LAYER_RESCUE_BLOCK_END") -> list[str]:
    block = output.split(start, 1)[1].split(end, 1)[0]
    return [line.split(";", 1)[0].strip() for line in block.splitlines() if line.split(";", 1)[0].strip()]


class EveryModeTests(unittest.TestCase):
    def check_station(self, model: str, preamble: list[str]) -> None:
        for line in PRINTERS[model][3]:
            self.assertIn(line, preamble, model)
        if model != "Bambu Lab P1S":
            for line in preamble:
                for pattern in P1S_ONLY:
                    self.assertNotRegex(line, pattern, f"{model}: {line}")

    def test_hotend_remap_only_where_the_job_enables_it(self) -> None:
        h2c = _preamble(build_resume_gcode(_job("Bambu Lab H2C"), ResumeOptions(start_layer=40, allow_untested=True))[0])
        h2d = _preamble(build_resume_gcode(_job("Bambu Lab H2D"), ResumeOptions(start_layer=40, allow_untested=True))[0])
        self.assertIn("M620 N", h2c)
        self.assertNotIn("M620 N", h2d)
        cut = [line for line in h2d if line.startswith("M620.11 S")]
        self.assertEqual(cut, ["M620.11 S1 L0 I0 B-1 R10 D8 E-10 F623.623"])

    def test_resume_retained(self) -> None:
        for model in PRINTERS:
            with self.subTest(model=model):
                output, _ = build_resume_gcode(_job(model), ResumeOptions(start_layer=40, allow_untested=True))
                self.check_station(model, _preamble(output))

    def test_restarted_after_power_loss(self) -> None:
        soft_endstops = {
            "Bambu Lab P1S": "M221 X0 Y0 Z0",
            "Bambu Lab H2C": "M211 X0 Y0 Z0",
            "Bambu Lab H2D": "M211 X0 Y0 Z0",
            "Bambu Lab A1": "M211 X0 Y0 Z0",
            "Bambu Lab A1 mini": "M211 X0 Y0 Z0",
        }
        for model, command in soft_endstops.items():
            with self.subTest(model=model):
                output, report = build_resume_gcode(
                    _job(model, timelapse_lift=False),
                    ResumeOptions(start_layer=40, z_reference_mode=ZReferenceMode.MANUAL, allow_untested=True),
                )
                preamble = _preamble(output)
                self.check_station(model, preamble)
                self.assertIn(command, preamble)
                other = "M221 X0 Y0 Z0" if command == "M211 X0 Y0 Z0" else "M211 X0 Y0 Z0"
                self.assertNotIn(other, preamble)
                # every Z move after the reference is relative
                body = output.split("; LAYER_RESCUE_BLOCK_END", 1)[1]
                positioning = "G90"
                for raw in body.splitlines():
                    code = raw.split(";", 1)[0].strip()
                    if code in {"G90", "G91"}:
                        positioning = code
                    elif re.match(r"^G[0-3]\b.*\bZ", code):
                        self.assertEqual(positioning, "G91", f"{model}: {code}")

    def test_insert_mode(self) -> None:
        for model in PRINTERS:
            with self.subTest(model=model):
                output, report = build_insert_gcode(
                    _job(model, part_height=12, addition_height=6),
                    InsertOptions(part_height_mm=12.0, allow_untested=True),
                )
                preamble = _block(output)
                self.check_station(model, preamble)
                pause = _block(output, PAUSE_BLOCK_START, PAUSE_BLOCK_END)
                self.assertIn("M400 U1", pause)
                park = next(line for line in pause if re.match(r"^G1 X[\d.]+ Y[\d.]+ F", line))
                x, y = (float(v) for v in re.findall(r"[XY]([\d.]+)", park))
                min_x, min_y, max_x, max_y = _reachable(analyze_gcode(_job(model, part_height=12, addition_height=6)))
                self.assertTrue(min_x <= x <= max_x and min_y <= y <= max_y, f"{model}: park {x},{y}")
                self.assertLess(output.index(PAUSE_BLOCK_END), output.index("; LAYER_RESCUE_BLOCK_START"))
                if model in {"Bambu Lab H2C", "Bambu Lab H2D"}:
                    after_wall = output.split(PAUSE_BLOCK_START, 1)[1]
                    for raw in after_wall.splitlines():
                        code = raw.split(";", 1)[0].strip()
                        if re.match(r"^M10[49] S[1-9]", code):
                            self.assertRegex(code, r" T0$", code)
