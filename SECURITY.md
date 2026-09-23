# Security and physical safety

Layer Rescue processes untrusted text files and emits machine-control commands. Treat both software security and physical motion as security boundaries.

## Supported reports

Please report command injection, unsafe path handling, archive traversal, unexpected executable startup commands, accidental Z homing/bed leveling, incorrect layer selection, and unsafe temperature/tool sequencing privately before public disclosure.

## Operator requirements

- Keep the printer supervised during startup.
- Be ready to stop the printer immediately.
- After a power cycle or Z stepper release, use manual-reference mode only after aligning a clean nozzle to the last successful layer surface.
- Never use retained-Z mode after a power cycle, Z step loss, or Z motor release.
- Never resume after plate movement or part movement.
- Confirm the actual last deposited layer; sensor detection time is not sufficient.
- Clean the nozzle and inspect the generated Preview.
- Use matching material; filament mapping does not rewrite material temperatures or flow behavior.

The project provides no guarantee that a physically failed print is recoverable.
