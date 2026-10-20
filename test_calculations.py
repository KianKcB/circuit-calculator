"""Tests for circuit calculations."""

import math
import unittest
from decimal import Decimal

from calculations import calculate_ohms_law, parallel_resistance, series_resistance
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


class CommandLineInterfaceTests(unittest.TestCase):
    def run_with_inputs(self, entries):
        responses = iter(entries)
        output = []
        run_cli(input_fn=lambda _prompt: next(responses), output_fn=output.append)
        return "\n".join(output)

    def test_series_resistance_uses_blank_line_to_finish_entry(self):
        output = self.run_with_inputs(["1", "10", "20", "", "4"])
        self.assertIn("Equivalent series resistance: 30.0 Ω", output)
        self.assertIn("Goodbye.", output)

    def test_parallel_short_circuit_is_reported(self):
        output = self.run_with_inputs(["2", "0", "10", "", "4"])
        self.assertIn("Equivalent parallel resistance: 0.0 Ω", output)
        self.assertIn("creates a short circuit", output)

    def test_ohms_law_prompts_for_selected_quantity_and_displays_unit(self):
        output = self.run_with_inputs(["3", "2", "12", "6", "4"])
        self.assertIn("Current: 2.0 A", output)

    def test_invalid_menu_choice_and_non_numeric_entry_return_to_menu(self):
        output = self.run_with_inputs(["abc", "1", "not-a-number", "4"])
        self.assertIn("Error: Choose an option from 1 to 4", output)
        self.assertIn("is not a valid number", output)
        self.assertIn("Goodbye.", output)

    def test_calculation_error_returns_to_menu(self):
        output = self.run_with_inputs(["2", "-1", "", "4"])
        self.assertIn("Error: resistance at index 0 must be non-negative", output)
        self.assertIn("Goodbye.", output)

if __name__ == "__main__":
    unittest.main()
