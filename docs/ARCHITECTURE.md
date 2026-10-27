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

`schematic.py` now owns immutable layout/junction/wire state, explicit net
resolution and revision-scoped undo/results. `gui.py` renders that state with Tk
and invokes the existing DC solver on a worker thread. The UI thread alone
updates widgets, and results are accepted only for the submitted revision.
Native electrical export compiles wires into nets; graphical persistence is a
separate future schema. See GUI_DESIGN.md for exact junction/crossing semantics.

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
