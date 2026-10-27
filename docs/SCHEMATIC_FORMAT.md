# Schematic project format v1 and GUI-2 contract

Date: 2026-10-27. A separate UTF-8 JSON document preserves editor state without
changing native electrical circuit format v1. File suffix: `.ccproj.json`.

```text
{
  "format": "circuit-calculator-project",
  "version": 1,
  "document": <complete native electrical document v1, before wire resolution>,
  "layout": {
    "positions": [{"node": "g", "x": 160.0, "y": 420.0}, ...],
    "wires": [{"name": "W1", "first": "return", "second": "g"}, ...]
  },
  "view": {"zoom": 1.0, "scroll_x": 0.0, "scroll_y": 0.0}
}
```

The snippet describes the schema; angle brackets/ellipses are not JSON syntax.
Every listed field is required. Reject unknown fields, duplicate object keys,
non-integer/unsupported versions, malformed Unicode, non-finite numbers, booleans
as numbers and nonzero values lost to float underflow. No expressions, external
files or executable models are evaluated. Reuse a shared bounded JSON/atomic-file
implementation with native circuit persistence so their safety rules cannot drift.

The embedded document stores original junction identities and uncompiled R/V/I
endpoints, reference selection, title and description. Loading validates the
existing CircuitDocument, Schematic, Position and Wire rules without invoking a
solver or compiling wires. Valid unfinished/floating/shorted editor states can be
saved even when DC analysis would reject them. There is no duplicate compiled
network to synchronize, and no cached result is trusted from disk.

Limits: 1,048,576 UTF-8 bytes, nesting depth 16, 100 junctions, 200 components and
400 wires. Exactly one position per declared node; all wire endpoints declared;
wire names and unordered endpoint pairs unique. Wire names/endpoints are at most
256 Unicode characters. Coordinates are finite and within +/-100000. Export
normalizes coordinates to floats. Zoom is in [0.4, 2.5]; scroll fractions are in
[0, 1]. Scroll is Tk's leading-edge fraction, not pixel coordinates. A different
window/viewport size may clamp fractions to keep the view inside its scroll region;
Tk also quantizes scrolling to pixel boundaries.
View numbers round to normal floats, with no arbitrary epsilon acceptance.

APIs in project_io.py: frozen ViewState and SchematicProject containers,
`dumps_project` / `loads_project`, `save_project` / `load_project`.
Malformed data raises ProjectFormatError(ValueError); filesystem failures remain
OSError subclasses. Deterministic output sorts object keys and preserves array
ordering. Default atomic saves refuse existing paths; overwrite=True explicitly
uses replacement. Same filesystem/link and durability limits as electrical saves.
Results, Undo/Redo history, active tools and selection are intentionally not saved.

## GUI workflow

Open Project restores graph, layout and view. Save Project reuses the current
project path; Save As chooses a new one and asks before replacing an existing
file. Import Circuit and Export Circuit retain the distinct electrical-only
workflow. Document changes and camera changes mark the project dirty; saving
clears it only after success. Undo back to a saved state can clear dirty state.
Exporting a circuit does not mark graphical work saved.

Changing documents or closing with unsaved changes offers Save / Discard / Cancel.
Canceling Save As, declining replacement, or failing a save keeps the current
document open/dirty. Failed project load never partially replaces the editor.
Loading/new/import resets history and increments the same monotonic revision,
even when the graph is identical, so pending old results cannot be accepted.
Camera-only changes preserve electrical results. Opening projects clears results.

Acceptance: exact state/metadata/view round trips and deterministic output,
malformed/version/type/numeric/resource cases, no-clobber and failed-write cleanup,
save/load/compile/solve equivalence, GUI save/reopen/dirty/cancel/failure workflows,
stale-result rejection across document boundaries, and fresh installed API/CLI
checks. Bump local package to 0.4.0; both file format versions remain 1. No new
devices, solver changes, free component placement or wire-routing behavior.
