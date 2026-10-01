# Security and physical safety

Layer Rescue reads untrusted files and writes commands that move a machine. A bug that makes the printer home Z over a part, crash the nozzle or run unexpected commands is treated as a security issue.

## Reporting

Report privately through [GitHub security advisories](https://github.com/EmirhanSyl/layer-rescue/security/advisories/new). Please do not open a public issue first.

Useful details: Layer Rescue version, printer and firmware version, Z mode, the source and generated G-code, and what the printer did.

Examples of what to report:

- Z homing or bed leveling in the output
- wrong start layer or Z height
- in insert mode: a move below the part top after the pause, or a wall line that overlaps the part
- unsafe temperature, tool change or extrusion sequence
- command injection or unsafe path handling in the post-processing integration

## Supported versions

Only the latest release gets fixes.

## Before running a recovery job

- Stay at the printer during startup and be ready to stop it.
- Use the restarted (manual) mode after any power cycle or Z motor release, and only after touching the clean nozzle to the last good layer. Never use the retained mode in that case.
- Do not resume if the part or the plate has moved.
- Enter the last layer that actually got filament, not the layer where the printer noticed the problem.
- Check the Bambu Studio preview and use the same material.
- If you accept the risks of an untested printer or multi-filament job, watch the whole start sequence: the parking, purging and homing moves were written for the P1S.

## Before running an insert-mode job

- Measure the part height at its highest point with calipers. A part taller than entered is hit by the nozzle.
- Stay at the printer until the first layers on the part are down.
- Do not remove or shift the plate when seating the part. Press the part in gently so the wall stays on the bed.
- Seat the part the same way round as in Bambu Studio.

Layer Rescue cannot guarantee that a failed print is recoverable.
