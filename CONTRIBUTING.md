# Contributing

Safety is more important than convenience. A change that supports more inputs must not silently weaken an existing guard.

## Ground rules

- Add tests for every parser or preamble change.
- Never introduce Z homing or bed leveling into recovery output.
- In manual-reference mode, keep the single `G92 Z` assignment before every Z movement and derive it only from the preceding contiguous layer.
- Preserve the final `M109` after tool/AMS selection.
- Reject an unknown state instead of guessing.
- Keep printer-specific templates explicit.
- Do not add a printer model without testing representative G-code from that model.
- Do not commit user G-code, serial numbers, printer names, access tokens, or cloud metadata.

## Local checks

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

## Pull requests

Describe the physical printer scenario, the source G-code characteristics, the expected first retained layer/Z, and how collision risk was tested. Hardware testing must be supervised and should begin without an existing part on the bed.
