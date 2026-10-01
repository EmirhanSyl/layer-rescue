# Contributing

Bug reports, test results from real printers and pull requests are welcome. Please read the [Code of Conduct](CODE_OF_CONDUCT.md) first.

## Setup

```bash
git clone https://github.com/EmirhanSyl/layer-rescue.git
cd layer-rescue
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

The only third-party runtime dependency is `pyclipper` (polygon offsets for insert mode). Do not add more without a strong reason.

## Rules for G-code changes

This tool moves a real machine, so safety comes before supporting more inputs.

- Add a test for every parser or preamble change.
- Never add Z homing or bed leveling to the output.
- In restarted (manual) mode every Z move must stay relative (`G91`). The validator enforces this; do not weaken it.
- On Bambu firmware `G90` also resets extrusion to absolute. Put `M83` after every `G90` you emit.
- Keep the final `M109` after tool/AMS selection.
- In insert mode, nothing may move in XY below the part top + 1 mm between the pause and the descent onto the part. The validator enforces this.
- When the state is unknown, reject the file instead of guessing.
- Do not add a printer model without testing G-code from that model.
- Do not commit user G-code with serial numbers, printer names, access codes or cloud metadata.

## Translations

The window is available in English and Turkish (`src/layer_rescue/i18n.py`).

- Every window text has a key in `STRINGS`, in both languages, with the same `{placeholders}`.
- The core modules raise and warn in English (the CLI and bug reports stay English). The window translates those messages with `MESSAGE_PATTERNS`; when you add or change a user-facing `ResumeError` or warning, add or update its pattern. Messages without a pattern are shown in English.
- `tests/test_i18n.py` checks that both languages have the same keys and placeholders and that common messages are translated.
- To add a language, add it to `LANGUAGES` and `STRINGS` (and patterns if you want translated messages).

## Pull requests

- Keep each PR focused on one change.
- Describe the printer scenario, the expected first layer and Z, and how you tested it (printer, simulation or unit tests only).
- Add a line to `CHANGELOG.md` under **Unreleased**.
- First hardware tests should be supervised, ideally without a part on the bed.

Releases are made by the maintainer; see [docs/releasing.md](docs/releasing.md).
