# Development workflow

Read PROJECT_STATUS.md, ARCHITECTURE.md and ROADMAP.md, then inspect current Git
status. Preserve staged and unstaged user changes. Do not commit, push, reset or
switch branches without the user's authorization.

## Python and installation policy

The installable package requires Python >=3.11. Maintained CI targets CPython
3.11-3.14 on Windows and Linux; other versions/platforms are not in the matrix.
This replaces the previously unverified README Python 3.7 support claim. The
existing flat imports and direct script execution remain supported. The current
local package version is 0.3.0; no release or registry publication has occurred.
The project's license is still undecided; no license grant is invented by packaging.

For source development on Windows:

```text
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -B -m unittest -v
```

For the pinned DC validation baseline:

```text
.venv/Scripts/python -m pip install -c constraints-ci.txt -e ".[dc]"
.venv/Scripts/python -B -m unittest -v
```

Linux/macOS use `.venv/bin/python` instead. Editable installs are convenient for
development but do not prove wheel/sdist contents are correct. Base runtime has
no third-party dependencies. `requirements-dc.txt` retains the source-only NumPy
installation path and matches the `[dc]` extra's broader compatibility range.

## Build and verify distributions

```text
python -m venv .venv-build
.venv-build/Scripts/python -m pip install -r requirements-build.txt
.venv-build/Scripts/python -m build
python -B scripts/check_distributions.py
```

The checker selects the version declared in pyproject.toml and requires exactly
one matching wheel, so older artifacts can remain in `dist/`. Build creates a source
archive and then a wheel from that archive. The checker creates a temporary venv
under ignored `.build-check/`, installs that exact local wheel with no dependency
resolution, tests core-only behavior, installs its DC extra with constraints,
checks dependencies, and tests the full DC installation. It never modifies the
caller's environment. Repeat using each Python interpreter you want to verify.

Pinned frontend dependencies are in requirements-build.txt; the backend is pinned
in pyproject.toml and the DC baseline in constraints-ci.txt. Update pins deliberately
and rerun installed checks. The broad runtime NumPy range is not a lockfile.
Pins stabilize resolution, not bit-identical archives or hosted OS images.

## CI and change protocol

`.github/workflows/tests.yml` runs the same build and fresh-install checks on push,
pull request and manual dispatch, across Windows/Linux and CPython 3.11-3.14.
Official checkout/setup-python actions are pinned to verified v7 commit SHAs;
contents permission is read-only and checkout credentials are not persisted.
Local success is not proof that hosted jobs have run. No upload/publish step exists.

Before each feature, document scope, physical laws, units, sign conventions,
degenerate cases, API, compatibility, alternatives and acceptance tests. Keep
domain data, numerical algorithms and I/O separate. Run focused tests, then the
full suite. Record exact outcomes and limits. Stop at a coherent review checkpoint
and update the next action in PROJECT_STATUS.md.

Lint/type-check tooling remains deferred; stdlib unittest is the test runner.

## GUI development

Launch `python main.py gui --example` in a desktop session with Tkinter/Tk.
Tk is optional in some Python distributions; install it using that distributor's
instructions. NumPy remains optional until simulation. Keep editing/connectivity
logic in schematic.py, rendering/dialogs in gui.py, and solver/math in dc.py.
Read GUI_DESIGN.md before extending wiring or layout persistence.

Run `python -B scripts/check_gui.py -v` for nine Tk widget/workflow checks with
a display and NumPy available. These tests are opt-in: the regular 162-test suite
remains headless and needs no Tk import. Hosted CI currently exercises editor
logic and package imports, not the interactive Tk tests. A future display-enabled
CI lane can run them without weakening the core/DC dependency boundary.
