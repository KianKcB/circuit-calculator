# GUI-5: bend handles and optional right-angle routing

Contract, 2026-10-28. Preserve Circuit/device laws/DC results and project v3.

Selecting a wire in Select mode shows square handles for its saved bends.
Drag one handle to a 20-unit grid point. Preview remains outside document/history
and does not change the scroll region. Release commits one edit; Escape cancels.
A click without dragging does not snap an off-grid bend. Delete removes the
selected bend, retaining the wire and both endpoint identities. Shift-click the
interior of a selected wire segment to insert a projected bend; it is geometry,
not a junction. Explicit Split Wire remains the only segment-to-junction action.
Handle tags carry the wire name separately from the bend index so colon/Unicode
names remain valid. Changing tools/documents/history clears transient selection.

An optional Right-angle wires checkbox applies deterministic Manhattan routing
to newly drawn/rerouted paths. Space toggles horizontal-first/vertical-first
while a wire is pending. Each diagonal anchor-to-anchor leg acquires one elbow.
Remove duplicate points and collinear points strictly between their neighbors;
retain backtracking/corners. Endpoints stay exact, including off-grid terminals.
Orthogonalize converts only the selected wire. No obstacle avoidance is promised.
Generated routes still obey the 32-bend limit; failure preserves state/pending
anchors rather than truncating a path. Preferences are transient controller state,
not circuit/project properties, so changing them does not make a document dirty.

Right-angle geometry is explicit output, not a persistent constraint: subsequent
endpoint/handle movement can make a segment diagonal. Conversion must be requested
again to restore right angles. This keeps existing movement semantics predictable
and avoids implicit rerouting of old projects. Keep the normal free-path default.

Model API: insert_wire_bend, move_wire_bend, remove_wire_bend, orthogonalize_wire;
use frozen Waypoint values and validate indices/types/bounds before replacing
state. Simplification/conversion never changes electrical nodes/wires/reference.
No schema migration or dependency; local package 0.7.0.

Acceptance: hand-derived routes in both orders, duplicate/collinear/backtracking
cases, exact endpoint/source identity, bend limits and invalid edit rollback,
one-step Undo/Redo/cancel, off-grid click/no-op, zoomed handle hit tests, pending
preview/commit consistency, v3 round trips and analytical divider equivalence.
Run headless and real Tk workflows on both maintained local interpreters and
fresh installed checks before committing. User authorized git add/commit for
completed local batches on 2026-10-28; pushing remains a separate user action.
