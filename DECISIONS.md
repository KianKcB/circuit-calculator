# Decisions

## 2026-10-27: PKG-1 installation and continuous integration

Goal: make distribution contents and optional-dependency behavior testable in
fresh environments, with a maintained Python-version target. Preserve all four
flat public modules/import paths and direct `python main.py` use. Use explicit
setuptools py-modules, not a source-tree migration. The installed command shares
the existing UTF-8 entry point. Version 0.1.0 describes this first local package;
no registry publication or licensing choice is implied. No project license has
been selected; distribution remains local pending the user's licensing decision.

Set installation minimum to Python 3.11; maintained CI target is CPython
3.11-3.14 on Windows/Linux. The older README 3.7 claim was never runtime-verified.
These versions are not all claimed verified until checks actually run. Newer
versions may install but are outside the current matrix. No source-language
rewrite is needed. This is a documented packaging support-policy change.

Base runtime has zero third-party dependencies. NumPy is an optional dc extra
(`>=1.26.4,<3`); source users retain requirements-dc.txt with the same range.
CI uses a pinned NumPy 2.4.6 baseline, plus pinned build frontend/dependencies and
setuptools backend. Broad runtime range is compatibility policy, not a complete
lock. Pins stabilize dependency resolution, not bit-identical wheels or moving
hosted runners. No lock/hash or vulnerability-audit claim is made.

Use GitHub Actions' official checkout/setup-python actions and read-only contents
permissions. Each job builds an sdist then a wheel from that sdist, installs the
local wheel into a fresh venv, verifies core-only behavior, installs the dc extra
under constraints, and verifies the full suite with no skips. Test modules alone
are copied outside the checkout; isolated Python must load product modules from
the venv. Exercise console and module commands, missing-NumPy advice and a known
DC circuit. Reuse stdlib unittest and subprocess instead of adding tox/pytest.
Acceptance: clean build/install checks on available local runtimes; no installed
test/source leakage; all numerical tests preserved; CI configured and clearly
distinguished from actual hosted-run evidence. Packaging/CI deployment/publishing
is out of scope; user controls commits/pushes.

References: [PyPA pyproject guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/),
[official setup-python](https://github.com/actions/setup-python),
[Python version status](https://devguide.python.org/versions/).

## 2026-10-27: NUM-1 standalone numerical repair

Scope: the six audited defects in series/parallel resistance, Ohm's law and
power. Preserve signatures, ordinary CLI behavior and zero/short semantics.
No change to DC, voltage-divider total-overflow policy or current-divider
negligible-weight underflow policy in this batch.

Series retains native arithmetic for all Rational values (integers/Fractions)
and for Decimal/integer mixtures, including Decimal-only results and the active
Decimal context. Other mixtures use validated floats and `math.fsum`; this
defines formerly failing Decimal/float and Decimal/Fraction mixtures. Native
finite values need not fit a float; float paths reject conversion overflow or
nonzero input rounded to zero. Native sums may round according to their numeric
context but cannot return infinity or silently collapse a positive total to zero.

Parallel uses `Rmin / sum(Rmin/Ri)`, avoiding reciprocal overflow. Every input
is validated before short-circuit handling. Tiny weights may round away, but a
positive equivalent resistance must not become zero: raise ValueError instead.
Preserve representable subnormal results; do not impose a magnitude cutoff.

Ohm's law and power normalize inputs through the existing float validator and
reject non-finite or nonzero-underflow results with ValueError. Legitimate zero
remains valid where the physical formula defines it; zero denominators remain
errors. Power evaluates the two or three normalized floats using exact Fraction
arithmetic and rounds once at the output. This modest scalar-only cost avoids
both intermediate square overflow and underflow, without a new dependency or
precision setting. It is not arbitrary-precision input support: inputs still
must pass float normalization. Simple float operation reordering was rejected
because it does not reliably protect both extremes.

Acceptance: regressions for all six reproducers; Decimal context and native-type
compatibility; subnormal and true-zero cases; power checked against independent
high-precision Decimal calculations; resistance invariants; CLI recovery after
range errors; all baseline and DC tests pass. Affected implementation is confined
to calculations.py, with a dedicated numerical test module and updated docs.

Integration review identified an additional input boundary: CLI float parsing
turned text such as `1e-1000` into zero before validation. NUM-1 therefore also
updates main.py with one shared parser: when float parsing returns zero, check
the original decimal text and reject a nonzero value. Actual zero and supported
subnormal input remain valid. A regression covers both scalar and resistance
entry and recovery to the menu. This closes the end-to-end false-short loophole.

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
