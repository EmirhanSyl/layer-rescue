from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from layer_rescue.cli import main
from test_core import sample_gcode


class CliTests(unittest.TestCase):
    def _run_on_copy(self, *arguments: str, source: str | None = None) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "job.gcode"
            path.write_text(source if source is not None else sample_gcode(), encoding="utf-8")
            stream = io.StringIO()
            with redirect_stdout(stream), redirect_stderr(stream):
                result = main([*arguments, str(path)])
            return result, path.read_text(encoding="utf-8")

    def test_retained_mode_batch_conversion(self) -> None:
        result, output = self._run_on_copy("--last-layer", "2", "--z-mode", "retained")
        self.assertEqual(result, 0)
        self.assertIn("; Z reference mode: retained", output)
        self.assertNotIn("G92 Z", output)

    def test_manual_mode_batch_conversion(self) -> None:
        result, output = self._run_on_copy(
            "--last-layer",
            "2",
            "--z-mode",
            "manual",
            "--confirm-manual-z-aligned",
        )
        self.assertEqual(result, 0)
        self.assertIn("; Z reference mode: manual", output)
        self.assertIn("G92 Z0.4", output)

    def test_missing_path_is_an_error_outside_the_packaged_app(self) -> None:
        stream = io.StringIO()
        with redirect_stderr(stream), self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)

    def test_post_processing_command_for_source_install(self) -> None:
        from layer_rescue.cli import post_processing_command

        self.assertTrue(post_processing_command().endswith(" -m layer_rescue"))

    def test_manual_mode_requires_explicit_alignment_confirmation(self) -> None:
        result, output = self._run_on_copy("--last-layer", "2", "--z-mode", "manual")
        self.assertEqual(result, 2)
        self.assertNotIn("; LAYER_RESCUE_BLOCK_START", output)

    def test_insert_mode_batch_conversion(self) -> None:
        from fake_slicer import bambu_like_gcode

        result, output = self._run_on_copy(
            "--part-height", "10.05", "--wall-height", "4", "--confirm-attended", source=bambu_like_gcode()
        )
        self.assertEqual(result, 0)
        self.assertIn("; LAYER_RESCUE_INSERT_MODE", output)
        self.assertIn("M400 U1", output)

    def test_insert_mode_by_layer_number(self) -> None:
        from fake_slicer import bambu_like_gcode

        result, output = self._run_on_copy("--part-layer", "50", "--confirm-attended", source=bambu_like_gcode())
        self.assertEqual(result, 0)
        self.assertIn("then print from layer 51 on a 10 mm part", output)

    def test_insert_mode_without_reprinting_supports(self) -> None:
        from fake_slicer import bambu_like_gcode

        result, output = self._run_on_copy(
            "--part-height", "10", "--confirm-attended", "--no-reprint-supports",
            source=bambu_like_gcode(support_at=(150.0, 128.0)),
        )
        self.assertEqual(result, 0)
        self.assertNotIn("; LAYER_RESCUE_SUPPORT", output)

    def test_insert_mode_requires_attended_confirmation(self) -> None:
        from fake_slicer import bambu_like_gcode

        result, output = self._run_on_copy("--part-height", "10", source=bambu_like_gcode())
        self.assertEqual(result, 2)
        self.assertNotIn("; LAYER_RESCUE_INSERT_MODE", output)


    def test_allow_untested_flag(self) -> None:
        source = sample_gcode(printer="Bambu Lab X1C")
        result, output = self._run_on_copy("--last-layer", "2", "--z-mode", "retained", source=source)
        self.assertEqual(result, 2)
        self.assertNotIn("LAYER_RESCUE", output)
        result, output = self._run_on_copy(
            "--last-layer", "2", "--z-mode", "retained", "--allow-untested", source=source
        )
        self.assertEqual(result, 0)
        self.assertIn("; LAYER_RESCUE_BLOCK_START", output)


if __name__ == "__main__":
    unittest.main()
