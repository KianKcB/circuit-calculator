# Circuit Calculator

A Python circuit calculator with standalone electrical formulas, linear DC
network analysis, and a Tk desktop editor prototype.

## Features

- **Series resistance:** sums a non-empty iterable of resistances.
- **Parallel resistance:** calculates equivalent resistance using the reciprocal-sum formula. A zero-ohm branch produces zero equivalent resistance and is reported as a short circuit.
- **Ohm's law:** calculates one missing quantity from the other two using `V = I × R`. Choose voltage, current, or resistance as the quantity to solve for.
- **Electrical power:** calculates power in watts from voltage and current (`P = V × I`), current and resistance (`P = I² × R`), or voltage and resistance (`P = V² / R`).
- **Voltage divider:** calculates the ideal voltage drop across a selected resistor in a series network.
- **Current divider:** calculates current through a selected branch in a parallel network, including defined ideal short-circuit cases.
- **Interactive CLI:** guides you through each calculation, shows units, and returns to the menu after successful calculations or handled input errors.
- **Native circuit documents:** versioned JSON with circuit metadata, strict input validation and safe explicit saves.
- **DC file command:** solves a supported circuit document and returns JSON results with units and diagnostics.
- **Desktop prototype:** Tk editor with independent R/V/I placement, movement and rotation, routed wires, explicit wire splitting, reference selection, undo/redo, project save/reopen, circuit import/export and DC results.

## Project layout

```text
circuit-calculator/
├── circuit_calculator/  # Models, formulas, solver, persistence, CLI and GUI
├── tests/               # Headless regression suite
├── docs/                # Architecture, roadmap, status and format specifications
├── requirements/        # Build/DC dependencies and CI constraints
├── scripts/             # Build/install and optional Tk verification helpers
├── examples/            # Example circuit documents
├── compat/              # Installed adapters for historical flat imports
├── main.py              # Small compatibility launcher for the checkout
├── pyproject.toml       # Package metadata and command entry point
└── README.md
```

Application modules live together in `circuit_calculator/`: `circuit.py` is the
model, `calculations.py` standalone formulas, `dc.py` analysis, `circuit_io.py`
persistence, `schematic.py` editor state, `gui.py` Tk rendering, and `cli.py` command
handling. `project_io.py` stores graphical projects; `_document_io.py` shares
strict JSON and atomic-file handling between the two formats.
Start with [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for current
progress and [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for development commands.

## Requirements and setup

- Python 3.11 or newer; the maintained CI target is CPython 3.11–3.14 on
  Windows and Linux. Newer versions are outside the current test matrix.
- The formula CLI and circuit model need only the standard library. DC solving
  adds the optional NumPy dependency.
- Version 0.20.0 is currently a local development package. Installation commands
  below use this checkout; it has not been published to a package registry.

Open a terminal in the project directory and check that Python is available:

```bash
python --version
```

For an isolated installation from this directory on Windows:

```text
python -m venv .venv
.venv\Scripts\python -m pip install .
.venv\Scripts\circuit-calculator
```

For DC support, install the extra instead:

```text
.venv\Scripts\python -m pip install ".[dc]"
```

On Linux/macOS the equivalent paths are `.venv/bin/python` and
`.venv/bin/circuit-calculator`. macOS is not currently in the CI matrix.
The base install has no third-party runtime dependencies; building/installing
uses setuptools. Source-only formula use still needs no installation step.
New code uses imports such as `from circuit_calculator.circuit import Circuit`.
After installation, older imports such as `from circuit import Circuit` also
work through the adapters in `compat/`. Source-only code should use package imports.

For development and repeatable dependency checks, see [DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Run the application

```bash
python -m circuit_calculator
```

After installation you can also use `circuit-calculator` from the environment's
Scripts/bin directory. Existing `python main.py` checkout commands and installed
`python -m main` commands still work.

Choose an operation from the menu:

1. Calculate equivalent resistance in series.
2. Calculate equivalent resistance in parallel.
3. Use Ohm's law.
4. Calculate electrical power.
5. Calculate voltage/current dividers.
6. Exit.

For series and parallel calculations, enter one resistance in ohms per line. Press Enter on a blank line to finish entering values. For Ohm's law, choose the quantity to calculate and enter the other two values when prompted.

## Usage examples

### Series resistance

Choose option `1`, enter `10`, then `20`, and press Enter on a blank line. The result is `30.0 Ω`.

### Parallel resistance

Choose option `2`, enter `10`, then `10`, and press Enter on a blank line. The result is `5.0 Ω`.

If any parallel branch is `0 Ω`, the equivalent resistance is `0.0 Ω` and the CLI displays a short-circuit warning.

### Ohm's law

Choose option `3`, then choose `2` to calculate current. Enter a voltage of `12` and a resistance of `6`. The result is `2.0 A`.

The CLI displays resistance in ohms (`Ω`), voltage in volts (`V`), and current in amperes (`A`). Enter plain numeric values; the CLI does not parse unit suffixes such as `V` or `kΩ`.

### Electrical power

Choose option `4`, then select which two known quantities to use. For example, choose current and resistance, enter `2` amperes and `3` ohms, and the result is `12.0 W`. The other supported combinations are voltage and current, and voltage and resistance. Power from voltage and current can be negative when their signs indicate power flowing in the opposite direction.

### Voltage divider

Choose option `5`, then `1`. Enter the total input voltage and the series resistor values, one per line, ending with a blank line. Then select the resistor by its one-based position in the list. For example, with `12 V` across `1000 Ω` and `2000 Ω`, selecting resistor `2` returns `8.0 V`.

For an ideal series network, the voltage across resistor `Rk` is `Vk = Vin × Rk / (R1 + R2 + ... + Rn)`. The input voltage may be positive, zero, or negative. The function's `target_index` is zero-based; the CLI uses one-based selections.

### Current divider

Choose option `5`, then `2`. Enter the total current and parallel branch resistances, one per line, ending with a blank line. Select the branch by its one-based position. For example, a total current of `6 A` through parallel branches of `2 Ω` and `6 Ω` gives `4.5 A` through branch `1`.

For an ideal parallel network with positive branch resistances, `Ik = Itotal × (1/Rk) / Σ(1/Rj)`. A single zero-ohm branch carries all supplied current and the positive-resistance branches carry zero. If multiple zero-ohm branches are present, current through a selected shorted branch is undefined; an all-zero network is also undefined. The function's `target_index` is zero-based; the CLI uses one-based selections.

## Input validation and errors

- Resistance calculations require at least one value. Values must be finite, real, and non-negative; booleans, complex values, and text are rejected by the calculation functions.
- The CLI reads each entry as a number. Non-numeric entries and invalid calculation values produce an error message and return to the main menu.
- Ohm's law requires exactly two known values and a valid target quantity. Voltage and current may be signed, while resistance must be non-negative.
- Power calculations require exactly two of voltage, current, and resistance. Voltage and current may be signed; resistance must be finite and non-negative. Calculating power from voltage and zero resistance is undefined and reported as an error.
- Divider calculations accept finite real input voltage/current and finite non-negative resistor values. Target indices in the Python functions are zero-based and must be in range; the CLI asks for a one-based resistor or branch number. A voltage divider with zero total resistance is undefined. A current divider with multiple shorted branches is undefined for a selected shorted branch, and any all-zero-resistance network is undefined.
- A current cannot be calculated when resistance is zero, and resistance cannot be calculated when current is zero. These cases are reported as calculation errors.
- Invalid menu choices are reported without terminating the program. Choosing exit, or ending input with Ctrl+C or end-of-file, exits cleanly.

### Numeric range and return types

Series sums retain integer/Fraction arithmetic for those inputs, and Decimal
arithmetic for Decimal/integer mixtures. Decimal sums follow the active Decimal
context. Other mixtures, including Decimal with float or Fraction, return a
float. Float sums use accurate summation and reject overflow.

Parallel resistance, Ohm's law and power return float results (parallel wraps
its value in `ParallelResistanceResult`). They reject nonzero inputs or results
that round to zero and values outside finite float range with `ValueError`.
Representable subnormal values remain valid: a `1e-320` ohm branch is not a
short circuit. CLI text that is too small to survive float conversion is also
rejected. True zero follows the physical rules above.

Power calculations avoid intermediate squaring overflow/underflow. For example,
`calculate_power(current=1e200, resistance=1e-200)` returns approximately
`1e200` watts. Inputs still normalize to floats; this is not arbitrary-precision
power analysis. Negative power from voltage/current is supported.

Divider policies are unchanged: voltage division rejects an overflowing total
resistance, while negligible current-divider conductance weights may round to
zero. Ordinary floating-point rounding still applies to every float result.

## Run the tests

From the project directory, run:

```bash
python -m unittest -v
```

## Current limitations

The menu still exposes only standalone formulas. The Python DC API below solves
small linear networks of positive resistors and independent sources. The first
desktop network editor is available below. Controlled/reactive/nonlinear
components are not yet implemented. GUI component values accept SI engineering
prefixes; numerical policies and remaining limitations are recorded in
[PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## Linear DC analysis from Python

```python
from circuit_calculator.circuit import Circuit, Resistor, VoltageSource
from circuit_calculator.dc import solve_dc

circuit = Circuit(
    nodes=("ground", "input", "output"),
    elements=(
        VoltageSource("V1", "input", "ground", 12),
        Resistor("R1", "input", "output", 1000),
        Resistor("R2", "output", "ground", 2000),
    ),
    reference_node="ground",
)
result = solve_dc(circuit)
print(result.node_voltages["output"])       # approximately 8 V
print(result.elements["R1"].current_amperes)  # approximately 0.004 A
print(result.elements["V1"].power_watts)      # approximately -0.048 W
```

The reference is explicitly zero volts. Resistor current runs `node_a` to
`node_b`; voltage-source current runs plus to minus; current-source current
runs `from_node` to `to_node`. Terminal voltage follows the same ordering.
Positive power is absorbed and negative power is delivered. Results are read-only.

`assemble_dc` exposes the immutable MNA matrix and ordering without NumPy.
`solve_dc` rejects missing reference, floating networks, conflicting or redundant
voltage-source constraints, and unsafe numerical results through `DCError`
subclasses. A zero-volt source can represent an ideal short with a measured
branch current, but loops of such sources are rejected as non-unique.
See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for numerical limits and exact source-loop
policy. This is a small-network DC engine, not a complete SPICE simulator.

## Save, load and analyze circuit documents

Native version-1 JSON stores the electrical circuit plus a title/description.
It preserves component/node order, Unicode names and source polarity. Persistence
needs only the standard library; solving also needs the `[dc]` extra.

```python
from circuit_calculator.circuit_io import CircuitDocument, save_document, load_document

# `circuit` is the Circuit from the Python example above.
document = CircuitDocument(circuit, title="Divider", description="12 V input")
save_document(document, "my-circuit.json")
restored = load_document("my-circuit.json")
assert restored.circuit == circuit
```

Saving refuses to replace an existing path by default. Use `overwrite=True`
explicitly when replacing your document. Saves install a completed temporary
file atomically; default creation requires filesystem hard-link support.
Malformed documents raise `CircuitFormatError`; filesystem failures retain
their ordinary Python error types. Loading never executes expressions or resolves
external files. See [CIRCUIT_FORMAT.md](docs/CIRCUIT_FORMAT.md) for schema and size limits.

Run the provided example from the checkout:

```text
python -m circuit_calculator dc examples/divider.json
```

With the package installed, use `circuit-calculator dc FILE.json` or
`python -m main dc FILE.json`. Results contain node voltages, element voltages,
currents and absorbed/delivered power with explicit unit labels, plus numerical
diagnostics. The example gives `out = 8 V`, resistor current `0.004 A`, and source
power `-0.048 W`. Output is JSON with full float precision. Errors go to stderr
with exit code 1; invalid command arguments use code 2. The dense DC command
accepts at most 200 unknowns (non-reference nodes plus voltage-source currents).
Running without arguments still opens the original formula menu.

To also save the same results as full-precision CSV in base SI units:

```text
python -m circuit_calculator dc examples/divider.json --csv divider-results.csv
```

JSON stdout is unchanged. Existing CSV files require `--overwrite-csv`; the input
circuit can never be replaced by this export. Rows identify the reference, net
voltages, element voltages/currents/powers and numerical diagnostics, with explicit
units and literal `node:`/`element:` identifiers. See [RESULTS_CSV.md](docs/RESULTS_CSV.md).

## Desktop DC network editor (prototype)

```text
python -m circuit_calculator gui --example
```

Or, after installation, `circuit-calculator gui --example`. Omit `--example` to
start with one empty junction. Tkinter/Tk must be installed with your Python
distribution; some Linux distributions package it separately. Drawing/exporting
needs no NumPy; simulation needs the `[dc]` extra. See [GUI_DESIGN.md](docs/GUI_DESIGN.md)
for the framework decision and supported scope.

1. Choose **Resistor**, **Voltage source**, or **Current source**, click empty
   canvas space and enter a name/value in base SI units. Each symbol gets two
   terminal dots labeled a/b, +/−, or from/to. Values may use scientific notation.
2. Choose **Junction** to place extra connection points. The starting empty `n1`
   junction must be connected or deleted before simulation of another network.
   Creating a component by clicking two existing free junctions is also supported.
3. Choose **Wire**, click a terminal/junction dot, click empty space to add bends,
   then click the ending dot. Escape cancels; Backspace removes a pending bend.
   Choose **Reference** to select the zero-volt dot. Crossings, overlaps and
   proximity never create connections.
4. Use **Select / move** to drag a component body or junction. Select a body and
   choose **Rotate 90°**, or press R while the canvas has focus. Rotation is
   clockwise and preserves terminal identities, source signs and attached wires.
   **Edit value**, **Delete**, **Undo/Redo** and Ctrl+Z/Ctrl+Y operate on the topology.
   Select a component, free junction or wire and choose **Rename** (F2 on the
   canvas) to change its name. Connections and polarity are preserved; owned
   terminal identities stay fixed. Duplicate names within the same kind are rejected.
   Zoom with +/− and pan with scrollbars or the middle mouse button.
   **Fit circuit** (F on the canvas) fits the symbols, wires and labels;
   **100%** resets magnification. Zoom and resizing retain the viewed world center.
5. Select **Simulate DC** or press F5. The example gives `out = 8 V`; results
   include node voltages, branch currents/power and conservation diagnostics.
   Edits clear results and stale worker results are discarded.

**Export CSV** saves the current accepted DC result. It stays disabled before
simulation and after edits/history/document changes; camera changes retain valid
results. Exporting results does not save or alter the graphical project. The
open project path is protected from replacement by a CSV export.

Select a wire and choose **Reroute wire** to replace its bends, finishing at its
original ending dot. **Straighten** removes its bends. These operations preserve
endpoint identities. Moving a symbol/junction moves attached endpoints while
bends stay at their world coordinates; segments may become diagonal.

In **Select / move**, selecting a wire shows square bend handles. Drag a handle
to move a bend; select a handle and choose **Delete** to remove that bend while
keeping the wire. Shift-click a selected segment to insert a bend. Escape cancels
a drag; Undo restores the previous path. Bends never become electrical junctions.

Enable **Right-angle wires** for newly drawn/rerouted paths. Space swaps elbow
order while drawing. **Orthogonalize** converts a selected wire to horizontal and
vertical segments. This is a geometry edit, not obstacle avoidance or a permanent
constraint: later endpoint/handle movement can make segments diagonal again.

Choose **Split wire** and click a segment to insert a junction. At crossings,
select the intended wire away from the crossing first. Only that wire splits.
To join the other crossing wire, select it away from the new dot and Split at
that existing junction. Every split/join is explicit and undoable. Ordinary
Junction placement and bends never split or connect intersecting wires.

**Open Project**, **Save Project** (Ctrl+S), and **Save As** preserve junction
positions, symbol placements/rotations, wire bends, metadata, zoom and pan in `.ccproj.json`
files. Opening a project clears old results/history and restores its editable
graph. Unsaved changes offer Save / Discard / Cancel; canceled or failed saves
keep your document open. Camera changes mark the project dirty without discarding
valid electrical results. A different window size may clamp the restored pan.

**Import circuit** arranges a native electrical JSON circuit automatically.
**Export circuit** saves resolved electrical connectivity and metadata only;
it does not mark your graphical project saved. The two formats are separate.
Limits: 100 free junctions, 200 components, 500 total nodes (including terminals),
800 wires, 32 bends per wire and 200 DC unknowns. Electrical imports retain the 100-node limit.
A wire that shorts both terminals of a component
produces an explicit unsupported-short error.

Open the included graphical project directly:

```text
python -m circuit_calculator gui examples/routed-divider.ccproj.json
```

The equivalent installed command is `circuit-calculator gui FILE.ccproj.json`.
Projects can be saved even while the circuit is unfinished or not yet solvable.
No cached simulation results or Undo/Redo history are loaded from disk.
See [SCHEMATIC_FORMAT.md](docs/SCHEMATIC_FORMAT.md) for the strict project schema,
limits, API and atomic-save semantics.

New project saves use version 3; `examples/divider.ccproj.json` (v1) and
`examples/placed-divider.ccproj.json` (v2) remain supported and unchanged.
Older application versions cannot open v3 saves; use Save As to keep an original
file when needed. Moving or rotating a junction-based
component gives it dedicated terminals wired back to its original junctions;
Undo restores the exact previous graph. Terminals move/delete with their body.
Wires support straight/diagonal segments with explicit bends and splitting.
Bend handles and optional right-angle routing are available; obstacle avoidance
and persistent orthogonal constraints remain planned.
The electrical model and solver stay independent of Tk and layout coordinates.
See [COMPONENT_EDITING.md](docs/COMPONENT_EDITING.md) for geometry and migration rules.
See [IDENTITY_EDITING.md](docs/IDENTITY_EDITING.md) for name, unit and history rules.
**Copy** captures a selected component's value and orientation in the in-app
clipboard. **Paste** then click places an unconnected copy; R rotates its preview,
and Escape cancels. **Duplicate** places a copy 40 units right and down. Canvas
shortcuts are Ctrl+C/Ctrl+V/Ctrl+D. Each copy has fresh terminals and a fresh name;
wire it explicitly before simulation. Source wires and ground are not copied.
See [COMPONENT_COPY.md](docs/COMPONENT_COPY.md) for snapshot/history rules.
GUI component creation and **Edit value** accept matching units and engineering
prefixes, for example `4.7kΩ`, `2mA`, `12V`, or bare base-unit numbers. Prefix case
matters: `m` is milli and `M` is mega. Canvas/results use readable prefixes;
files and CSV retain base SI values. Dialogs initialize with the full stored
number, not a rounded label. The formula menu keeps its existing numeric syntax.
See [QUANTITIES.md](docs/QUANTITIES.md) for accepted units, precision and limits.
**Project details** edits the title and multiline description together. Apply
updates the document; **Save Project** writes it to disk. Invalid entries stay
open for correction, while Cancel/Escape keeps the original details. Enter adds
a description line, Ctrl+Enter applies, and Ctrl+Tab leaves the multiline field.
See [PROJECT_DETAILS.md](docs/PROJECT_DETAILS.md) for metadata/history rules.
Canvas R/F and Ctrl+C/V/D, plus Undo/Redo and project file shortcuts, support
Windows virtual letter keys under the observed non-Latin keyboard layout.
Ctrl+Shift+Z also redoes an edit. Document shortcuts work in the read-only results
panel; modal forms retain their own text controls. Alt/AltGr is ignored.
See [SHORTCUTS.md](docs/SHORTCUTS.md) for scope and platform limits.
Click a component, junction, terminal or wire to open **Selected item** beside
**All results**. The inspector shows connections and sign conventions, plus
voltage/current/power from the current solve. Wires show net voltage; individual
wire current is not calculated. Edits clear old values, while selection/camera
changes preserve results. Both views scroll and support text selection/copy.
See [RESULT_INSPECTION.md](docs/RESULT_INSPECTION.md) for the result-validity rules.
The **Voltage probe** tab measures **V(A) − V(B)** between two chosen junctions
or component terminals. **Swap A / B** reverses polarity; **Clear** resets the
choices. Only current accepted results appear. Choices clear after document edits,
Undo/Redo or opening a project, and remain transient when saving. See
[VOLTAGE_PROBE.md](docs/VOLTAGE_PROBE.md) for range and freshness rules.
Enable **Node voltages** to show current voltages beside junctions and terminals;
`(ref)` marks the reference net. Labels use the simulation reference and clear
when results become outdated. **Fit circuit** includes the labels. The display
choice is temporary and does not change the saved circuit. Dense layouts may
still have overlapping labels. See [RESULT_ANNOTATIONS.md](docs/RESULT_ANNOTATIONS.md).
Enable **Component I / P** independently to show signed current and power beside
each component. `+I` states the positive terminal direction; a negative current
flows the other way. Positive power is absorbed and negative power delivered.
These labels also use only current results and participate in Fit. See
[COMPONENT_ANNOTATIONS.md](docs/COMPONENT_ANNOTATIONS.md) for signs and placement.
**Reduce overlaps** tries nearby positions for result labels without moving the
circuit. Gray dashed guides link moved text to its junction or component label.
Dense layouts may still overlap; a panel note flags unresolved placement. All
labels remain visible, and Fit includes moved text and guides. This preference
is temporary. See [ANNOTATION_LAYOUT.md](docs/ANNOTATION_LAYOUT.md) for its limits.
**Find item** (Ctrl+F) filters components, junctions, terminals and wires by name
or terminal label. **Show item** selects and centers a match without changing
zoom, connectivity or current results. Matching names in different categories
remain separate. Camera movement can mark the project dirty; search cancellation
does not move it. See [ITEM_SEARCH.md](docs/ITEM_SEARCH.md).
See [WIRE_ROUTING.md](docs/WIRE_ROUTING.md) for routing, splitting and crossing rules.
See [BEND_EDITING.md](docs/BEND_EDITING.md) for bend handles and right-angle routing.
See [VIEWPORT.md](docs/VIEWPORT.md) for camera behavior. Scroll bounds now follow
the circuit rather than the decorative grid; older project scroll fractions may
show a different view, while electrical data and layout coordinates are preserved.

## Future roadmap

The following are planned ideas and are **not implemented**:

- Multi-component/OS-clipboard copy/paste, obstacle-aware routing, global annotation
  layout optimization, movable annotations and richer schematic editing.
- Extended DC analysis with controlled sources and equivalent-port calculations.
- RC and RLC circuit analysis.

See [ROADMAP.md](docs/ROADMAP.md) for phased dependencies, [TESTING.md](docs/TESTING.md)
for validation, and [PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for the next batch.
