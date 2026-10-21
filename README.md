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
| `test_calculations.py` | Unit tests for the calculations and CLI behavior. |
| `.gitignore` | Excludes Python caches, virtual environments, test caches, and local environment files. |

## Requirements and setup

- Python 3.7 or newer.
- No third-party packages are required; the application and tests use the Python standard library.

Open a terminal in the project directory and check that Python is available:

```bash
python --version
```

There is no dependency installation step. On systems where the Python command is named `python3`, use `python3` in place of `python` in the commands below.

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

The project supports these divider formulas for a selected resistor or branch, but it does not solve arbitrary interconnected circuit networks or calculate a complete circuit's node voltages and branch currents. It also does not calculate power distribution across a full circuit or convert unit prefixes. The CLI accepts plain numbers and interprets resistance in ohms, voltage in volts, current in amperes, and power in watts.

## Future roadmap

The following are planned ideas and are **not implemented**:

- Graphical circuit drawing.
- DC resistive circuit analysis using nodal and mesh methods.
- RC and RLC circuit analysis.
