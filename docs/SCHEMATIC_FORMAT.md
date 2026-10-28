# Schematic project format v3, with v1/v2 loading

Date: 2026-10-28. A separate UTF-8 JSON document preserves editor state without
changing native electrical circuit format v1. File suffix: `.ccproj.json`.

```text
{
  "format": "circuit-calculator-project",
  "version": 3,
  "document": <complete native electrical document v1, before wire resolution>,
  "layout": {
    "positions": [{"node": "g", "x": 160.0, "y": 420.0}, ...],
    "wires": [{"name": "W1", "first": "return", "second": "g", "bends": [{"x": 500.0, "y": 500.0}, ...]}, ...],
    "placements": [{"element": "R1", "x": 330.0, "y": 160.0, "rotation": 0}, ...]
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

The embedded document stores original node/terminal identities and uncompiled R/V/I
endpoints, reference selection, title and description. Loading validates the
existing CircuitDocument, Schematic, Position and Wire rules without invoking a
solver or compiling wires. Valid unfinished/floating/shorted editor states can be
saved even when DC analysis would reject them. There is no duplicate compiled
network to synchronize, and no cached result is trusted from disk.

Limits: 1,048,576 UTF-8 bytes, nesting depth 16, 100 free junctions, 200 components,
500 total nodes including dedicated terminals, and 800 wires. Exactly one position
per declared node; all wire endpoints declared;
wire names and unordered endpoint pairs unique. Wire names/endpoints are at most
256 Unicode characters. Coordinates are finite and within +/-100000. Export
normalizes coordinates to floats. Zoom is in [0.4, 2.5]; scroll fractions are in
[0, 1]. Scroll is Tk's leading-edge fraction, not pixel coordinates. A different
window/viewport size may clamp fractions to keep the view inside its scroll region;
Tk also quantizes scrolling to pixel boundaries.
View numbers round to normal floats, with no arbitrary epsilon acceptance.

Every v2/v3 layout requires `placements`, including an empty array for a wholly
junction-based graph. Each record has exactly element/x/y/rotation; element is a
unique existing component name, at most 256 characters. Rotation must be an integer
0, 90, 180 or 270 (clockwise). Coordinates follow the position numeric rules.
The placed component owns its two terminal nodes: no other element may use them
directly; wires may connect to them. Terminal positions must exactly match the
center plus/minus 60 world units on the rotated axis. No tolerance repairs or
coordinate-inferred connectivity are performed. See COMPONENT_EDITING.md.

Every v3 wire requires `bends`, an array of at most 32 objects with exactly x/y.
Coordinates follow the position rules (finite numbers, +/-100000, no booleans or
nonzero underflow). An empty array denotes a straight wire. The path runs from
first node position through the bends to second node position. Bends are never
electrical nodes; geometry and crossings cannot create connectivity. Consecutive
coincident points are legal after endpoint movement. See WIRE_ROUTING.md.

## Version compatibility

The loader accepts v1's original shape with only positions/wires in layout, at
most 100 nodes and 400 wires. It preserves the original graph/geometry with an
empty placement list; it does not convert components on load. V1 rejects a
placements field. V2 adds placements and uses the current node/wire limits, but
has no bends field. Both old versions load with empty bend tuples and reject
the new field. Unsupported versions are errors. All new saves use v3, even for
straight wires. Older application versions cannot read v3; keep an original
file or use Save As when compatibility with an older application is needed.
Native electrical import/export remains format v1 and contains no layout.
Original v1/v2 fixtures remain unchanged beside a separate v3 routed example.

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
checks. GUI-3 additionally verifies rotation/movement preserve terminal identity,
source polarity and compile/solve equivalence, strict placement geometry, v1
loading and v2 output. GUI-4 verifies routed paths/splits, strict bend schema,
v1/v2 compatibility and v3 output. Local package is 0.6.0; native electrical format
remains v1. No new devices or solver algorithms are added.
