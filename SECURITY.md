# Security and physical safety

Layer Rescue reads untrusted files and writes commands that move a machine. A bug that makes the printer home Z over a part, crash the nozzle or run unexpected commands is treated as a security issue.

## Reporting

Report privately through [GitHub security advisories](https://github.com/EmirhanSyl/layer-rescue/security/advisories/new). Please do not open a public issue first.

Useful details: Layer Rescue version, printer and firmware version, Z mode, the source and generated G-code, and what the printer did.

Examples of what to report:

- Z homing or bed leveling in the output
- wrong start layer or Z height
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

Layer Rescue cannot guarantee that a failed print is recoverable.
