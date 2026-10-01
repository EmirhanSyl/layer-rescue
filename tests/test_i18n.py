from __future__ import annotations

import string
import tempfile
import unittest
from pathlib import Path

from fake_slicer import bambu_like_gcode
from layer_rescue.gcode import ResumeError, analyze_gcode
from layer_rescue.i18n import LANGUAGES, MESSAGE_PATTERNS, STRINGS, Translator, load_language, save_language, translate_message
from layer_rescue.insert import InsertOptions, plan_insert
from layer_rescue.resume import ResumeOptions, build_resume_gcode
from test_core import sample_gcode


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


class StringTableTests(unittest.TestCase):
    def test_every_language_has_every_key(self) -> None:
        for language in LANGUAGES:
            self.assertEqual(set(STRINGS[language]), set(STRINGS["en"]), language)

    def test_placeholders_match_english(self) -> None:
        for key, english in STRINGS["en"].items():
            for language in LANGUAGES:
                self.assertEqual(_fields(STRINGS[language][key]), _fields(english), f"{language}: {key}")

    def test_message_templates_only_use_captured_groups(self) -> None:
        for pattern, template in MESSAGE_PATTERNS:
            self.assertLessEqual(_fields(template), set(pattern.groupindex), pattern.pattern)


class MessageTranslationTests(unittest.TestCase):
    def assertTranslated(self, message: str) -> None:
        translated = translate_message(message, "tr")
        self.assertNotEqual(translated, message, f"no Turkish pattern for: {message}")
        self.assertEqual(translate_message(message, "en"), message)

    def test_insert_option_errors(self) -> None:
        text = bambu_like_gcode(part_height=12, addition_height=6)
        analysis = analyze_gcode(text)
        bad = [
            InsertOptions(part_height_mm=2),
            InsertOptions(part_height_mm=12, wall_height_mm=11.5),
            InsertOptions(part_height_mm=12, clearance_mm=2),
            InsertOptions(part_height_mm=12, wall_lines=20),
            InsertOptions(part_height_mm=12, brim_mm=30),
            InsertOptions(part_height_mm=12, standby_temperature=50),
            InsertOptions(part_height_mm=12, adhesion_layers=20),
            InsertOptions(part_height_mm=18),
        ]
        for options in bad:
            with self.assertRaises(ResumeError) as caught:
                plan_insert(analysis, options)
            self.assertTranslated(str(caught.exception))

    def test_insert_warnings(self) -> None:
        plan = plan_insert(
            bambu_like_gcode(part_height=12, addition_height=6, support_at=(150, 128), support_top=14),
            InsertOptions(part_height_mm=12.1),
        )
        self.assertTrue(plan.warnings)
        for warning in plan.warnings:
            self.assertTranslated(warning)

    def test_resume_errors(self) -> None:
        text = sample_gcode()
        for options in (ResumeOptions(start_layer=1), ResumeOptions(start_layer=99), ResumeOptions(start_layer=2, nozzle_temperature=400)):
            with self.assertRaises(ResumeError) as caught:
                build_resume_gcode(text, options)
            self.assertTranslated(str(caught.exception))
        for source in (sample_gcode(printer="Bambu Lab X1C"), sample_gcode(second_tool=True)):
            with self.assertRaises(ResumeError) as caught:
                build_resume_gcode(source, ResumeOptions(start_layer=3))
            self.assertTranslated(str(caught.exception))
            self.assertIn("riskleri kabul edin", translate_message(str(caught.exception), "tr"))

    def test_untested_warnings(self) -> None:
        _, report = build_resume_gcode(
            sample_gcode(printer="Bambu Lab X1C", second_tool=True), ResumeOptions(start_layer=3, allow_untested=True)
        )
        untested = [warning for warning in report.warnings if warning.startswith("Untested")]
        self.assertEqual(len(untested), 2)
        for warning in untested:
            self.assertTranslated(warning)

    def test_unknown_message_is_kept(self) -> None:
        self.assertEqual(translate_message("Something new.", "tr"), "Something new.")

    def test_internal_errors_keep_english_details(self) -> None:
        translated = translate_message("Internal validation failed: wall line inside the part's clearance at line 5.", "tr")
        self.assertIn("wall line inside the part's clearance at line 5.", translated)


class TranslatorTests(unittest.TestCase):
    def test_switching_runs_listeners(self) -> None:
        tr = Translator("en", remember=False)
        seen: list[str] = []
        tr.on_change(lambda: seen.append(tr("button.create")))
        tr.set_language("tr")
        tr.set_language("tr")  # no change, no callback
        self.assertEqual(seen, ["Create G-code", "G-code oluştur"])

    def test_language_is_remembered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sub" / "settings.json"
            save_language("tr", path)
            self.assertEqual(load_language(path), "tr")
            save_language("en", path)
            self.assertEqual(load_language(path), "en")

    def test_broken_settings_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            self.assertIn(load_language(path), LANGUAGES)


if __name__ == "__main__":
    unittest.main()
