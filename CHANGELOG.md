# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Printer profiles. The machine-specific part of the resume sequence (filament station, purge and wipe, X homing, tool selection, temperatures, insert-mode park position) now depends on the printer family instead of always using P1S moves.
- Experimental H2 series sequence (H2D, H2D Pro, H2S, H2C), behind the untested-setup confirmation: purge and wipe with the firmware's `G150.3` / `G150.2` / `G150.1` instead of P1S coordinates (which are on the H2 bed), tool and hotend selected together (`M620 S<n>A H<h>`, `T<n> H<h>`) with the job's `M620.10` / `M620.11` flush and cut settings, temperatures addressed to the extruder (`M104/M109 S.. T<e>`), and `G28 X T300` like the stock H2 start. The cut sequence (`M620.11 S…`) is only sent inside an `M628 S1` / `M629` block and the tool change is followed by `M628 S0` / `M629`, as in the stock H2 start. Checked against real H2C and H2D Benchy slices: the H2D (two nozzles, no hotend rack) uses the same sequence; hotend remap (`M620 N`) is only sent when the job's own start G-code sends it (H2C). The H2D Pro selects the tool without a hotend (`M620 S0A`, `T0`, no `H`); the tool selection now mirrors the job instead of requiring `T<n> H<h>`. The single-nozzle H2S sends temperatures without an extruder index and records no cut sequence; Layer Rescue now does the same there (checked against a real H2S slice). Restarted (power cut) mode on the H2 is experimental and warned about up front: after a power cut Z is not homed, and the Z behaviour of `G150.x` and `G28 X T300` on an unhomed axis is not documented. Like the stock H2 start G-code (`G380 S2 Z42` / `Z-12` before these commands), the bed is lowered 30 mm (relative, less if the part is close to the maximum height) before `G28 X T300` and the purge/wipe macros, and again before the end G-code's `G150.x`.
- Bambu Lab A1 sequence (not the A1 mini), behind the untested-setup confirmation: the P1S moves put the purge at Y265 over the rear edge of the A1 bed and drove to the P1S cutter at X20 Y-3. The A1 now purges and wipes off the bed on the left (`X-48.2`, shaken against `X-28.5`) and loads the filament inside `M620 S<n>A … M621` like the stock A1 start G-code.
- Bambu Lab P2S sequence (experimental, behind the untested-setup confirmation). The P2S has the P1S's 256 mm CoreXY frame but its stock G-code is the single-nozzle H2S's: `G28 X T300`, purge and wipe with `G150.3` / `G150.2` / `G150.1`, `G1 Y-16` away from the bin, no layer-num comments. It used to fall back to the P1S moves. Power-cut mode as on the H2.
- Bambu Lab A2L sequence (experimental, behind the untested-setup confirmation). The A2L is a bed slinger that uses the H2 firmware macros: purge and wipe with `G150.3` / `G150.2` / `G150.1`, leaving the bin with `G1 X20` (relative) like its stock start, single nozzle without extruder index or hotend. Its stock start homes X and Z together (`G28 X Z P0 T300 W`), so Layer Rescue sends a plain `G28 X`. Power-cut mode lowers the bed 30 mm before the macros as on the H2, and warns to turn timelapse off (the A2L timelapse calls `G150.3` 0.4 mm above the part on every layer).
- Layers are found in G-code without `; layer num/total_layer_count` comments (the A2L layer-change G-code only writes `M73 L<n>`).
- Bambu Lab A1 mini sequence: same structure as the A1 with its own positions (purge at `X-13.5`, shaken against `X0`), from the stock A1 mini start G-code.

### Changed

- Insert mode parks at a rear corner of the printer's own bed, inside the area every nozzle can reach (unchanged on the P1S: X236/X20, Y250).

### Fixed

- Restarted (manual Z) mode turned soft endstops off with `M221 X0 Y0 Z0`, the P1S command. The A1, A1 mini and H2 start G-code uses `M211 X0 Y0 Z0`; each printer now gets its own.
- Insert mode on the H2: the standby and adhesion temperatures are sent to the printing extruder (`M104 S.. T<e>`).

- The purge before resuming ran at a fixed `F200` (about 8 mm³/s), several times what a 0.2 mm nozzle profile allows (2 mm³/s for PLA), so the extruder could skip or grind. The purge feed now follows the active filament's `filament_max_volumetric_speed` (80 %, never faster than before). Applies to resume and insert mode.

## [1.0.1] - 2026-10-01

First release on PyPI: `pipx install layer-rescue`.

### Changed

- README links and images use full GitHub URLs, so the project page on PyPI shows them correctly.
- The README installs Intel Macs, Linux and other systems from PyPI instead of from source.
- Test write-ups play their videos from GitHub; the `.mp4` files are no longer in the repository. The README shows a photo of the rescued test prints.

### Fixed

- The release workflow and build scripts read the version without importing the package (the 1.0.0 release run failed before `pyclipper` was installed).

## [1.0.0] - 2026-10-01

First stable release. Every mode has been tested on a real P1S; the write-ups are in [docs/tests](docs/tests/).

### Added

- Untested setups can be tried at your own risk: jobs for other printers or with several filaments (AMS) are no longer refused outright. The window explains why the job is untested and asks you to accept the risks (CLI `--allow-untested`); the accepted risks are listed in the warnings. By-object printing and spiral vase are still refused.
- Multi-filament jobs resume with the filament slot that was active at the selected layer instead of always slot 0.
- Real-printer test write-ups in English and Turkish (`docs/tests/`), linked from the README.
- App icon for the window, the Windows `.exe` and installer and the macOS app (`packaging/icon/make_icon.py` redraws it).
- The window is available in English and Turkish. Switch with the **English / Türkçe** buttons at the top right; the change applies immediately and is remembered. On first start the language follows the system language.
- Error messages and warnings from the conversion are shown in the selected language (CLI output stays English).
- Insert mode (beta): seat a loose, broken or finished part in a holding wall and print on top of it. The wall is derived from the part's own sliced outline below the wall height (the opening only grows with height so the part can be lowered in), with clearance, brim and a lead-in chamfer. The job pauses (`machine_pause_gcode`, `M400 U1` on the P1S) above the part, then continues with the retained-mode resume sequence and every Z shifted to the measured part height. The first layers on the part are printed hotter, slower and without part cooling. GUI tab with a top-view preview; CLI `--part-height` / `--part-layer` with `--confirm-attended`.
- Insert mode reprints the supports below the part height that carry supports above it (tree supports inside a hollow part or next to it), before the pause, only where the lowered part cannot hit them and only on top of support printed below. The wall keeps clear of them. `--no-reprint-supports` / GUI checkbox.
- Insert mode leaves 0.4 mm under the part's overhangs, so the part stands on its own bottom instead of resting on the wall, and the wall no longer fills the inside of hollow parts deeper than 3 mm.
- Insert-mode output validation: wall lines never inside the part's clearance, no XY move below the part top after the pause, nothing printed below the part top afterwards, bed and excluded-area checks, single object and no prime tower.
- macOS support: `LayerRescue.app` for Apple Silicon, built by the release workflow with `packaging/macos/build.sh` (not yet signed with a Developer ID). Intel Macs can install from source.
- Opening the app directly, without Bambu Studio, shows the command to paste into Post-processing Scripts.
- CI on Windows, macOS and Linux (Python 3.10–3.13).
- Release workflow: pushing a `v*` tag builds the Windows installer, the macOS app, the wheel and the sdist and publishes them on GitHub Releases with SHA-256 checksums. Optional PyPI upload.
- `packaging/windows/build.ps1` to build the installer locally.
- Issue and pull request templates, code of conduct, release guide.

### Changed

- README rewritten for first-time readers: what it can do, real-world tests, picking the layer, several objects, limitations and what's next, how to share results, and credits for the test models, with screenshots of the window. The Turkish README follows it.
- Clearer window: a file summary, a short explanation per tab, and numbered steps (where the print stopped, whether the printer was restarted, safety checks, options).
- The safety confirmations are grouped under a **Safety checks** heading that says what they are for. Only the check for the selected Z mode is shown, and **Create G-code** stays disabled until the required checks are ticked; the status line says what is missing.
- The resume tab shows the layer and Z that printing restarts at while you type.
- Insert tab: colour legend for the top view, preview result and warnings under **Result**, advanced settings next to the preview.
- `core.py` is split into `gcode`, `machine_state`, `resume` and `fileio` modules; `layer_rescue.core` still exports the same names.
- First runtime dependency: `pyclipper` (polygon offsets for the holding wall).
- The version is defined once in `src/layer_rescue/_version.py`.
- Installers are no longer committed to the repository; they are attached to GitHub Releases.

### Fixed

- Jobs with independent support layer heights (Bambu counts extra layers in the markers' total, e.g. `358/360`) were rejected by the output validation in both modes.

## [0.2.2] - 2026-09-24

### Fixed

- Restarted (manual) mode printed in the air after a power cycle. Z is not homed at that point, so absolute `G1 Z` moves did not match the aligned nozzle and the bed dropped (about 11 mm in the reported case). Every Z move is now written as a relative move from the aligned position, so the result no longer depends on `G92 Z` or on the Z the firmware believes it is at.

### Changed

- Restarted mode turns off soft endstops (`M221 X0 Y0 Z0`), as the stock P1S start G-code does.
- Travel moves that also change Z are split: lift before travelling, lower after travelling.
- Restarted mode rejects sources it cannot convert safely: conditional firmware blocks that change Z, `G92 Z`, and extruding moves that change Z.

## [0.2.1] - 2026-09-24

### Fixed

- Resumed jobs extruded no filament. On Bambu firmware `G90` also switches the extruder to absolute mode, and the resume block sent `G90` after `M83`. `M83` is now sent after the last `G90`, and the output is rejected if any extrusion would run in absolute mode.

### Added

- 30 mm purge and nozzle wipe at the rear chute before returning to the part (`purge_length_mm`).
- The nozzle moves above the first point of the resumed layer before lowering onto it.

## [0.2.0] - 2026-09-23

### Added

- Z reference modes: `retained` (printer stayed on) and `manual` (printer was restarted, nozzle aligned by hand). CLI options `--z-mode` and `--confirm-manual-z-aligned`.

### Deprecated

- `--assume-z-known`; use `--z-mode retained`.

## [0.1.0] - 2026-09-22

### Added

- First release for the Bambu Lab P1S, single filament.
- Bambu Studio post-processing integration with a layer selection window.
- Layer/Z parsing and machine state reconstruction.
- Guards against Z homing, bed leveling, multi-filament jobs, by-object printing, spiral vase and absolute extrusion.
- Atomic in-place rewrite with a backup file.
- CLI analysis and batch conversion.

[Unreleased]: https://github.com/EmirhanSyl/layer-rescue/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v1.0.1
[1.0.0]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v1.0.0
[0.2.2]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.2.2
[0.2.1]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.2.1
[0.2.0]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.2.0
[0.1.0]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.1.0
