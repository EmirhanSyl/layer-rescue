# Layer Rescue

Layer Rescue is an experimental, conservative G-code post-processor for resuming an interrupted Bambu Lab P1S print at a chosen layer. It integrates with Bambu Studio's **Post-processing Scripts** feature, so Bambu Studio keeps its own filament mapping and `.gcode.3mf` metadata and refreshes Preview after the tool edits the G-code.

> [!CAUTION]
> Resuming an interrupted print can crash the toolhead into the existing part. The MVP is intentionally limited and refuses inputs it cannot handle conservatively. Never use it after the printer has lost its Z position.

## MVP support

- Bambu Lab P1S
- Single logical filament (`T0`)
- By-layer printing
- Relative extrusion (`M83`)
- Bambu Studio G-code with layer and Z markers
- Printer remained powered on; Z coordinates are still valid
- Original part is still firmly attached to the unchanged build plate

Not yet supported: multi-filament/AMS tool changes, by-object printing, spiral vase, lost Z position, other printer models, or direct `.gcode.3mf` editing.

## What it changes

Given “last successfully printed layer 461,” Layer Rescue:

1. retains the Bambu header and configuration comments;
2. removes executable startup and layers before 462;
3. reconstructs temperatures, motion limits, speed/flow factors, and fan state;
4. emits a relative Z safety lift and optional `G28 X` CoreXY home;
5. never emits Z homing or bed leveling;
6. restores filament/tool selection and reasserts `M109` after `T1000`;
7. approaches the selected Z at the rear filament-change station;
8. retains all layers from 462 through the original end G-code;
9. writes atomically and keeps a sibling backup.

## Install from source

```bash
python3 -m pip install .
```

For an isolated command, `pipx install .` is recommended.

## Bambu Studio integration

1. Switch Bambu Studio to Advanced/Expert mode.
2. Search the Process settings for **Post-processing Scripts**.
3. Enter the absolute path to the installed `layer-rescue` command.
4. Slice normally.
5. Bambu Studio launches Layer Rescue and appends the temporary G-code path automatically.
6. Choose **Leave unchanged** for ordinary prints, or enter the last successfully printed layer for a recovery job.
7. Inspect Preview before sending the job.

Bambu Studio may display a security warning because post-processing scripts are executable commands. Only approve a tool you installed from a source you trust.

## CLI

Analyze without modifying:

```bash
layer-rescue --analyze print.gcode
```

Resume after layer 461:

```bash
layer-rescue --last-layer 461 --assume-z-known print.gcode
```

Override temperatures:

```bash
layer-rescue --last-layer 461 --assume-z-known --nozzle-temp 220 --bed-temp 55 print.gcode
```

The batch command requires `--assume-z-known` on purpose.

## Safety model

Layer Rescue cannot determine the physical top of a failed print. The layer entered by the operator must be the last layer that actually received filament—not the layer where the printer finally detected the fault.

The tool validates that:

- the first retained marker is the requested next layer;
- retained layers are contiguous through the original end;
- no active `G29` command remains;
- no bare or Z-axis `G28` command remains;
- the print temperature is reasserted after `T1000`;
- the source uses a supported printer, print sequence, tool count, and extrusion mode.

This software is not affiliated with or endorsed by Bambu Lab.

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before proposing printer support or changing safety checks.

## License

MIT
