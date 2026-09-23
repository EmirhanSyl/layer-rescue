from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from layer_rescue.cli import main
from test_core import sample_gcode


class CliTests(unittest.TestCase):
    def _run_on_copy(self, *arguments: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "job.gcode"
            path.write_text(sample_gcode(), encoding="utf-8")
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

    def test_manual_mode_requires_explicit_alignment_confirmation(self) -> None:
        result, output = self._run_on_copy("--last-layer", "2", "--z-mode", "manual")
        self.assertEqual(result, 2)
        self.assertNotIn("; LAYER_RESCUE_BLOCK_START", output)


if __name__ == "__main__":
    unittest.main()
