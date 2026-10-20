"""Electrical circuit calculations."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from numbers import Number
import math


@dataclass(frozen=True)
class ParallelResistanceResult:
    """Equivalent resistance and short-circuit status for parallel branches."""

    equivalent_resistance: float
    has_short_circuit: bool


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


def parallel_resistance(resistances):
    """Return equivalent resistance and short-circuit status for parallel branches.

    Values follow the same validation rules as :func:`series_resistance`.
    A zero-ohm branch short-circuits the parallel network, so the equivalent
    resistance is zero and ``has_short_circuit`` is true.
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

    has_short_circuit = any(value == 0 for value in values)
    if has_short_circuit:
        return ParallelResistanceResult(0.0, True)

    reciprocal_sum = math.fsum(1.0 / float(value) for value in values)
    return ParallelResistanceResult(1.0 / reciprocal_sum, False)
