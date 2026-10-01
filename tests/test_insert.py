from __future__ import annotations

import math
import re
import tempfile
import unittest
from pathlib import Path

from fake_slicer import bambu_like_gcode

from layer_rescue import geometry as geo
from layer_rescue.flow import extrusion_per_mm, flow_settings_from_config
from layer_rescue.gcode import LAYER_MARKER_RE, ResumeError, analyze_gcode
from layer_rescue.insert import (
    PAUSE_BLOCK_END,
    PAUSE_BLOCK_START,
    InsertOptions,
    _layer_frame,
    _offset_z,
    build_insert_gcode,
    plan_insert,
    recommended_wall_height,
    validate_insert_output,
)
from layer_rescue.toolpath import Extrusion, LayerToolpaths, arc_points, read_toolpaths
from layer_rescue.wall import WallOptions, plan_wall


def _moves(text: str, start: str, end: str) -> list[str]:
    lines = text.splitlines()
    a = next(i for i, line in enumerate(lines) if line.strip() == start)
    b = next(i for i, line in enumerate(lines) if line.strip() == end)
    return lines[a:b]


class GeometryTests(unittest.TestCase):
    def test_buffered_square_loop_is_the_outer_surface(self) -> None:
        loop = [(0, 0), (19.58, 0), (19.58, 19.58), (0, 19.58), (0, 0)]
        region = geo.fill_holes(geo.buffer_polylines([(loop, 0.42)]))
        self.assertAlmostEqual(geo.area_mm2(region), 20.0 * 20.0, delta=0.5)
        self.assertEqual(len(region), 1)

    def test_rotation_symmetry(self) -> None:
        square = geo.union([geo.to_int([(0, 0), (10, 0), (10, 10), (0, 10)])])
        l_shape = geo.union([geo.to_int([(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)])])
        self.assertTrue(geo.symmetric_under_rotation(square))
        self.assertFalse(geo.symmetric_under_rotation(l_shape))

    def test_config_polygon(self) -> None:
        bed = geo.polygon_from_config("0x0,256x0,256x256,0x256")
        self.assertAlmostEqual(geo.area_mm2(bed), 256 * 256, delta=0.01)
        self.assertTrue(geo.contains_point(bed, (128, 128)))
        self.assertFalse(geo.contains_point(bed, (300, 128)))

    def test_full_circle_arc(self) -> None:
        points = arc_points((10, 0), (10, 0), (0, 0), clockwise=False)
        self.assertGreater(len(points), 50)
        for x, y in points:
            self.assertAlmostEqual(math.hypot(x, y), 10.0, places=6)
        # counter-clockwise: the first step goes up (positive Y)
        self.assertGreater(points[0][1], 0)


class FlowTests(unittest.TestCase):
    def test_extrusion_per_mm(self) -> None:
        # 0.42 x 0.2 bead, 1.75 mm filament: about 0.0314 mm of filament per mm
        self.assertAlmostEqual(extrusion_per_mm(0.42, 0.2, 1.75), 0.03135, places=4)

    def test_settings_from_config_are_capped(self) -> None:
        analysis = analyze_gcode(bambu_like_gcode())
        flow = flow_settings_from_config(analysis.config)
        self.assertEqual(flow.line_width, 0.42)
        self.assertEqual(flow.first_layer_line_width, 0.5)
        self.assertLessEqual(flow.wall_speed, 100)
        self.assertLessEqual(flow.first_layer_speed, 40)
        self.assertAlmostEqual(flow.flow_ratio, 0.98)


class ToolpathTests(unittest.TestCase):
    def test_reads_walls_arcs_and_objects(self) -> None:
        analysis = analyze_gcode(bambu_like_gcode(shape="circle"))
        paths = read_toolpaths(analysis, [5])[5]
        self.assertEqual(paths.object_ids, {"101"})
        features = {e.feature for e in paths.extrusions}
        self.assertIn("Outer wall", features)
        self.assertIn("Sparse infill", features)
        outline = paths.outline_extrusions()
        self.assertTrue(all("wall" in e.feature.lower() for e in outline))
        region = geo.fill_holes(geo.buffer_polylines([(e.points, e.width) for e in outline]))
        self.assertAlmostEqual(geo.area_mm2(region), math.pi * 10.0**2, delta=1.0)


class WallPlanTests(unittest.TestCase):
    def _layers(self, sizes: list[float]) -> tuple[list, dict]:
        text = bambu_like_gcode()
        analysis = analyze_gcode(text)
        layers = list(analysis.layers[: len(sizes)])
        toolpaths = {}
        for layer, size in zip(layers, sizes):
            h = size / 2
            loop = [(100 - h, 100 - h), (100 + h, 100 - h), (100 + h, 100 + h), (100 - h, 100 + h), (100 - h, 100 - h)]
            toolpaths[layer.number] = LayerToolpaths(layer, [Extrusion(tuple(loop), 0.42, "Outer wall", "1")])
        return layers, toolpaths

    def test_opening_grows_and_outside_is_fixed(self) -> None:
        # A part that is wider higher up (a flare): the opening must let the top section pass.
        layers, toolpaths = self._layers([10, 10, 12, 14, 14])
        flow = flow_settings_from_config(analyze_gcode(bambu_like_gcode()).config)
        plan = plan_wall(layers, toolpaths, flow, WallOptions(chamfer_mm=0))
        areas = [geo.area_mm2(layer.opening) for layer in plan.layers]
        self.assertEqual(areas, sorted(areas))
        # Bottom layers are thicker (more loops) than the top ones.
        self.assertGreater(len(plan.layers[0].loops), len(plan.layers[-1].loops))
        # No loop of any layer lies inside that layer's opening + clearance.
        for layer in plan.layers:
            keep_out = geo.offset(layer.opening, 0.25 + layer.width / 2 - 0.02)
            for loop in layer.loops:
                for point in geo.to_float(loop):
                    self.assertFalse(geo.contains_point(keep_out, point))

    def test_wall_lines_setting_sets_the_thickness(self) -> None:
        layers, toolpaths = self._layers([10] * 5)
        flow = flow_settings_from_config(analyze_gcode(bambu_like_gcode()).config)
        plan = plan_wall(layers, toolpaths, flow, WallOptions(wall_lines=6, chamfer_mm=0))
        # beads from both sides meet in the middle: 6 lines = 6 contours per layer
        self.assertEqual(len(plan.layers[2].loops), 6)


class InsertModeTests(unittest.TestCase):
    def test_structure_of_the_output(self) -> None:
        text = bambu_like_gcode(part_height=10.0, addition_height=4.0)
        output, report = build_insert_gcode(text, InsertOptions(part_height_mm=10.03, wall_height_mm=5.0))

        markers = [int(m.group(1)) for line in output.splitlines() if (m := LAYER_MARKER_RE.match(line))]
        self.assertEqual(markers, list(range(1, 26)) + list(range(51, 71)))
        self.assertEqual(report.part_layer, 50)
        self.assertEqual(report.resume_layer, 51)
        self.assertAlmostEqual(report.z_offset_mm, 0.03)
        self.assertAlmostEqual(report.first_layer_thickness_mm, 0.2)
        self.assertEqual(report.wall_layers, 25)
        self.assertAlmostEqual(report.wall_top_z, 5.0)
        self.assertAlmostEqual(report.park_z, 25.03)
        self.assertGreater(report.wall_filament_mm, 10)

        # Start G-code (homing and bed leveling on the empty bed) is kept.
        head = output[: output.index("; LAYER_RESCUE_INSERT_MODE")]
        self.assertIn("G28\n", head)
        self.assertIn("G29", head)

        pause = _moves(output, PAUSE_BLOCK_START, PAUSE_BLOCK_END)
        self.assertIn("M400 U1", pause)
        lift = next(i for i, line in enumerate(pause) if line.startswith("G1 Z"))
        park = next(i for i, line in enumerate(pause) if line.startswith("G1 X"))
        self.assertLess(lift, park, "lift before any XY move")
        self.assertIn("M104 S140 ; standby while paused (reheated before printing)", pause)

        after = output[output.index(PAUSE_BLOCK_END):]
        self.assertNotIn("G29", after)
        self.assertIn("G1 Z10.23 F600 ; descend onto the recovered layer start", after)
        # Every absolute Z of the remaining job is shifted by +0.03
        self.assertIn("G1 Z10.43", after)
        self.assertIn("G1 Z14.53 F900", after)  # end G-code lift

    def test_source_toolpaths_below_the_part_are_gone(self) -> None:
        output, _ = build_insert_gcode(bambu_like_gcode(), InsertOptions(part_height_mm=10.0, wall_height_mm=5.0))
        before_pause = output[output.index("; LAYER_RESCUE_INSERT_MODE"): output.index(PAUSE_BLOCK_START)]
        self.assertNotIn("; FEATURE: Outer wall", before_pause)
        self.assertNotIn("Sparse infill", before_pause)
        self.assertIn("; FEATURE: Layer Rescue wall", before_pause)
        # the slicer frame (timelapse block, progress) survives
        self.assertIn("M971 S11 C10 O0", before_pause)

    def test_adhesion_layers(self) -> None:
        output, report = build_insert_gcode(bambu_like_gcode(), InsertOptions(part_height_mm=10.0, wall_height_mm=5.0))
        after = output[output.index("; LAYER_RESCUE_BLOCK_END"):]
        self.assertEqual(report.nozzle_temperature, 220)
        self.assertIn("M109 S230", output[output.index(PAUSE_BLOCK_END): output.index("; LAYER_RESCUE_BLOCK_END")])
        self.assertIn("M220 S50", after)
        restore = after.index("; Layer Rescue: end of adhesion layers")
        self.assertLess(after.index("layer num/total_layer_count: 52/"), restore)
        self.assertLess(restore, after.index("layer num/total_layer_count: 53/"))
        tail = after[restore:]
        self.assertIn("M104 S220", tail)
        self.assertIn("M220 S100", tail)
        self.assertIn("M106 S255", tail)

    def test_adhesion_can_be_disabled(self) -> None:
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0, adhesion_layers=0)
        output, _ = build_insert_gcode(bambu_like_gcode(), options)
        self.assertNotIn("M220 S50", output)
        self.assertNotIn("M109 S230", output)

    def test_nearest_layer_and_negative_offset(self) -> None:
        output, report = build_insert_gcode(
            bambu_like_gcode(), InsertOptions(part_height_mm=9.93, wall_height_mm=4.0, z_fine_mm=-0.02)
        )
        self.assertEqual(report.part_layer, 50)
        self.assertAlmostEqual(report.z_offset_mm, -0.09)
        self.assertAlmostEqual(report.first_layer_thickness_mm, 0.18)
        self.assertIn("G1 Z10.11 F600 ; descend", output)

    def test_arcs_l_shape_and_warnings(self) -> None:
        _, circle = build_insert_gcode(
            bambu_like_gcode(shape="circle"), InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        )
        self.assertTrue(circle.symmetric)
        _, l_shape = build_insert_gcode(
            bambu_like_gcode(shape="L", addition_size=14), InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        )
        self.assertFalse(l_shape.symmetric)
        self.assertTrue(any("printed in the air" in warning for warning in l_shape.warnings))

    def test_recommended_wall_height(self) -> None:
        self.assertEqual(recommended_wall_height(10.0), 5.0)
        self.assertEqual(recommended_wall_height(4.0), 3.0)
        self.assertEqual(recommended_wall_height(3.0), 2.0)
        self.assertEqual(recommended_wall_height(80.0), 15.0)
        plan = plan_insert(bambu_like_gcode(), InsertOptions(part_height_mm=10.0))
        self.assertEqual(plan.wall_height_mm, 5.0)

    def test_rejections(self) -> None:
        text = bambu_like_gcode()
        cases = {
            "at least 1 mm below": InsertOptions(part_height_mm=10.0, wall_height_mm=9.5),
            "at least 3 mm tall": InsertOptions(part_height_mm=2.0, wall_height_mm=2.0),
            "nothing left to print": InsertOptions(part_height_mm=14.0, wall_height_mm=5.0),
            "fine adjustment": InsertOptions(part_height_mm=10.0, wall_height_mm=5.0, z_fine_mm=0.5),
            "clearance": InsertOptions(part_height_mm=10.0, wall_height_mm=5.0, clearance_mm=2.0),
        }
        for message, options in cases.items():
            with self.subTest(message):
                with self.assertRaisesRegex(ResumeError, message):
                    build_insert_gcode(text, options)

    def test_rejects_unsupported_jobs(self) -> None:
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        with self.assertRaisesRegex(ResumeError, "single object"):
            build_insert_gcode(bambu_like_gcode(objects=2), options)
        with self.assertRaisesRegex(ResumeError, "prime tower"):
            build_insert_gcode(bambu_like_gcode(prime_tower=True), options)
        with self.assertRaisesRegex(ResumeError, "does not fit on the bed"):
            build_insert_gcode(bambu_like_gcode(center=(8.0, 128.0)), options)
        with self.assertRaisesRegex(ResumeError, "excluded area"):
            build_insert_gcode(bambu_like_gcode(center=(28.0, 26.0)), options)
        with self.assertRaisesRegex(ResumeError, "too small"):
            build_insert_gcode(bambu_like_gcode(part_size=4.0, addition_size=3.0), options)
        with self.assertRaisesRegex(ResumeError, "Untested printer.*--allow-untested"):
            build_insert_gcode(bambu_like_gcode(printer="Bambu Lab X1 Carbon"), options)

    def test_other_printer_with_accepted_risks(self) -> None:
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0, allow_untested=True)
        output, report = build_insert_gcode(bambu_like_gcode(printer="Bambu Lab X1 Carbon"), options)
        self.assertIn("; LAYER_RESCUE_BLOCK_START", output)
        self.assertTrue(any(warning.startswith("Untested printer") for warning in report.warnings))

    def test_output_cannot_be_processed_twice(self) -> None:
        output, _ = build_insert_gcode(bambu_like_gcode(), InsertOptions(part_height_mm=10.0, wall_height_mm=5.0))
        with self.assertRaisesRegex(ResumeError, "already been processed"):
            build_insert_gcode(output, InsertOptions(part_height_mm=10.0, wall_height_mm=5.0))

    def test_validator_catches_a_low_move_after_the_pause(self) -> None:
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        text = bambu_like_gcode()
        output, _ = build_insert_gcode(text, options)
        plan = plan_insert(text, options)
        broken = output.replace(PAUSE_BLOCK_END, "G1 Z3\nG1 X100 Y100\n" + PAUSE_BLOCK_END, 1)
        with self.assertRaisesRegex(ResumeError, "after the pause"):
            validate_insert_output(broken, plan)
        broken = output.replace("; LAYER_RESCUE_BLOCK_END", "; LAYER_RESCUE_BLOCK_END\nG1 Z9.5", 1)
        with self.assertRaisesRegex(ResumeError, "hit the seated part"):
            validate_insert_output(broken, plan)
        # a wall line moved into the part
        broken = re.sub(r"(; FEATURE: Layer Rescue wall\n(?:.*\n){6})", r"\1G1 X128 Y128 E0.5\n", output, count=1)
        with self.assertRaisesRegex(ResumeError, "clearance"):
            validate_insert_output(broken, plan)

    def test_validator_still_checks_e_mode_in_generated_wall_code(self) -> None:
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        text = bambu_like_gcode()
        output, _ = build_insert_gcode(text, options)
        plan = plan_insert(text, options)
        broken = output.replace(
            "M83 ; relative extrusion (G90 also switches E to absolute on Bambu firmware)", "M82", 1
        )
        with self.assertRaisesRegex(ResumeError, "absolute E mode"):
            validate_insert_output(broken, plan)

    def test_supports_outside_the_part_are_reprinted_before_the_pause(self) -> None:
        text = bambu_like_gcode(support_at=(150.0, 128.0))
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        output, report = build_insert_gcode(text, options)
        self.assertEqual(report.last_printed_layer, 50)
        self.assertEqual(report.support_layers, 50)
        markers = [int(m.group(1)) for line in output.splitlines() if (m := LAYER_MARKER_RE.match(line))]
        self.assertEqual(markers, list(range(1, 71)))
        before_pause = output[: output.index(PAUSE_BLOCK_START)]
        self.assertIn("; LAYER_RESCUE_SUPPORT layer 50,", before_pause)
        self.assertNotIn("; LAYER_RESCUE_SUPPORT layer 51,", output)
        # the wall stays clear of the support column
        plan = plan_insert(text, options)
        column = plan.supports.layers[3].footprint
        for loop in plan.wall.layers[2].loops:
            for point in geo.to_float(loop):
                self.assertFalse(geo.contains_point(geo.offset(column, 0.9), point))
        self.assertTrue(any("printed again" in w for w in report.warnings))

    def test_supports_inside_a_hollow_part_are_reprinted(self) -> None:
        _, report = build_insert_gcode(
            bambu_like_gcode(hollow=True, support_at=(128.0, 128.0)),
            InsertOptions(part_height_mm=10.0, wall_height_mm=5.0),
        )
        self.assertEqual(report.support_layers, 50)

    def test_supports_that_end_below_the_part_are_not_reprinted(self) -> None:
        output, report = build_insert_gcode(
            bambu_like_gcode(support_at=(150.0, 128.0), support_top=8.0),
            InsertOptions(part_height_mm=10.0, wall_height_mm=5.0),
        )
        self.assertEqual(report.support_layers, 0)
        self.assertEqual(report.last_printed_layer, 25)
        self.assertNotIn("; LAYER_RESCUE_SUPPORT", output)

    def test_support_in_the_parts_path_is_cut(self) -> None:
        text = bambu_like_gcode(support_at=(138.0, 128.0))  # column straddles the part's edge
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        plan = plan_insert(text, options)
        self.assertGreater(plan.supports.dropped_mm, 50)
        self.assertTrue(any("lowered in" in w for w in plan.warnings))
        for layer in plan.supports.layers.values():
            keep_out = geo.offset(layer.keep_out, -0.05)
            for piece in layer.pieces:
                for point in piece.points:
                    self.assertFalse(geo.contains_point(keep_out, point))
        build_insert_gcode(text, options)  # the output validator agrees

    def test_reprinting_supports_can_be_turned_off(self) -> None:
        output, report = build_insert_gcode(
            bambu_like_gcode(support_at=(150.0, 128.0)),
            InsertOptions(part_height_mm=10.0, wall_height_mm=5.0, reprint_supports=False),
        )
        self.assertNotIn("; LAYER_RESCUE_SUPPORT", output)
        self.assertTrue(any("reprinting them is off" in w for w in report.warnings))

    def test_validator_catches_support_in_the_parts_path(self) -> None:
        text = bambu_like_gcode(support_at=(150.0, 128.0))
        options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
        output, _ = build_insert_gcode(text, options)
        plan = plan_insert(text, options)
        broken = re.sub(
            r"(; LAYER_RESCUE_SUPPORT layer 30,.*\n(?:.*\n){9})", r"\1G1 X128 Y128 E0.5\n", output, count=1
        )
        self.assertNotEqual(broken, output)
        with self.assertRaisesRegex(ResumeError, "lowered in"):
            validate_insert_output(broken, plan)

    def test_overhangs_do_not_rest_on_the_wall(self) -> None:
        # A part 10 mm wide up to 2 mm, then 20 mm (from layer Z 2.2): the wall opens 0.4 mm below the step.
        text = bambu_like_gcode(part_size=20.0)
        analysis = analyze_gcode(text)
        flow = flow_settings_from_config(analysis.config)
        layers = list(analysis.layers[:25])
        toolpaths = {}
        for layer in layers:
            h = 5.0 if layer.z <= 2.0 + 1e-6 else 10.0
            loop = [(100 - h, 100 - h), (100 + h, 100 - h), (100 + h, 100 + h), (100 - h, 100 + h), (100 - h, 100 - h)]
            toolpaths[layer.number] = LayerToolpaths(layer, [Extrusion(tuple(loop), 0.42, "Outer wall", "1")])
        plan = plan_wall(layers, toolpaths, flow, WallOptions(chamfer_mm=0))
        wide = geo.area_mm2(plan.layers[-1].opening)
        by_z = {layer.layer.z: geo.area_mm2(layer.opening) for layer in plan.layers}
        self.assertLess(by_z[1.6], wide - 1)  # still hugging the narrow foot
        self.assertAlmostEqual(by_z[1.8], wide, delta=1)  # 0.4 mm below the step: already open
        self.assertAlmostEqual(by_z[2.0], wide, delta=1)

    def test_marker_total_above_the_last_layer(self) -> None:
        # Bambu counts independent support layers in the markers' total: "358/360" with 358 layers.
        text = re.sub(r"(; layer num/total_layer_count: \d+)/70", r"\1/72", bambu_like_gcode())
        _, report = build_insert_gcode(text, InsertOptions(part_height_mm=10.0, wall_height_mm=5.0))
        self.assertEqual(report.resume_layer, 51)
        from layer_rescue.resume import ResumeOptions, build_resume_gcode

        _, resumed = build_resume_gcode(text, ResumeOptions(start_layer=51))
        self.assertEqual(resumed.retained_layers, 20)

    def test_layer_frame_keeps_markers_and_timelapse_only(self) -> None:
        analysis = analyze_gcode(bambu_like_gcode())
        frame = _layer_frame(analysis, analysis.layers[4])
        joined = "\n".join(frame)
        self.assertIn("; layer num/total_layer_count: 5/70", joined)
        self.assertIn("M622 J1", joined)
        self.assertIn("M623", joined)
        self.assertNotIn("G1 X", joined)
        self.assertNotIn("E-.8", joined)

    def test_offset_z(self) -> None:
        body = ["G1 Z10 F900", "G91", "G1 Z2", "G90", "M83", "G1 X1 Y2 Z3.5 ; move", "G1 Z249.99"]
        shifted = _offset_z(body, 0.05, 250.0)
        self.assertEqual(shifted, ["G1 Z10.05 F900", "G91", "G1 Z2", "G90", "M83", "G1 X1 Y2 Z3.55 ; move", "G1 Z249.99"])
        with self.assertRaisesRegex(ResumeError, "G92"):
            _offset_z(["G92 Z3"], 0.1, 250.0)

    def test_rewrite_file_in_place(self) -> None:
        from layer_rescue.fileio import rewrite_with

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "job.gcode"
            path.write_text(bambu_like_gcode(), encoding="utf-8")
            options = InsertOptions(part_height_mm=10.0, wall_height_mm=5.0)
            report, backup = rewrite_with(path, lambda text: build_insert_gcode(text, options))
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertIn("; LAYER_RESCUE_INSERT_MODE", path.read_text(encoding="utf-8"))
            self.assertEqual(report.resume_layer, 51)


if __name__ == "__main__":
    unittest.main()
