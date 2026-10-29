# PROBE-1: two-point DC voltage measurement

The Voltage probe results tab measures **V(A) − V(B)** using two explicit
junction/terminal pickers. A is positive and B negative; Swap reverses polarity.
Selecting the same endpoint, or two aliases on the same resolved net, yields
zero only when the accepted result contains a finite voltage for that net.
The probe neither inserts components nor solves another circuit. It never
reports individual wire current.

The pure `probe.voltage_between` helper resolves endpoint identities through
`Schematic.net_names()` and reads an accepted DCResult. The caller must establish
that the result belongs to the current revision, just as for selected-item
inspection. Non-finite endpoint values or subtraction overflow produce a range
diagnostic, never an infinity or a fabricated zero. Display uses nine significant
digits and SI prefixes; normal binary floating-point rounding still applies.
There is no new voltage tolerance or claim of arbitrary-range accuracy.

`probe_panel.VoltageProbePanel` imports Tk only when constructed. Numbered picker
rows map to exact node identities, so equal human terminal/junction labels cannot
confuse measurements. Choices are transient and clear on every committed document
revision (including layout/metadata edits, Undo/Redo and new/open). They survive
selection, zoom/pan, tab changes and repeated solves at the same revision.
Clear resets choices; Swap also handles incomplete choices. No project/native/CSV
schema changes, cached numerical project data or new runtime dependencies.

The panel reads only EditorSession.result. Starting another solve immediately
removes old numbers. Pending, failed and rejected stale jobs cannot restore them.
An active Voltage probe tab stays selected after a successful solve.

Validation includes analytical 12 V / 1k / 2k divider measurements (+4 V and
−4 V), all three reference choices, node/element reorderings, owned-terminal and
wire aliases, same endpoint, missing data, finite subtraction overflow and smallest
subnormal values. Opt-in Tk checks cover actual picker events, Swap/Clear,
document/history invalidation, failed/stale jobs, camera preservation and equal
display labels. Hosted Linux verification remains pending.
