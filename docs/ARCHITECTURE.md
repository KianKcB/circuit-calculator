# Architecture

The local checkout is authoritative. Application implementations live in the
`circuit_calculator/` package. Its calculations.py contains standalone formulas,
cli.py owns command/interactive I/O, circuit.py owns immutable electrical data,
and dc.py owns DC assembly, topology checks, solution and results. The model and
solver have no GUI dependency. Tests, documentation, requirements, workflow helpers
and examples are grouped in their corresponding top-level folders.

`circuit_io.py` is now the native persistence client. CircuitDocument owns title
and description without changing Circuit. Strict version-1 JSON schema, numerical
conversion rules, limits and save semantics are defined in CIRCUIT_FORMAT.md.
The DC file command in cli.py composes load -> size guard -> solve -> JSON
presentation. Analysis limits do not prevent storing valid unsolvable descriptions.

`schematic.py` now owns immutable layout/junction/wire/component-placement state, explicit net
resolution and revision-scoped undo/results. `gui.py` renders that state with Tk
and invokes the existing DC solver on a worker thread. The UI thread alone
updates widgets, and results are accepted only for the submitted revision.
Native electrical export compiles wires into nets; graphical persistence is a
separate version-3 schema in project_io.py, with version-1/2 loading retained. It
embeds the original uncompiled CircuitDocument, node positions, individual wires,
ComponentPlacement values and a ViewState. Dedicated component terminal nodes keep
their identity through movement/rotation; coordinates never determine connectivity.
Legacy shared-junction elements acquire dedicated terminals and explicit wires
on their first body move/rotation. See COMPONENT_EDITING.md for invariants.
Wire owns an immutable tuple of Waypoint bends. Path points use node positions
at the ends and fixed world-coordinate bends inside; only Wire.first/second
participate in net resolution. Splitting explicitly creates/reuses a junction
and replaces one wire with two while partitioning its geometry. See WIRE_ROUTING.md.
Bend insertion/movement/removal and explicit Manhattan conversion also live in
schematic.py. The conversion simplifies duplicate and between-collinear points,
preserves reversals/endpoints and uses normal wire validation for bend limits.
Routing preferences and handle/drag selection stay in gui.py, outside persistence.
See BEND_EDITING.md; the graphical schema remains v3.
Canvas symbols/labels/selection handles now live in canvas_renderer.py; gui.py
delegates drawing and owns controller actions/workers. The renderer tags actual
circuit graphics separately from decoration. viewport.py supplies pure zoom,
fit and scroll arithmetic; no Tk/NumPy is imported by these modules at import time.
Fit uses measured graphic/text bounds, and camera actions preserve world center
and numerical results. See VIEWPORT.md for bounds and compatibility semantics.
_document_io.py shares bounded JSON and atomic-file primitives between both file
formats. Circuit I/O exposes validated data adapters for embedding without
relaxing its existing schema. See SCHEMATIC_FORMAT.md and GUI_DESIGN.md.

Opening a project/new/import resets history while incrementing the existing
monotonic revision. Dirty state compares graph and view against the last clean
snapshot, independently of simulation results. Camera-only changes preserve
results; document boundaries clear them and reject old pending completions.
Pending route previews live only in the editor controller, outside Schematic
and the persistent scroll region. Completing one route is one history entry;
Escape cancels without changing graph, dirty state or results. Other committed
edits cancel pending routes to avoid stale wire/endpoint references.

Packaging declares the application package and installed compatibility modules
explicitly. Canonical imports use circuit_calculator; compat/ aliases retain
historical installed imports with the same module and class identities. The console
command calls circuit_calculator.cli.main, shared with the package and root launchers.
Base installation is dependency-free; the dc extra supplies NumPy.
See DEVELOPMENT.md for the >=3.11 installation floor and current CI target.

## DC milestone design (2026-10-27)

Scope: positive finite resistors and signed independent voltage/current sources,
one explicit reference node, unique DC solutions. No zero-ohm resistors, reactive
devices, controlled sources, file parsing, or UI integration in this batch.

Use MNA: `G v + B j = i`, `B.T v = e`. Unknowns are non-reference
node voltages in declared node order, then voltage-source currents in element
order. Current sources subtract from their origin's RHS and add to their
destination's RHS. Source currents run plus to minus. Resistor current runs
node_a to node_b; current-source voltage runs from_node to to_node. For every
element, voltage is first terminal minus second terminal and power is `v*i`:
positive means absorbed, negative means delivered. Units are V, A, ohm, W.

`assemble_dc(circuit)` returns immutable tuples for matrix, RHS and ordering.
`solve_dc(circuit)` returns immutable node and element mappings plus diagnostics.
Assembly remains standard-library-only. NumPy is imported only when solving.
Use dense LAPACK solve, never explicit inversion or a least-squares fallback.
Dense storage and solve are intended for small educational networks.

Validate ideal voltage constraints and resistor/voltage-source paths to reference
before solving. Current sources cannot anchor a floating voltage. Voltage loops
with exact contradictory binary-float constraints are distinguished from redundant
constraints with non-unique source currents; exact Fraction arithmetic avoids an
arbitrary voltage tolerance. No least-squares reinterpretation is permitted.
An unanchored resistor/voltage-source region with nonzero net imposed current is
reported as an inconsistent current cutset; a balanced region is floating.

Equilibrate matrix rows then columns by their maximum absolute entry. Report the
2-norm condition number of this scaled matrix, rejecting values above 1e12.
This is a conservative numerical policy, not proof of physical singularity.
Reject non-finite arithmetic, representational underflow where detected, and
failed componentwise residual checks. Residual relative threshold is 1e-9;
electrical absolute tolerances are separately 1e-12 A, V and W. These guard
computed results, not model parameter acceptance. Small residuals do not prove
small forward error; condition checks complement them.

Acceptance: hand-derived series, parallel, bridge, supernode, signed and mixed
source examples; KCL at every node, voltage constraints and power balance;
orientation/order invariance; invalid topology and numerical range failures;
full existing suite remains green. Preserve the staged model files verbatim.

References: [Qucs MNA formulation](https://qucs.sourceforge.net/tech/node14.html)
and [NumPy linear algebra](https://numpy.org/doc/stable/reference/routines.linalg.html).
