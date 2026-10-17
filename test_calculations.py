"""Tests for circuit calculations."""

import math
import unittest
from decimal import Decimal

from calculations import series_resistance


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


if __name__ == "__main__":
    unittest.main()
