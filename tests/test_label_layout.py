"""Independent pixel-geometry, deterministic fallback and resource-bound oracles."""

from dataclasses import FrozenInstanceError
from itertools import repeat
import math
import random
import subprocess
import sys
import unittest

from circuit_calculator.label_layout import (Rect, place_labels, intersects, MAX_CHECKS,
                                             MAX_LABELS, MAX_OBSTACLES, OFFSETS)


class LabelLayoutTests(unittest.TestCase):
    def test_measured_rectangles_validate_finite_pixel_extents_and_are_immutable(self):
        rectangle = Rect(-10, -20, 10, 20)
        with self.assertRaises(FrozenInstanceError):
            rectangle.left = 2
        for values in ((0, 0, 0, 10), (0, 0, 10, .5), (0, 0, -10, 10),
                       (0, 0, math.inf, 10), (math.nan, 0, 10, 10), (-1e308, 0, 1e308, 10),
                       (0, 0, 10**1000, 10)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Rect(*values)
        for value in (True, '1', None, 1j):
            with self.assertRaises(TypeError):
                Rect(value, 0, 10, 10)

    def test_hand_derived_positive_area_intersection_and_edge_touching(self):
        first = Rect(0, 0, 10, 10)
        self.assertTrue(intersects(first, Rect(9, 9, 20, 20)))
        self.assertFalse(intersects(first, Rect(10, 0, 20, 10)))
        self.assertFalse(intersects(first, Rect(0, 10, 10, 20)))
        self.assertFalse(intersects(first, Rect(-20, -20, -10, -10)))

    def test_original_positions_and_empty_inputs_are_preferred(self):
        labels = (Rect(0, 0, 10, 10), Rect(50, 50, 70, 70))
        layout = place_labels(labels, (Rect(500, 500, 600, 600),))
        self.assertEqual(layout.rectangles, labels)
        self.assertFalse(layout.unresolved)
        self.assertFalse(layout.exhausted)
        self.assertEqual(place_labels(()).rectangles, ())

    def test_duplicate_labels_follow_fixed_first_clear_order(self):
        rectangle = Rect(0, 0, 10, 10)
        expected = (rectangle, Rect(0, -24, 10, -14), Rect(0, 24, 10, 34))
        first = place_labels((rectangle,) * 3)
        self.assertEqual(first.rectangles, expected)
        for _ in range(3):
            self.assertEqual(place_labels((rectangle,) * 3), first)

    def test_geometry_obstacle_and_negative_grid_boundaries(self):
        layout = place_labels((Rect(-65, -65, -55, -55),), (Rect(-67, -67, -54, -54),))
        self.assertEqual(layout.rectangles, (Rect(-65, -89, -55, -79),))
        self.assertFalse(layout.unresolved)

    def test_gap_is_exact_without_an_arbitrary_overlap_tolerance(self):
        labels = (Rect(0, 0, 10, 10), Rect(13, 0, 23, 10))
        self.assertEqual(place_labels(labels, gap=3).rectangles, labels)
        self.assertNotEqual(place_labels(labels, gap=4).rectangles, labels)

    def test_resolved_simple_layout_clears_obstacles_and_other_labels(self):
        labels = (Rect(0, 0, 10, 10),) * 5
        obstacles = (Rect(0, 0, 10, 10),)
        layout = place_labels(labels, obstacles)
        self.assertFalse(layout.unresolved)
        # Independent distance oracle: at least one separating axis has 3px gap.
        def clear(a, b):
            return max(b.left - a.right, a.left - b.right,
                       b.top - a.bottom, a.top - b.bottom) >= 3
        for i, rectangle in enumerate(layout.rectangles):
            for other in (*obstacles, *layout.rectangles[:i]):
                self.assertTrue(clear(rectangle, other))
        self.assertEqual(labels, (Rect(0, 0, 10, 10),) * 5)

    def test_dense_fallback_keeps_text_at_original_position(self):
        rectangle = Rect(0, 0, 10, 10)
        layout = place_labels((rectangle,), (Rect(-1000, -1000, 1000, 1000),))
        self.assertEqual(layout.rectangles, (rectangle,))
        self.assertEqual(layout.unresolved, (0,))
        self.assertFalse(layout.exhausted)
        self.assertEqual(layout.checks, len(OFFSETS))

    def test_budget_exhaustion_keeps_remaining_positions_and_reports_uncertainty(self):
        labels = (Rect(0, 0, 10, 10), Rect(40, 0, 50, 10))
        layout = place_labels(labels, (Rect(-10000, 500, 10000, 510),), max_checks=1)
        self.assertEqual(layout.rectangles, labels)
        self.assertEqual(layout.unresolved, (1,))
        self.assertTrue(layout.exhausted)
        self.assertEqual(layout.checks, 1)

    def test_full_label_limit_sparse_layout_stays_clear(self):
        labels = tuple(Rect((i % 35) * 40, (i // 35) * 40,
                            (i % 35) * 40 + 10, (i // 35) * 40 + 10) for i in range(MAX_LABELS))
        layout = place_labels(labels)
        self.assertEqual(layout.rectangles, labels)
        self.assertFalse(layout.unresolved)
        self.assertFalse(layout.exhausted)
        self.assertLessEqual(layout.checks, MAX_CHECKS)

    def test_large_global_obstacles_cannot_expand_index_or_exceed_check_budget(self):
        labels = tuple(Rect(i * 30, 0, i * 30 + 10, 10) for i in range(MAX_LABELS))
        obstacles = (Rect(-1e12, 1000, 1e12, 1010),) * MAX_OBSTACLES
        layout = place_labels(labels, obstacles)
        self.assertEqual(len(layout.rectangles), MAX_LABELS)
        self.assertEqual(layout.checks, MAX_CHECKS)
        self.assertTrue(layout.exhausted)
        self.assertTrue(layout.unresolved)

    def test_input_and_numeric_budgets_are_bounded_even_for_infinite_iterables(self):
        rectangle = Rect(0, 0, 10, 10)
        for labels, obstacles in ((repeat(rectangle), ()), ((), repeat(rectangle))):
            with self.assertRaises(ValueError):
                place_labels(labels, obstacles)
        for labels in ('text', [None], [()], [True], None):
            with self.assertRaises(TypeError):
                place_labels(labels)
        for gap in (-1, 65, math.inf, math.nan):
            with self.assertRaises(ValueError):
                place_labels((), gap=gap)
        with self.assertRaises(TypeError):
            place_labels((), gap=True)
        for budget in (0, -1, True, 1.5, MAX_CHECKS + 1):
            with self.assertRaises(ValueError):
                place_labels((), max_checks=budget)

    def test_placement_is_translation_invariant_across_spatial_cell_boundaries(self):
        randomizer = random.Random(421)
        def rectangles(count):
            items = []
            for _ in range(count):
                x, y = randomizer.randint(-150, 150), randomizer.randint(-150, 150)
                items.append(Rect(x, y, x + randomizer.randint(10, 50), y + randomizer.randint(10, 40)))
            return tuple(items)
        for _ in range(10):
            labels, obstacles = rectangles(12), rectangles(20)
            original = place_labels(labels, obstacles)
            shifted = place_labels(tuple(r.shifted(73, -97) for r in labels),
                                   tuple(r.shifted(73, -97) for r in obstacles))
            self.assertFalse(original.exhausted)
            self.assertFalse(shifted.exhausted)
            self.assertEqual(shifted.rectangles, tuple(r.shifted(73, -97) for r in original.rectangles))
            self.assertEqual(shifted.unresolved, original.unresolved)

    def test_covering_global_obstacles_use_first_collision_and_keep_every_label(self):
        labels = tuple(Rect(i * 30, 0, i * 30 + 10, 10) for i in range(MAX_LABELS))
        layout = place_labels(labels, (Rect(-1e12, -1e12, 1e12, 1e12),) * MAX_OBSTACLES)
        self.assertEqual(layout.rectangles, labels)
        self.assertEqual(layout.unresolved, tuple(range(MAX_LABELS)))
        self.assertEqual(layout.checks, 17500)
        self.assertFalse(layout.exhausted)

    def test_dense_local_buckets_stream_duplicates_without_hiding_labels(self):
        labels = (Rect(0, 0, 100, 40),) * MAX_LABELS
        pattern = tuple(Rect(x - 60, y - 60, x + 60, y + 60)
                        for x in range(-300, 301, 100) for y in range(-200, 201, 100))
        obstacles = tuple(pattern[i % len(pattern)] for i in range(MAX_OBSTACLES))
        layout = place_labels(labels, obstacles)
        self.assertEqual(layout.rectangles, labels)
        self.assertEqual(layout.unresolved, tuple(range(MAX_LABELS)))
        self.assertFalse(layout.exhausted)
        self.assertLessEqual(layout.checks, MAX_CHECKS)

    def test_import_needs_no_tk_or_numpy(self):
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; import circuit_calculator.label_layout; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)
