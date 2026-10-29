# Testing

## Commands

```text
python -B -m unittest -v
python -B -m unittest -v tests.test_dc
python -B -S -m unittest -v
python -B scripts/check_distributions.py
git diff --check
```

`-B` avoids writing bytecode. `-S` omits site-packages: it exercises the
standard-library baseline and DC assembly while NumPy solve tests skip. Skips
are not solver verification. Without NumPy installed, use requirements/dc.txt
before assessing the full solver suite.

`scripts/check_distributions.py` requires a built wheel in `dist/` (see
DEVELOPMENT.md). It tests a fresh venv first without NumPy, then with the pinned
DC extra. Product modules must resolve inside that venv. Test files alone are
copied into a temporary directory outside the source modules and run using
isolated Python. The installed command, `python -m circuit_calculator`, and legacy
`python -m main` are exercised. Installed flat-import aliases must be identical
to their canonical package modules. The temporary environment is then checked
with an editable install, outside the checkout.
DC checks fail if any test is skipped. Core-only checks verify missing-dependency
advice and explicitly accept optional-solver skips.

The GitHub workflow targets CPython 3.11–3.14 on Windows/Linux. Hosted results
are not available until the workflow has actually been committed/pushed and run.
An additional Ubuntu 24.04 installed-GUI matrix (3.11/3.14) is configured under
Xvfb after the eight core/DC jobs; hosted execution remains unverified.

`python -B scripts/check_distributions.py --gui` additionally runs all Tk workflows
inside the fresh installed DC environment before switching it to editable mode.
The child uses `-I` and `--installed`, verifies origins and never inserts source
modules into sys.path. This needs a desktop display or an external Xvfb wrapper.

## Layers and references

- Legacy suite: formula validation and injected-I/O CLI workflows.
- Numerical suite: native Integer/Fraction/Decimal return policies; conversion
  and arithmetic overflow/underflow; subnormal versus actual-zero values;
  independent 100-digit Decimal power references; resistance invariants; CLI
  rejection of nonzero text that float parsing would silently turn into zero.
- Model suite: immutable component parameters, names, nodes and reference.
- Persistence suite: every element's round trip, normalized deterministic output,
  metadata/Unicode, malformed and duplicate fields, numeric/type/range failures,
  byte/depth/count limits, no-clobber/atomic replacement and failed-write cleanup.
- Project suite: exact uncompiled graph/layout/wire/metadata/view round trips,
  strict format/version/schema/numeric/resource failures, atomic preservation,
  native-format distinction and project-to-DC physical equivalence.
- DC command suite: preserved interactive menu, known-answer native-file JSON,
  bad arguments/files/topology, missing NumPy advice and pre-solve size guard.
- Editor logic suite: coordinates/crossings never connect, explicit wire
  merge/split/cycles, source orientation, delete/undo/redo, bounded history,
  revision-scoped result acceptance and analytical compiled-circuit results.
- Component editing suite: dedicated terminal allocation/ownership, four rotations,
  attached-wire invariants, legacy conversion for R/V/I, invalid geometry and
  limit rollback, deletion/reference cleanup, exact Undo, strict v1/v2 project
  compatibility and analytical placed-divider results.
- Wire routing suite: owned/bounded bends, fixed interior geometry during movement,
  reroute identity, diagonal/degenerate segment projection, split path partition,
  explicit crossing merge and deletion split, rollback at limits, Undo/Redo,
  strict v1/v2/v3 compatibility and analytical routed-divider equivalence.
- Bend editing suite: independently derived Manhattan paths in both orders,
  duplicate/collinear/backtracking behavior, exact endpoints, bend edit validation,
  generated-count rollback, history/format stability and analytical DC invariance.
- Viewport suite: independent fit/scroll arithmetic, signed/extreme/tiny bounds,
  invalid inputs and renderer/view imports with no Tk/NumPy side effects.
- Results CSV suite: independent values/signs/units, exact float recovery, quoting,
  literal Unicode/control identifiers, strict result validation, atomic preservation,
  path-alias protection, unchanged JSON plus optional CSV and CLI failures.
- Opt-in Tk checks: `python -B scripts/check_gui.py -v` in a display session with
  NumPy. Fifty-four tests exercise canvas hit targets/movement, creation/edit errors,
  reference/delete/undo, async success/failure/stale results, zoom and export/open,
  graphical save/reopen/view state, cancellation, failed saves/loads, dirty-state
  restoration and stale completion across document boundaries; blank placement,
  terminal wiring/reference, body drag/rotate, click-only selection, legacy
  conversion/Undo, terminal deletion protection and placed-project reopening.
  Routing checks cover preview/completion, cancel/Backspace, bend limits,
  reroute/straighten, explicit crossing splits/joins, zoomed path hit targets,
  endpoint/terminal rejection, stale-route cancellation and routed save/export.
  Bend tests cover drag/cancel/no-op, zoomed Unicode/colon handle tags, Shift-insert,
  Delete, right-angle preview/completion, elbow order, preference/result isolation,
  generated-count failure and minimum-width toolbar visibility.
  View tests map a real drawing area and verify full content/text fit, center
  preservation during zoom/reset/resize, graph/result/history invariance, signed
  and large layouts, handle/preview exclusion and saved fit-camera restoration.
  CSV tests cover accepted results/camera preservation, edit/history/new-solve
  invalidation, canceled/declined/failed writes, current-project protection and
  stale worker completion without opening an export dialog.
- DC assembly: explicit hand-written MNA matrix and RHS; topology errors.
- Grid reference suite: affine voltage fields on 2x2 through 12x12 resistor grids,
  independent boundary-source currents, every branch's V/I/P, KCL at all nodes,
  aggregate resistor/source power, node/element order and nonzero reference shifts.
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

## Latest local run: 2026-10-29

GUI-8 passed **264 headless tests** and **69 source Tk workflows** on both local
interpreters. The core-only run passed 239 with 25 expected NumPy skips. Fresh
offline installations on both passed the same 239 core/264 DC/69 installed Tk
counts with pinned NumPy 2.4.6, plus import/entry-point/CSV/dependency/editable checks.
Eight new headless tests cover R/V/I snapshot/identity/geometry/limit/history/file
invariants and an independent 6 V wired-copy divider. Nine Tk additions verify
placement/rotation/cancellation, clipboard isolation, save/undo, real keyboard
bindings and rejection of stale worker results. Preview items lack graph hit tags
and do not change scroll bounds or numerical revision.

GUI-7 source checks passed **256 headless tests** and **60 Tk workflows** on
Python 3.11.9 and 3.14.6. Core-only mode passed 232 with 24 expected NumPy skips.
Eight identity tests and six Tk workflows were added, including namespace/ground/
terminal invariants, exact project/history recovery, analytical divider values,
failed/no-op value edits, delayed-worker rejection and toolbar visibility at
900x600. Native v1/project v3/CSV v1 and numerical engine files remain unchanged.
Fresh installs on both interpreters passed the same 232 core/256 DC/60 Tk checks,
plus command/import/CSV/editable/dependency validation. The isolated build and
installs used cached exact pinned wheels offline after a PyPI DNS failure;
details are in PROJECT_STATUS.md. Hosted Linux checks remain unverified.

## Previous local run: 2026-10-28

DC-GRID: **248 headless tests** passed on Python 3.11.9 and 3.14.6; without
site-packages **225 passed with 23 expected NumPy skips**. Three grid tests were
added. Warmed 4/8/12 grids (28/92/188 unknowns) passed the independent oracle on
NumPy 1.26.4 and 2.5.2. Both native CLI paths solved the 188-unknown case and
exported 1,073 CSV rows with exact JSON/CSV node values. See DC_VALIDATION.md for
raw measurement scope, accuracy and environment-specific timings. Application
code is unchanged since RESULTS-1, so the prior 54 source/installed Tk workflows
remain the relevant GUI evidence; no redundant GUI rerun is claimed. Final fresh
installs passed 225 core tests with 23 expected skips, then all 248 under NumPy
2.4.6, on both interpreters. Command/CSV/origin/dependency/editable checks passed.

CI-GUI: workflow YAML parsed and 8 core/DC plus 2 installed-GUI jobs checked.
Both local Windows interpreters passed 224 core tests with 21 expected NumPy
skips, 245 full DC tests and 54 isolated installed Tk workflows, followed by
editable checks. Product origins were verified inside the fresh environments.
No hosted Linux execution is claimed.

RESULTS-1: **245 headless tests** passed on Python 3.11.9 and 3.14.6; without
site-packages **224 passed with 21 expected NumPy skips**. Both interpreters passed
**54 Tk workflows**. Twelve CSV/API/CLI tests and five GUI workflows were added.
The actual divider command emitted JSON/CSV agreeing on out=8 V and source power
=-0.048 W. Fresh core installs on both interpreters passed 224 tests with 21
expected skips, then all 245 under NumPy 2.4.6. Console/canonical/legacy CSV
commands, missing-dependency preservation, origins, pip check and editable imports
passed. Circuit/project formats and numerical algorithms remain unchanged.

GUI-6: **233 headless tests** passed on Python 3.11.9 and 3.14.6. Without
site-packages: **213 passed, 20 expected NumPy skips**. Both interpreters passed
**49 Tk tests**, including seven new viewport workflows. Seven headless viewport/
import tests were added. An initial cancellation regression exposed lazy Tk size
realization; it was fixed without weakening the saved-state assertion. Fit tests
map their windows, rather than treating a withdrawn 1-pixel canvas as visible.
Fresh core-only installs passed 213 tests with 20 expected skips, then all 233
under NumPy 2.4.6, on both interpreters. Both new modules passed installed-origin
checks; dependency, command/alias and editable checks passed. Live Fit Circuit
included the entire routed layout and labels. All 14 Canvas creation sites were
preserved by extraction. No hosted CI evidence is claimed.

GUI-5: source checks passed **226 headless tests** on Python 3.11.9 and 3.14.6;
without site-packages **206 passed with 20 expected NumPy skips**. Both interpreters
passed **42 real Tk workflows**. Twelve headless and nine widget tests were added.
Fresh core-only installs on both interpreters passed 206 tests with 20 expected
skips, then all 226 under NumPy 2.4.6. Dependency, canonical/legacy command/import,
edited-project round-trip and editable source checks passed. Live handles, drag
and right-angle conversion were inspected. No hosted CI evidence is claimed.

GUI-4: **214 headless tests** passed on Python 3.11.9 and 3.14.6. Without
site-packages, **195 passed, 19 expected NumPy skips**. Both interpreters passed
**33 Tk workflow tests**. Fifteen new headless tests and nine new Tk tests cover
routes/splits and v1/v2/v3 compatibility. The routed/split/save/load divider
retains 8 V output, 4 mA resistor current and -0.048 W source power. An initial
expanded Tk run exposed cross-thread collection of obsolete test-window cycles;
the harness now joins workers and collects those cycles on the main thread.
Current runs pass with normal garbage collection enabled. Fresh wheel checks on
both interpreters passed 195 tests with 19 expected skips without NumPy, then all
214 under NumPy 2.4.6. Installed command/import compatibility, routed/split project
persistence, pip dependency checks and editable imports passed. The live routed
layout, Split Wire, Undo and F5 were visually checked; output remains 8 V with
-0.048 W source power and zero reported KCL/power residuals. Wheel modules match
the checkout; old/new examples compile equivalently. No hosted CI claim.

GUI-3: all 199 headless tests passed on Python 3.11.9 and 3.14.6. Without
site-packages, 181 passed with 18 expected optional-NumPy skips. All 24 opt-in Tk
workflow tests passed on each interpreter. Movement/rotation preserve the divider's
8 V output and -0.048 W source power; strict v1 loading/v2 output, 500-node limits
and failed-edit rollback are covered. The placed-divider window was also visually
inspected for terminal labels and toolbar layout; keyboard rotation, Undo and
simulation were exercised. Fresh wheel checks on both interpreters passed 181
tests with 18 expected skips without NumPy, then all 199 under NumPy 2.4.6.
Installed commands/import aliases, placed-project round trips, dependency checks
and editable imports passed. Wheel modules match the source; source archives
include the new design/tests/example. No hosted CI result is claimed.

GUI-2: 185 headless tests passed on Python 3.11.9 and 3.14.6; without site-packages,
168 passed with 17 expected optional-NumPy skips. All 18 Tk workflow tests passed
on each interpreter, including project round trips, cancel/error preservation,
saved-state Undo, camera-only changes and stale results after a document reset.
Existing circuit-format tests passed after extracting shared JSON/file primitives.
The new project-to-DC example retains its analytical 8 V / -0.048 W result.
Fresh installed checks on both interpreters passed 168 tests with 17 expected
skips without NumPy, then all 185 with NumPy 2.4.6. Project API round trips,
legacy/canonical commands and module identity, pip dependency checks and editable
source imports passed. Tk workflows remain explicit local display tests.

REORG-1: all 162 existing tests and nine Tk workflow checks passed on Python
3.11.9 and 3.14.6 after moving code/tests into folders. Core-only checks passed
146 with 16 expected optional-NumPy skips. Fresh wheel installations passed
those same core/DC suites on both versions; pip dependency checks, installed
canonical/legacy command forms and module identity passed. Editable installs
also resolved canonical and historical imports outside the checkout. AST
comparison confirmed the seven implementations and seven regression modules
changed only import/patch paths. Markdown links and distribution paths checked.

GUI-1: 162 headless tests passed on Python 3.11.9 and 3.14.6; without site-packages,
146 passed with 16 expected optional-NumPy skips. Nine opt-in Tk workflow tests
passed on each interpreter. Visual inspection of the live editor identified and
fixed vertical component-label overlap. Interactive preview changes made by the
user were preserved; analytical DC results are verified by automated workflows,
not claimed from a manual simulation screenshot.

GUI-1 fresh installed checks on both interpreters passed 146 tests with 16
expected skips in core-only mode, then all 162 with no skips under NumPy 2.4.6.
Installed GUI help is exercised without importing Tk; interactive Tk checks remain
the explicit local nine-test script, not a hosted CI claim. Wheel contents match
the seven current product modules, and the source archive includes GUI design
and widget-test scripts.

PERSIST-1: Python 3.11.9 and 3.14.6 source runs each passed 144 tests. Without
site-packages: 129 passed and 15 optional-NumPy tests skipped. This batch adds
27 persistence tests and 7 command tests. The divider example executed through
`python -m circuit_calculator dc examples/divider.json` with 8 V output, 4 mA resistor currents
and zero reported KCL/power residuals. Fresh installed checks passed on both
interpreters: 129 passed with 15 expected skips in core-only mode, then all 144
with no skips under NumPy 2.4.6. These runs also exercised document save/load,
both console/module DC commands, and pip dependency checks outside the checkout.

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
