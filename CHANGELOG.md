# Changelog

## 0.2.2 - 2026-09-24

- Fix: after a printer restart, restarted (manual) mode printed in the air. The P1S has not homed Z after
  a power cycle, so the firmware's absolute Z did not match the manually aligned nozzle and the absolute
  `G1 Z...` moves drove the bed down (about 11 mm in the reported case). Restarted mode now rewrites every
  Z move in the preamble and the retained layers as a relative move from the aligned position (`G91` /
  `G1 Z±Δ` / `G90` / `M83`), tracking the slicer's absolute Z so the heights are exact and do not depend on
  `G92 Z` or the firmware's Z state.
- Restarted mode turns off soft endstops (`M221 X0 Y0 Z0`) the same way the stock P1S start G-code does.
- Travel moves that also change Z are split: lift first then travel, or travel first then lower.
- Restarted mode refuses conditional firmware blocks that change Z without restoring it, `G92 Z` in the
  source, and extruding moves that change Z. Validation rejects any absolute Z move in restarted mode.
- Retained mode is unchanged.

## 0.2.1 - 2026-09-24

- Fix: resumed jobs extruded no filament. Bambu firmware switches E to absolute mode on `G90`, and the
  resume block issued `G90` after its `M83` (for the Z safety lift), so every relative E value ran as an
  absolute position and the extruder only moved back and forth around zero. `M83` is now re-issued after
  the last `G90`, and output validation rejects any extrusion that would run in absolute E mode.
- The source scanner now applies the same `G90`/`G91` extrusion-mode rules.
- Purge 30 mm (`purge_length_mm`) over the rear chute, then shake/wipe, before returning to the part.
- Travel to the first XY point of the resumed layer at the lifted Z before descending.

## 0.1.0 - 2026-09-22

- Initial P1S single-filament MVP.
- Bambu Studio post-processing integration with a Tkinter layer selector.
- Conservative layer/Z parsing and machine-state reconstruction.
- Guards against Z homing, bed leveling, multi-filament jobs, by-object printing, spiral vase, and absolute extrusion.
- Atomic in-place rewrite with automatic backup.
- CLI analysis and batch conversion modes.
