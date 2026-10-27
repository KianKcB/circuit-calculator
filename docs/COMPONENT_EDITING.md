# GUI-3: placed symbols and terminal identity

Design contract, 2026-10-27. Preserve Circuit, R/V/I constitutive laws and DC
solver behavior. Geometry never creates electrical connections.

## State and editing

Schematic gains an immutable `placements` tuple of ComponentPlacement(element,
x, y, rotation). Rotation is exactly 0/90/180/270 degrees clockwise in canvas
coordinates. A symbol has terminal a/plus/from at center minus 60 units along its
axis, and b/minus/to at center plus 60. Each placed component owns two dedicated
electrical node identities. Wires continue to connect explicit node identities,
including these terminals. Terminal identifiers are allocated collision-free;
they do not depend on pixel positions or mutable displayed component names.

Exactly one existing Position represents each terminal. Validation enforces its
derived position and exclusive ownership by that component, preventing geometry
from drifting out of sync. A terminal cannot move/delete independently; select
its component body instead. Reference selection may target a terminal or junction.

Free placement creates R/V/I plus two unconnected terminals. Moving/rotating a
placed component updates its terminal positions; all wire identities/connections
remain unchanged. Wire crossings, coincident symbols and proximity never connect.
Deleting a placed component removes its terminals and incident wires, and clears
reference if necessary. At least one node must remain; if deleting the last
component would remove every node, ask the user to add a junction first.

Existing junction-based components remain valid. On first move/rotation, allocate
dedicated terminals and two explicit wires back to the original endpoints. This
is an electrical equivalence transformation: original nodes precede the generated
nodes, so resolved node names, source orientation and solved results are preserved.
Undo restores the exact previous representation in one step.

Limits become 100 free junctions, 200 components, at most 500 total nodes (including
owned terminals), 800 wires, and the existing 200 GUI DC unknowns. The additional
wire capacity accommodates explicit connections when converting old symbols.
Native circuit import retains its existing 100-junction limit. No implicit net
contraction occurs except the existing explicit wire compilation.

## Project compatibility

Project v2 adds required `layout.placements`, an array of objects with exactly
element/x/y/rotation. Other project fields and view rules remain unchanged.
Positions include owned terminals and must agree exactly with derived geometry.
Rotation must be a JSON integer, not a boolean/float. Unknown fields/versions,
duplicate placements, missing elements, shared terminals and invalid geometry
are rejected. Native electrical format v1 is unchanged.

Load both project v1 and v2. A v1 file retains its graph/layout unchanged with
an empty placements tuple. Saving writes v2, even if no components are placed;
older application versions cannot read v2. Save As can retain an original v1 copy.
Do not rewrite existing v1 example files. Add a separate placed-divider example.
Local application version: 0.5.0. No new dependencies or solver devices.

## GUI workflow and acceptance

R/V/I tools place a symbol on empty grid space. Choosing two existing free
junctions retains direct-connection creation. Use Wire on explicit terminal dots
or junctions. Select/drag a component body to move it; Rotate 90° (or R while
focused on the canvas) rotates the selected body. Terminal labels expose
component/terminal names rather than internal generated identifiers.

Moving or rotating invalidates current results conservatively, as other editor
edits do. Undo/Redo, dirty state and project save/reopen include placements.
Validate geometry/topology before applying an edit. Failed operations leave the
document unchanged. Routing remains straight segments; segment splitting and
automatic junction creation remain future work.

Acceptance: four rotations and wire attachment invariants, no proximity-derived
connections, conversion equivalence including current/voltage-source orientation,
placed-component deletion/reference cleanup, exact Undo, v1/v2 strict round trips,
project malformed-data cases, analytical placed-divider results, real Tk placement/
drag/rotate/wire/save/reopen workflows and installed package regressions.
