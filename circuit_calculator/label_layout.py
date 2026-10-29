"""Bounded, deterministic placement of measured result-label rectangles. No Tk."""

from dataclasses import dataclass
from heapq import merge
from itertools import groupby, islice
import math


MAX_LABELS = 700
MAX_OBSTACLES = 4096
MAX_CHECKS = 200_000
CELL = 64
MAX_CELLS = 16
OFFSETS = ((0, 0), (0, -24), (0, 24), (-32, 0), (32, 0),
           (0, -48), (0, 48), (-64, 0), (64, 0),
           (-32, -24), (32, -24), (-32, 24), (32, 24),
           (0, -96), (0, 96), (-128, 0), (128, 0),
           (-64, -48), (64, -48), (-64, 48), (64, 48),
           (0, -160), (0, 160), (-224, 0), (224, 0))


def _finite(value):
    if type(value) not in (int, float):
        raise TypeError('Pixel coordinates must be built-in real numbers')
    try:
        number = float(value)
    except OverflowError:
        raise ValueError('Pixel coordinate must be finite') from None
    if not math.isfinite(number):
        raise ValueError('Pixel coordinate must be finite')
    return number


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self):
        for name in ('left', 'top', 'right', 'bottom'):
            object.__setattr__(self, name, _finite(getattr(self, name)))
        width, height = self.right - self.left, self.bottom - self.top
        if not math.isfinite(width) or not math.isfinite(height) or min(width, height) < 1:
            raise ValueError('Measured rectangles need finite extents of at least one pixel')

    def shifted(self, x, y):
        return Rect(self.left + x, self.top + y, self.right + x, self.bottom + y)

    def padded(self, gap):
        return Rect(self.left - gap, self.top - gap, self.right + gap, self.bottom + gap)


@dataclass(frozen=True)
class Layout:
    rectangles: tuple
    unresolved: tuple
    checks: int
    exhausted: bool


def intersects(first, second):
    """Positive-area intersection; touching rectangle edges are allowed."""
    return (first.left < second.right and first.right > second.left
            and first.top < second.bottom and first.bottom > second.top)


def _bounded(values, maximum):
    if isinstance(values, (str, bytes)):
        raise TypeError('Expected an iterable of measured Rect values')
    items = tuple(islice(values, maximum + 1))
    if len(items) > maximum:
        raise ValueError('Annotation layout input limit exceeded')
    if any(type(item) is not Rect for item in items):
        raise TypeError('Expected measured Rect values')
    return items


def _cells(rect):
    left, right = math.floor(rect.left / CELL), math.floor(rect.right / CELL)
    top, bottom = math.floor(rect.top / CELL), math.floor(rect.bottom / CELL)
    if (right - left + 1) * (bottom - top + 1) > MAX_CELLS:
        return None
    return tuple((x, y) for x in range(left, right + 1) for y in range(top, bottom + 1))


class _Index:
    def __init__(self):
        self.rectangles, self.large, self.buckets = [], [], {}

    def add(self, rect):
        index = len(self.rectangles)
        self.rectangles.append(rect)
        cells = _cells(rect)
        if cells is None:
            self.large.append(index)
        else:
            for cell in cells:
                self.buckets.setdefault(cell, []).append(index)

    def nearby(self, rect):
        cells = _cells(rect)
        if cells is None:
            return range(len(self.rectangles))
        # Each bucket and the global list already have ascending insertion IDs.
        # Stream their merge and deduplicate adjacent IDs; an early collision
        # must not materialize/sort thousands of IDs from crowded grid buckets.
        streams = (self.large, *(self.buckets.get(cell, ()) for cell in cells))
        return (number for number, _ in groupby(merge(*streams)))


def place_labels(labels, obstacles=(), *, gap=3, max_checks=MAX_CHECKS):
    """Greedy first-clear placement; unresolved entries retain original positions."""
    labels, obstacles = _bounded(labels, MAX_LABELS), _bounded(obstacles, MAX_OBSTACLES)
    gap = _finite(gap)
    if not 0 <= gap <= CELL:
        raise ValueError('Annotation gap must be between 0 and 64 pixels')
    if type(max_checks) is not int or not 1 <= max_checks <= MAX_CHECKS:
        raise ValueError('Annotation check budget must be an integer from 1 to 200000')
    index = _Index()
    for obstacle in obstacles:
        index.add(obstacle.padded(gap))
    placed, unresolved, checks = [], [], 0
    for number, original in enumerate(labels):
        chosen = None
        for x, y in OFFSETS:
            candidate = original.shifted(x, y)
            for other in index.nearby(candidate):
                if checks == max_checks:
                    return Layout(tuple((*placed, *labels[number:])),
                                  tuple((*unresolved, *range(number, len(labels)))), checks, True)
                checks += 1
                if intersects(candidate, index.rectangles[other]):
                    break
            else:
                chosen = candidate
                break
        if chosen is None:
            unresolved.append(number)
            chosen = original
        placed.append(chosen)
        index.add(chosen.padded(gap))
    return Layout(tuple(placed), tuple(unresolved), checks, False)
