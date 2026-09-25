# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- CI on Windows and Linux (Python 3.10–3.13).
- Release workflow: pushing a `v*` tag builds the Windows installer, wheel and sdist and publishes them on GitHub Releases with SHA-256 checksums. Optional PyPI upload.
- `packaging/windows/build.ps1` to build the installer locally.
- Issue and pull request templates, code of conduct, release guide.

### Changed

- The version is defined once in `src/layer_rescue/_version.py`.
- Installers are no longer committed to the repository; they are attached to GitHub Releases.

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

[Unreleased]: https://github.com/EmirhanSyl/layer-rescue/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.2.2
[0.2.1]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.2.1
[0.2.0]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.2.0
[0.1.0]: https://github.com/EmirhanSyl/layer-rescue/releases/tag/v0.1.0
