# GUI-4: wire paths and explicit splitting

Design contract, 2026-10-28. No electrical model, device law or solver changes.

Wire gains an immutable tuple of Waypoint(x, y) bends, at most 32 per wire.
Each coordinate is finite, real (not boolean), within +/-100000. A path runs
from its first node position through its bends to its second node position.
Bends are geometry only: they are never electrical nodes. Moving a junction or
component changes attached path endpoints; intermediate bends stay in world
coordinates. Straight/diagonal segments are supported; automatic orthogonal
routing, bend dragging and obstacle avoidance are deferred.

The Wire tool starts at a terminal/junction, adds bends on empty-space clicks,
and finishes at another explicit dot. A dashed preview shows the pending path.
Escape cancels, Backspace removes the last pending bend. Reroute Wire starts a
replacement path at the selected wire's first endpoint and must finish at its
original second endpoint. Straighten removes all bends from the selected wire.
Pending paths do not mutate history, dirty state or results; completion is one
undoable edit. Existing wire endpoint/name identities are preserved by rerouting.

Split Wire deliberately divides one selected segment at a projected click point.
Retain the old wire name on the first half and allocate a collision-free name
for the second half. Allocate a new junction, or explicitly reuse a free junction
at that point. Never reuse a node merely because coordinates coincide. Reusing
a placed terminal as a split junction is excluded; connect its dot with Wire.
Splitting preserves the old net and route geometry; connecting a reused junction
can deliberately merge nets. Deleting either half can split the net again.

The model API validates a point lies on the chosen nonzero segment, allowing
only 1e-8 world units of geometric roundoff. This tolerance never creates a
connection without the explicit split operation. Original wire endpoints cannot
be split; interior bends can. Consecutive coincident points are permitted after
endpoint movement, but zero-length segments cannot be split. All validation,
limits and duplicate-pair checks precede state replacement; failure is atomic.

At overlapping wires, Split requires the user to select the intended wire first.
To connect a crossing: select one wire away from the crossing, Split at the
crossing to create a junction; select the other wire away from the dot and Split
at that existing junction. Each step is explicit and undoable. Ordinary Wire,
Junction, movement, rerouting, overlap and crossing never split or merge paths.

Project v3 adds required `bends: [{x, y}, ...]` to every wire record (empty for a
straight wire). Load v1/v2 exactly as before, with empty bends; reject the new
field in older versions. Save v3 only. Existing v1/v2 fixtures remain unchanged;
add a separate routed example. Native electrical import/export remains v1.
Package 0.6.0; no dependencies added. Other project limits remain unchanged.

Acceptance: immutable/path bounds, pure-geometry electrical equivalence,
endpoint movement, reroute identity, straight/bent/diagonal splitting, explicit
crossing merge and deletion split, reference/source sign preservation, atomic
failure/limits, exact Undo/Redo, v1/v2/v3 round trips and malformed data, independent
divider solve, real Tk route/reroute/cancel/split/save workflows and installed checks.
