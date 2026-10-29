"""SI boundary behavior and exact decimal scaling, independent of Tk/NumPy."""

from decimal import Decimal, Inexact, Rounded, Overflow, Underflow, localcontext
import math
import sys
import unittest

from circuit_calculator.circuit import Resistor, VoltageSource, CurrentSource
from circuit_calculator.circuit_io import dumps_document, loads_document
from circuit_calculator.quantities import parse_quantity, format_quantity
from circuit_calculator.schematic import divider_example


class QuantityTests(unittest.TestCase):
    def test_every_si_engineering_prefix_and_micro_alias(self):
        reference = {'q': '1e-30', 'r': '1e-27', 'y': '1e-24', 'z': '1e-21',
                     'a': '1e-18', 'f': '1e-15', 'p': '1e-12', 'n': '1e-9',
                     'u': '1e-6', 'µ': '1e-6', 'μ': '1e-6', 'm': '.001', '': '1',
                     'k': '1e3', 'M': '1e6', 'G': '1e9', 'T': '1e12', 'P': '1e15',
                     'E': '1e18', 'Z': '1e21', 'Y': '1e24', 'R': '1e27', 'Q': '1e30'}
        for prefix, expected in reference.items():
            for suffix, unit in (('', 'V'), ('V', 'V'), ('ohm', 'ohm'), ('Ω', 'ohm'), ('A', 'A'), ('W', 'W')):
                with self.subTest(prefix=prefix, suffix=suffix):
                    self.assertEqual(parse_quantity('1' + prefix + suffix, unit), Decimal(expected))

    def test_signs_exponents_whitespace_and_dimensionless_number_syntax(self):
        for text, unit, expected in (('  +4.7 kohm  ', 'ohm', '4700'), ('4.7kΩ', 'Ω', '4700'),
                                     ('-.5mA', 'A', '-.0005'), ('2.e3V', 'V', '2000'),
                                     ('1e-3 kV', 'V', '1'), ('1E3', 'V', '1000'),
                                     ('1E', 'V', '1e18'), ('1EV', 'V', '1e18'),
                                     ('3.3', 'V', '3.3'), ('-0 µA', 'A', '-0')):
            with self.subTest(text=text):
                actual = parse_quantity(text, unit)
                self.assertEqual(actual, Decimal(expected))
                if expected == '-0':
                    self.assertTrue(actual.is_signed())

    def test_milli_mega_kilo_case_is_never_silently_coerced(self):
        self.assertEqual(parse_quantity('1m', 'A'), Decimal('.001'))
        self.assertEqual(parse_quantity('1M', 'A'), Decimal('1000000'))
        self.assertEqual(parse_quantity('1k', 'ohm'), Decimal('1000'))
        for text in ('1K', '1Meg', '1meg', '1MAA', '1kk', '4k7', '1m A', '1u V'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_quantity(text, 'A')

    def test_malformed_wrong_unit_unsupported_and_oversized_inputs(self):
        for text in ('', ' ', '.', '1e', '--1', '1+2', '1/2', '1_000', '1,000', 'NaN',
                     'Infinity', '-inf', '1V', '1A', '1W', '1F', '1H', '1ms', '1ΩΩ',
                     '1;print(1)', '1' * 257, '1e' + '9' * 200, '1\x00'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_quantity(text, 'ohm')
        for text in (None, True, 1, Decimal(1)):
            with self.subTest(text=text), self.assertRaises(TypeError):
                parse_quantity(text, 'V')
        for unit in ('v', 'amps', '', None, []):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                parse_quantity('1', unit)

    def test_scaling_is_exact_under_tiny_trapping_decimal_context(self):
        expected = Decimal('123456789012345678901234567890.123456789e30')
        original = Decimal('123456789012345678901234567890.123456789')
        with localcontext() as context:
            context.prec = 3
            context.Emax, context.Emin = 9, -9
            for signal in (Inexact, Rounded, Overflow, Underflow):
                context.traps[signal] = True
            actual = parse_quantity(str(original) + 'QΩ', 'ohm')
            tiny = parse_quantity('1e-400 qA', 'A')
        self.assertEqual(actual, expected)
        self.assertEqual(actual.as_tuple().digits, original.as_tuple().digits)
        self.assertEqual(tiny, Decimal('1e-430'))

    def test_parsing_does_not_bypass_existing_physical_or_float_range_guards(self):
        for text in ('0', '-1m', '1e-400', '1e400'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                Resistor('R', 'a', 'b', parse_quantity(text, 'ohm'))
        for constructor in (VoltageSource, CurrentSource):
            for text in ('1e-400', '1e400'):
                with self.subTest(constructor=constructor, text=text), self.assertRaises(ValueError):
                    constructor('S', 'a', 'b', parse_quantity(text, 'V'))
            self.assertEqual(constructor('S', 'a', 'b', parse_quantity('0', 'V')).__class__, constructor)
        tiny = CurrentSource('I', 'a', 'b', parse_quantity('5e-324 A', 'A'))
        self.assertEqual(tiny.current_amperes, math.ulp(0.0))

    def test_readable_display_signs_units_and_every_engineering_range(self):
        for value, unit, expected in ((0, 'V', '0 V'), (-0.0, 'A', '-0 A'),
                                      (4700, 'ohm', '4.7 kΩ'), (1e6, 'Ω', '1 MΩ'),
                                      (-.004, 'A', '-4 mA'), (-.048, 'W', '-48 mW'),
                                      (1e-6, 'A', '1 µA'), (1e-30, 'V', '1 qV'),
                                      (1e30, 'V', '1 QV'), (1e32, 'V', '100 QV')):
            with self.subTest(value=value, unit=unit):
                self.assertEqual(format_quantity(value, unit), expected)
        # Display -> exact decimal parse agrees within the explicitly rounded precision.
        for exponent in range(-30, 31, 3):
            for coefficient in (-999, -1, 1, 999):
                value = coefficient * 10.0**exponent
                rendered = format_quantity(value, 'A')
                recovered = float(parse_quantity(rendered, 'A'))
                self.assertTrue(math.isclose(value, recovered, rel_tol=1e-12))

    def test_rounding_promotes_at_prefix_boundaries(self):
        self.assertEqual(format_quantity(999.9999, 'ohm'), '1 kΩ')
        self.assertEqual(format_quantity(.0009999999, 'A'), '1 mA')
        self.assertEqual(format_quantity(-999999.9, 'V'), '-1 MV')
        self.assertEqual(format_quantity(999.9999, 'V', significant=9), '999.9999 V')
        self.assertEqual(format_quantity(999.9999e30, 'V'), '1e+33 V')

    def test_extreme_finite_display_never_becomes_a_false_zero_or_infinity(self):
        for value in (math.ulp(0.0), -math.ulp(0.0), sys.float_info.min,
                      sys.float_info.max, -sys.float_info.max, 1e-31, 1e33):
            with self.subTest(value=value):
                text = format_quantity(value, 'A', significant=9)
                parsed = parse_quantity(text, 'A')
                self.assertNotEqual(parsed, 0)
                self.assertTrue(parsed.is_finite())
                self.assertNotIn('inf', text)
                self.assertEqual(parsed.is_signed(), value < 0)
        self.assertEqual(float(parse_quantity(format_quantity(math.ulp(0.0), 'A'), 'A')), math.ulp(0.0))

    def test_display_invalid_type_unit_precision_or_nonfinite(self):
        for value in (True, '1', Decimal(1), complex(1)):
            with self.subTest(value=value), self.assertRaises(TypeError):
                format_quantity(value, 'A')
        for value in (float('nan'), float('inf'), -float('inf'), 10**1000):
            with self.subTest(value=value), self.assertRaises(ValueError):
                format_quantity(value, 'A')
        for precision in (True, 0, 16, 1.5, '6'):
            with self.subTest(precision=precision), self.assertRaises(ValueError):
                format_quantity(1, 'A', significant=precision)
        with self.assertRaises(ValueError):
            format_quantity(1, 'amps')

    def test_display_does_not_modify_exact_model_or_json_values(self):
        state = divider_example().change_value('R1', parse_quantity('1.234567891234567kΩ', 'ohm'))
        before = dumps_document(state.document)
        rendered = format_quantity(state.document.circuit.elements[1].resistance_ohms, 'ohm')
        self.assertEqual(rendered, '1.23457 kΩ')
        self.assertEqual(dumps_document(state.document), before)
        self.assertEqual(loads_document(before), state.document)
        self.assertEqual(state.document.circuit.elements[1].resistance_ohms, 1234.567891234567)


if __name__ == '__main__':
    unittest.main()
