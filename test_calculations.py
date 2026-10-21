"""Tests for circuit calculations."""

import math
import unittest
from decimal import Decimal

from calculations import (
    calculate_current_divider,
    calculate_ohms_law,
    calculate_power,
    calculate_voltage_divider,
    parallel_resistance,
    series_resistance,
)
from main import run_cli


class SeriesResistanceTests(unittest.TestCase):
    def test_sums_list_and_other_iterables(self):
        self.assertEqual(series_resistance([10, 20.5, 3]), 33.5)
        self.assertEqual(series_resistance((1, 2, 3)), 6)
        self.assertEqual(series_resistance(value for value in (2, 4)), 6)

    def test_allows_zero_and_single_value(self):
        self.assertEqual(series_resistance([0, 0.0]), 0)
        self.assertEqual(series_resistance([Decimal("2.5")]), Decimal("2.5"))

    def test_rejects_empty_or_non_iterable_input(self):
        for value in ([], (), iter(())):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "not be empty"):
                    series_resistance(value)
        for value in (None, 5, "12", b"12"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    series_resistance(value)

    def test_rejects_non_numeric_values(self):
        for value in ("2", None, object(), True, 1 + 2j):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    series_resistance([1, value])

    def test_rejects_negative_values(self):
        for value in (-1, -0.01, Decimal("-2")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "non-negative"):
                    series_resistance([value])

    def test_rejects_nan_and_infinities(self):
        for value in (math.nan, math.inf, -math.inf, Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite"):
                    series_resistance([value])


class ParallelResistanceTests(unittest.TestCase):
    def test_calculates_equivalent_resistance_for_parallel_branches(self):
        result = parallel_resistance([10, 10])
        self.assertAlmostEqual(result.equivalent_resistance, 5)
        self.assertFalse(result.has_short_circuit)

        result = parallel_resistance((6, 3))
        self.assertAlmostEqual(result.equivalent_resistance, 2)

        result = parallel_resistance(value for value in (Decimal("2.5"), Decimal("2.5")))
        self.assertAlmostEqual(result.equivalent_resistance, 1.25)

    def test_zero_resistance_reports_short_circuit(self):
        for values in ([0], [0, 10], [10, 0, 20], [0, 0]):
            with self.subTest(values=values):
                result = parallel_resistance(values)
                self.assertEqual(result.equivalent_resistance, 0)
                self.assertTrue(result.has_short_circuit)

    def test_rejects_empty_or_non_iterable_input(self):
        for value in ([], (), iter(())):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "not be empty"):
                    parallel_resistance(value)
        for value in (None, 5, "12", b"12"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parallel_resistance(value)

    def test_rejects_invalid_resistance_entries(self):
        invalid_types = ("2", None, object(), True, 1 + 2j)
        for value in invalid_types:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    parallel_resistance([10, value])

        invalid_values = (-1, -0.01, Decimal("-2"), math.nan, math.inf, -math.inf,
                          Decimal("NaN"), Decimal("Infinity"))
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parallel_resistance([value])


class OhmsLawTests(unittest.TestCase):
    def test_calculates_each_variable_from_the_other_two(self):
        self.assertEqual(calculate_ohms_law(current=2, resistance=5, solve_for="voltage"), 10)
        self.assertEqual(calculate_ohms_law(voltage=10, resistance=5, solve_for="current"), 2)
        self.assertEqual(calculate_ohms_law(voltage=10, current=2, solve_for="resistance"), 5)

    def test_supports_signed_voltage_and_current_and_decimal_inputs(self):
        self.assertEqual(calculate_ohms_law(current=-2, resistance=5, solve_for="voltage"), -10)
        self.assertEqual(calculate_ohms_law(voltage=Decimal("10"), resistance=Decimal("4"),
                                            solve_for="current"), 2.5)
        self.assertEqual(calculate_ohms_law(voltage=-10, current=-2, solve_for="resistance"), 5)

    def test_requires_exactly_two_values_and_a_valid_target(self):
        invalid_calls = (
            {"solve_for": "voltage"},
            {"current": 2, "solve_for": "voltage"},
            {"current": 2, "resistance": 5, "voltage": 10, "solve_for": "voltage"},
            {"voltage": 10, "current": 2, "solve_for": "voltage"},
            {"current": 2, "resistance": 5, "solve_for": "power"},
        )
        for kwargs in invalid_calls:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    calculate_ohms_law(**kwargs)

    def test_rejects_invalid_values_and_negative_resistance(self):
        for value in ("10", None, object(), True, 1 + 2j):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    calculate_ohms_law(current=value, resistance=5, solve_for="voltage")

        for value in (math.nan, math.inf, -math.inf, Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "finite"):
                    calculate_ohms_law(voltage=value, resistance=5, solve_for="current")

        with self.assertRaisesRegex(ValueError, "non-negative"):
            calculate_ohms_law(current=2, resistance=-5, solve_for="voltage")

        with self.assertRaisesRegex(ValueError, "negative resistance"):
            calculate_ohms_law(voltage=-10, current=2, solve_for="resistance")

    def test_reports_undefined_division_cases(self):
        with self.assertRaisesRegex(ValueError, "resistance is zero"):
            calculate_ohms_law(voltage=10, resistance=0, solve_for="current")
        with self.assertRaisesRegex(ValueError, "current is zero"):
            calculate_ohms_law(voltage=0, current=0, solve_for="resistance")


class PowerCalculationTests(unittest.TestCase):
    def test_calculates_power_from_each_pair_of_values(self):
        self.assertEqual(calculate_power(voltage=12, current=2), 24)
        self.assertEqual(calculate_power(current=2, resistance=3), 12)
        self.assertEqual(calculate_power(voltage=12, resistance=3), 48)

    def test_supports_signed_voltage_and_current(self):
        self.assertEqual(calculate_power(voltage=-12, current=2), -24)

    def test_requires_exactly_two_valid_values(self):
        invalid_calls = (
            {},
            {"voltage": 12},
            {"voltage": 12, "current": 2, "resistance": 3},
        )
        for kwargs in invalid_calls:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    calculate_power(**kwargs)

    def test_rejects_invalid_values_and_zero_resistance_division(self):
        for value in ("12", None, object(), True, 1 + 2j):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    calculate_power(voltage=value, current=2)

        for value in (-1, math.nan, math.inf, -math.inf, Decimal("NaN")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_power(current=2, resistance=value)

        with self.assertRaisesRegex(ValueError, "resistance is zero"):
            calculate_power(voltage=12, resistance=0)


class VoltageDividerTests(unittest.TestCase):
    def test_calculates_voltage_across_selected_resistors(self):
        self.assertAlmostEqual(calculate_voltage_divider(12, [1000, 2000], 1), 8)
        resistances = (1000, 2000, 3000)
        self.assertAlmostEqual(calculate_voltage_divider(12, resistances, 0), 2)
        self.assertAlmostEqual(calculate_voltage_divider(12, resistances, 2), 6)
        self.assertAlmostEqual(calculate_voltage_divider(12, (value for value in [1, 2]), 1), 8)

    def test_supports_positive_zero_and_negative_input_voltage(self):
        self.assertAlmostEqual(calculate_voltage_divider(12, [1, 1], 0), 6)
        self.assertEqual(calculate_voltage_divider(0, [1, 1], 0), 0)
        self.assertAlmostEqual(calculate_voltage_divider(-12, [1, 1], 1), -6)

    def test_zero_resistors_are_allowed_when_total_is_positive(self):
        self.assertEqual(calculate_voltage_divider(12, [0, 2, 0], 0), 0)
        self.assertEqual(calculate_voltage_divider(12, [0, 2, 0], 2), 0)
        self.assertEqual(calculate_voltage_divider(12, [0, 2, 0], 1), 12)

    def test_rejects_empty_or_invalid_resistances(self):
        with self.assertRaisesRegex(ValueError, "not be empty"):
            calculate_voltage_divider(12, [], 0)
        for resistances in ("10", b"10", 10):
            with self.subTest(resistances=resistances):
                with self.assertRaises(TypeError):
                    calculate_voltage_divider(12, resistances, 0)
        for resistance in (-1, True, "2", 1 + 2j, math.nan, math.inf, -math.inf):
            with self.subTest(resistance=resistance):
                with self.assertRaises((TypeError, ValueError)):
                    calculate_voltage_divider(12, [2, resistance], 0)

    def test_rejects_invalid_input_voltage(self):
        for voltage in (None, "12", True, 1 + 2j, object()):
            with self.subTest(voltage=voltage):
                with self.assertRaises(TypeError):
                    calculate_voltage_divider(voltage, [1, 1], 0)
        for voltage in (math.nan, math.inf, -math.inf, Decimal("Infinity")):
            with self.subTest(voltage=voltage):
                with self.assertRaises(ValueError):
                    calculate_voltage_divider(voltage, [1, 1], 0)

    def test_rejects_invalid_target_indices(self):
        for index in (-1, 2):
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, "target_index"):
                    calculate_voltage_divider(12, [1, 1], index)
        for index in (True, 0.5, "0"):
            with self.subTest(index=index):
                with self.assertRaisesRegex(TypeError, "target_index"):
                    calculate_voltage_divider(12, [1, 1], index)

    def test_rejects_zero_or_non_finite_total_resistance(self):
        with self.assertRaisesRegex(ValueError, "total resistance is zero"):
            calculate_voltage_divider(12, [0, 0], 0)
        with self.assertRaisesRegex(ValueError, "total series resistance must be finite"):
            calculate_voltage_divider(12, [1e308, 1e308], 0)
        with self.assertRaisesRegex(ValueError, "representable"):
            calculate_voltage_divider(Decimal("1e10000"), [1, 1], 0)


class CurrentDividerTests(unittest.TestCase):
    def test_calculates_current_through_selected_branches(self):
        self.assertAlmostEqual(calculate_current_divider(3, [4, 8], 0), 2)
        self.assertAlmostEqual(calculate_current_divider(3, [4, 8], 1), 1)
        self.assertAlmostEqual(calculate_current_divider(11, [2, 3, 6], 1), 11 / 3)
        self.assertAlmostEqual(calculate_current_divider(11, [2, 3, 6], 2), 11 / 6)
        self.assertAlmostEqual(calculate_current_divider(3, iter([4, 8]), 0), 2)

    def test_supports_positive_zero_and_negative_total_current(self):
        self.assertAlmostEqual(calculate_current_divider(4, [2, 2], 0), 2)
        self.assertEqual(calculate_current_divider(0, [2, 2], 0), 0)
        self.assertAlmostEqual(calculate_current_divider(-4, [2, 2], 1), -2)

    def test_models_one_zero_ohm_branch_as_a_short_circuit(self):
        self.assertEqual(calculate_current_divider(5, [0, 4, 8], 0), 5)
        self.assertEqual(calculate_current_divider(5, [0, 4, 8], 1), 0)
        self.assertEqual(calculate_current_divider(0, [0, 4], 0), 0)

    def test_handles_multiple_zero_ohm_branches_without_arbitrary_splitting(self):
        self.assertEqual(calculate_current_divider(5, [0, 0, 8], 2), 0)
        with self.assertRaisesRegex(ValueError, "multiple zero-ohm branches"):
            calculate_current_divider(5, [0, 0, 8], 0)
        with self.assertRaisesRegex(ValueError, "multiple zero-ohm branches"):
            calculate_current_divider(0, [0, 0, 8], 1)
        with self.assertRaisesRegex(ValueError, "all branch resistances are zero"):
            calculate_current_divider(5, [0, 0, 0], 1)
        with self.assertRaisesRegex(ValueError, "all branch resistances are zero"):
            calculate_current_divider(0, [0, 0], 0)

    def test_rejects_empty_or_invalid_resistances(self):
        with self.assertRaisesRegex(ValueError, "not be empty"):
            calculate_current_divider(5, [], 0)
        for resistances in ("10", b"10", 10):
            with self.subTest(resistances=resistances):
                with self.assertRaises(TypeError):
                    calculate_current_divider(5, resistances, 0)
        for resistance in (-1, True, "2", 1 + 2j, math.nan, math.inf, -math.inf):
            with self.subTest(resistance=resistance):
                with self.assertRaises((TypeError, ValueError)):
                    calculate_current_divider(5, [2, resistance], 0)

    def test_rejects_invalid_input_current(self):
        for current in (None, "5", True, 1 + 2j, object()):
            with self.subTest(current=current):
                with self.assertRaises(TypeError):
                    calculate_current_divider(current, [2, 2], 0)
        for current in (math.nan, math.inf, -math.inf):
            with self.subTest(current=current):
                with self.assertRaises(ValueError):
                    calculate_current_divider(current, [2, 2], 0)

    def test_rejects_invalid_target_indices_and_unrepresentable_results(self):
        for index in (-1, 2):
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, "target_index"):
                    calculate_current_divider(5, [1, 2], index)
        for index in (True, 0.5, "0"):
            with self.subTest(index=index):
                with self.assertRaisesRegex(TypeError, "target_index"):
                    calculate_current_divider(5, [1, 2], index)
        with self.assertRaisesRegex(ValueError, "representable"):
            calculate_current_divider(Decimal("1e10000"), [1, 2], 0)

    def test_scaled_conductances_handle_extreme_positive_resistances(self):
        self.assertEqual(calculate_current_divider(3, [1e-300, 1e300], 0), 3)
        self.assertEqual(calculate_current_divider(3, [1e-300, 1e300], 1), 0)


class CommandLineInterfaceTests(unittest.TestCase):
    def run_with_inputs(self, entries):
        responses = iter(entries)
        output = []
        run_cli(input_fn=lambda _prompt: next(responses), output_fn=output.append)
        return "\n".join(output)

    def test_series_resistance_uses_blank_line_to_finish_entry(self):
        output = self.run_with_inputs(["1", "10", "20", "", "6"])
        self.assertIn("Equivalent series resistance: 30.0 Ω", output)
        self.assertIn("Goodbye.", output)

    def test_parallel_short_circuit_is_reported(self):
        output = self.run_with_inputs(["2", "0", "10", "", "6"])
        self.assertIn("Equivalent parallel resistance: 0.0 Ω", output)
        self.assertIn("creates a short circuit", output)

    def test_ohms_law_prompts_for_selected_quantity_and_displays_unit(self):
        output = self.run_with_inputs(["3", "2", "12", "6", "6"])
        self.assertIn("Current: 2.0 A", output)

    def test_power_calculation_uses_selected_formula_and_displays_watts(self):
        output = self.run_with_inputs(["4", "2", "2", "3", "6"])
        self.assertIn("Power: 12.0 W", output)

    def test_voltage_divider_uses_one_based_cli_resistor_selection(self):
        output = self.run_with_inputs(["5", "1", "12", "1000", "2000", "", "2", "6"])
        self.assertIn("Voltage across resistor 2 (2000.0 Ω): 8.0 V", output)

    def test_current_divider_uses_one_based_cli_branch_selection(self):
        output = self.run_with_inputs(["5", "2", "6", "2", "6", "", "1", "6"])
        self.assertIn("Current through branch 1 (2.0 Ω): 4.5 A", output)

    def test_divider_submenu_can_return_to_main_menu(self):
        output = self.run_with_inputs(["5", "3", "6"])
        self.assertIn("3. Return to main menu", output)
        self.assertIn("Goodbye.", output)

    def test_invalid_divider_selection_returns_to_main_menu(self):
        output = self.run_with_inputs(["5", "9", "6"])
        self.assertIn("Error: Choose 1 for voltage divider", output)
        self.assertIn("Goodbye.", output)

    def test_non_numeric_and_out_of_range_divider_inputs_are_handled(self):
        output = self.run_with_inputs(
            ["5", "1", "not-a-number", "5", "1", "12", "10", "20", "", "3", "6"]
        )
        self.assertIn("is not a valid number", output)
        self.assertIn("Resistor must be between 1 and 2", output)
        self.assertIn("Goodbye.", output)

    def test_out_of_range_current_branch_selection_is_handled(self):
        output = self.run_with_inputs(["5", "2", "6", "2", "6", "", "3", "6"])
        self.assertIn("Branch must be between 1 and 2", output)
        self.assertIn("Goodbye.", output)

    def test_divider_calculation_error_returns_to_main_menu(self):
        output = self.run_with_inputs(["5", "2", "5", "0", "0", "", "1", "6"])
        self.assertIn("current division is undefined when all branch resistances are zero", output)
        self.assertIn("Goodbye.", output)

    def test_invalid_menu_choice_and_non_numeric_entry_return_to_menu(self):
        output = self.run_with_inputs(["abc", "1", "not-a-number", "6"])
        self.assertIn("Error: Choose an option from 1 to 6", output)
        self.assertIn("is not a valid number", output)
        self.assertIn("Goodbye.", output)

    def test_calculation_error_returns_to_menu(self):
        output = self.run_with_inputs(["2", "-1", "", "6"])
        self.assertIn("Error: resistance at index 0 must be non-negative", output)
        self.assertIn("Goodbye.", output)

if __name__ == "__main__":
    unittest.main()
