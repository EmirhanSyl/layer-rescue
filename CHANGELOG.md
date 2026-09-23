# Changelog

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
