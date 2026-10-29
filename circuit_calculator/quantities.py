"""Bounded GUI engineering quantities; storage and numerical models stay in SI."""

from decimal import Decimal, DecimalException
import math
import re


_POWERS = dict(zip(('q', 'r', 'y', 'z', 'a', 'f', 'p', 'n', 'µ', 'm', '',
                    'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y', 'R', 'Q'), range(-30, 31, 3)))
_INPUT_POWERS = {**_POWERS, 'u': -6, 'μ': -6}
_SYMBOLS = {power: symbol for symbol, power in _POWERS.items()}
_UNITS = {'ohm': ('ohm', 'Ω'), 'Ω': ('ohm', 'Ω'), 'V': ('V',), 'A': ('A',), 'W': ('W',)}
_NUMBER = re.compile(r'([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)\s*(\S*)')


def _units(unit):
    if not isinstance(unit, str) or unit not in _UNITS:
        raise ValueError('Unit must be ohm, Ω, V, A or W')
    return _UNITS[unit]


def parse_quantity(text, unit):
    """Parse exact decimal/scientific input with one optional matching SI suffix."""
    aliases = _units(unit)
    if not isinstance(text, str):
        raise TypeError('Quantity must be text')
    if len(text) > 256:
        raise ValueError('Quantity exceeds 256 characters')
    matched = _NUMBER.fullmatch(text.strip())
    if matched is None:
        raise ValueError('Enter a decimal number with an optional SI prefix and matching unit')
    number, suffix = matched.groups()
    factors = {prefix + label: power for prefix, power in _INPUT_POWERS.items()
               for label in ('', *aliases)}
    if suffix not in factors:
        raise ValueError(f'Use a matching {aliases[-1]} unit and a case-sensitive SI engineering prefix (for example k, M, m, u)')
    try:
        value = Decimal(number)
        if not value.is_finite():
            raise ValueError('Quantity must be a finite decimal number')
        sign, digits, exponent = value.as_tuple()
        # Decimal multiplication/scaleb would round under the caller's context.
        value = Decimal((sign, digits, exponent + factors[suffix]))
        if not value.is_finite():
            raise ValueError('Quantity exponent is out of range')
        return value
    except DecimalException as error:
        raise ValueError('Quantity exponent is out of range') from error


def format_quantity(value, unit, *, significant=6):
    """Rounded display only; never use as an electrical serialization."""
    label = _units(unit)[-1]
    if type(significant) is not int or not 1 <= significant <= 15:
        raise ValueError('Display precision must be an integer from 1 to 15')
    if type(value) not in (int, float):
        raise TypeError('Display quantity must be a built-in real number')
    try:
        value = float(value)
    except OverflowError as error:
        raise ValueError('Display quantity must be finite') from error
    if not math.isfinite(value):
        raise ValueError('Display quantity must be finite')
    magnitude = abs(value)
    if magnitude == 0 or magnitude < 1e-30 or magnitude >= 1e33:
        return f'{value:.{significant}g} {label}'
    exponent = max(-30, min(30, math.floor(math.log10(magnitude) / 3) * 3))
    scaled = value / 10.0**exponent
    text = format(scaled, f'.{significant}g')
    if abs(float(text)) >= 1000:
        exponent += 3
        if exponent > 30:
            return f'{value:.{significant}g} {label}'
        text = format(value / 10.0**exponent, f'.{significant}g')
    return f'{text} {_SYMBOLS[exponent]}{label}'
