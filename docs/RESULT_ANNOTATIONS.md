# ANNOTATE-1: optional node-voltage labels

Scope: read-only DC node voltages beside existing junction/terminal names.
An opt-in Node voltages checkbox controls presentation only. No branch-current,
power, wire-current or color-scale inference. No project/schema changes.

Every label uses the exact endpoint identity, resolves explicit wire aliases,
and reads only the current accepted EditorSession.result. Values are relative
to the solve reference and use nine significant digits with SI prefixes. All
aliases of the reference net carry `(ref)`. This is a node voltage, not a
two-point difference; changing reference shifts these labels as expected.
The Voltage probe retains its separate reference-independent difference contract.

Pure annotations.py formats data without importing Tk/NumPy or solving. A missing
result yields no labels; missing net entries yield no fabricated zero. Invalid
non-finite values are rejected. The caller establishes revision correspondence.

The renderer places separate decorative text below/right of each endpoint name,
using fixed readable font size and no electrical entity tags. Values cannot create
connections or override hit targets. Dense/overlapping layouts may still overlap;
automatic collision avoidance and movable annotations remain future work.

Annotation bounds participate in Fit but do not change the base scroll region.
This preserves camera position, saved view fractions and dirty state when labels
are toggled or simulation results arrive/clear. Explicit Fit/zoom/pan retain their
usual saved-camera behavior. The checkbox is transient, defaults off per window,
and may remain enabled across new/open with no values until a successful solve.

Edit, Undo/Redo, document replacement, new solves, failures and rejected stale
worker completions must never show old values. Geometric drag previews suppress
labels; cancellation may restore a still-current result. Existing graph, model,
solver, history, serialization and exports remain unchanged.

Acceptance: analytical signed/reference/alias values, display rounding and missing
data; real canvas labels and electrical-tag isolation; camera/dirty preservation;
Fit including text at multiple zooms; edit/history/open/pending/failure freshness;
minimum-window controls; source/core and isolated installed regression checks.
