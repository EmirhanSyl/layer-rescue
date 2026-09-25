# Layer Rescue

[![CI](https://github.com/EmirhanSyl/layer-rescue/actions/workflows/ci.yml/badge.svg)](https://github.com/EmirhanSyl/layer-rescue/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/EmirhanSyl/layer-rescue?include_prereleases)](https://github.com/EmirhanSyl/layer-rescue/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[Türkçe](README.tr.md)

Resume an interrupted Bambu Lab P1S print from a chosen layer.

Layer Rescue runs as a Bambu Studio post-processing script. After slicing, it asks for the last layer that printed correctly and rewrites the G-code so the job starts from the next layer, on top of the part that is still on the plate. Bambu Studio keeps its own filament mapping and `.gcode.3mf` metadata, and the preview shows the result before you send it.

> [!CAUTION]
> Resuming a print can drive the nozzle into the existing part. Stay at the printer during startup and be ready to stop it. See [SECURITY.md](SECURITY.md).

## Supported

- Bambu Lab P1S, single filament
- Bambu Studio G-code, by-layer printing, relative extrusion
- The part is still firmly attached to the same plate

Not supported yet: AMS/multi-filament jobs, by-object printing, spiral vase, other printer models.

## Install

**Windows:** download `LayerRescue-Setup-<version>-win-x64.exe` from [Releases](https://github.com/EmirhanSyl/layer-rescue/releases) and run it. The last page of the installer shows the command to paste into Bambu Studio.

**From source** (any OS, Python 3.10+; the window needs Tkinter):

```bash
pipx install git+https://github.com/EmirhanSyl/layer-rescue.git
```

## Set up Bambu Studio

1. Switch Bambu Studio to Advanced mode.
2. In the process settings, find **Post-processing Scripts**.
3. Enter the full path to `LayerRescue.exe` (or to the `layer-rescue` command), in quotes.

Studio may show a warning because post-processing scripts are executables. Only approve tools you installed from a source you trust.

## Resume a print

1. Find the last layer that actually got filament. If filament ran out at layer 462 but the printer stopped at 490, enter 461.
2. Slice the original project. The Layer Rescue window opens.
3. Enter the last good layer and choose a Z mode:
   - **Printer stayed powered on (`retained`)**: the printer kept its Z position. Nothing else to do.
   - **Printer was restarted (`manual`)**: after a power cycle Z is not homed. Clean the nozzle, move it over a flat printed area of the last good layer, and lower it until it just touches the surface. Do not move the part or the plate.
4. Check the preview and send the job.

For normal prints, click **Leave unchanged**.

### What the generated job does

It keeps the original header and settings, drops the start sequence and the finished layers, restores temperatures, fans and motion limits, lifts the nozzle, homes X/Y only (`G28 X`), purges at the rear chute, moves above the first point of the layer, lowers onto it and continues with the original G-code to the end.

It never homes Z and never runs bed leveling. In manual mode every Z move is relative to the position you aligned, so the job does not depend on the Z the printer thinks it is at after a restart.

The file is rewritten in place and a `.layer-rescue.bak` copy of the original is kept next to it.

## Command line

```bash
layer-rescue --analyze print.gcode
layer-rescue --last-layer 461 --z-mode retained print.gcode
layer-rescue --last-layer 461 --z-mode manual --confirm-manual-z-aligned print.gcode
```

`--nozzle-temp` and `--bed-temp` override the detected temperatures. Run `layer-rescue --help` for all options.

## Contributing

Bug reports with the printer model, firmware version and G-code are the most useful contribution. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Not affiliated with or endorsed by Bambu Lab.
