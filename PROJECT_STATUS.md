# Project status and continuation

Date: 2026-10-27. DC-1 is committed as `2f4bbe9`; NUM-1 is committed as `8ce68fb`.
The working tree was clean at the start of PKG-1. PKG-1 changes below are local
and uncommitted; no commit or push was performed by the agent. Always recheck
the working tree before continuing.

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
Baseline weaknesses: duplicated validation with differing numeric policies; legacy output
overflow/underflow; no reproducible installation or compatibility matrix.
README omitted the model and described all network solving as future work;
updated for the new programmatic DC subset. The historical Python 3.7 claim is
not runtime-verified here. No file import/execution, network transmission or
destructive file handling exists in the application. Future parsers must validate
untrusted input. Current iterable APIs can consume unbounded input; they are not
safe parsers for arbitrary external data.

### Reproduced legacy defects (historical; fixed in NUM-1)

These were baseline findings, not regressions introduced by DC. All six are now
covered by passing regression tests. The table preserves the original evidence:

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

## Batch NUM-1: standalone numerical reliability

Status: VERIFIED locally, committed as `8ce68fb`. Depends on the existing scalar APIs;
no new dependency. Base commit `2f4bbe9`; no pre-existing uncommitted modifications.

- `calculations.py`: shared finite-value validation, native series type handling,
  compensated float sums, scaled parallel conductances, Ohm's law range guards,
  exact intermediate power arithmetic on normalized float operands.
- `main.py`: shared numeric text parser rejects underflow before a false zero
  resistance/current/voltage can reach the calculation layer.
- `test_numerical_calculations.py`: 29 tests, including all six reproducers,
  Decimal context traps, subnormal preservation, physical identities, independent
  high-precision power references and complete injected-I/O CLI recovery.
- README, DECISIONS, ROADMAP, TESTING and this status document synchronized.

Validation: `python -B -m unittest -v`: **110 passed, no skips**.
`python -B -S -m unittest -q`: **97 passed, 13 solver tests skipped**.
Focused numerical suite was first run against the unfixed implementation and
failed as expected; all original 81 tests remain unchanged and pass.
`git diff --check` passed with only Windows line-ending advisories.

Review: no formula changes to the dividers or DC solver; native series range
is retained without forcing Decimal/Fraction/integer values through float.
Mixed Decimal/float and Decimal/Fraction series inputs now deliberately produce
float results. Nonzero-to-zero conversion/results raise ValueError; finite
subnormals are accepted. Decimal arithmetic continues to honor the caller's
context and traps (arithmetic exceptions are reported as ValueError).
Power may differ in its last bit from separately rounded square/multiply steps;
it now rounds the exact result of normalized operands once. See DECISIONS.md.

Limits: floating-point rounding and precision loss remain; this is not exact
real arithmetic. Current-divider negligible-weight underflow and voltage-divider
total-overflow rejection are unchanged. No cross-version/platform tests,
installation checks or large-scale benchmarks were added in this batch.

## Batch PKG-1: installation and CI foundation

Status: local installation VERIFIED; hosted CI CONFIGURED, NOT YET RUN.
Base `8ce68fb`, no pre-existing uncommitted modifications. This batch adds:

- `pyproject.toml`: explicit flat modules, version 0.1.0, Python >=3.11,
  zero base runtime dependencies, optional NumPy dc extra, installed command.
- `main.main`: shared console/script entry point retaining UTF-8 output.
- `dc.py`: missing-NumPy advice usable from an installed environment.
- Pinned build backend/frontend and NumPy validation baseline; source dependency
  shortcut aligned with package metadata; source manifest and output ignore rules.
- Two stdlib verification scripts: fresh venv, local wheel installation,
  isolated product imports outside checkout, copied tests, console/module CLI,
  missing optional dependency and known-answer DC smoke checks.
- `.github/workflows/tests.yml`: eight Windows/Linux jobs across CPython
  3.11-3.14, each building an sdist and a wheel from it, then checking both
  installation modes. Official action commit SHAs verified through GitHub API.
- Setup, support policy, testing and roadmap documents synchronized.

Actual local verification on Windows:

| Interpreter | Source suite | Fresh installed core | Fresh installed DC (NumPy 2.4.6) |
| --- | --- | --- | --- |
| Python 3.11.9 | 110 passed | 97 passed, 13 expected skips | 110 passed, no skips |
| Python 3.14.6 | 110 passed | 97 passed, 13 expected skips | 110 passed, no skips |

Commands: `python -B -m unittest -q`, `py -3.14 -B -m unittest -q`,
`.venv-build/Scripts/python -m build`, `python -B scripts/check_distributions.py`,
and `py -3.14 -B scripts/check_distributions.py`. Both installed modes exercised
console and module entry points. Both DC environments passed `pip check`.
Archive inspection confirmed exactly four product modules in the wheel,
optional-only NumPy metadata and tests/scripts/pins in the source archive.
Workflow YAML parsed and matrix checked locally. No numerical test changes.

Support-policy change: install floor is now 3.11; the historical unverified 3.7
claim is retired. CI targets 3.11-3.14; 3.12/3.13 and Linux await actual hosted
execution. Newer Python versions may install but are not supported by the current
matrix. Source tests also passed with the pre-existing NumPy 1.26.4 (3.11) and
2.5.2 (3.14); those are additional evidence, not fully locked environments.

Limits: no hosted workflow has run, no registry publication, no project license
selection, no hash lock or bit-reproducible build guarantee. Generic flat module
names remain for compatibility; a future namespace migration needs a separate
plan. Local build artifacts and build venv are ignored. Temporary install-check
venvs were removed by the check scripts after their runs.

## Exact next action

Review PKG-1 as a coherent commit candidate. Suggested commit message:
`Add installable package and CI for core and DC environments`.
The user handles staging/commits/pushes.

After pushing, inspect the first hosted workflow run before claiming CI is
verified. Next development batch: native versioned JSON persistence with strict
schema/type validation, deterministic round trips and malformed-input tests,
followed by a DC CLI workflow before GUI work. See ROADMAP.md for long-term gates.
