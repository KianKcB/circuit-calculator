# Circuit Calculator

A small Python command-line tool for calculating equivalent resistance in series and parallel circuits, and solving for voltage, current, or resistance with Ohm's law.

## Features

- **Series resistance:** sums a non-empty iterable of resistances.
- **Parallel resistance:** calculates equivalent resistance using the reciprocal-sum formula. A zero-ohm branch produces zero equivalent resistance and is reported as a short circuit.
- **Ohm's law:** calculates one missing quantity from the other two using `V = I × R`. Choose voltage, current, or resistance as the quantity to solve for.
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
4. Exit.

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

## Input validation and errors

- Resistance calculations require at least one value. Values must be finite, real, and non-negative; booleans, complex values, and text are rejected by the calculation functions.
- The CLI reads each entry as a number. Non-numeric entries and invalid calculation values produce an error message and return to the main menu.
- Ohm's law requires exactly two known values and a valid target quantity. Voltage and current may be signed, while resistance must be non-negative.
- A current cannot be calculated when resistance is zero, and resistance cannot be calculated when current is zero. These cases are reported as calculation errors.
- Invalid menu choices are reported without terminating the program. Choosing exit, or ending input with Ctrl+C or end-of-file, exits cleanly.

## Run the tests

From the project directory, run:

```bash
python -m unittest -v
```

## Current limitations

The project handles individual resistor values and the basic Ohm's law relationship. It does not model circuit diagrams or interconnected networks, convert unit prefixes, or solve for power. The CLI accepts plain numbers and interprets resistance in ohms, voltage in volts, and current in amperes.

## Future roadmap

The following are planned ideas and are **not implemented**:

- Graphical circuit drawing.
- DC resistive circuit analysis using nodal and mesh methods.
- RC and RLC circuit analysis.
