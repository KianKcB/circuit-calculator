# Decisions

## 2026-10-27: retain the existing model

Frozen component dataclasses, unique names, declared nodes and explicit source
orientation already support MNA. Optional reference and disconnected networks
are valid descriptions; the DC analysis layer applies stricter solvability rules.
No speculative inheritance or graphical coordinates are added. Stable names
are sufficient now; hierarchy will need explicit scoped terminal mapping later.

## 2026-10-27: optional NumPy DC backend

Choose NumPy dense solve over custom Gaussian elimination to avoid maintaining
a numerical kernel. SciPy sparse solve is deferred until size benchmarks justify
it. NumPy uses a BSD license; a future binary distribution must include relevant
NumPy and bundled numerical-library notices. No packages were installed in this
session. Existing formula CLI and assembly remain standard-library-only.
The locally tested backend is NumPy 1.26.4 on Python 3.11.9. Dependency ranges
are not a claim that every allowed version has been tested.

## 2026-10-27: keep legacy formula repair separate

Legacy numerical defects do not feed the new solver, which uses the model
directly. Repairing them together would mix API compatibility changes (notably
Decimal-preserving series sums) with simulation work. Record concrete reproducers
in PROJECT_STATUS.md and prioritize a separate regression-focused batch.

## 2026-10-27: stage the roadmap into reviewable batches

DC results and diagnostics precede persistence and GUI. Controlled sources and
advanced DC need not delay the first editor. Nonlinear semiconductor fidelity
and broad SPICE compatibility require a backend/licensing study before coding.
