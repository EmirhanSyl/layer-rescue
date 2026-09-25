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

No third-party runtime dependencies are used. Keep it that way unless there is a strong reason.

## Rules for G-code changes

This tool moves a real machine, so safety comes before supporting more inputs.

- Add a test for every parser or preamble change.
- Never add Z homing or bed leveling to the output.
- In restarted (manual) mode every Z move must stay relative (`G91`). The validator enforces this; do not weaken it.
- On Bambu firmware `G90` also resets extrusion to absolute. Put `M83` after every `G90` you emit.
- Keep the final `M109` after tool/AMS selection.
- When the state is unknown, reject the file instead of guessing.
- Do not add a printer model without testing G-code from that model.
- Do not commit user G-code with serial numbers, printer names, access codes or cloud metadata.

## Pull requests

- Keep each PR focused on one change.
- Describe the printer scenario, the expected first layer and Z, and how you tested it (printer, simulation or unit tests only).
- Add a line to `CHANGELOG.md` under **Unreleased**.
- First hardware tests should be supervised, ideally without a part on the bed.

Releases are made by the maintainer; see [docs/releasing.md](docs/releasing.md).
