# GUI-7: names and component values

Contract, 2026-10-29. This batch adds collision-safe name editing to the existing
R/V/I value editor. It changes no physical laws, source conventions, document
schemas or dependencies. Local package version is 0.10.0.

## Names and graph invariants

Select a component body, free junction or wire and choose **Rename**, or press
F2 while the canvas has focus. Cancel leaves the document and current result
unchanged. The old name is offered as the initial value. Names remain
case-sensitive; surrounding spaces and Unicode are preserved. Names must contain
non-whitespace text, be valid UTF-8 and contain at most 256 characters, matching
the existing file-format name limit. This does not normalize or migrate old data.

`Schematic.rename(kind, name, new_name)` validates the entire replacement before
returning immutable state. Duplicate names are rejected within the node, component
or wire namespace respectively. The namespaces remain separate: a component may
share a name with a junction or wire. Renaming to the existing name is a no-op.

- Component rename changes the element name and its placement reference. Its
  dedicated terminal node identities, positions, value, polarity, wires and order
  remain fixed. Displayed terminal labels follow the new component name.
- Free-junction rename updates its position identity, every oriented device/wire
  endpoint and the reference node when applicable, in the original tuple order.
- Wire rename changes only its name, retaining endpoints and all bend geometry.
- Owned terminal identifiers cannot be renamed independently. Select the body
  instead. Keeping these identities stable avoids treating a label edit as a
  terminal replacement.

The alternative of separate immutable IDs plus editable labels would require a
schema migration and new identity rules throughout the application. For this
bounded editor, atomic graph-wide replacement preserves existing file semantics
and offers a smaller compatible change. Broader hierarchy remains planned.

## Values, history and results

**Edit value** retains the existing numeric editor and now names the component's
unit and sign convention. Enter resistance in ohms (> 0), source voltage as
V(+) - V(-) in volts, or source current from first to second terminal in amperes.
Source values may be signed or zero. No expressions or SI prefixes are accepted
by this editor. Decimal text reaches the existing model validation before float
normalization; overflow, nonzero underflow and non-finite values are rejected.

Every successful name/value edit is one Undo/Redo entry and conservatively clears
the current numerical result. An old worker completion cannot restore stale
results. Invalid, canceled and no-op edits preserve revision, history and results.
Renaming a representative junction can change exported net names, while the
electrical solution and orientation remain equivalent. Results must be recomputed
under the new names before CSV export.

Project v3 and electrical v1 already store these names; no schema bump is needed.
Graphical saves retain the exact edited graph, positions and wire routes. The
document and edit toolbars are separated from a wire row to keep the new
action reachable at the supported window sizes.

Acceptance: namespace collisions, Unicode/colon names, terminal ownership,
ground/endpoint rewriting, exact undo and serialization, analytical divider
values, real Tk canvas labels/selection, cancellation/failure rollback, delayed
worker rejection, and source/installed regressions. Full GUI maturity remains
in progress; bulk renaming and hierarchy are outside this batch.
