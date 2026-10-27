# Architecture

The local checkout is authoritative. Preserve the flat modules while they remain
small. `calculations.py` contains standalone formulas; `main.py` owns interactive
I/O; `circuit.py` owns immutable, validated electrical data. The new `dc.py` owns
linear DC assembly, topology checks, solution and results. None depends on a GUI.
Future persistence and schematic layout must be separate clients of the model.

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
