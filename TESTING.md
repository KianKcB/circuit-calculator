# Testing

## Commands

```text
python -B -m unittest -v
python -B -m unittest -v test_dc
python -B -S -m unittest -v
python -B scripts/check_distributions.py
git diff --check
```

`-B` avoids writing bytecode. `-S` omits site-packages: it exercises the
standard-library baseline and DC assembly while NumPy solve tests skip. Skips
are not solver verification. Without NumPy installed, use requirements-dc.txt
before assessing the full solver suite.

`scripts/check_distributions.py` requires a built wheel in `dist/` (see
DEVELOPMENT.md). It tests a fresh venv first without NumPy, then with the pinned
DC extra. Product modules must resolve inside that venv. Test files alone are
copied into a temporary directory outside the source modules and run using
isolated Python. Both the installed command and `python -m main` are exercised.
DC checks fail if any test is skipped. Core-only checks verify missing-dependency
advice and explicitly accept optional-solver skips.

The GitHub workflow targets CPython 3.11–3.14 on Windows/Linux. Hosted results
are not available until the workflow has actually been committed/pushed and run.

## Layers and references

- Legacy suite: formula validation and injected-I/O CLI workflows.
- Numerical suite: native Integer/Fraction/Decimal return policies; conversion
  and arithmetic overflow/underflow; subnormal versus actual-zero values;
  independent 100-digit Decimal power references; resistance invariants; CLI
  rejection of nonzero text that float parsing would silently turn into zero.
- Model suite: immutable component parameters, names, nodes and reference.
- DC assembly: explicit hand-written MNA matrix and RHS; topology errors.
- DC solution: hand-derived divider, parallel, supernode, balanced/unbalanced
  bridges and multiple-source results. KCL at reference and other nodes,
  constitutive relationships and total absorbed/delivered power are checked
  independently of matrix assembly.
- Metamorphic checks: node ordering/renaming, reference shifts, element ordering,
  source/resistor orientation and uniform resistance scaling.
- Numerical failures: overflowing conductance/matrix/RHS, ill-conditioning and
  result range. Input errors remain model errors, not solver failures.

No coverage percentage, SPICE comparison, cross-platform test or large-network
benchmark has been measured. Analytical tests validate this subset but do not
establish industrial simulator equivalence. The six audited legacy extreme-value
defects now have regression coverage; see PROJECT_STATUS.md.

Runtime tolerances and conditioning policy are documented in ARCHITECTURE.md.
Expected reference answers are derived independently and must not be changed to
accommodate an implementation error.

## Latest local run: 2026-10-27

PKG-1 on Windows: the unchanged 110-test source suite passed on Python 3.11.9
and 3.14.6. Fresh installed wheels passed 97 tests with 13 expected skips in
core-only mode, then all 110 with no skips under NumPy 2.4.6, on both interpreters.
Installed console/module commands, missing-dependency advice, imports from the
venv, known-answer DC result and `pip check` also passed. An isolated build made
the source archive and its wheel; archive contents/metadata were inspected.
Workflow YAML/matrix parsed locally; no hosted CI run is claimed.

NUM-1, Python 3.11.9 / NumPy 1.26.4: 110 tests passed with no skips. Without
site-packages: 97 passed and 13 solver tests skipped. This batch started at 81
passing tests and added 29 numerical/CLI tests. The new tests were run before
fixes and exposed the expected defects; baseline expectations were not changed.

The earlier DC-1 run had 81 passing tests (initial project baseline: 59).
Its README DC example returned 8 V, 0.004 A and -0.048 W as expected.
