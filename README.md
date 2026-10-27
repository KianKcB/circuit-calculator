# Circuit Calculator

A small Python command-line tool for calculating equivalent resistance in series and parallel circuits, and solving for voltage, current, or resistance with Ohm's law.

## Features

- **Series resistance:** sums a non-empty iterable of resistances.
- **Parallel resistance:** calculates equivalent resistance using the reciprocal-sum formula. A zero-ohm branch produces zero equivalent resistance and is reported as a short circuit.
- **Ohm's law:** calculates one missing quantity from the other two using `V = I × R`. Choose voltage, current, or resistance as the quantity to solve for.
- **Electrical power:** calculates power in watts from voltage and current (`P = V × I`), current and resistance (`P = I² × R`), or voltage and resistance (`P = V² / R`).
- **Voltage divider:** calculates the ideal voltage drop across a selected resistor in a series network.
- **Current divider:** calculates current through a selected branch in a parallel network, including defined ideal short-circuit cases.
- **Interactive CLI:** guides you through each calculation, shows units, and returns to the menu after successful calculations or handled input errors.

## Project files

| File | Purpose |
| --- | --- |
| `main.py` | Interactive command-line menu and input/output handling. |
| `calculations.py` | Series resistance, parallel resistance, and Ohm's law calculations and validation. |
| `circuit.py` | Immutable validated resistor and independent-source circuit model. |
| `dc.py` | Linear DC MNA assembly, solving, results and diagnostics. |
| `test_dc.py` | Analytical reference circuits and solver failure tests. |
| `test_calculations.py` | Unit tests for the calculations and CLI behavior. |
| `.gitignore` | Excludes Python caches, virtual environments, test caches, and local environment files. |

## Requirements and setup

- Python 3.7 or newer.
- The formula CLI and circuit model need only the standard library. DC solving
  requires NumPy: `python -m pip install -r requirements-dc.txt`.
- Locally verified with Python 3.11.9 and NumPy 1.26.4. The historical Python 3.7
  minimum has not been tested in the current environment.

Open a terminal in the project directory and check that Python is available:

```bash
python --version
```

For formula-only use there is no dependency installation step. On systems where the Python command is named `python3`, use `python3` in place of `python` in the commands below.

## Run the application

```bash
python main.py
```

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

## Run the tests

From the project directory, run:

```bash
python -m unittest -v
```

## Current limitations

The menu still exposes only standalone formulas. The Python DC API below solves
small linear networks of positive resistors and independent sources. GUI, file
loading, controlled/reactive/nonlinear components and unit prefixes are not yet
implemented. Legacy formula extreme-number limitations are recorded in
[PROJECT_STATUS.md](PROJECT_STATUS.md).

## Linear DC analysis from Python

```python
from circuit import Circuit, Resistor, VoltageSource
from dc import solve_dc

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
See [ARCHITECTURE.md](ARCHITECTURE.md) for numerical limits and exact source-loop
policy. This is a small-network DC engine, not a complete SPICE simulator.

## Future roadmap

The following are planned ideas and are **not implemented**:

- Graphical circuit drawing.
- Extended DC analysis with controlled sources and equivalent-port calculations.
- RC and RLC circuit analysis.

See [ROADMAP.md](ROADMAP.md) for phased dependencies, [TESTING.md](TESTING.md)
for validation, and [PROJECT_STATUS.md](PROJECT_STATUS.md) for the next batch.
