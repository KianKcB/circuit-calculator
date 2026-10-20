"""Interactive command-line interface for circuit calculations."""

import sys

from calculations import calculate_ohms_law, parallel_resistance, series_resistance


def _read_resistances(input_fn, output_fn):
    output_fn("Enter one resistance in ohms (Ω) per line. Press Enter on a blank line when done.")
    resistances = []
    while True:
        entry = input_fn("Resistance (Ω): ").strip()
        if not entry:
            return resistances
        try:
            resistances.append(float(entry))
        except ValueError as error:
            raise ValueError(f"'{entry}' is not a valid number") from error


def _read_number(input_fn, label, unit):
    entry = input_fn(f"Enter {label} ({unit}): ").strip()
    try:
        return float(entry)
    except ValueError as error:
        raise ValueError(f"'{entry}' is not a valid number for {label}") from error


def _calculate_series(input_fn, output_fn):
    resistances = _read_resistances(input_fn, output_fn)
    result = series_resistance(resistances)
    output_fn(f"Equivalent series resistance: {result} Ω")


def _calculate_parallel(input_fn, output_fn):
    resistances = _read_resistances(input_fn, output_fn)
    result = parallel_resistance(resistances)
    output_fn(f"Equivalent parallel resistance: {result.equivalent_resistance} Ω")
    if result.has_short_circuit:
        output_fn("Warning: a zero-ohm branch creates a short circuit.")


def _calculate_with_ohms_law(input_fn, output_fn):
    output_fn("Calculate: 1) Voltage  2) Current  3) Resistance")
    choice = input_fn("Choose a quantity: ").strip()

    if choice == "1":
        current = _read_number(input_fn, "current", "A")
        resistance = _read_number(input_fn, "resistance", "Ω")
        result = calculate_ohms_law(current=current, resistance=resistance, solve_for="voltage")
        output_fn(f"Voltage: {result} V")
    elif choice == "2":
        voltage = _read_number(input_fn, "voltage", "V")
        resistance = _read_number(input_fn, "resistance", "Ω")
        result = calculate_ohms_law(voltage=voltage, resistance=resistance, solve_for="current")
        output_fn(f"Current: {result} A")
    elif choice == "3":
        voltage = _read_number(input_fn, "voltage", "V")
        current = _read_number(input_fn, "current", "A")
        result = calculate_ohms_law(voltage=voltage, current=current, solve_for="resistance")
        output_fn(f"Resistance: {result} Ω")
    else:
        raise ValueError("Choose 1 for voltage, 2 for current, or 3 for resistance")


def run_cli(input_fn=None, output_fn=None):
    """Run the menu; optional I/O functions make the CLI easy to test."""
    if input_fn is None:
        input_fn = input
    if output_fn is None:
        output_fn = print

    while True:
        output_fn("\nCircuit Calculator")
        output_fn("1. Calculate equivalent resistance in series")
        output_fn("2. Calculate equivalent resistance in parallel")
        output_fn("3. Use Ohm's law")
        output_fn("4. Exit")

        try:
            choice = input_fn("Choose an option: ").strip()
            if choice == "1":
                _calculate_series(input_fn, output_fn)
            elif choice == "2":
                _calculate_parallel(input_fn, output_fn)
            elif choice == "3":
                _calculate_with_ohms_law(input_fn, output_fn)
            elif choice == "4":
                output_fn("Goodbye.")
                return
            else:
                raise ValueError("Choose an option from 1 to 4")
        except (TypeError, ValueError, OverflowError) as error:
            output_fn(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            output_fn("\nInput ended. Goodbye.")
            return


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_cli()
