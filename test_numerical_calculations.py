"""Range regressions and independent references for standalone formulas."""

from decimal import Decimal, localcontext, Overflow
from fractions import Fraction
import math
import unittest

from calculations import (series_resistance, parallel_resistance,
                          calculate_ohms_law, calculate_power)
from main import run_cli


class SeriesNumericalTests(unittest.TestCase):
    def test_floating_sum_overflow_is_a_value_error(self):
        with self.assertRaisesRegex(ValueError, 'finite'):
            series_resistance([1e308, 1e308])

    def test_mixed_decimal_float_and_fraction_use_float(self):
        for values in ([Decimal('1'), 1.0], [Decimal('1'), Fraction(1, 2)]):
            with self.subTest(values=values):
                result = series_resistance(values)
                self.assertIsInstance(result, float)
                self.assertEqual(result, 2.0 if isinstance(values[1], float) else 1.5)

    def test_native_return_types_and_ranges_are_preserved(self):
        cases = [([1, 2], 3, int),
                 ([Fraction(1, 3), 1], Fraction(4, 3), Fraction),
                 ([Decimal('1.25'), 2], Decimal('3.25'), Decimal),
                 ([Decimal('1e-1000')], Decimal('1e-1000'), Decimal),
                 ([10**400, 1], 10**400 + 1, int)]
        for values, expected, result_type in cases:
            with self.subTest(values=values):
                result = series_resistance(values)
                self.assertEqual(result, expected)
                self.assertIsInstance(result, result_type)

    def test_float_conversion_underflow_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            series_resistance([Decimal('1e-1000'), 1.0])

    def test_floating_sum_retains_small_contributions(self):
        self.assertEqual(series_resistance([1e16, 1.0, 1.0]), 1e16 + 2)

    def test_decimal_context_overflow_trapped_or_untrapped(self):
        for trap in (True, False):
            with self.subTest(trap=trap), localcontext() as context:
                context.Emax = 2
                context.traps[Overflow] = trap
                with self.assertRaisesRegex(ValueError, 'finite'):
                    series_resistance([Decimal('900'), Decimal('900')])

    def test_decimal_context_underflow_to_zero_is_rejected(self):
        with localcontext() as context:
            context.prec = 2
            context.Emin = -2
            with self.assertRaisesRegex(ValueError, 'nonzero'):
                series_resistance([Decimal('1e-100')])

    def test_decimal_signaling_nan_is_a_value_error(self):
        with self.assertRaisesRegex(ValueError, 'finite'):
            series_resistance([Decimal('sNaN')])


class ParallelNumericalTests(unittest.TestCase):
    def test_tiny_positive_branch_is_not_a_short(self):
        for resistance in (1e-320, float.fromhex('0x0.0000000000001p-1022')):
            result = parallel_resistance([resistance])
            self.assertEqual(result.equivalent_resistance, resistance)
            self.assertFalse(result.has_short_circuit)

    def test_subnormal_equivalent_is_preserved(self):
        self.assertEqual(parallel_resistance([1e-320, 1e-320]).equivalent_resistance, 5e-321)

    def test_unrepresentable_positive_equivalent_is_rejected(self):
        tiny = float.fromhex('0x0.0000000000001p-1022')
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            parallel_resistance([tiny, tiny])

    def test_input_conversion_underflow_even_with_short_is_rejected(self):
        for values in ([Decimal('1e-1000')], [0, Decimal('1e-1000')]):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, 'nonzero'):
                    parallel_resistance(values)

    def test_extreme_dynamic_range_and_large_equal_branches(self):
        self.assertEqual(parallel_resistance([1e-300, 1e300]).equivalent_resistance, 1e-300)
        self.assertEqual(parallel_resistance([1e308, 1e308]).equivalent_resistance, 5e307)

    def test_permutation_scaling_and_physical_bounds(self):
        for scale in (1e-200, 1.0, 1e200):
            values = [2 * scale, 3 * scale, 6 * scale]
            equivalent = parallel_resistance(values).equivalent_resistance
            self.assertTrue(math.isclose(equivalent, scale, rel_tol=1e-15))
            self.assertEqual(equivalent, parallel_resistance(reversed(values)).equivalent_resistance)
            self.assertGreater(equivalent, 0)
            self.assertLessEqual(equivalent, min(values))


class OhmsLawNumericalTests(unittest.TestCase):
    def test_conversion_underflow_is_not_silently_zero(self):
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            calculate_ohms_law(current=Decimal('1e-1000'), resistance=1, solve_for='voltage')

    def test_result_underflow_in_each_formula_is_rejected(self):
        for kwargs in ({'current': 1e-300, 'resistance': 1e-300, 'solve_for': 'voltage'},
                       {'voltage': 1e-300, 'resistance': 1e300, 'solve_for': 'current'},
                       {'voltage': 1e-300, 'current': 1e300, 'solve_for': 'resistance'}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'nonzero'):
                calculate_ohms_law(**kwargs)

    def test_overflow_in_each_formula_is_rejected(self):
        for kwargs in ({'current': 1e300, 'resistance': 1e300, 'solve_for': 'voltage'},
                       {'voltage': 1e300, 'resistance': 1e-300, 'solve_for': 'current'},
                       {'voltage': 1e300, 'current': 1e-300, 'solve_for': 'resistance'}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'finite'):
                calculate_ohms_law(**kwargs)

    def test_true_zero_and_subnormal_remain_valid(self):
        self.assertEqual(calculate_ohms_law(current=0, resistance=1e300, solve_for='voltage'), 0)
        self.assertEqual(calculate_ohms_law(voltage=0, resistance=1, solve_for='current'), 0)
        self.assertEqual(calculate_ohms_law(voltage=0, current=1, solve_for='resistance'), 0)
        self.assertEqual(calculate_ohms_law(current=1e-320, resistance=1, solve_for='voltage'), 1e-320)


class PowerNumericalTests(unittest.TestCase):
    def test_square_overflow_and_underflow_do_not_destroy_finite_answers(self):
        cases = [({'current': 1e200, 'resistance': 1e-200}, 1e200),
                 ({'voltage': 1e200, 'resistance': 1e200}, 1e200),
                 ({'current': 1e-200, 'resistance': 1e200}, 1e-200),
                 ({'voltage': 1e-200, 'resistance': 1e-200}, 1e-200)]
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                self.assertTrue(math.isclose(calculate_power(**kwargs), expected, rel_tol=1e-15))

    def test_high_precision_decimal_reference_for_float_inputs(self):
        with localcontext() as context:
            context.prec = 100
            for magnitude in (1e-150, 0.3, 1.0, 1e150):
                for resistance in (1e-100, 3.0, 1e100):
                    for formula in ('current', 'voltage'):
                        with self.subTest(magnitude=magnitude, resistance=resistance, formula=formula):
                            squared = Decimal.from_float(magnitude) ** 2
                            rd = Decimal.from_float(resistance)
                            expected = float(squared * rd if formula == 'current' else squared / rd)
                            if expected == 0 or not math.isfinite(expected):
                                with self.assertRaises(ValueError):
                                    calculate_power(**{formula: magnitude, 'resistance': resistance})
                            else:
                                self.assertEqual(calculate_power(**{formula: magnitude, 'resistance': resistance}), expected)

    def test_overflow_and_nonzero_underflow_in_all_formulas(self):
        cases = ({'voltage': 1e300, 'current': 1e300},
                 {'current': 1e300, 'resistance': 1},
                 {'voltage': 1e300, 'resistance': 1},
                 {'voltage': 1e-300, 'current': 1e-300},
                 {'current': 1e-300, 'resistance': 1},
                 {'voltage': 1e-300, 'resistance': 1})
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                calculate_power(**kwargs)

    def test_true_zero_signed_power_and_subnormal(self):
        self.assertEqual(calculate_power(current=1e300, resistance=0), 0)
        self.assertEqual(calculate_power(voltage=0, resistance=1e-300), 0)
        self.assertEqual(calculate_power(voltage=-1e-320, current=1), -1e-320)
        self.assertEqual(calculate_power(current=-2, resistance=3), 12)

    def test_conversion_underflow_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            calculate_power(current=Decimal('1e-1000'), voltage=1)


class NumericalCLITests(unittest.TestCase):
    def test_tiny_nonzero_text_is_rejected_before_becoming_a_short_or_zero_source(self):
        entries = iter(['2', '1e-1000', '4', '1', '-1e-1000', '6'])
        output = []
        run_cli(lambda prompt: next(entries), output.append)
        text = '\n'.join(output)
        self.assertEqual(text.count('too small'), 2)
        self.assertNotIn('short circuit', text)
        self.assertIn('Goodbye.', text)

    def test_actual_zero_and_subnormal_text_still_work(self):
        entries = iter(['2', '0e-1000', '', '2', '1e-320', '', '6'])
        output = []
        run_cli(lambda prompt: next(entries), output.append)
        text = '\n'.join(output)
        self.assertEqual(text.count('short circuit'), 1)
        self.assertIn('1e-320', text)
        self.assertNotIn('Error:', text)

    def test_range_errors_recover_and_valid_extreme_power_is_displayed(self):
        entries = iter(['1', '1e308', '1e308', '',
                        '4', '2', '1e200', '1e-200',
                        '4', '1', '1e-300', '1e-300', '6'])
        output = []
        run_cli(lambda prompt: next(entries), output.append)
        text = '\n'.join(output)
        self.assertEqual(text.count('Error:'), 2)
        self.assertIn('must be finite', text)
        self.assertIn('nonzero', text)
        self.assertIn('Power:', text)
        self.assertIn('Goodbye.', text)


class SharedNumericPolicyTests(unittest.TestCase):
    def test_float_paths_reject_conversion_overflow_and_underflow(self):
        for value in (10**400, Decimal('1e400'), Fraction(1, 10**400)):
            for operation in (lambda x: parallel_resistance([x]),
                              lambda x: series_resistance([x, 1.0]),
                              lambda x: calculate_power(voltage=x, current=1),
                              lambda x: calculate_ohms_law(current=x, resistance=1, solve_for='voltage')):
                with self.subTest(value=value, operation=operation), self.assertRaises(ValueError):
                    operation(value)

    def test_short_does_not_hide_invalid_resistance(self):
        for value in (-1, math.inf, math.nan, Decimal('sNaN')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parallel_resistance([0, value])

    def test_power_formulas_agree_with_ohms_law(self):
        for voltage in (-12, 0, 12):
            current = calculate_ohms_law(voltage=voltage, resistance=3, solve_for='current')
            self.assertEqual(calculate_power(voltage=voltage, current=current),
                             calculate_power(current=current, resistance=3))
            self.assertEqual(calculate_power(current=current, resistance=3),
                             calculate_power(voltage=voltage, resistance=3))


if __name__ == '__main__':
    unittest.main()
