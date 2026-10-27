# Native circuit document, version 1

Status: version-1 contract implemented by PERSIST-1, 2026-10-27. This is an electrical
document format; schematic coordinates, cached solutions and external references
are excluded. No circuit file content is executed or fetched.

## Schema

UTF-8 JSON without a BOM. Every listed key is required and unknown keys are
rejected, including inside metadata, circuit and each element. Objects cannot
contain duplicate keys. Arrays preserve declared node/element ordering. Names
are case-sensitive and preserve spaces; no implicit ground name is assumed.

```json
{
  "format": "circuit-calculator",
  "version": 1,
  "metadata": {"title": "Divider", "description": "12 V input"},
  "circuit": {
    "nodes": ["g", "in", "out"],
    "reference_node": "g",
    "elements": [
      {"type": "voltage_source", "name": "V1", "plus_node": "in", "minus_node": "g", "voltage_volts": 12},
      {"type": "resistor", "name": "R1", "node_a": "in", "node_b": "out", "resistance_ohms": 1000},
      {"type": "resistor", "name": "R2", "node_a": "out", "node_b": "g", "resistance_ohms": 2000}
    ]
  }
}
```

The third element type is `current_source`, with exactly `type`, `name`,
`from_node`, `to_node`, `current_amperes`. All numerical parameters are JSON
numbers, not booleans or strings. Resistors are strictly positive; source values
may be signed or zero. Units and source orientation match circuit.py and
ARCHITECTURE.md. NaN/infinity, overflow and nonzero-to-zero conversion are errors.
Decimal parsing preserves numeric text until the model validates float conversion.
No expression syntax, SI prefixes, SPICE syntax or implicit type coercion exists.

`version` must be the JSON integer 1 (not true or 1.0). `reference_node` is a
declared string or null. Unsolvable/floating descriptions are still valid documents;
solvability belongs to DC analysis. Duplicate nodes/names, undeclared endpoints
and self-connections retain the model's existing validation rules.

## Resource limits

At most 1,048,576 UTF-8 bytes, JSON nesting depth 16, 10,000 nodes and 20,000
elements. Node/component names are at most 256 Unicode characters; title at most
256 and description at most 4096. Strings must encode as valid UTF-8. Empty title
and description are allowed. These are import/export limits, not restrictions
on programmatic Circuit construction. The same limits apply to generated output.
File reads stop after the byte limit plus one byte. Limits reduce accidental
resource exhaustion; this is not an arbitrary-size hostile-data service.

## APIs and file handling

`circuit_io.CircuitDocument(circuit, title="", description="")` keeps metadata
separate from the domain model. `dumps_document` / `loads_document` handle text;
`save_document` / `load_document` handle explicit local paths. Errors in the
document raise `CircuitFormatError(ValueError)` with field context. Ordinary
filesystem errors remain OSError subclasses. No schema migration is implied:
unsupported versions require a future explicit migrator, never best-effort loading.

Output is deterministic: sorted object keys, two-space indentation, Unicode
characters, a trailing newline, and preserved array ordering. Repeated load/dump
cycles preserve normalized model floats. Byte identity with hand-authored input
is not promised.

Saving validates/serializes before touching the destination, writes and fsyncs a
temporary sibling, then atomically installs it. Default creation uses a hard link
so existing destinations are never replaced, including concurrent creation.
`overwrite=True` explicitly opts into os.replace. The temporary sibling is
removed on failure. Parent directories must exist; filesystem errors are exposed.
Default save requires filesystem hard-link support. Replacement provides atomic
visibility where the filesystem supports it, not a directory-fsync/power-loss
durability guarantee. Permissions/metadata of an overwritten file are not retained.

## Acceptance and scope

Round-trip all R/V/I parameters, ordering, missing reference, metadata and Unicode;
reject malformed/oversized/deep data, duplicate/unknown fields, wrong types,
unsupported versions and unsafe numeric values. Verify existing-file preservation,
replacement and failure cleanup. Construct, save, load and solve analytical DC
examples, then compare results and conservation checks. Install the new module
in the package and run core-only/full-DC checks. The file-based DC CLI
applies a 200-unknown size guard before allocating a dense matrix.

## DC command

`circuit-calculator dc FILE.json` (or `python -m circuit_calculator dc FILE.json`) loads the
document and writes deterministic, indented JSON with `title`, `reference_node`,
`node_voltages_volts`, per-element `voltage_volts`/`current_amperes`/`power_watts`,
and numerical diagnostics. Values retain float precision; there is no display
rounding policy hidden in the export. Sign conventions match the solver.
Exit code 0 means success, 1 a file/model/solver/dependency failure (stderr error,
no partial stdout result), and 2 invalid command arguments. No arguments retain
the existing interactive formula menu. Dense CLI size is capped at 200 unknowns
(non-reference nodes plus voltage-source currents); the programmatic solver's
size policy is unchanged. No GUI, SPICE import or graphical layout is implied.
