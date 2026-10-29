# RESULTS-2: selected item inspection

Design contract, 2026-10-29. Add a read-only Selected item tab alongside All results
in the existing right panel. This is a presentation client of accepted DCResult
snapshots, not another solver or a persistent annotation format.

Selecting a component, junction, terminal or wire opens Selected item. Display
component type/value, human-readable terminal labels, voltage polarity and positive
current direction. With a current result, show voltage/current/power using the
existing nine-significant-digit SI formatter. Classify positive power as absorbed,
negative as delivered and exact zero as zero; do not invent a new tolerance.
Source power/current signs must match the full results and CSV.

Junctions and terminals show their resolved electrical net and whether that net
contains the reference, plus current net voltage when available. Wire inspection
shows endpoints, bend count and resolved net voltage. Do not infer an individual
wire current or power: wire contraction stores no branch-current unknown for each
drawn wire, and redundant wire paths do not have uniquely reported currents.
Shared coordinates and crossings retain their existing non-connectivity rules.

Without a current result, show topology/conventions and a clear Simulate DC prompt,
never placeholder numerical zeros. Edits, Undo/Redo, loading, new solves and stale
worker completion must not leave old numbers in the inspector. Camera changes,
selection and tab changes preserve results and the electrical revision. Inspection
uses the persisted state, not transient drag or paste preview geometry.

Keep text construction in a pure inspection.py helper. Its optional result must
be a current accepted DCResult from the controller's EditorSession; this formatter
does not establish correspondence between arbitrary external state/result pairs.
Handle absent/deleted selections without crashing or displaying unrelated values.
Changing selection never changes circuit, history or file data. Tabs/selection
are transient and not saved in project v3. Avoid resetting a user's inspector
scroll/selection when unchanged text is redrawn. Both text views need scrollbars.
The panel's new widget sizes may clamp an old saved pan to the current viewport;
graph/layout data and file schemas stay unchanged. Fit Circuit remains available.
Document shortcuts retain their scope in both read-only text views; native copy
and text selection remain available. Keep Tk/NumPy imports optional at import time.

Acceptance: analytical divider R/V/I orientation and delivered/absorbed signs,
node aliases/reference/terminal labels, wire-current non-inference, invalid/absent
selection, stale/cleared result behavior, exact data/export preservation, GUI tab/
click/solve/edit/history/camera/paste/cancel flows and fresh installed checks.
No new dependency, model law or native v1/project v3/CSV v1 field is needed.
