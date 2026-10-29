# Development workflow

Read PROJECT_STATUS.md, ARCHITECTURE.md and ROADMAP.md, then inspect current Git
status. Preserve staged and unstaged user changes. Do not commit, push, reset or
switch branches without the user's authorization.

On 2026-10-28 the user authorized `git add` and `git commit` for completed changes
made during this work. Commit coherent verified batches, preserving unrelated
changes and staging explicit paths. Pushing remains a separate user action.

## Python and installation policy

The installable package requires Python >=3.11. Maintained CI targets CPython
3.11-3.14 on Windows and Linux; other versions/platforms are not in the matrix.
This replaces the previously unverified README Python 3.7 support claim. The
installed flat imports and root launcher remain supported. The current
local package version is 0.19.0; no release or registry publication has occurred.
The project's license is still undecided; no license grant is invented by packaging.

For source development on Windows:

```text
python -m venv .venv
.venv/Scripts/python -m pip install -e .
.venv/Scripts/python -B -m unittest -v
```

For the pinned DC validation baseline:

```text
.venv/Scripts/python -m pip install -c requirements/ci-constraints.txt -e ".[dc]"
.venv/Scripts/python -B -m unittest -v
```

Linux/macOS use `.venv/bin/python` instead. Editable installs are convenient for
development but do not prove wheel/sdist contents are correct. Base runtime has
no third-party dependencies. `requirements/dc.txt` retains the source-only NumPy
installation path and matches the `[dc]` extra's broader compatibility range.

## Build and verify distributions

```text
python -m venv .venv-build
.venv-build/Scripts/python -m pip install -r requirements/build.txt
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
Finally it changes that temporary environment to an editable installation and
verifies canonical and legacy imports outside the checkout. That last check uses
source-origin expectations instead of the wheel test's site-packages requirement.

Pinned frontend dependencies are in requirements/build.txt; the backend is pinned
in pyproject.toml and the DC baseline in requirements/ci-constraints.txt. Update pins deliberately
and rerun installed checks. The broad runtime NumPy range is not a lockfile.
Pins stabilize resolution, not bit-identical archives or hosted OS images.

## CI and change protocol

`.github/workflows/tests.yml` runs the same build and fresh-install checks on push,
pull request and manual dispatch, across Windows/Linux and CPython 3.11-3.14.
Official checkout/setup-python actions are pinned to verified v7 commit SHAs;
contents permission is read-only and checkout credentials are not persisted.
Local success is not proof that hosted jobs have run. No upload/publish step exists.

A separate installed-GUI job targets Ubuntu 24.04 with Python 3.11 and 3.14,
after the eight core/DC jobs. It installs explicit Tk/Xvfb/xauth runtime packages,
builds the distribution and runs `scripts/check_distributions.py --gui` under a
virtual display. The checker runs `python -I -B scripts/check_gui.py --installed`
inside its fresh DC environment, checking product module origins before Tk tests.
Source-mode GUI checks remain available; core-only checks never require a display.
Run `python -B scripts/check_distributions.py --gui` locally when a display exists.
This lane is CONFIGURED; hosted Linux execution has not been verified here.

References: [Ubuntu 24.04 runner image](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)
and [Ubuntu xvfb-run manual](https://manpages.ubuntu.com/manpages/noble/man1/xvfb-run.1.html).
Xvfb/xauth are explicitly installed rather than relying on an image's preinstalled
packages. No new third-party action is added; existing pinned action revisions remain.

Before each feature, document scope, physical laws, units, sign conventions,
degenerate cases, API, compatibility, alternatives and acceptance tests. Keep
domain data, numerical algorithms and I/O separate. Run focused tests, then the
full suite. Record exact outcomes and limits. Stop at a coherent review checkpoint
and update the next action in PROJECT_STATUS.md.

Lint/type-check tooling remains deferred; stdlib unittest is the test runner.

## File organization and import migration

All application implementations live in `circuit_calculator/`. Use qualified
imports, for example `from circuit_calculator.circuit import Circuit`. The CLI
implementation is now `circuit_calculator/cli.py`; `main.py` at the root only
forwards to it. `python -m circuit_calculator` is the preferred checkout and
installed invocation. Existing checkout `python main.py` and installed
`python -m main` still work. Installed legacy imports are aliases in `compat/`;
install with `pip install -e .` before using them from a source checkout.

`tests/` contains the headless suite and an initializer for default unittest
discovery. `python -B -m unittest -v` still works from the repository root; focus
a module with `python -B -m unittest -v tests.test_dc`. The installed verifier
copies only tests into an isolated temporary directory, never application sources.

Technical documentation lives in `docs/`, dependency inputs in `requirements/`,
workflow helpers in `scripts/`, sample documents in `examples/`, and CI in
`.github/workflows/`. Add future features to the existing package rather than
creating new top-level implementation modules. Historical status entries may
refer to their original paths; the REORG-1 entry records the migration.

## GUI development

Launch `python -m circuit_calculator gui --example` in a desktop session with Tkinter/Tk.
Tk is optional in some Python distributions; install it using that distributor's
instructions. NumPy remains optional until simulation. Keep editing/connectivity
logic in schematic.py, rendering/dialogs in gui.py, and solver/math in dc.py.
Read GUI_DESIGN.md, COMPONENT_EDITING.md, WIRE_ROUTING.md and BEND_EDITING.md before extending layout.
SCHEMATIC_FORMAT.md defines graphical project v3, with v1/v2 loading, separately
from electrical circuit v1. The placed example can be launched with
`python -m circuit_calculator gui examples/routed-divider.ccproj.json`.
Use project_io.py for projects and circuit_io.py for electrical export/import;
keep shared parsing/file primitives in _document_io.py. Never compile wires
merely to save a project, and never persist trusted/cached numerical results.

Run `python -B scripts/check_gui.py -v` for the opt-in Tk widget/workflow checks
with a display and NumPy available. The regular unittest suite remains headless
and needs no Tk import. The configured display-enabled CI lane runs installed
Tk checks without weakening the core/DC dependency boundary; hosted evidence
remains pending. See TESTING.md for counts and actual local verification.
For bounded analytical grid timing/accuracy reports, run
`python -B scripts/benchmark_dc.py --sizes 4 8 12 --repeats 3`.
See DC_VALIDATION.md for the oracle proof, CLI/native integration, measured
environments and limitations. These are diagnostic measurements, not timing gates.

The Tk test harness joins its workers and collects obsolete widget cycles on
the owning thread between windows; do not leave old Tk interpreters for a later
solver worker's cyclic garbage collection.
canvas_renderer.py owns Canvas graphics; viewport.py contains pure camera math.
results_io.py formats/writes CSV from existing DCResult snapshots without solving.
quantities.py parses exact Decimal GUI input and formats rounded SI display;
neither model storage nor JSON/CSV export uses the display formatter.
editor_dialogs.py owns the project-details form and imports Tk only on demand.
Its error StringVar is released when the modal closes on the owning UI thread.
shortcuts.py resolves whitelisted command names from platform keycodes/symbols
and modifier/scope rules. The controller dispatches them once without overriding
unhandled Text bindings or modal forms. See SHORTCUTS.md.
inspection.py formats selection topology and accepted current DCResult values.
The controller refreshes it on selection/state/result changes and avoids rewriting
unchanged text. Inspection never solves, modifies model data or persists results.
navigation.py owns immutable search items, literal Unicode filtering and
geometry-only reveal positions. The lazy Find form stores raw identities apart
from labels and revalidates against current state when returning to the controller.
Controller callbacks remain in gui.py. Viewport tests that assert actual visible
fit map their test window first; a withdrawn 1-pixel drawing area cannot be fitted.
The opt-in runner assembles feature mixins from tests/gui_workflows/. Its initializer
is empty and module names omit test_, keeping regular discovery headless. Installed
mode checks product origins first, then adds only the tests directory for helpers.
Keep test IDs/order and base.py main-thread cleanup stable. See TK_TEST_LAYOUT.md.
probe.py resolves two endpoint voltages and guards finite subtraction;
probe_panel.py owns the lazy Tk pickers and transient revision-scoped choices.
The controller passes accepted results through the existing refresh path.
See VOLTAGE_PROBE.md for polarity and invalidation rules.
annotations.py formats accepted node voltages by exact endpoint identity.
The renderer draws decorative values with no electrical hit tags. Fit includes
their bounds, while the base scroll region/saved view fractions stay independent
of annotations. See RESULT_ANNOTATIONS.md for the scope and layout limitations.
Component I/P formatting also lives in annotations.py. Rendering reuses each
component's actual label box/anchor via generated indexes, including parallel
legacy symbols. Clear empty results before consulting old scene indexes during
edits/deletion. Both annotation toggles use the same freshness/Fit path. See
COMPONENT_ANNOTATIONS.md for signs, placement and validation.
