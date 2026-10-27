# Desktop GUI decision and GUI-1 contract

Date: 2026-10-27. Phase 6 begins with a bounded network editor; the complete
schematic editor remains incremental. Existing staged PERSIST-1 work is preserved.

## Framework decision

| Candidate | Evidence and tradeoff | Decision for this batch |
| --- | --- | --- |
| Tkinter/ttk + Canvas | CPython interface to Tk; Canvas provides tagged items, coordinates, bindings and scrolling. Tkinter is optional in some Python distributions. Local Tk 8.6 is available. A small explicit graph editor needs no new pip GUI dependency. | Select for GUI-1. Keep editing/connectivity logic independent so the renderer can change later. |
| PySide6 / Qt | QGraphicsScene supports graphics items and interaction; Qt has richer scene/editor facilities. Adds a substantial binding/runtime dependency and a separate distribution/license review. | Reassess if component-centric editing, scene complexity or accessibility exceed the Tk prototype. |
| wxPython | FloatCanvas offers world-coordinate drawing and navigation; introduces another GUI distribution plus its canvas dependencies. | No current advantage sufficient to add another dependency for this small slice. |

These are engineering choices for the present scope, not performance benchmarks.
Tcl/Tk distribution notices must be retained in future bundles; project licensing
is still undecided. No executable distribution is being published in this batch.

Sources: [Python Tkinter](https://docs.python.org/3/library/tkinter.html),
[Tk Canvas](https://www.tcl-lang.org/man/tcl8.6/TkCmd/canvas.htm),
[Tcl/Tk terms](https://www.tcl-lang.org/software/tcltk/license.html),
[Qt scene](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QGraphicsScene.html),
[Qt licenses](https://doc.qt.io/qtforpython-6/licenses.html),
[wx FloatCanvas](https://docs.wxpython.org/wx.lib.floatcanvas.html).

## Electrical editing rules

Nodes are explicit named junctions, with positions stored separately. A component
is created by choosing two existing junction identities in order. Those choices
are node_a/node_b for resistors, plus/minus for voltage sources, and from/to for
current sources. Symbols and result signs follow that same order.

A wire explicitly joins two junction identities. Wire-connected nodes resolve
by union into an electrical net named after its first declared node. The selected
reference junction identifies the zero-volt net. Coincident coordinates,
crossings, overlapping edges and dragging near an item never create connections.
To connect crossing wires, add/select an explicit junction and connect endpoints
to it. This batch does not automatically split wire segments or infer T-junctions.

Moving a junction preserves all endpoint identities. Deleting one removes its
incident components and wires, and clears reference if necessary. Every edit is
undoable. Removing a wire can split a net; undo restores the exact graph. A wire
that collapses a component's two endpoints is rejected at compilation with an
actionable unsupported-short diagnostic. No device is silently discarded.
Duplicate components/wires and undeclared endpoints are invalid; a wire cycle
is redundant connectivity and is permitted. Two distinct elements may share nodes.

## GUI-1 scope and acceptance

Implement junction placement/movement, R/V/I creation, explicit wire connections,
reference selection, component-value editing, selection/deletion, Undo/Redo,
pan/zoom, a divider example, native electrical-document import/export, and DC
simulation with node/branch results and useful errors. Limits: 100 junctions,
200 components, 400 wires and 200 DC unknowns. Validate before applying edits.
Geometry is finite and bounded. Circuit/model constructors remain unchanged.

Simulation runs on one worker thread; Tk calls stay on the UI thread. Editing,
Undo/Redo or loading invalidates results. A result from an older document revision
cannot replace current results. This is responsiveness for small supported DC
networks, not cancellation of arbitrary long numerical jobs.

Native v1 circuit files preserve electrical connectivity and metadata only.
Export resolves wires into nets; importing one arranges junctions automatically.
GUI-2 now adds a separate project v1 format that preserves original junctions,
coordinates, individual wires, metadata, zoom and pan. History, tool/selection and
simulation results are not saved. Open/Save Project and Import/Export Circuit are
distinct controls. See SCHEMATIC_FORMAT.md for strict schema/save semantics.

This is a junction-based prototype. Free component placement/rotation,
multi-segment wire routing, automatic segment splitting,
copy/paste and the complete phase-6 workflow remain planned. Do not mark phase 6
complete. Tests must cover topology independent of geometry, net merge/split,
orientation, delete/undo, stale-result rejection, analytical export/load/solve
equivalence, Tk widget workflows and installed distribution imports. Graphical
project round trips and canceled/failed file workflows are verified in GUI-2.
