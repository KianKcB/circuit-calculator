"""Immutable item catalog, plain-name filtering and geometry-only reveal points."""

from dataclasses import dataclass
import math

from .schematic import Schematic


@dataclass(frozen=True)
class SearchItem:
    kind: str
    name: str
    label: str

    @property
    def selection(self):
        return self.kind, self.name


def catalog_items(state):
    if type(state) is not Schematic:
        raise TypeError('Expected a Schematic')
    owners = state.terminal_owners()
    return (tuple(SearchItem('element', e.name, e.name) for e in state.document.circuit.elements) +
            tuple(SearchItem('terminal' if n in owners else 'node', n, state.endpoint_label(n))
                  for n in state.document.circuit.nodes) +
            tuple(SearchItem('wire', w.name, w.name) for w in state.wires))


def filter_items(items, query):
    if not isinstance(query, str):
        raise TypeError('Search text must be a string')
    if len(query) > 256:
        raise ValueError('Search text exceeds 256 characters')
    try:
        query.encode('utf-8')
    except UnicodeEncodeError as error:
        raise ValueError('Search text must contain valid Unicode') from error
    query = query.casefold()
    return tuple(item for item in items if query in item.name.casefold() or query in item.label.casefold())


def selection_position(state, selection):
    """Revalidate identity, then choose a world position without changing geometry."""
    if not any(item.selection == selection for item in catalog_items(state)):
        raise ValueError('Item no longer exists. Open Find item again.')
    kind, name = selection
    if kind == 'element':
        placement = state.component_placement(name)
        return placement.x, placement.y
    if kind in ('node', 'terminal'):
        point = next(p for p in state.positions if p.node == name)
        return point.x, point.y
    points = state.wire_points(name)
    lengths = tuple(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
    remaining = math.fsum(lengths) / 2
    if remaining == 0:
        return points[0]
    for first, second, length in zip(points, points[1:], lengths):
        if length == 0:
            continue
        if remaining <= length:
            fraction = remaining / length
            return (first[0] + fraction * (second[0] - first[0]),
                    first[1] + fraction * (second[1] - first[1]))
        remaining -= length
    return points[-1]  # finite summation can round the final subtraction
