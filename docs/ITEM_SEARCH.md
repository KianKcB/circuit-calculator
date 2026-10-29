# GUI-10: find and reveal an existing item

Design contract, 2026-10-29. Add Find item / Ctrl+F for the bounded editor. A modal
list filters existing components, junctions, terminals and wires by name or human
terminal label. Match plain case-folded substrings, preserving whitespace; do not
interpret expressions, regexes or netlist syntax. Limit search text to 256 valid
Unicode characters. Empty query lists all items in deterministic declared order.

Rows keep exact (kind, identifier) values separate from display labels. Duplicate
names in different namespaces remain distinct rows. Internal row IDs are generated
independently of user names. Terminal labels can be R1.a/from/+/− while identity
still uses the actual owned node ID. Return a selection, never a saved graph.
Revalidate it against the current state after the modal closes.
The table has vertical and horizontal scrollbars; resize the Name column to read
long labels without changing their identity or filtering semantics.

Show item cancels any pending route/paste and selects the requested existing item,
opens the inspector, and centers the current camera without changing zoom. Center
components on their existing placement helper, nodes on their saved positions,
and wires halfway along polyline length. Repeated zero-length segments are valid;
an entirely coincident path reveals its endpoint. Do not derive connectivity from
these coordinates or evaluate identifiers as Canvas tag expressions.

Search, cancellation and filtering leave graph/history/results/camera unchanged.
A successful reveal preserves graph, revision and results, while camera changes
use ordinary project dirty/save rules. No-op reveal must not create a circuit edit.
Unknown/deleted selections fail before canceling current work. Clipboard remains
unchanged. Selection/filter text are transient; native v1/project v3/CSV v1 stay
unchanged. The dialog releases Tcl variables/traces on the UI thread when closed.

Keep catalog/filter/reveal-position math in a pure navigation.py module. Use lazy
Tk widgets in editor_dialogs.py and the existing controller camera/selection
workflow. No new dependency, device or solver function is needed.

Acceptance: namespace collisions, Unicode/case/space and arbitrary identifier
characters, terminal identity, deterministic filters and no-match/error recovery,
node/component/polyline midpoint geometry including degeneracy, current-state
revalidation, dialog Apply/Cancel/Enter/navigation, camera-only dirty state,
current-result/history/clipboard preservation, exact project saves, keyboard scope
and source/fresh-installed regressions. Non-Latin shortcuts follow SHORTCUTS.md.
