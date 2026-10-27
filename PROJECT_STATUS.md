# Project status and continuation

Date: 2026-10-27. This is a local review checkpoint; nothing was committed or
pushed. Always recheck the working tree before continuing.

## Initial audit

- Branch `main`, HEAD `0da215d` (electrical power and divider calculations).
  Recent history also contains README, CLI, Ohm's law and parallel resistance.
  Remote state was not fetched or assessed.
- Pre-existing staged additions: `circuit.py` and `test_circuit.py` (303 lines).
  They have been preserved without edits or index changes. No other pre-existing
  tracked modifications were reported.
- Complete non-Git source tree: `calculations.py`, `main.py`, `circuit.py`,
  `test_calculations.py`, `test_circuit.py`, `README.md`, `.gitignore` plus ignored
  bytecode cache. No AGENTS.md, packaging, dependency, CI or tool configurations
  were found in the project. No parent AGENTS.md was found at C:\ or C:\Projects.
- Python 3.11.9; pre-existing NumPy 1.26.4 available. No dependencies installed.
- Baseline: `python -B -m unittest -v`: **59 tests passed**.

### Working capabilities and architectural assessment

Series/parallel equivalents, signed Ohm's law, three power formulas, ideal voltage
and current division, short-circuit rules and injected-I/O menu are implemented.
The existing 47 calculation/CLI tests cover ordinary examples and many invalid
inputs; 12 model tests cover names, endpoints, types, signs, frozen elements and
reference validation. No coverage measurement was made.

The immutable model owns tuples and normalized finite floats, rejects duplicate
names/nodes, undeclared endpoints and self-connections, and accepts signed source
values. Positive resistance is required. Ground is optional for description,
required for analysis. Multiple components may share endpoints; disconnected
descriptions are legal. Names are case-sensitive and retain surrounding spaces.
Source orientation is explicit and suitable for MNA. The model has no serialization,
hierarchy or multi-terminal support; layout is correctly absent. No model rewrite
is justified. Subclasses are accepted by the model but deliberately rejected by
DC to avoid accidentally simulating unknown device behavior.

Strengths: small modules, pure formulas, immutable data and testable CLI.
Weaknesses: duplicated validation with differing numeric policies; legacy output
overflow/underflow; no reproducible installation or compatibility matrix.
README omitted the model and described all network solving as future work;
updated for the new programmatic DC subset. The historical Python 3.7 claim is
not runtime-verified here. No file import/execution, network transmission or
destructive file handling exists in the application. Future parsers must validate
untrusted input. Current iterable APIs can consume unbounded input; they are not
safe parsers for arbitrary external data.

### Reproduced legacy defects (still open)

These are baseline findings, not regressions introduced by DC:

| Reproducer | Observed outcome | Required follow-up |
| --- | --- | --- |
| `series_resistance([1e308, 1e308])` | `inf` | Reject non-finite result. |
| `series_resistance([Decimal('1'), 1.0])` | `TypeError` during sum | Decide mixed numeric policy while retaining existing Decimal-only return behavior. |
| `parallel_resistance([1e-320])` | zero equivalent, short flag false | Scale conductances and guard range. |
| `parallel_resistance([Decimal('1e-1000')])` | uncaught `ZeroDivisionError` | Reject conversion underflow before division; CLI does not catch this exception. |
| `calculate_power(current=1e200, resistance=1e-200)` | `OverflowError` despite finite mathematical result | Avoid intermediate squaring overflow; standardize errors. |
| `calculate_ohms_law(current=Decimal('1e-1000'), resistance=1, solve_for='voltage')` | silently zero | Define and enforce conversion/result underflow policy. |

Voltage-divider total-overflow rejection is intentional in current tests, even
where scaling could yield a finite ratio. Current-divider weight underflow is
also explicitly accepted by existing tests. Changing either requires a documented
compatibility decision. Infinity is rejected rather than used to represent an
open circuit; omitted branches represent opens in DC. Zero-resistance formula
rules differ appropriately from strictly positive model resistors.

## Batch DC-1: linear resistive DC analysis

Status: VERIFIED for the bounded subset documented in ARCHITECTURE.md.

Requirements/dependencies: existing circuit model, NumPy only for numerical solve.
Changes: `dc.py`, `test_dc.py`, optional `requirements-dc.txt`, README and six
engineering documents. Provides immutable MNA assembly and result mappings,
node voltages, resistor/source currents, absorbed/delivered power, and condition,
KCL and power diagnostics. Topology errors distinguish missing reference,
contradictory voltage loops, non-unique source currents, inconsistent current
cutsets and balanced floating regions. Numerical failures never return a
least-squares circuit solution.

Design/review: dense NumPy solve with row/column equilibration; no explicit
inverse, custom elimination kernel or new hierarchy. Source-loop and current
cutset consistency uses exact supplied binary-float values. See DECISIONS.md
and ARCHITECTURE.md for alternatives, sign conventions and tolerance policies.

Final validation after the last source change:

- `python -B -m unittest -v`: **81 passed**, no skips (59 existing + 22 new).
- `python -B -S -m unittest -v`: **68 passed, 13 explicitly skipped** because
  site-packages/NumPy are unavailable in that mode.
- README Python example executed: output voltage **8.0 V**, R1 current
  **0.004 A**, source power **-0.048 W**.
- `python -B -m pip check`: **No broken requirements found** in the existing
  environment; this does not validate a clean install.
- New modules parse with Python 3.7 grammar using `ast.parse`; no Python 3.7
  runtime test was performed.
- `git diff --check`: passed (Git emitted only its LF-to-CRLF advisory).
- `git diff -- circuit.py test_circuit.py`: empty; existing staged files remain
  unchanged. Final review covered topology signs, MNA stamps, scaling recovery,
  current orientation, immutable result ownership and failure propagation.

### Known DC limits

- Small dense networks only; no performance or memory scaling benchmark.
- Conservative scaled-condition cutoff can reject solvable circuits. It is not
  a physical singularity proof or a guarantee of forward accuracy.
- Binary floating-point rounding remains; guards detect selected range loss and
  residual failures, not every lost low-order contribution. Values such as
  `0.1 + 0.2` and `0.3` are not identical ideal-source constraints.
- Floating voltage can coexist with other problems; diagnostics report the
  first detected class. One reference is required for the full network.
- No controlled sources, reactive/nonlinear analysis, GUI, persistence or DC menu.
- Analytical references only; no external SPICE benchmark, fresh installation,
  version matrix or platform matrix has been run.

## Exact next action

Review this coherent DC milestone together with the pre-existing staged model.
Suggested commit message: `Add validated linear DC MNA analysis and development roadmap`.
The user handles staging/commits/pushes.

Next implementation batch: add regressions for the six legacy numerical
reproducers above, settle mixed-number and underflow policy, repair the standalone
formulas without breaking ordinary CLI behavior or Decimal-only series sums.
Then tackle reproducible installation/CI, native persistence and a DC user workflow
before GUI work. See ROADMAP.md for all long-term phases and acceptance gates.
