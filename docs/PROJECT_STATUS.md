# Project status and continuation

Date: 2026-10-28. GUI-6 was committed as `199bb16`; RESULTS-1 began with a
clean working tree and no unrelated changes. The user has now authorized staging
and committing completed local batches; pushing remains a separate action.
Package version is now 0.9.0;
electrical document v1 and schematic-project v3 are separate formats. Project-v1/v2
loading remains supported.
Use README and DEVELOPMENT.md for current package paths/commands; historical
batch entries below retain their original snapshot names and results.

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

Status: local installation VERIFIED, committed as `341d094`; hosted CI CONFIGURED
(no hosted results recorded in this document).
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

## Batch PERSIST-1: native documents and file-based DC workflow

Status: VERIFIED locally, including fresh installed core-only and DC workflows.
Base `341d094`, no pre-existing uncommitted modifications. No new dependency.
Local package version is now 0.2.0; native document format is independently v1.

- `circuit_io.py`: immutable CircuitDocument metadata, strict JSON loading and
  deterministic serialization; byte/depth/node/element/string limits; Decimal
  numeric parsing preserves underflow until model validation; no arbitrary code,
  expressions, file references or unsupported fields/types are interpreted.
- Atomic saves serialize before I/O, refuse existing destinations by default,
  and require explicit overwrite=True for replacement. No-clobber install uses a
  hard link; failures retain ordinary filesystem exceptions and clean temp files.
- `main.py`: `dc FILE.json` composes load/size check/solve/JSON results. The
  no-argument formula menu is preserved. Error exit codes and SI units are explicit;
  200-unknown guard precedes dense matrix allocation.
- `test_circuit_io.py` and `test_dc_cli.py`: 34 tests covering all-element/metadata
  round trips, malformed/unknown/duplicate data, non-finite/range failures, resource
  limits, Unicode, save preservation/replacement/failure cleanup, an independently
  derived DC circuit, CLI errors and size-guard ordering.
- `examples/divider.json`: 12 V across 1 kohm/2 kohm with expected 8 V output.
- Package metadata includes the fifth module, manifest includes native examples,
  and installed checks exercise load/save plus console/module DC commands. Wheel
  selection now follows declared package version so retained 0.1 artifacts cannot
  be tested in place of 0.2.
- CIRCUIT_FORMAT.md is the full format/API/resource/save-semantics contract.
  README, architecture, testing, roadmap and decisions are synchronized.

Source commands after implementation: `python -B -m unittest -q` and
`py -3.14 -B -m unittest -q`: **144 passed** on each interpreter. Without
site-packages: `python -B -S -m unittest -q`: **129 passed, 15 expected skips**.
`python -B main.py dc examples/divider.json` returned 8 V, 0.004 A and -0.048 W,
with zero reported KCL and power-balance residuals. Syntax/whitespace checks pass.

Fresh installed package checks: `python -B scripts/check_distributions.py` and
`py -3.14 -B scripts/check_distributions.py` each passed **129 tests with 15
expected skips** in core-only mode, then **all 144 with no skips** after adding
NumPy 2.4.6. Both installed console and module DC commands and persistence APIs
were exercised outside the checkout. Both environments passed `pip check`.
`.venv-build/Scripts/python -m build` produced the 0.2.0 source archive and a
wheel built from that archive. No hosted CI results are claimed for this batch.

Limits: supports only existing R/V/I devices and metadata, not SPICE or schematic
layout. Unknown format versions are rejected; no migration history yet exists.
Default saves require hard-link support; replacement does not retain previous
permissions/metadata or guarantee directory-fsync durability. Input limits are
application policy, not a hostile-data service guarantee. Programmatic solver
size policy remains unchanged. GUI/framework selection is the next milestone.

## Batch GUI-1: Tk DC network editor prototype

Status: headless logic, local Tk workflows and fresh installed workflows VERIFIED.
The complete phase-6 schematic editor remains IN PROGRESS.
Starts from staged PERSIST-1 over HEAD `341d094`; no unrelated changes detected.
Package version is now 0.3.0; electrical file format remains v1.

- GUI_DESIGN.md records Tk/PySide/wx comparison, source links, scope, limits,
  explicit junction/crossing semantics and graphical-save limitations.
- schematic.py owns immutable positions/wires plus the existing CircuitDocument,
  explicit wire union into nets, bounded Undo/Redo and revision-scoped results.
  Coordinates never create connections; moving nodes preserves endpoints;
  delete removes incident topology; unsupported device shorts produce errors.
- gui.py renders junctions and R/V/I symbols, explicit wires/reference, creation,
  value editing, movement, deletion, Undo/Redo, pan/zoom and native circuit
  import/export. Simulation uses one worker; widgets update on the Tk thread.
  Edits invalidate results, and older-revision futures cannot display stale data.
- `python main.py gui --example` / installed `circuit-calculator gui --example`
  launches the prototype; F5 simulates. No-argument CLI and file DC commands remain.
  Tk/display failures get clean command errors; NumPy is still optional until solve.
- test_schematic.py adds 18 headless tests. scripts/check_gui.py adds nine opt-in
  Tk workflow checks, separate from headless discovery. Package verification checks
  both new modules and installed GUI help without requiring a display.
- Existing model, solver mathematics and circuit-file schema are unchanged.

Executed locally on Windows: source unittest suite **162 passed** on Python
3.11.9 and 3.14.6; `python -B -S -m unittest -q`: **146 passed, 16 expected skips**.
`python -B scripts/check_gui.py -q` and its Python 3.14 equivalent each passed
**nine Tk workflow tests**. Tests cover creation/movement/reference/delete/undo,
invalid values, async solve/error/stale completion, export/reopen and zoom hit
selection. Analytical editor divider resolves to out=8 V and V1 power=-0.048 W.
Visual inspection using the computer-use skill found overlapping vertical labels;
labels were anchored outward and the refreshed window was inspected. User edits
in the visible preview were left intact; manual screenshot-based solving is not
claimed as evidence. GUI window is left available for the user.

Limits: junction-based prototype, no free component placement/rotation or segment
routing/splitting. Native export saves topology/metadata only, not coordinates,
wire segmentation, view/history or selection. Reopen auto-arranges nodes. Default
save protections remain; replacing a file requires an explicit GUI confirmation.
Tk may need distributor installation; no new pip GUI dependency was added. Core
CI covers editor logic and package command help; hosted interactive GUI testing,
macOS, accessibility, performance and executable distribution remain unverified.
The next batch is full graphical-project persistence, not a phase-6 completion claim.

Installed validation: `python -B scripts/check_distributions.py` and
`py -3.14 -B scripts/check_distributions.py` each passed **146 tests with 16
expected skips** without NumPy, then **162 passed with no skips** using NumPy
2.4.6. Both environments passed pip check, installed GUI command help, existing
CLI/DC commands and editor topology tests. The wheel contains the seven current
product modules; the source archive includes GUI design and widget-test scripts.
`git diff --check` passed. No hosted GUI/CI execution is claimed.

## Batch REORG-1: package, tests and documentation organization

Status: VERIFIED locally, including source, Tk, wheel and editable-install checks.
Base `c4a13dd`, initially clean, no unrelated modifications to preserve. Local
package version is 0.3.1. This batch changes organization and packaging only.

- circuit_calculator/: the seven existing implementation modules, with main.py
  renamed to cli.py; package initializer and __main__ entry point added.
- tests/: all seven existing regression modules plus discovery initializer.
- docs/: all eight technical documents; README remains at repository root with
  a concise directory map and working relative links.
- requirements/: build.txt, dc.txt and ci-constraints.txt. Scripts and CI paths
  updated to match; no dependency versions or runtime requirements changed.
- compat/: seven small installed adapters, aliasing canonical modules so old
  imports retain exact module/class identity. New checkout imports use package
  paths; installed/editable environments retain old flat imports. Root main.py
  remains a thin compatibility launcher.
- scripts/ and examples/ retain their roles. Manifest, package metadata, command
  entry point and isolated installation checks updated. Source archives include
  the root launcher, moved docs/tests, requirements and compatibility adapters.
- AST comparison against HEAD confirmed all seven implementation modules and
  seven regression modules changed only import/patch paths, with no algorithm
  or expected-value changes. Function signatures, native file formats and GUI
  behavior remain unchanged.

Source verification: `python -B -m unittest -q` and `py -3.14 -B -m unittest -q`
passed **162 tests**. `python -B -S -m unittest -q` passed **146 with 16 expected
skips**. `python -B scripts/check_gui.py -q` passed **nine Tk workflow tests**.
The package DC command returned expected 8 V divider output; root launcher help
still works. All local Markdown links checked successfully. Distribution build
produced the new package plus compatibility modules.

Python 3.11 fresh wheel checks passed core-only **146 + 16 expected skips** and
DC **162, no skips** under NumPy 2.4.6. Canonical and installed legacy aliases were
verified identical. Editable installation then verified source-origin canonical
imports and the same legacy aliases outside the checkout. Python 3.14 completed
the same checks successfully: **146 + 16 expected skips** in core-only mode,
**162 with no skips** with DC, pip dependency checks, canonical/legacy module
identity and editable imports/command help. Nine Tk checks also passed on 3.14.
Build used `.venv-build/Scripts/python -m build`; the two install runs used
`python -B scripts/check_distributions.py` and its `py -3.14` equivalent.
Markdown links, syntax and whitespace checks passed. The built wheel retains
only product modules and adapters; docs/tests/requirements remain in the source
archive rather than being installed as importable application packages.

Migration: new source code should use `from circuit_calculator.circuit import
Circuit` (or other package modules) and `python -m circuit_calculator`.
`python main.py` remains available in the checkout; installed `python -m main`
and historical imports still work. Flat imports directly from an uninstalled
checkout now require installation or migration to the qualified package names.
No changes to running GUI sessions or user documents were requested/performed.
Hosted CI is configured but was not inspected/run from this session.

## Batch GUI-2: schematic-project persistence and safe file workflow

Status: source/project/Tk and fresh wheel/editable validation VERIFIED locally.
Base `992fbac`, initially clean; no unrelated modifications. No dependencies added.

- project_io.py defines immutable ViewState/SchematicProject and strict version-1
  project JSON. It stores original CircuitDocument identities/endpoints, metadata,
  positions, individual wires and bounded zoom/pan. Saving never compiles wires,
  so unfinished or temporarily unsolvable editor states remain editable.
- _document_io.py extracts bounded UTF-8/JSON/duplicate-key/numeric parsing and
  atomic file primitives shared by electrical and graphical formats. Native
  circuit I/O exposes owned validated data adapters for embedding. Existing native
  schema, public file functions and exception behavior remain covered by tests.
- GUI adds Open Project, Save Project, Save As, and an associated path. Two toolbar
  rows keep file/edit actions visible. Electrical Import/Export remain distinct.
  Dirty state compares graph and camera to the clean snapshot. Save clears it
  only on success; exporting a circuit does not save graphical work. Undo back
  to the clean state clears dirty, while camera-only edits retain valid results.
- Save / Discard / Cancel protects document changes and close. Canceled file
  dialogs, declined replacements and write failures preserve unsaved state.
  Failed project load preserves graph/view/results. Document reset clears history
  and increments the same monotonic revision, rejecting pending old results even
  for an identical graph.
- GUI command accepts a project path, validated before launching Tk. It rejects
  combining a path with --example. examples/divider.ccproj.json demonstrates
  preserved graph/layout/wire state; examples/divider.json remains electrical-only.
- 20 project tests, one session-boundary test and two command tests bring the
  headless suite to 185. Tk checks expand from nine to 18, covering project
  save/reopen/view restoration, cancellation, file preservation, dirty/Undo state,
  electrical export, failed loads and old results across document boundaries.
- Format, architecture, user/developer documentation and roadmap updated in docs/.

Executed on Windows: `python -B -m unittest -q` and `py -3.14 -B -m unittest -q`
passed **185 tests** each. Without site-packages: **168 passed, 17 expected skips**.
Both Python 3.11.9 and 3.14.6 passed **18 Tk workflow tests**. The analytical
project save/load/compile/solve round trip preserves out=8 V and source power
-0.048 W. Native circuit regressions pass after shared-helper extraction.
Syntax and local Markdown link checks passed. Fresh package checks on Python
3.11.9 and 3.14.6 each passed **168 tests with 17 expected skips** in core-only
mode and **185 with no skips** under NumPy 2.4.6. Both passed pip check, canonical
and legacy command/import identity, installed project save/load, and editable
source imports outside the checkout. Commands were `python -B
scripts/check_distributions.py` and the `py -3.14` equivalent. An isolated build
produced the 0.4.0 wheel from its source archive. No hosted CI result is claimed.

Limits: existing junction-based R/V/I editor and straight wires; free component
placement/rotation and terminal-level routing are still planned. Project v1 does
not persist results, Undo/Redo history, selection or active tool. Tk pan fractions
may quantize/clamp with pixel/viewport sizes; no exact screen-pixel restoration
across different window sizes is promised. Shared atomic saves retain hard-link
requirements and directory-fsync durability limits. No hosted GUI/CI run, macOS
GUI check, project-version migration or backend change is claimed.

## Batch GUI-3: independent symbol placement, movement and rotation

Status: source, Tk, project compatibility and fresh wheel/editable checks VERIFIED
locally. Phase 6 as a whole remains in progress.

Base `f68462d`, initially clean, no unrelated modifications or new dependencies.
Design/compatibility contract: COMPONENT_EDITING.md, with schema in
SCHEMATIC_FORMAT.md and rationale in DECISIONS.md.

- schematic.py adds immutable ComponentPlacement and two dedicated terminal nodes
  per placed R/V/I symbol. Coordinates/rotation are validated together; terminals
  remain stable through body movement and clockwise quarter-turn rotation. Wires
  keep their endpoint identities; overlapping geometry never connects electrically.
- Legacy junction-based components retain their representation on loading. First
  body movement/rotation allocates terminals with two explicit wires back to the
  original nodes. Compiled names, source polarity and DC results are preserved.
  One Undo restores the exact previous graph. Body deletion cleans owned nodes,
  incident wires and reference; terminals cannot move/delete independently.
- GUI tools place components on empty space or retain two-free-junction creation.
  Wire/Reference accept terminal dots. Body drag has a nonmutating preview and
  commits one history entry; click-only selection does not snap/convert a symbol.
  Rotate 90° and canvas R/R-shift shortcuts preserve connections. Labels/results
  show component terminal names rather than generated internal node identifiers.
- project_io.py saves strict v2 placements, loads v1 unchanged, and rejects invalid
  ownership/geometry/rotation. Existing v1 fixtures remain unchanged; the separate
  examples/placed-divider.ccproj.json is a v2 editable example. Native electrical
  import/export remains v1. Limits: 100 free junctions, 200 components, 500 total
  nodes, 800 wires; v1 input retains 100 nodes/400 wires. DC guard stays 200 unknowns.
- Fourteen headless tests and six Tk workflow tests cover geometry/topology,
  signed-source conversion, four rotations, deletion, exact Undo, limit rollback,
  strict migration, placement/wiring/drag/rotate and graphical reopen. Installed
  smoke checks now round-trip a placed/rotated project.

Executed source checks: Python 3.11.9 and 3.14.6 each passed **199 tests**.
`python -B -S -m unittest -q`: **181 passed, 18 expected optional-NumPy skips**.
Both interpreters passed **24 opt-in Tk workflow tests**. The analytical placed
divider retains **8 V output**, **-0.048 W source power** and balanced total power
after movement/rotation/save/load. Live placed-divider layout inspected using the
computer-use skill; terminal labels, polarity and toolbar controls were visible.
The live keyboard-R rotation retained attached wires, Ctrl+Z restored the layout,
and F5 displayed 8 V / -0.048 W with zero reported KCL/power residuals. The preview
was left open at the original saved layout; no example file was overwritten.

Fresh package checks on Python 3.11.9 and 3.14.6 each passed **181 tests with 18
expected skips** in core-only mode and **199 with no skips** under NumPy 2.4.6.
Both passed pip check, canonical/legacy command and module-identity checks,
placed/rotated project save/load, and editable source imports outside the checkout.
Commands: `python -B scripts/check_distributions.py` and the `py -3.14` equivalent.
An isolated build produced the 0.5.0 source archive and wheel. Wheel application
modules match the checkout byte-for-byte; the source archive includes the new
design/tests/example. Python syntax, local Markdown links and `git diff --check`
passed; native circuit/model/solver/formula files and existing v1 fixtures are
unchanged. No hosted CI result is claimed.

Limits: straight wires only, no segment routing/splitting, automatic connection,
copy/paste, rename or multi-selection. A bare starting n1 junction must be wired
or deleted before solving another network. New saves require a v2-capable app;
Save As retains an original v1 copy. At least one node must remain after deleting
a body. Geometry edits conservatively clear simulation results. No hosted CI or
cross-platform GUI validation is claimed. The complete phase-6 milestone remains
in progress.

## Batch GUI-4: routed wires and explicit segment splitting

Status: source, Tk, compatibility, physical equivalence and fresh wheel/editable
installation VERIFIED locally. The full phase-6 milestone remains in progress.

Base `c0951d8`, initially clean. No unrelated modifications or new dependencies.
Design contract: WIRE_ROUTING.md; schema: SCHEMATIC_FORMAT.md; rationale: DECISIONS.md.

- Wire owns immutable Waypoint bends (32 maximum); existing three-argument
  construction remains compatible. Only endpoint identities resolve electrical
  nets. Bends/crossings/overlap cannot connect nodes. Endpoint movement retains
  interior world-coordinate bends; geometry can include diagonal segments.
- Schematic exposes path points, nearest-segment projection, route replacement
  and explicit splitting. Splitting preserves route portions and the original
  first-half name, allocates a second wire name, and creates a junction unless an
  existing free junction is explicitly reused. Reject original endpoints,
  degenerate segments, component-terminal reuse, invalid geometry and limits
  before replacing state. One split of a crossing affects only the chosen wire.
- GUI Wire clicks add pending bends between explicit dots. Dashed previews stay
  outside saved graph/scroll bounds; Escape cancels, Backspace removes a bend.
  Reroute/straighten preserve endpoint identities; reroute must finish at the
  original ending dot. Invalid route input preserves pending work for correction.
  Other committed edits cancel pending routes to avoid stale references.
- Split Wire uses projected segment hits. At overlaps, select the intended wire
  away from the crossing first. To join both wires, split each explicitly using
  the same junction. Undo/Redo restores exact paths/topology. No implicit splits.
- Project v3 requires bounded x/y bend records on every wire; load v1/v2 with no
  bends and strict old schemas. Older fixture files remain unchanged. The separate
  examples/routed-divider.ccproj.json demonstrates a v3 routed/split divider.
  Native electrical format/model/solver/formula behavior remains unchanged.
- Fifteen headless and nine Tk tests cover ownership, movement, path partition,
  diagonal/degenerate projection, explicit net merge/split, limit/error rollback,
  exact history, strict version migration and real route/file/export workflows.
  Installed smoke checks round-trip a placed/rotated/routed/split project.

Source verification: `python -B -m unittest -q` and the `py -3.14` equivalent
passed **214 tests** each. Without site-packages: **195 passed, 19 expected NumPy
skips**. Both Python 3.11.9 and 3.14.6 passed **33 opt-in Tk workflow tests**.
Analytical routed/split/save/load result: **out=8 V**, **R1 current=0.004 A**,
**V1 power=-0.048 W**, balanced total power. The first expanded Tk run exposed
Tcl cleanup on a worker thread; the harness now joins workers and collects obsolete
test-window cycles on the owning thread, with normal GC still enabled.
Live routed layout and explicit segment split inspected using the computer-use
skill. Ctrl+Z restored the saved layout; Select mode and F5 left the preview open
with out=8 V, V1=-0.048 W and zero reported KCL/power residuals. No original
example or user document was overwritten.

Fresh installation checks on Python 3.11.9 and 3.14.6 each passed **195 tests
with 19 expected skips** without NumPy, then **214 tests with no skips** under
NumPy 2.4.6. Both passed pip check, canonical/legacy command/module identity,
routed/split project round trips and editable imports outside the checkout.
Commands: `python -B scripts/check_distributions.py` and the `py -3.14` equivalent.
An isolated build produced the 0.6.0 wheel from its source archive. Wheel modules
match the checkout; v1/v2/v3 examples compile to the same electrical document.
Syntax, local Markdown links and `git diff --check` passed. Core electrical
model/solver/formula files and existing v1/v2 fixtures are unchanged; the index
is empty. No hosted CI run is claimed.

Limits: manually entered straight/diagonal segments, no bend dragging, automatic
orthogonal routing or obstacle avoidance. Splitting permits 1e-8 world units of
geometric roundoff only within the explicit operation. At self-overlapping path
segments the nearest segment is used, with the first segment winning ties. Bends
remain fixed during endpoint movement. New saves need a v3-capable app; preserve
older originals with Save As. No hosted CI or cross-platform GUI result is claimed.
Phase 6 remains in progress.

## Batch GUI-5: bend editing and optional right-angle routing

Status: source, Tk, fresh wheel/editable installation and visual checks VERIFIED
locally; committed as `0087d36`.

Base `9dc4c4c`, initially clean. BEND_EDITING.md defines scope and acceptance.
No electrical model/solver/device changes, dependencies or format migrations.

- schematic.py adds deterministic Manhattan geometry through explicit anchors,
  preserving endpoints/reversals and simplifying duplicates/between-collinear
  points. Add validated bend insertion/movement/removal and selected-wire conversion.
- GUI shows bend handles only for the selected wire in Select mode. Drag previews
  retain saved state/history/scroll bounds; release commits once and Escape cancels.
  Click-only selection preserves off-grid geometry. Shift-click inserts a projected
  bend; Delete removes the selected bend while keeping the wire. Tags separate
  Unicode/colon wire names from indices. Selection handles do not alter scroll bounds.
- Optional Right-angle wires applies to completed new/rerouted paths, with Space
  toggling elbow order. Orthogonalize converts one selected wire. Preferences are
  transient and do not dirty projects or invalidate electrical results. Generated
  paths obey the existing 32-bend limit; failure retains pending anchors for correction.
  Later movement can make segments diagonal, with no implicit route constraints.
- Twelve headless tests plus nine real Tk tests cover independent route answers,
  geometry/identity invariance, count/bounds failures, one-step history/cancel,
  drag/no-op, zoomed Unicode handles, generated-path rollback, preview/completion,
  electrical isolation of elbow dots, preference/result behavior and toolbar fit.
  Installed smoke checks include bend movement and right-angle conversion.

Source: **226 tests passed** on Python 3.11.9 and 3.14.6; without site-packages,
**206 passed, 20 expected NumPy skips**. Both interpreters passed **42 Tk tests**.
Analytical result remains **out=8 V**, **source power=-0.048 W**, balanced power.
Fresh core-only installs on both interpreters passed **206 tests with 20 expected
skips**, followed by **226 with no skips** under NumPy 2.4.6. Canonical/legacy
commands and class identity, pip check, edited-project round trips and editable
source imports outside the checkout passed. Commands: scripts/check_distributions.py
with Python 3.11 and 3.14, after an isolated 0.7.0 build.
The live preview showed square handles, a successful mouse drag and explicit
right-angle conversion. Source model/solver/formula files and v1/v2/v3 examples
remain unchanged. Syntax, documentation links and diff whitespace checks passed.

Limits: no obstacle avoidance, persistent orthogonal constraint or automatic
rerouting during movement. All edits retain existing endpoint/net identities.
Package 0.7.0, project v3, native electrical v1. Hosted CI remains unverified.

## Batch GUI-6: measured viewport and renderer separation

Status: source, real Tk, fresh wheel/editable installation and visual checks
VERIFIED locally; committed as `199bb16`.

Base `0087d36`, initially clean. VIEWPORT.md records requirements and camera
compatibility. No graph/device/solver changes, dependencies or schema migration.

- canvas_renderer.py contains the existing symbols, labels, dots, wires and bend
  handles. gui.py delegates drawing while retaining editing, dialogs and workers.
  Tagged circuit content excludes grid, handles and previews from fit/scroll bounds.
- viewport.py supplies independently tested fit/zoom/scroll arithmetic with explicit
  type/range/nonfinite failures. Fit remeasures readable fixed-size labels, respects
  existing zoom limits and reports when scrolling is still needed. 100% and plus/
  minus zoom preserve the viewed world center; resize does too.
- Scroll bounds permit centering every part of the circuit. Lazy actual Tk size
  realization is reconciled without dirtying a clean initial view or losing saved
  camera input. A cancellation regression caught this and remains covered.
  Camera actions retain current numerical results and geometry history.
- Seven headless and seven mapped Tk tests cover math/import boundaries, actual
  label/content visibility, zoom/reset/resize center, signed/extreme layouts,
  selection/preview exclusion, graph/result invariants and saved-camera round trips.
  Fresh installation checks also verify origins of both new modules.

Source: **233 tests passed** on Python 3.11.9 and 3.14.6; without site-packages,
**213 passed, 20 expected NumPy skips**. Both interpreters passed **49 Tk tests**.
Fresh core-only installs on both interpreters passed **213 tests with 20 expected
skips**, then **233 with no skips** under NumPy 2.4.6. Both new modules resolve
inside the fresh environment; import/command compatibility, pip check and editable
source imports passed. A live routed project was fully fitted with readable labels.
Static extraction review preserved all 14 Canvas creation sites; drawing remains
covered by the existing editing/solver/file workflows. Build/format version: 0.8.0/v3.

Limits: existing 0.4–2.5 zoom range can require scrolling for very large circuits.
View fractions remain v3 leading fractions, but older renderer bounds can produce
a different camera view. Graph/layout and existing fixture files remain unchanged.
No hosted CI result claimed. Phase 6 remains in progress.

## Batch RESULTS-1: full-precision DC CSV export

Status: source, Tk, fresh wheel/editable checks and actual CLI JSON/CSV comparison
VERIFIED locally; prepared for the authorized local commit.

Base `199bb16`, initially clean; no new dependencies or circuit/project schema change.
RESULTS_CSV.md specifies the versioned long-form export and failure behavior.

- results_io.py serializes existing DCResult snapshots with explicit V/A/W/1 units,
  full float precision and signed currents/power. Reference/net/element/diagnostic
  rows use deterministic ordering. Literal qualified identifiers preserve names
  including Unicode, quotes, delimiters and control characters.
- Validate result types, finite values and the zero-volt reference before atomic
  output. Default writes refuse existing paths, replacement is explicit, and
  protected input/project paths reject resolved/same-file aliases. No truncation.
- `dc INPUT --csv OUTPUT [--overwrite-csv]` retains default JSON stdout. CSV is
  produced only after a successful solve; CSV failure produces error/exit 1 and
  no JSON. The input document cannot be replaced, even with the overwrite flag.
- GUI Export CSV requires a current accepted result. Edits/history/new simulations/
  document boundaries disable it; view changes preserve it. Cancel/decline/failure
  leave graph, dirty state, result and output untouched. Stale workers cannot export.
- Twelve headless and five Tk tests cover values/units/signs, exact float recovery,
  Unicode/control quoting, literal identifiers, malformed data, atomic preservation,
  path protection, JSON/CSV agreement and current/stale/canceled GUI workflows.
  Installed command checks exercise optional CSV in canonical/legacy entry points,
  including missing-NumPy failure without a created CSV.

Source: **245 tests passed** on Python 3.11.9 and 3.14.6; without site-packages,
**224 passed, 21 expected NumPy skips**. Both passed **54 Tk workflows**.
Actual CLI JSON/CSV agree on **out=8 V** and **V1 power=-0.048 W** (16 CSV rows).
Fresh installs on both interpreters passed **224 tests with 21 expected skips**
in core-only mode, then **245 with no skips** under NumPy 2.4.6. CSV command
checks passed through console, canonical module and legacy module entry points;
missing NumPy creates no CSV. Origin, pip dependency and editable imports passed.
The live GUI shows Export CSV disabled before simulation; no user document or
existing example was replaced. Package 0.9.0 was built from its source archive.

Limits: CSV describes compiled electrical nets, not every graphical alias. It is
an export, not a circuit/result-cache import format. No display prefixes/rounding
are applied. Project v3/native circuit v1 stay unchanged. Hosted CI remains unverified.

## Exact next action

Commit RESULTS-1 with explicit paths. Then configure a bounded
Linux display-enabled Tk CI lane and strengthen analytical grid/size validation
of the existing DC solver. No push is authorized; do not claim hosted results.
