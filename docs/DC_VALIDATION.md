# DC-GRID: manufactured resistor-grid reference and bounded measurements

Contract, 2026-10-28. Verify the existing solver without modifying it.

An N by N square grid has 1 kohm horizontal/vertical resistors. Its boundary
nodes are independently constrained relative to reference g by voltage sources:

`V[row, column] = 0.5 * column - 0.25 * row` volts.

This affine field satisfies interior KCL: opposite horizontal differences cancel,
as do opposite vertical differences. Boundary constraints fix the solution.
For the difference of two putative solutions, zero boundary voltages and positive
resistances imply the sum of conductance times squared edge differences is zero;
all differences vanish. Boundary source currents then follow uniquely from KCL.
The source-only graph is a star, with no redundant voltage constraint loop.

Horizontal branch orientation is left to right: voltage -0.5 V, current -0.5 mA.
Vertical orientation is top to bottom: voltage +0.25 V, current +0.25 mA.
Each source current (boundary to g) is minus the sum of outward resistor currents.
Both zero/signed voltages and absorbed/delivered source powers occur. Total
resistor dissipation is `N*(N-1)*(0.5^2 + 0.25^2)/1000` watts; total source power
is its negative. Tests independently check every node/branch and KCL including g.
Voltage/current/power limits are absolute 1e-10 V, 1e-12 A/W per branch, and
1e-11 A/W for aggregate KCL/power. Expectations are derived before running the solver.

MNA unknown count is `N^2 + 4*N - 4`. N=4/8/12 gives 28/92/188 unknowns, within
the DC command's 200-unknown guard. The 12x12 fixture has 308 components and is
an API/native-command reference, beyond the editor's separate 100-imported-node
and 200-component caps.
This is bounded small-network evidence, not large-network scalability or a SPICE
comparison. Source/element ordering and a nonzero reference shift are also tested.

`python -B scripts/benchmark_dc.py --sizes 4 8 12 --repeats 3 --output report.json`
runs one warmup per size, times complete solve_dc calls, and validates each result
after timing. Output includes versions, engine/reference SHA-256, raw samples,
medians, condition numbers and independent errors/conservation. Creation refuses
an existing report. No GUI/device/numerical algorithm/dependency is added.

Measured on Windows, 2026-10-28, with three timed solves after one warmup per
size. Accuracy fields below describe the final checked sample; every timed sample
passed the independent oracle. Different Python/NumPy/backend environments and
machine load are not controlled performance comparisons.

| Python / NumPy | N | Unknowns | Median solve ms | Max node error V | Max branch-current error A | Scaled condition |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 3.11.9 / 1.26.4 | 4 | 28 | 1.067 | 0 | 2.17e-19 | 3.38 |
| 3.11.9 / 1.26.4 | 8 | 92 | 13.733 | 8.88e-16 | 1.14e-18 | 19.4 |
| 3.11.9 / 1.26.4 | 12 | 188 | 185.188 | 1.78e-15 | 2.71e-18 | 48.5 |
| 3.14.6 / 2.5.2 | 4 | 28 | 1.138 | 0 | 2.17e-19 | 3.38 |
| 3.14.6 / 2.5.2 | 8 | 92 | 2.867 | 8.88e-16 | 1.19e-18 | 19.4 |
| 3.14.6 / 2.5.2 | 12 | 188 | 90.112 | 1.78e-15 | 2.71e-18 | 48.5 |

On the 12x12 case, both interpreters gave total resistor power **0.04125 W**, as
predicted, with independent maximum KCL residual **3.53e-18 A** or less.
Native-file commands on both interpreters also solved this 188-unknown/308-element
case and exported **1,073 CSV records**; all exported node voltages recovered
exactly from JSON/CSV and the independent full-branch oracle passed.

Timing is machine/backend/load dependent and is not an automated pass/fail
performance gate. These measurements do not establish an arbitrary circuit-size
limit, pathological-conditioning reliability, or external-simulator agreement.
