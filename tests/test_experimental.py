"""Experimental insert-mode features: no holding wall (--no-wall) and the reheat pass (--reheat)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from fake_slicer import bambu_like_gcode  # noqa: I001

from layer_rescue.cli import main
from layer_rescue.gcode import LAYER_MARKER_RE, ResumeError, _code, _command, _parameter, analyze_gcode
from layer_rescue.i18n import translate_message
from layer_rescue.insert import (
    INSERT_MARKER,
    NO_WALL_MARKER,
    PAUSE_BLOCK_START,
    WALL_MARKER,
    InsertOptions,
    build_insert_gcode,
    plan_insert,
    validate_insert_output,
)
from layer_rescue.preview import plan_shapes, plan_svg
from layer_rescue.reheat import REHEAT_END, REHEAT_START, reheat_z_values
from layer_rescue.resume import ResumeOptions, ZReferenceMode, _validate_output, build_resume_gcode
from test_printers import PRINTERS, _job

PREAMBLE_END = "; LAYER_RESCUE_BLOCK_END"


def _source(**kwargs: object) -> str:
    return bambu_like_gcode(part_height=12, addition_height=6, **kwargs)


def _block(text: str, start: str, end: str) -> list[str]:
    lines = text.splitlines()
    a = next(i for i, line in enumerate(lines) if line.strip() == start)
    b = next(i for i, line in enumerate(lines) if line.strip() == end)
    return lines[a : b + 1]


def _markers(text: str) -> list[int]:
    return [int(m.group(1)) for m in (LAYER_MARKER_RE.match(line) for line in text.splitlines()) if m]


class NoWallTests(unittest.TestCase):
    def test_same_job_without_the_wall(self) -> None:
        text = _source()
        with_wall, wall_report = build_insert_gcode(text, InsertOptions(part_height_mm=12))
        bare, report = build_insert_gcode(text, InsertOptions(part_height_mm=12, holding_wall=False))
        self.assertTrue(any(line.startswith(WALL_MARKER) for line in with_wall.splitlines()))
        self.assertFalse(any(line.startswith(WALL_MARKER) for line in bare.splitlines()))
        self.assertIn(NO_WALL_MARKER, bare.splitlines())
        # Same layer frames, same pause, same resume: only the wall toolpaths are gone.
        self.assertEqual(_markers(bare), _markers(with_wall))
        self.assertEqual(_block(bare, PAUSE_BLOCK_START, PREAMBLE_END)[2:], _block(with_wall, PAUSE_BLOCK_START, PREAMBLE_END)[2:])
        self.assertFalse(report.holding_wall)
        self.assertTrue(wall_report.holding_wall)
        self.assertEqual(report.wall_filament_mm, 0.0)
        self.assertGreater(wall_report.wall_filament_mm, 0.0)
        self.assertTrue(any(w.startswith("Experimental: no holding wall") for w in report.warnings))
        # The square part is symmetric: the "wall cannot fix its orientation" warning only applies with a wall.
        self.assertTrue(any("cannot fix its orientation" in w for w in wall_report.warnings))
        self.assertFalse(any("cannot fix its orientation" in w for w in report.warnings))

    def test_nothing_is_printed_before_the_pause(self) -> None:
        bare, _ = build_insert_gcode(_source(), InsertOptions(part_height_mm=12, holding_wall=False))
        lines = bare.splitlines()
        start = lines.index(INSERT_MARKER)
        pause = lines.index(PAUSE_BLOCK_START)
        for raw in lines[start:pause]:
            code = _code(raw)
            if code and _command(code) in {"G1", "G2", "G3"}:
                prints = (_parameter(code, "E") or 0) > 0 and (
                    _parameter(code, "X") is not None or _parameter(code, "Y") is not None
                )
                self.assertFalse(prints, raw)

    def test_supports_are_still_reprinted(self) -> None:
        text = bambu_like_gcode(part_height=12, addition_height=6, support_at=(150, 128), support_top=14)
        bare, report = build_insert_gcode(text, InsertOptions(part_height_mm=12, holding_wall=False))
        self.assertGreater(report.support_layers, 0)
        self.assertTrue(any(line.startswith("; LAYER_RESCUE_SUPPORT") for line in bare.splitlines()))

    def test_part_near_the_bed_edge_is_not_rejected_for_a_wall_that_is_not_printed(self) -> None:
        text = bambu_like_gcode(part_height=12, addition_height=6, center=(13.0, 128.0))
        with self.assertRaises(ResumeError):
            plan_insert(text, InsertOptions(part_height_mm=12))
        plan_insert(text, InsertOptions(part_height_mm=12, holding_wall=False))

    def test_preview_has_no_wall(self) -> None:
        plan = plan_insert(_source(), InsertOptions(part_height_mm=12, holding_wall=False))
        kinds = {shape.kind for shape in plan_shapes(plan)}
        self.assertNotIn("wall-top", kinds)
        self.assertNotIn("brim", kinds)
        self.assertIn("no wall (experimental)", plan_svg(plan))

    def test_validator_rejects_a_wall_that_was_not_asked_for(self) -> None:
        text = _source()
        with_wall, _ = build_insert_gcode(text, InsertOptions(part_height_mm=12))
        plan = plan_insert(text, InsertOptions(part_height_mm=12, holding_wall=False))
        with self.assertRaises(ResumeError):
            validate_insert_output(with_wall, plan)


class ReheatTests(unittest.TestCase):
    def _build(self, **options: object) -> tuple[str, object, list[str]]:
        text = _source()
        out, report = build_insert_gcode(text, InsertOptions(part_height_mm=12, reheat_pass=True, **options))
        return out, report, _block(out, REHEAT_START, REHEAT_END)

    def test_block_sits_right_after_the_resume_preamble(self) -> None:
        out, report, block = self._build()
        lines = out.splitlines()
        self.assertEqual(lines.index(REHEAT_START), lines.index(PREAMBLE_END) + 1)
        self.assertEqual(report.reheat_hover_z, 12.2)
        self.assertGreater(report.reheat_path_mm, 0)
        self.assertAlmostEqual(report.reheat_seconds, report.reheat_path_mm / 20.0, delta=0.1)

    def test_no_extrusion_and_never_below_the_gap(self) -> None:
        _, _, block = self._build(reheat_gap_mm=0.3)
        z_values = []
        net_e = 0.0
        for raw in block:
            code = _code(raw)
            if not code or _command(code) != "G1":
                continue
            e = _parameter(code, "E")
            moves_xy = _parameter(code, "X") is not None or _parameter(code, "Y") is not None
            if moves_xy:
                self.assertIsNone(e, raw)
            elif e is not None:
                net_e += e
            if _parameter(code, "Z") is not None:
                z_values.append(_parameter(code, "Z"))
        self.assertAlmostEqual(net_e, 0.0)  # retracted for the dry pass, restored after it
        self.assertGreaterEqual(min(z_values), 12.0 + 0.05)
        self.assertIn(12.3, z_values)

    def test_traces_the_first_layer_on_top(self) -> None:
        _, report_one, one = self._build(reheat_passes=1)
        _, report_two, two = self._build(reheat_passes=2)
        xy_one = [raw for raw in one if raw.startswith("G1 X")]
        xy_two = [raw for raw in two if raw.startswith("G1 X")]
        self.assertGreater(len(xy_one), 4)
        self.assertGreater(len(xy_two), len(xy_one))
        self.assertAlmostEqual(report_two.reheat_seconds, 2 * report_one.reheat_seconds, delta=0.2)

    def test_temperature_is_set_and_restored(self) -> None:
        out, _, block = self._build(reheat_temperature=240)
        temps = [raw for raw in block if raw.startswith("M109")]
        self.assertEqual(len(temps), 2)
        self.assertTrue(temps[0].startswith("M109 S240"))
        self.assertNotIn("S240", temps[1])

    def test_default_jobs_are_unchanged(self) -> None:
        out, report = build_insert_gcode(_source(), InsertOptions(part_height_mm=12))
        self.assertNotIn(REHEAT_START, out)
        self.assertNotIn(NO_WALL_MARKER, out)
        self.assertIsNone(report.reheat_hover_z)

    def test_both_features_together(self) -> None:
        out, report = build_insert_gcode(
            _source(), InsertOptions(part_height_mm=12, holding_wall=False, reheat_pass=True)
        )
        self.assertIn(REHEAT_START, out)
        self.assertIn(NO_WALL_MARKER, out)
        self.assertFalse(report.holding_wall)

    def test_option_limits_are_checked_and_translated(self) -> None:
        analysis = analyze_gcode(_source())
        for bad in (
            {"reheat_gap_mm": 0.01},
            {"reheat_gap_mm": 2.0},
            {"reheat_speed_mm_s": 500},
            {"reheat_passes": 0},
            {"reheat_temperature": 100},
        ):
            with self.assertRaises(ResumeError) as caught:
                plan_insert(analysis, InsertOptions(part_height_mm=12, reheat_pass=True, **bad))
            message = str(caught.exception)
            self.assertNotEqual(translate_message(message, "tr"), message, message)
        # Out-of-range reheat values do not matter while the pass is off.
        plan_insert(analysis, InsertOptions(part_height_mm=12, reheat_gap_mm=0.01))

    def test_validator_rejects_extrusion_in_the_pass(self) -> None:
        text = _source()
        options = InsertOptions(part_height_mm=12, reheat_pass=True)
        out, _ = build_insert_gcode(text, options)
        plan = plan_insert(text, options)
        lines = out.splitlines()
        end = lines.index(REHEAT_END)
        lines.insert(end, "G1 X130 Y130 E0.5")
        with self.assertRaises(ResumeError):
            validate_insert_output("\n".join(lines) + "\n", plan)
        without = [line for line in out.splitlines() if line not in (REHEAT_START, REHEAT_END)]
        with self.assertRaises(ResumeError):
            validate_insert_output("\n".join(without) + "\n", plan)

    def test_warnings_are_translated(self) -> None:
        plan = plan_insert(_source(), InsertOptions(part_height_mm=12, holding_wall=False, reheat_pass=True))
        experimental = [w for w in plan.warnings if w.startswith("Experimental")]
        self.assertEqual(len(experimental), 2)
        for warning in experimental:
            self.assertNotEqual(translate_message(warning, "tr"), warning, warning)


class CliExperimentalTests(unittest.TestCase):
    def _run(self, *arguments: str) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job.gcode"
            path.write_text(_source(), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = main([*arguments, str(path), "--no-backup"])
            return code, out.getvalue(), path.read_text(encoding="utf-8")

    def test_flags_reach_the_job(self) -> None:
        code, out, text = self._run(
            "--part-height", "12", "--confirm-attended", "--no-wall", "--reheat", "--reheat-gap", "0.3",
            "--reheat-speed", "15", "--reheat-passes", "2",
        )
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertFalse(result["holding_wall"])
        self.assertEqual(result["reheat_hover_z"], 12.3)
        self.assertGreater(result["reheat_seconds"], 0)
        self.assertIn(REHEAT_START, text)
        self.assertIn(NO_WALL_MARKER, text)

    def test_no_wall_outside_insert_mode_is_an_error(self) -> None:
        code, _, text = self._run("--last-layer", "10", "--z-mode", "retained", "--no-wall")
        self.assertEqual(code, 2)
        self.assertNotIn("LAYER_RESCUE", text)

    def test_reheat_reaches_a_resume_job(self) -> None:
        code, out, text = self._run(
            "--last-layer", "40", "--z-mode", "retained", "--reheat", "--reheat-gap", "0.3"
        )
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertEqual(result["reheat_hover_z"], 8.3)
        self.assertGreater(result["reheat_seconds"], 0)
        self.assertIn(REHEAT_START, text)

    def test_resume_json_without_reheat(self) -> None:
        code, out, text = self._run("--last-layer", "40", "--z-mode", "retained")
        self.assertEqual(code, 0)
        self.assertIsNone(json.loads(out)["reheat_hover_z"])
        self.assertNotIn(REHEAT_START, text)


class ResumeReheatTests(unittest.TestCase):
    """The reheat pass in resume mode, on every printer profile, after a stop and after a power cut."""

    START = 40  # resumes at Z 8.0 on the fake 0.2 mm jobs; the last printed layer is at Z 7.8

    def _build(self, model: str = "Bambu Lab P1S", mode: str = "retained", **options: object) -> tuple[str, object]:
        source = _job(model, timelapse_lift=False)
        return build_resume_gcode(
            source,
            ResumeOptions(start_layer=self.START, z_reference_mode=mode, allow_untested=True, **options),
        )

    def _pass(self, out: str) -> list[str]:
        return _block(out, REHEAT_START, REHEAT_END)

    def test_every_printer_and_both_modes(self) -> None:
        for model in PRINTERS:
            for mode in (ZReferenceMode.RETAINED, ZReferenceMode.MANUAL):
                with self.subTest(model=model, mode=mode.value):
                    plain, _ = self._build(model, mode)
                    out, report = self._build(model, mode, reheat_pass=True, reheat_gap_mm=0.1)
                    lines = out.splitlines()
                    start = lines.index(REHEAT_START)
                    self.assertEqual(start, lines.index(PREAMBLE_END) + 1)
                    block = self._pass(out)
                    # Everything outside the pass is the job without it.
                    self.assertEqual(lines[:start] + lines[start + len(block) :], plain.splitlines())
                    self.assertEqual(report.reheat_hover_z, 7.9)
                    # Nominal Z: down to 0.1 mm above the last layer, never lower, back to the layer height.
                    z_values = reheat_z_values(block, 8.0)
                    self.assertAlmostEqual(min(z_values), 7.9)
                    self.assertAlmostEqual(z_values[-1], 8.0)
                    for raw in block:
                        code = _code(raw)
                        if code and _command(code) == "G1":
                            moves_xy = _parameter(code, "X") is not None or _parameter(code, "Y") is not None
                            self.assertFalse(moves_xy and _parameter(code, "E") is not None, raw)
                            if mode is ZReferenceMode.MANUAL and _parameter(code, "Z") is not None:
                                # Restarted mode never uses absolute Z: each Z move sits between G91 and G90.
                                index = block.index(raw)
                                self.assertEqual(block[index - 1], "G91", raw)

    def test_default_jobs_are_unchanged(self) -> None:
        for mode in ("retained", "manual"):
            out, report = self._build(mode=mode)
            self.assertNotIn(REHEAT_START, out)
            self.assertIsNone(report.reheat_hover_z)
            self.assertFalse(any(w.startswith("Experimental: reheat") for w in report.warnings))

    def test_temperature_names_the_extruder_on_two_nozzle_printers(self) -> None:
        for model, suffix in (("Bambu Lab P1S", ""), ("Bambu Lab H2D", " T0"), ("Bambu Lab H2S", "")):
            with self.subTest(model=model):
                out, _ = self._build(model, reheat_pass=True, reheat_temperature=240)
                temps = [line.split(";")[0].strip() for line in self._pass(out) if line.startswith("M109")]
                self.assertEqual(temps, [f"M109 S240{suffix}", f"M109 S220{suffix}"])

    def test_traces_every_object_of_the_resumed_layer(self) -> None:
        single, one = build_resume_gcode(
            bambu_like_gcode(timelapse_lift=False), ResumeOptions(start_layer=20, reheat_pass=True)
        )
        several, three = build_resume_gcode(
            bambu_like_gcode(timelapse_lift=False, objects=3), ResumeOptions(start_layer=20, reheat_pass=True)
        )
        self.assertAlmostEqual(three.reheat_path_mm, 3 * one.reheat_path_mm, delta=1.0)
        self.assertAlmostEqual(three.reheat_seconds, three.reheat_path_mm / 20.0, delta=0.1)

    def test_option_limits_and_translations(self) -> None:
        for bad in ({"reheat_gap_mm": 0.01}, {"reheat_speed_mm_s": 1}, {"reheat_passes": 11}, {"reheat_temperature": 350}):
            with self.assertRaises(ResumeError) as caught:
                self._build(reheat_pass=True, **bad)
            self.assertNotEqual(translate_message(str(caught.exception), "tr"), str(caught.exception))
        self._build(reheat_gap_mm=0.01)  # ignored while the pass is off
        _, report = self._build(reheat_pass=True)
        warning = next(w for w in report.warnings if w.startswith("Experimental: reheat"))
        self.assertNotEqual(translate_message(warning, "tr"), warning)

    def test_validator_rejects_a_bad_or_missing_pass(self) -> None:
        for mode in (ZReferenceMode.RETAINED, ZReferenceMode.MANUAL):
            with self.subTest(mode=mode.value):
                out, report = self._build(mode=mode, reheat_pass=True)
                args = (self.START, 70, mode, report.reference_z)
                _validate_output(out, *args, 7.85, start_z=8.0)
                lines = out.splitlines()
                end = lines.index(REHEAT_END)
                extruding = lines[:end] + ["G1 X130 Y130 E0.5"] + lines[end:]
                with self.assertRaises(ResumeError):
                    _validate_output("\n".join(extruding) + "\n", *args, 7.85, start_z=8.0)
                with self.assertRaises(ResumeError):  # a pass where none was asked for
                    _validate_output(out, *args)
                plain, _ = self._build(mode=mode)
                with self.assertRaises(ResumeError):  # no pass where one was asked for
                    _validate_output(plain, *args, 7.85, start_z=8.0)
                if mode is ZReferenceMode.RETAINED:  # the hover height lowered onto the old surface
                    too_low = [line.replace("G1 Z8 F600 ; reheat height", "G1 Z7.8 F600 ; reheat height") for line in lines]
                    self.assertNotEqual(too_low, lines)
                    with self.assertRaises(ResumeError):
                        _validate_output("\n".join(too_low) + "\n", *args, 7.85, start_z=8.0)


if __name__ == "__main__":
    unittest.main()
