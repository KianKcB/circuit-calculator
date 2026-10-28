"""Independent pixel/world camera arithmetic without Tk or optional NumPy."""

import unittest
import subprocess
import sys

from circuit_calculator.viewport import clamp_zoom, fit_zoom, scroll_region, scroll_fraction


class ViewportTests(unittest.TestCase):
    def test_renderer_and_view_math_import_without_tk_or_numpy(self):
        subprocess.run([sys.executable, '-B', '-c',
            "import sys; import circuit_calculator.viewport, circuit_calculator.canvas_renderer; "
            "assert 'tkinter' not in sys.modules; assert 'numpy' not in sys.modules"], check=True)

    def test_zoom_clamps_and_rejects_invalid_values(self):
        self.assertEqual(clamp_zoom(.01), .4)
        self.assertEqual(clamp_zoom(100), 2.5)
        self.assertEqual(clamp_zoom(1.25), 1.25)
        for value in (True, '1', 0, -1, float('nan'), float('inf'), 10**1000):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                clamp_zoom(value)

    def test_fit_uses_available_dimensions_and_current_scale(self):
        # 400x200 pixels into 600x400, with 50 pixels each side: width limits at 1.25.
        self.assertEqual(fit_zoom(1, (0, 0, 400, 200), 600, 400, padding=50), 1.25)
        self.assertEqual(fit_zoom(2, (-100, -100, 300, 100), 600, 400, padding=50), 2.5)
        self.assertEqual(fit_zoom(1, (0, 0, 100, 400), 600, 400, padding=50), .75)

    def test_fit_tiny_and_large_content_reports_bounded_zoom(self):
        self.assertEqual(fit_zoom(1, (20, 30, 20, 30), 600, 400), 2.5)
        self.assertEqual(fit_zoom(1, (-100000, -100000, 100000, 100000), 600, 400), .4)
        self.assertEqual(fit_zoom(1, (0, 0, 100, 100), 1, 1), .4)

    def test_padded_scroll_region_supports_centering_content_edges(self):
        region = scroll_region((-100, -200, 300, 400), 600, 400, padding=20)
        self.assertEqual(region, (-420, -420, 620, 620))
        for center in (-100, 300):
            fraction = scroll_fraction(center, region[0], region[2], 600)
            origin = region[0] + fraction * (region[2] - region[0])
            self.assertAlmostEqual(origin + 300, center)

    def test_scroll_fraction_hand_derived_and_clamped(self):
        self.assertEqual(scroll_fraction(400, 0, 1000, 200), .3)
        self.assertEqual(scroll_fraction(-100, 0, 1000, 200), 0)
        self.assertEqual(scroll_fraction(2000, 0, 1000, 200), .8)
        self.assertEqual(scroll_fraction(50, 0, 100, 200), 0)

    def test_invalid_bounds_extents_and_padding_are_explicit(self):
        for bounds in ((0, 0, -1, 1), (0, 0, 1), (0, 0, 1, float('inf')), (0, True, 1, 1),
                       (-1e308, 0, 1e308, 1)):
            with self.subTest(bounds=bounds), self.assertRaises((TypeError, ValueError)):
                fit_zoom(1, bounds, 600, 400)
        for width, height, padding in ((0, 100, 1), (100, -1, 1), (True, 100, 1), (100, 100, -1),
                                      (100, 100, float('nan'))):
            with self.subTest(args=(width, height, padding)), self.assertRaises((TypeError, ValueError)):
                scroll_region((0, 0, 1, 1), width, height, padding=padding)
        with self.assertRaises(ValueError):
            scroll_region((-1e308, 0, 1, 1), 1e308, 400, padding=1e308)
        with self.assertRaises(ValueError):
            scroll_fraction(0, 1, 1, 100)
        with self.assertRaises(ValueError):
            scroll_fraction(0, -1e308, 1e308, 100)


if __name__ == '__main__':
    unittest.main()
