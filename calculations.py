"""Electrical circuit calculations."""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from fractions import Fraction
from numbers import Integral, Number, Rational
import math

_UNSET = object()


@dataclass(frozen=True)
class ParallelResistanceResult:
    """Equivalent resistance and short-circuit status for parallel branches."""

    equivalent_resistance: float
    has_short_circuit: bool


def series_resistance(resistances):
    """Return the total resistance of a non-empty iterable of resistances.

    Values must be real numeric values that are finite and non-negative.
    Booleans are rejected even though ``bool`` is a subclass of ``int``.
    Rational-only and Decimal/integer inputs retain native arithmetic; other
    mixtures use floats. Non-finite totals and underflow to zero are errors.
    """
    if isinstance(resistances, (str, bytes)) or not isinstance(resistances, Iterable):
        raise TypeError("resistances must be a non-empty iterable of numeric values")

    values = list(resistances)
    if not values:
        raise ValueError("resistances must not be empty")

    for index, value in enumerate(values):
        _validate_finite_real(value, f"resistance at index {index}")
        if value < 0:
            raise ValueError(f"resistance at index {index} must be non-negative")

    # Preserve native sums where their arithmetic is compatible. Decimal mixed
    # with floats or Fractions follows the same float policy as other formulas.
    native = (all(isinstance(value, Rational) for value in values)
              or all(isinstance(value, (Decimal, Integral)) for value in values))
    try:
        if native:
            result = sum(values)
        else:
            result = math.fsum(_finite_real_float(value, f"resistance at index {index}")
                               for index, value in enumerate(values))
    except (OverflowError, DecimalException) as error:
        raise ValueError("total series resistance must be finite within the numeric context") from error
    _validate_finite_real(result, "total series resistance")
    if result == 0 and any(value != 0 for value in values):
        raise ValueError("total series resistance must be representable as a nonzero number")
    return result


def parallel_resistance(resistances):
    """Return equivalent resistance and short-circuit status for parallel branches.

    Values must be finite, non-negative reals representable as floats without
    losing a nonzero value to zero. A positive equivalent must remain nonzero.
    A zero-ohm branch short-circuits the parallel network, so the equivalent
    resistance is zero and ``has_short_circuit`` is true.
    """
    values = _validated_resistances(resistances)
    if any(value == 0 for value in values):
        return ParallelResistanceResult(0.0, True)

    smallest = min(values)
    # At least one weight is 1; reciprocals never need to be represented.
    total_weight = math.fsum(smallest / value for value in values)
    equivalent = smallest / total_weight
    if equivalent == 0:
        raise ValueError("equivalent resistance must be representable as a nonzero number")
    return ParallelResistanceResult(equivalent, False)


def calculate_ohms_law(*, voltage=_UNSET, current=_UNSET, resistance=_UNSET, solve_for):
    """Calculate one missing Ohm's law value from the other two.

    ``solve_for`` must be ``"voltage"``, ``"current"``, or ``"resistance"``.
    Supply exactly the other two values. Voltage and current may be signed;
    resistance must be non-negative. Values must be finite real numbers.
    Float conversion and results reject overflow and nonzero underflow to zero.
    """
    variables = {
        "voltage": voltage,
        "current": current,
        "resistance": resistance,
    }
    if solve_for not in variables:
        raise ValueError("solve_for must be 'voltage', 'current', or 'resistance'")

    supplied = {name for name, value in variables.items() if value is not _UNSET}
    if solve_for in supplied or len(supplied) != 2:
        raise ValueError("provide exactly two values, leaving solve_for unset")

    known = _validated_known_values(variables, supplied)
    if solve_for == "voltage":
        result = known["current"] * known["resistance"]
    elif solve_for == "current":
        if known["resistance"] == 0:
            raise ValueError("current is undefined when resistance is zero")
        result = known["voltage"] / known["resistance"]
    else:
        if known["current"] == 0:
            raise ValueError("resistance is undefined when current is zero")
        result = known["voltage"] / known["current"]
        if result < 0:
            raise ValueError("voltage and current imply a negative resistance")

    if not math.isfinite(result):
        raise ValueError(f"calculated {solve_for} must be finite")
    # With valid nonzero denominators, a nonzero result is expected exactly
    # when both supplied operands are nonzero.
    if result == 0 and all(value != 0 for value in known.values()):
        raise ValueError(f"calculated {solve_for} must be representable as a nonzero number")
    return result


def calculate_power(*, voltage=_UNSET, current=_UNSET, resistance=_UNSET):
    """Calculate electrical power from any two of voltage, current, and resistance.

    Uses ``P = V * I``, ``P = I**2 * R``, or ``P = V**2 / R``. Supply exactly
    two finite real values. Voltage and current may be signed; resistance must
    be non-negative. Power calculated from voltage and zero resistance is
    undefined and raises ``ValueError``.
    Inputs normalize to floats; exact intermediate arithmetic avoids premature
    square overflow/underflow. Unrepresentable final results raise ValueError.
    """
    variables = {
        "voltage": voltage,
        "current": current,
        "resistance": resistance,
    }
    supplied = {name for name, value in variables.items() if value is not _UNSET}
    if len(supplied) != 2:
        raise ValueError("provide exactly two of voltage, current, and resistance")

    known = _validated_known_values(variables, supplied)
    # Exact arithmetic on at most three normalized float operands avoids
    # intermediate square overflow/underflow; round only the final result.
    exact = {name: Fraction(value) for name, value in known.items()}
    if "voltage" in exact and "current" in exact:
        power = exact["voltage"] * exact["current"]
    elif "current" in exact and "resistance" in exact:
        power = exact["current"] ** 2 * exact["resistance"]
    else:
        if exact["resistance"] == 0:
            raise ValueError("power is undefined when resistance is zero")
        power = exact["voltage"] ** 2 / exact["resistance"]
    return _finite_real_float(power, "calculated power")


def _validated_known_values(variables, supplied):
    """Normalize supplied V/I/R operands with a consistent resistance domain."""
    known = {}
    for name, value in variables.items():
        if name in supplied:
            known[name] = _finite_real_float(value, name)
            if name == "resistance" and known[name] < 0:
                raise ValueError("resistance must be non-negative")
    return known


def _validate_finite_real(value, name):
    """Check numeric type and finiteness without narrowing native numeric range."""
    if isinstance(value, bool) or not (isinstance(value, Number) or isinstance(value, Decimal)):
        raise TypeError(f"{name} must be a real numeric value")
    if isinstance(value, complex):
        raise TypeError(f"{name} must be a real numeric value")
    if isinstance(value, Decimal):
        finite = value.is_finite()
    elif isinstance(value, Rational):
        finite = True
    else:
        try:
            finite = math.isfinite(value)
        except (TypeError, ValueError, OverflowError):
            finite = False
    if not finite:
        raise ValueError(f"{name} must be finite")


def _finite_real_float(value, name):
    """Validate a finite real numeric value and convert it to a usable float."""
    _validate_finite_real(value, name)
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be representable as a finite number") from error
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be representable as a finite number")
    if converted == 0 and value != 0:
        raise ValueError(f"{name} must be representable as a nonzero number")
    return converted


def _validated_resistances(resistances):
    """Return a validated list of non-negative resistance values as floats."""
    if isinstance(resistances, (str, bytes)) or not isinstance(resistances, Iterable):
        raise TypeError("resistances must be a non-empty iterable of numeric values")

    values = list(resistances)
    if not values:
        raise ValueError("resistances must not be empty")

    validated = []
    for index, value in enumerate(values):
        resistance = _finite_real_float(value, f"resistance at index {index}")
        if resistance < 0:
            raise ValueError(f"resistance at index {index} must be non-negative")
        validated.append(resistance)
    return validated


def _validated_target_index(target_index, item_count):
    """Validate a zero-based target index and return it as a built-in int."""
    if isinstance(target_index, bool) or not isinstance(target_index, Integral):
        raise TypeError("target_index must be an integer")
    target_index = int(target_index)
    if target_index < 0 or target_index >= item_count:
        raise ValueError(f"target_index must be between 0 and {item_count - 1}")
    return target_index


def calculate_voltage_divider(input_voltage, resistances, target_index):
    """Calculate the voltage drop across one resistor in an ideal series divider.

    ``target_index`` is zero-based. The input voltage may be signed; all
    resistances must be finite, real, and non-negative. A zero total series
    resistance has no defined divider ratio and raises ``ValueError``.
    """
    voltage = _finite_real_float(input_voltage, "input_voltage")
    values = _validated_resistances(resistances)
    target_index = _validated_target_index(target_index, len(values))

    try:
        total_resistance = math.fsum(values)
    except OverflowError as error:
        raise ValueError("total series resistance must be finite") from error
    if not math.isfinite(total_resistance):
        raise ValueError("total series resistance must be finite")
    if total_resistance == 0:
        raise ValueError("voltage division is undefined when total resistance is zero")

    voltage_drop = voltage * (values[target_index] / total_resistance)
    if not math.isfinite(voltage_drop):
        raise ValueError("calculated voltage drop must be finite")
    return voltage_drop


def calculate_current_divider(input_current, resistances, target_index):
    """Calculate current through one branch of an ideal parallel network.

    ``target_index`` is zero-based. If one branch is shorted, it carries all
    supplied current and positive-resistance branches carry none. Multiple
    zero-ohm branches have no uniquely determined current split if a shorted
    branch is selected; an all-zero network is always undefined. For networks
    with positive resistances, scaled conductances avoid overflowing while
    taking reciprocals of very small resistances.
    """
    current = _finite_real_float(input_current, "input_current")
    values = _validated_resistances(resistances)
    target_index = _validated_target_index(target_index, len(values))

    zero_count = sum(resistance == 0 for resistance in values)
    if zero_count == len(values):
        raise ValueError("current division is undefined when all branch resistances are zero")
    if zero_count:
        if values[target_index] > 0:
            return 0.0
        if zero_count > 1:
            raise ValueError("current is undefined across multiple zero-ohm branches")
        return current

    # Scale conductances by the smallest resistance so every weight is <= 1.
    smallest_resistance = min(values)
    weights = [smallest_resistance / resistance for resistance in values]
    total_weight = math.fsum(weights)
    branch_current = current * (weights[target_index] / total_weight)
    if not math.isfinite(branch_current):
        raise ValueError("calculated branch current must be finite")
    return branch_current
