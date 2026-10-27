"""Interactive command-line interface for circuit calculations."""

import sys
from decimal import Decimal

from calculations import (
    calculate_current_divider,
    calculate_ohms_law,
    calculate_power,
    calculate_voltage_divider,
    parallel_resistance,
    series_resistance,
)


def _parse_number(entry, description="number"):
    """Parse CLI text without silently turning a nonzero value into zero."""
    try:
        value = float(entry)
    except ValueError as error:
        raise ValueError(f"'{entry}' is not a valid {description}") from error
    if value == 0 and Decimal(entry) != 0:
        raise ValueError(f"'{entry}' is too small to represent as a nonzero number")
    return value


def _read_resistances(input_fn, output_fn):
    output_fn("Enter one resistance in ohms (Ω) per line. Press Enter on a blank line when done.")
    resistances = []
    while True:
        entry = input_fn("Resistance (Ω): ").strip()
        if not entry:
            return resistances
        resistances.append(_parse_number(entry))


def _read_number(input_fn, label, unit):
    entry = input_fn(f"Enter {label} ({unit}): ").strip()
    return _parse_number(entry, f"number for {label}")


def _read_one_based_selection(input_fn, item_name, item_count):
    entry = input_fn(f"Choose a {item_name} (1-{item_count}): ").strip()
    try:
        selection = int(entry)
    except ValueError as error:
        raise ValueError(f"'{entry}' is not a valid {item_name} number") from error
    if selection < 1 or selection > item_count:
        raise ValueError(f"{item_name.capitalize()} must be between 1 and {item_count}")
    return selection


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


def _calculate_power(input_fn, output_fn):
    output_fn("Calculate power from: 1) Voltage and current  2) Current and resistance  3) Voltage and resistance")
    choice = input_fn("Choose known quantities: ").strip()

    if choice == "1":
        voltage = _read_number(input_fn, "voltage", "V")
        current = _read_number(input_fn, "current", "A")
        power = calculate_power(voltage=voltage, current=current)
    elif choice == "2":
        current = _read_number(input_fn, "current", "A")
        resistance = _read_number(input_fn, "resistance", "Ω")
        power = calculate_power(current=current, resistance=resistance)
    elif choice == "3":
        voltage = _read_number(input_fn, "voltage", "V")
        resistance = _read_number(input_fn, "resistance", "Ω")
        power = calculate_power(voltage=voltage, resistance=resistance)
    else:
        raise ValueError("Choose 1 for voltage and current, 2 for current and resistance, or 3 for voltage and resistance")

    output_fn(f"Power: {power} W")


def _calculate_dividers(input_fn, output_fn):
    output_fn("1. Voltage divider (series circuit)")
    output_fn("2. Current divider (parallel circuit)")
    output_fn("3. Return to main menu")
    choice = input_fn("Choose a divider: ").strip()

    if choice == "3":
        return
    if choice not in ("1", "2"):
        raise ValueError("Choose 1 for voltage divider, 2 for current divider, or 3 to return")

    if choice == "1":
        input_voltage = _read_number(input_fn, "total input voltage", "V")
        resistances = _read_resistances(input_fn, output_fn)
        if not resistances:
            raise ValueError("at least one series resistor is required")
        selection = _read_one_based_selection(input_fn, "resistor", len(resistances))
        voltage_drop = calculate_voltage_divider(input_voltage, resistances, selection - 1)
        output_fn(
            f"Voltage across resistor {selection} ({resistances[selection - 1]} Ω): "
            f"{voltage_drop} V"
        )
    else:
        input_current = _read_number(input_fn, "total input current", "A")
        resistances = _read_resistances(input_fn, output_fn)
        if not resistances:
            raise ValueError("at least one parallel branch is required")
        selection = _read_one_based_selection(input_fn, "branch", len(resistances))
        branch_current = calculate_current_divider(input_current, resistances, selection - 1)
        output_fn(
            f"Current through branch {selection} ({resistances[selection - 1]} Ω): "
            f"{branch_current} A"
        )


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
        output_fn("4. Calculate electrical power")
        output_fn("5. Calculate voltage/current dividers")
        output_fn("6. Exit")

        try:
            choice = input_fn("Choose an option: ").strip()
            if choice == "1":
                _calculate_series(input_fn, output_fn)
            elif choice == "2":
                _calculate_parallel(input_fn, output_fn)
            elif choice == "3":
                _calculate_with_ohms_law(input_fn, output_fn)
            elif choice == "4":
                _calculate_power(input_fn, output_fn)
            elif choice == "5":
                _calculate_dividers(input_fn, output_fn)
            elif choice == "6":
                output_fn("Goodbye.")
                return
            else:
                raise ValueError("Choose an option from 1 to 6")
        except (TypeError, ValueError, OverflowError) as error:
            output_fn(f"Error: {error}")
        except (EOFError, KeyboardInterrupt):
            output_fn("\nInput ended. Goodbye.")
            return


def main():
    """Installed command entry point, also used by direct script execution."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_cli()


if __name__ == "__main__":
    main()
