# Layer Rescue

Layer Rescue is an experimental, conservative G-code post-processor for resuming an interrupted Bambu Lab P1S print at a chosen layer. It integrates with Bambu Studio's **Post-processing Scripts** feature, so Bambu Studio keeps its own filament mapping and `.gcode.3mf` metadata and refreshes Preview after the tool edits the G-code.

> [!CAUTION]
> Resuming an interrupted print can crash the toolhead into the existing part. The tool is intentionally limited and refuses inputs it cannot handle conservatively. Restarted-printer recovery requires exact manual Z alignment and continuous supervision.

## MVP support

- Bambu Lab P1S
- Single logical filament (`T0`)
- By-layer printing
- Relative extrusion (`M83`)
- Bambu Studio G-code with layer and Z markers
- Retained-Z mode when the printer stayed powered on
- Manual-reference mode after a restart, using `G92 Z` before any Z movement
- Original part is still firmly attached to the unchanged build plate

Not yet supported: multi-filament/AMS tool changes, by-object printing, spiral vase, unattended recovery, other printer models, or direct `.gcode.3mf` editing.

## Z reference modes

### Printer stayed powered on (`retained`)

Use this only when the printer never lost power and the Z motors did not release or skip. Layer Rescue preserves the printer's existing logical Z coordinate, lifts the bed/nozzle gap by 2 mm, and optionally re-homes CoreXY with `G28 X`.

### Printer was restarted (`manual`)

After a restart, the physical bed position and the firmware's logical Z coordinate no longer necessarily agree. Before sending the recovery job:

1. clean the nozzle;
2. place it over a flat, actually printed area of the last successful layer;
3. adjust Z until the nozzle just touches that surface;
4. keep the part and plate fixed;
5. choose **Printer was restarted (manual Z reference)** and confirm the alignment.

The generated job assigns that physical position to the preceding layer's known slicer height with `G92 Z...`. This assignment is emitted before every Z move. The job then makes a relative safety lift, homes CoreXY only, and later approaches the next layer's absolute Z.

Manual mode never runs `G28 Z`. Homing Z with an unfinished part on the plate can lift the object into the gantry. Manual mode requires `G28 X` and cannot be combined with `--no-home-corexy`.

## What it changes

Given “last successfully printed layer 461,” Layer Rescue:

1. retains the Bambu header and configuration comments;
2. removes executable startup and layers before 462;
3. reconstructs temperatures, motion limits, speed/flow factors, and fan state;
4. preserves Z or assigns a manually aligned Z reference, depending on the selected mode;
5. emits a relative Z safety lift and `G28 X` CoreXY home;
6. never emits Z homing or bed leveling;
7. restores filament/tool selection and reasserts `M109` after `T1000`;
8. approaches the selected Z at the rear filament-change station;
9. retains all layers from 462 through the original end G-code;
10. writes atomically and keeps a sibling backup.

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

Resume after layer 461 while printer Z was retained:

```bash
layer-rescue --last-layer 461 --z-mode retained print.gcode
```

Resume after a restart, after manually touching the nozzle to layer 461:

```bash
layer-rescue --last-layer 461 --z-mode manual --confirm-manual-z-aligned print.gcode
```

Override temperatures by adding `--nozzle-temp 220 --bed-temp 55`. The old `--assume-z-known` flag remains as a deprecated alias for `--z-mode retained`.

## Safety model

Layer Rescue cannot determine the physical top of a failed print. The layer entered by the operator must be the last layer that actually received filament—not the layer where the printer finally detected the fault.

The tool validates that:

- the first retained marker is the requested next layer;
- retained layers are contiguous through the original end;
- no active `G29` command remains;
- no bare or Z-axis `G28` command remains;
- manual mode emits exactly one `G92 Z`, with the preceding layer height, before every Z movement;
- retained mode emits no `G92 Z` assignment;
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
