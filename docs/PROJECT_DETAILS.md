# GUI-9: editable project details

Design contract, 2026-10-29. Expose the title and description already present in
CircuitDocument; do not add another metadata store or change either file schema.
The circuit, layout and camera remain independent of these descriptive fields.
Implementation: GUI-9, local package 0.13.0; verification is recorded in
PROJECT_STATUS.md and TESTING.md. Native v1/project v3/CSV v1 remain unchanged.

**Project details** opens one modal form with a single-line title and multiline
description. Initialize from the current document exactly. Both fields may be
empty, are valid UTF-8, and retain existing 256/4096-character limits. Preserve
spaces, Unicode and description newlines. One Apply updates both fields atomically;
Cancel/Escape preserves all state. Validation errors remain in the open form with
an inline explanation, allowing correction without re-entering the other field.

Enter in the description inserts a newline; Ctrl+Enter applies. Enter in the title
or on a button keeps normal dialog behavior. Buttons and form fields must be
keyboard reachable. Focus/selection begins in the title. Keep Tk imports lazy so
ordinary installed/core tests and programmatic metadata editing need no display.
Use Tab from the title and Ctrl+Tab to leave the multiline description. Enter on
Cancel cancels; it never applies the form. The dialog's temporary error StringVar
is released on the UI thread when it closes, before later worker allocations can
trigger cyclic collection of closed widget wrappers.

`Schematic.set_metadata(title, description)` returns a validated immutable
document replacement while preserving the exact circuit object and graphical
tuples. Apply it to the current schematic after the dialog returns, rather than
restoring a graph snapshot captured before a modal event loop. No-op metadata is
a no-op in EditorSession. A successful change is one Undo/Redo entry and marks
the project dirty. Preserve the existing conservative result policy: any committed
document edit clears results and rejects earlier workers, even though descriptive
text does not change the physical equations. The user can rerun DC normally.

Project saves/reopening and native electrical export retain these existing fields.
Undo restores both fields together. No simulation result, clipboard, schema,
dependency or solver change is required. Dialog text is data and is never executed
or sent externally. Native JSON remains authoritative for the metadata limits.

Acceptance: Unicode/empty/boundary and invalid text, exact graph/layout/identity
preservation, atomic no-op/failure/undo behavior, native/project round trips,
known-answer electrical equivalence, real dialog Apply/Cancel/validation/newline/
keyboard workflow, dirty/save/open and stale-worker protection, plus fresh core/DC
and installed Tk checks. General component property forms remain a separate task.
