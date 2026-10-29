# GUI-8: isolated component copies

Design contract, 2026-10-29. Implement a bounded in-app component clipboard,
Copy/Paste placement and one-step Duplicate for the existing R/V/I subset.
No operating-system clipboard, multi-selection, wires/subcircuits or expressions
are interpreted. The clipboard is an immutable value/rotation snapshot, not a
reference to a live component or its electrical endpoints.

## Model and identity

`ComponentTemplate(kind, value, rotation)` accepts exactly the existing resistor,
voltage and current kinds, normalizes value using the existing model validator,
and permits only 0/90/180/270 clockwise rotation. `copy_component(name)` captures
one existing component. For a legacy shared-junction symbol, use the existing
placement helper's nearest right-angle orientation. No source circuit is changed.

`paste_component(template, x, y)` chooses the first unused R/V/I number in the
component namespace, allocates two fresh terminal IDs, and adds one placed
component. Preserve value and first/second terminal orientation, including signed
or zero sources. Never copy original wires, reference selection or shared nodes.
Existing nodes/components/positions/wires retain their order and identities.
Coordinates do not connect, even if the copy overlaps an existing node or symbol.
Use the normal editor limits and geometry validation before returning state.

`duplicate_component(name, x, y)` combines snapshot and paste. Unlike Copy, a
successful duplicate is a graph edit and one history entry. Invalid coordinates,
unknown components, invalid templates or exhausted node/component limits leave
the original immutable state unchanged.

## Controller workflow

Copy (Ctrl+C on the canvas) captures the selected component body. It preserves
the current value and rotation. On Windows, clipboard shortcuts also use physical
virtual keycodes so non-Latin keyboard layouts work; Alt/AltGr input is ignored.
The keycodes follow [Microsoft's virtual-key table](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes).
Other platforms retain Latin key-symbol dispatch. Other existing letter shortcuts
(such as R/F and Ctrl+Z) still depend on the active keyboard layout; toolbar
actions remain available. Broader shortcut normalization is a separate follow-up.
Copy preserves
the graph, current result and dirty/history state. Paste (Ctrl+V) enters a visible
placement mode. Show a snapped preview at the pointer, then commit one copy on
the next click; R rotates only the pending copy, preserving source and clipboard.
Escape or changing tools cancels. The preview is decoration and
must not change the scroll region, electrical graph or simulation revision.
Repeated Paste reuses the snapshot but allocates fresh names and endpoints.

Duplicate (Ctrl+D) immediately adds a selected component 40 world units right and
down, then selects the copy for movement/renaming/wiring. Preserve the clipboard.
If the offset would put a terminal outside the allowed coordinate range, reject
the operation and suggest Copy/Paste at another location.

Keep the in-app clipboard across Undo/Redo, deletion and document opening; the
stored immutable value does not depend on the source still existing. Do not
persist it to a project or read the OS clipboard. Every committed paste/duplicate
invalidates results, rejects older workers and participates in project saves and
one-step Undo. A disconnected copy may make DC analysis unsolvable until wired
or deleted; explain this in the status instead of silently attaching it.

Acceptance: R/V/I and every orientation, identity collisions and ownership,
original graph preservation, overlapping geometry, source signs/zero, bounds/
resource rollback, exact project/history recovery, deterministic repeated copies,
clipboard snapshot isolation across source edits/deletion/opening, canceled
preview/result preservation, real Tk hit/placement/history and installed checks.
Native v1/project v3/CSV v1 stay unchanged. General copy/paste remains planned.
