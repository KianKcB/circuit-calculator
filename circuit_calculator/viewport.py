"""Pure pixel-bound/zoom arithmetic for the Tk view, independent of connectivity."""

import math

MIN_ZOOM, MAX_ZOOM = .4, 2.5


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f'{label} must be a real number')
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f'{label} must be finite') from error
    if not math.isfinite(result):
        raise ValueError(f'{label} must be finite')
    return result


def clamp_zoom(value):
    value = _finite(value, 'zoom')
    if value <= 0:
        raise ValueError('zoom must be positive')
    return min(MAX_ZOOM, max(MIN_ZOOM, value))


def _bounds(bounds):
    values = tuple(_finite(v, 'bounds') for v in bounds)
    if len(values) != 4 or values[2] < values[0] or values[3] < values[1]:
        raise ValueError('Bounds must be ordered left, top, right, bottom')
    if not math.isfinite(values[2] - values[0]) or not math.isfinite(values[3] - values[1]):
        raise ValueError('Bounds extent must be finite')
    return values


def _extent(value):
    value = _finite(value, 'viewport extent')
    if value <= 0:
        raise ValueError('Viewport extent must be positive')
    return value


def fit_zoom(zoom, bounds, width, height, *, padding=32):
    zoom = clamp_zoom(zoom)
    left, top, right, bottom = _bounds(bounds)
    width, height = _extent(width), _extent(height)
    padding = _finite(padding, 'padding')
    if padding < 0:
        raise ValueError('Padding must be nonnegative')
    factor = min(max(1, width - 2 * padding) / max(1, right - left),
                 max(1, height - 2 * padding) / max(1, bottom - top))
    return clamp_zoom(zoom * factor)


def scroll_region(bounds, width, height, *, padding=32):
    left, top, right, bottom = _bounds(bounds)
    width, height = _extent(width), _extent(height)
    padding = _finite(padding, 'padding')
    if padding < 0:
        raise ValueError('Padding must be nonnegative')
    edges = (left - width / 2 - padding, top - height / 2 - padding,
             right + width / 2 + padding, bottom + height / 2 + padding)
    if not all(math.isfinite(v) for v in edges):
        raise ValueError('Padded scroll region must be finite')
    return (math.floor(edges[0]), math.floor(edges[1]), math.ceil(edges[2]), math.ceil(edges[3]))


def scroll_fraction(center, low, high, extent):
    center, low, high = (_finite(value, 'scroll coordinate') for value in (center, low, high))
    extent = _extent(extent)
    if high <= low:
        raise ValueError('Scroll region must have positive extent')
    span = high - low
    if not math.isfinite(span):
        raise ValueError('Scroll region extent must be finite')
    return min(max(0, 1 - extent / span), max(0, (center - extent / 2 - low) / span))
