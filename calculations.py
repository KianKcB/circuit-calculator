"""Electrical circuit calculations."""

from collections.abc import Iterable
from decimal import Decimal
from numbers import Number
import math


def series_resistance(resistances):
    """Return the total resistance of a non-empty iterable of resistances.

    Values must be real numeric values that are finite and non-negative.
    Booleans are rejected even though ``bool`` is a subclass of ``int``.
    """
    if isinstance(resistances, (str, bytes)) or not isinstance(resistances, Iterable):
        raise TypeError("resistances must be a non-empty iterable of numeric values")

    values = list(resistances)
    if not values:
        raise ValueError("resistances must not be empty")

    for index, value in enumerate(values):
        if isinstance(value, bool) or not (isinstance(value, Number) or isinstance(value, Decimal)):
            raise TypeError(f"resistance at index {index} must be a real numeric value")
        if isinstance(value, complex):
            raise TypeError(f"resistance at index {index} must be a real numeric value")
        try:
            finite = math.isfinite(value)
        except (TypeError, ValueError, OverflowError):
            finite = False
        if not finite:
            raise ValueError(f"resistance at index {index} must be finite")
        if value < 0:
            raise ValueError(f"resistance at index {index} must be non-negative")

    return sum(values)
