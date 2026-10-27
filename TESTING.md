# Testing

## Commands

```text
python -B -m unittest -v
python -B -m unittest -v test_dc
python -B -S -m unittest -v
git diff --check
```

`-B` avoids writing bytecode. `-S` omits site-packages: it exercises the
standard-library baseline and DC assembly while NumPy solve tests skip. Skips
are not solver verification. Without NumPy installed, use requirements-dc.txt
before assessing the full solver suite.

## Layers and references

- Legacy suite: formula validation and injected-I/O CLI workflows.
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
establish industrial simulator equivalence. Regressions for legacy extreme-value
defects remain a priority; see PROJECT_STATUS.md.

Runtime tolerances and conditioning policy are documented in ARCHITECTURE.md.
Expected reference answers are derived independently and must not be changed to
accommodate an implementation error.

## Latest local run: 2026-10-27

Python 3.11.9 / NumPy 1.26.4: 81 tests passed with no skips. Without site-packages:
68 passed and 13 solver tests skipped. Baseline before changes: 59 passed.
README's DC example also ran and returned 8 V, 0.004 A and -0.048 W as expected.
