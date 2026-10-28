"""GUI-independent junction editor state and explicit wire/net resolution."""

from dataclasses import dataclass, replace
from collections import Counter
import math

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument

MAX_JUNCTIONS = 100
MAX_NODES = 500
MAX_ELEMENTS = 200
MAX_WIRES = 800
MAX_BENDS = 32


def terminals(element):
    if type(element) is Resistor:
        return element.node_a, element.node_b
    if type(element) is VoltageSource:
        return element.plus_node, element.minus_node
    if type(element) is CurrentSource:
        return element.from_node, element.to_node
    raise TypeError('Unsupported editor component type')


def component(kind, name, first, second, value):
    constructors = {'resistor': Resistor, 'voltage': VoltageSource, 'current': CurrentSource}
    if kind not in constructors:
        raise ValueError('Choose resistor, voltage or current')
    return constructors[kind](name, first, second, value)


def value_of(element):
    if type(element) is Resistor:
        return element.resistance_ohms
    if type(element) is VoltageSource:
        return element.voltage_volts
    if type(element) is CurrentSource:
        return element.current_amperes
    raise TypeError('Unsupported editor component type')


@dataclass(frozen=True)
class Position:
    node: str
    x: float
    y: float

    def __post_init__(self):
        for value in (self.x, self.y):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError('Junction coordinates must be real numbers')
            if abs(value) > 100_000 or not math.isfinite(value):
                raise ValueError('Junction coordinates must be finite and within +/-100000')


@dataclass(frozen=True)
class Waypoint:
    x: float
    y: float

    def __post_init__(self):
        Position('bend', self.x, self.y)


def project_segment(x, y, first, second):
    """Nearest point and distance on a finite segment, with clamped fraction."""
    dx, dy = second[0] - first[0], second[1] - first[1]
    square = dx * dx + dy * dy
    fraction = max(0, min(1, ((x - first[0]) * dx + (y - first[1]) * dy) / square)) if square else 0
    point = (first[0] + fraction * dx, first[1] + fraction * dy)
    return point, math.hypot(x - point[0], y - point[1])


@dataclass(frozen=True)
class Wire:
    name: str
    first: str
    second: str
    bends: tuple = ()

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('Wire name must be non-empty text')
        if self.first == self.second:
            raise ValueError('A wire must join distinct junctions')
        if isinstance(self.bends, (str, bytes)):
            raise TypeError('Wire bends must be Waypoint values')
        bends = tuple(self.bends)
        if len(bends) > MAX_BENDS:
            raise ValueError('Wire limit: at most 32 bends')
        if not all(type(point) is Waypoint for point in bends):
            raise TypeError('Wire bends must be Waypoint values')
        object.__setattr__(self, 'bends', bends)


@dataclass(frozen=True)
class ComponentPlacement:
    element: str
    x: float
    y: float
    rotation: int = 0

    def __post_init__(self):
        if not isinstance(self.element, str) or not self.element.strip():
            raise ValueError('Placement element must be non-empty text')
        Position(self.element, self.x, self.y)
        if type(self.rotation) is not int or self.rotation not in (0, 90, 180, 270):
            raise ValueError('Rotation must be an integer 0, 90, 180 or 270')

    def terminal_coordinates(self):
        dx, dy = {0: (60, 0), 90: (0, 60), 180: (-60, 0), 270: (0, -60)}[self.rotation]
        return ((self.x - dx, self.y - dy), (self.x + dx, self.y + dy))


def _next_id(prefix, used):
    index = 1
    while f'{prefix}{index}' in used:
        index += 1
    return f'{prefix}{index}'


@dataclass(frozen=True)
class Schematic:
    document: CircuitDocument
    positions: tuple
    wires: tuple = ()
    placements: tuple = ()

    def __post_init__(self):
        if type(self.document) is not CircuitDocument:
            raise TypeError('Expected a CircuitDocument')
        circuit = self.document.circuit
        positions, wires, placements = tuple(self.positions), tuple(self.wires), tuple(self.placements)
        if len(circuit.nodes) > MAX_NODES or len(circuit.elements) > MAX_ELEMENTS or len(wires) > MAX_WIRES:
            raise ValueError('Editor limit: 500 total nodes, 200 components, 800 wires')
        if not all(type(position) is Position for position in positions):
            raise TypeError('Positions must be Position values')
        if len(positions) != len(circuit.nodes) or {p.node for p in positions} != set(circuit.nodes):
            raise ValueError('Exactly one position is required per junction')
        for element in circuit.elements:
            terminals(element)
        elements = {e.name: e for e in circuit.elements}
        uses = Counter(node for e in circuit.elements for node in terminals(e))
        position_map = {p.node: (p.x, p.y) for p in positions}
        placed_names, owned = set(), set()
        for placement in placements:
            if type(placement) is not ComponentPlacement:
                raise TypeError('Placements must be ComponentPlacement values')
            if placement.element not in elements or placement.element in placed_names:
                raise ValueError('Placements require unique existing component names')
            placed_names.add(placement.element)
            for node, coordinates in zip(terminals(elements[placement.element]), placement.terminal_coordinates()):
                if uses[node] != 1:
                    raise ValueError('Placed components require dedicated, unshared terminal nodes')
                if position_map[node] != coordinates:
                    raise ValueError('Terminal positions must agree with component placement geometry')
                owned.add(node)
        if len(circuit.nodes) - len(owned) > MAX_JUNCTIONS:
            raise ValueError('Editor limit: 100 free junctions')
        names, pairs = set(), set()
        for wire in wires:
            if type(wire) is not Wire:
                raise TypeError('Wires must be Wire values')
            if wire.name in names or frozenset((wire.first, wire.second)) in pairs:
                raise ValueError('Wire names and endpoint pairs must be unique')
            if wire.first not in circuit.nodes or wire.second not in circuit.nodes:
                raise ValueError('Wire endpoints must be declared junctions')
            names.add(wire.name)
            pairs.add(frozenset((wire.first, wire.second)))
        object.__setattr__(self, 'positions', positions)
        object.__setattr__(self, 'wires', wires)
        object.__setattr__(self, 'placements', placements)

    @classmethod
    def from_document(cls, document):
        if type(document) is not CircuitDocument:
            raise TypeError('Expected a CircuitDocument')
        if len(document.circuit.nodes) > MAX_JUNCTIONS or len(document.circuit.elements) > MAX_ELEMENTS:
            raise ValueError('Editor limit: 100 imported junctions, 200 components')
        return cls(document, tuple(Position(node, 140 + (i % 4) * 200, 140 + (i // 4) * 160)
                                   for i, node in enumerate(document.circuit.nodes)))

    def net_names(self):
        nodes = self.document.circuit.nodes
        parents = dict.fromkeys(nodes)
        for node in nodes:
            parents[node] = node

        def find(node):
            while parents[node] != node:
                parents[node] = parents[parents[node]]
                node = parents[node]
            return node

        for wire in self.wires:
            parents[find(wire.second)] = find(wire.first)
        first_names = {}
        result = {}
        for node in nodes:
            root = find(node)
            result[node] = first_names.setdefault(root, node)
        return result

    def compile(self):
        circuit = self.document.circuit
        mapping = self.net_names()
        elements = []
        for element in circuit.elements:
            first, second = (mapping[node] for node in terminals(element))
            if first == second:
                raise ValueError(f'Wire shorts both terminals of {element.name}; remove the wire or component')
            elements.append(type(element)(element.name, first, second, value_of(element)))
        reference = mapping[circuit.reference_node] if circuit.reference_node is not None else None
        resolved = Circuit(tuple(dict.fromkeys(mapping.values())), elements, reference)
        return replace(self.document, circuit=resolved)

    def _circuit(self, **changes):
        return replace(self.document, circuit=replace(self.document.circuit, **changes))

    def terminal_owners(self):
        elements = {e.name: e for e in self.document.circuit.elements}
        return {node: p.element for p in self.placements for node in terminals(elements[p.element])}

    def endpoint_label(self, node):
        owner = self.terminal_owners().get(node)
        if owner is None:
            return node
        element = next(e for e in self.document.circuit.elements if e.name == owner)
        labels = ('a', 'b') if type(element) is Resistor else ('+', '−') if type(element) is VoltageSource else ('from', 'to')
        return f'{owner}.{labels[terminals(element).index(node)]}'

    def component_placement(self, name):
        for placement in self.placements:
            if placement.element == name:
                return placement
        positions = {p.node: p for p in self.positions}
        pairs = Counter()
        for element in self.document.circuit.elements:
            a, b = terminals(element)
            pair = frozenset((a, b))
            index = pairs[pair]
            pairs[pair] += 1
            if element.name == name:
                first, second = positions[a], positions[b]
                dx, dy = second.x - first.x, second.y - first.y
                length = math.hypot(dx, dy)
                ux, uy = (dx / length, dy / length) if length else (1, 0)
                return ComponentPlacement(name, (first.x + second.x) / 2 - uy * index * 48,
                    (first.y + second.y) / 2 + ux * index * 48,
                    (int(round(math.degrees(math.atan2(uy, ux)) / 90)) * 90) % 360)
        raise ValueError('Select an existing component')

    def add_placed_component(self, kind, name, x, y, value, rotation=0):
        nodes = self.document.circuit.nodes
        first = _next_id('terminal_', nodes)
        second = _next_id('terminal_', (*nodes, first))
        element = component(kind, name, first, second, value)
        placement = ComponentPlacement(name, x, y, rotation)
        points = tuple(Position(node, *coordinates) for node, coordinates in
                       zip((first, second), placement.terminal_coordinates()))
        return Schematic(self._circuit(nodes=(*nodes, first, second),
                         elements=(*self.document.circuit.elements, element)),
                         (*self.positions, *points), self.wires, (*self.placements, placement))

    def place_component(self, name, x, y, rotation):
        existing = next((e for e in self.document.circuit.elements if e.name == name), None)
        if existing is None:
            raise ValueError('Select an existing component')
        placement = ComponentPlacement(name, x, y, rotation)
        if name in {p.element for p in self.placements}:
            points = dict(zip(terminals(existing), placement.terminal_coordinates()))
            return replace(self,
                positions=tuple(Position(p.node, *points[p.node]) if p.node in points else p for p in self.positions),
                placements=tuple(placement if p.element == name else p for p in self.placements))
        nodes = self.document.circuit.nodes
        first = _next_id('terminal_', nodes)
        second = _next_id('terminal_', (*nodes, first))
        replacement = type(existing)(name, first, second, value_of(existing))
        wires = list(self.wires)
        for new_node, old_node in zip((first, second), terminals(existing)):
            wires.append(Wire(_next_id('W', {w.name for w in wires}), new_node, old_node))
        points = tuple(Position(node, *coordinates) for node, coordinates in
                       zip((first, second), placement.terminal_coordinates()))
        return Schematic(self._circuit(nodes=(*nodes, first, second),
                         elements=tuple(replacement if e.name == name else e for e in self.document.circuit.elements)),
                         (*self.positions, *points), tuple(wires), (*self.placements, placement))

    def move_component(self, name, x, y):
        return self.place_component(name, x, y, self.component_placement(name).rotation)

    def rotate_component(self, name):
        placement = self.component_placement(name)
        return self.place_component(name, placement.x, placement.y, (placement.rotation + 90) % 360)

    def add_node(self, name, x, y):
        return Schematic(self._circuit(nodes=(*self.document.circuit.nodes, name)),
                         (*self.positions, Position(name, x, y)), self.wires, self.placements)

    def move_node(self, name, x, y):
        if name in self.terminal_owners():
            raise ValueError('Move the component body; its terminals cannot move independently')
        if name not in self.document.circuit.nodes:
            raise ValueError('Unknown junction')
        return replace(self, positions=tuple(Position(name, x, y) if p.node == name else p
                                             for p in self.positions))

    def add_element(self, element):
        return replace(self, document=self._circuit(elements=(*self.document.circuit.elements, element)))

    def add_wire(self, wire):
        return replace(self, wires=(*self.wires, wire))

    def _wire(self, name):
        wire = next((w for w in self.wires if w.name == name), None)
        if wire is None:
            raise ValueError('Select an existing wire')
        return wire

    def wire_points(self, name):
        wire = self._wire(name)
        positions = {p.node: (p.x, p.y) for p in self.positions}
        return (positions[wire.first], *((p.x, p.y) for p in wire.bends), positions[wire.second])

    def route_wire(self, name, bends):
        wire = replace(self._wire(name), bends=bends)
        return replace(self, wires=tuple(wire if w.name == name else w for w in self.wires))

    def nearest_wire_segment(self, name, x, y):
        Waypoint(x, y)
        points = self.wire_points(name)
        candidates = [(index, *project_segment(x, y, first, second))
                      for index, (first, second) in enumerate(zip(points, points[1:])) if first != second]
        if not candidates:
            raise ValueError('This wire has no nonzero segment to split')
        return min(candidates, key=lambda candidate: candidate[2])

    def split_wire(self, name, segment, x, y, *, junction=None):
        """Explicitly split one segment, optionally joining an existing free node."""
        wire = self._wire(name)
        point = Waypoint(x, y)
        points = self.wire_points(name)
        if type(segment) is not int or not 0 <= segment < len(points) - 1:
            raise ValueError('Choose a valid wire segment')
        first, second = points[segment:segment + 2]
        _, distance = project_segment(x, y, first, second)
        if first == second or distance > 1e-8:
            raise ValueError('Split point must lie on a nonzero wire segment')
        if (x, y) in (points[0], points[-1]):
            raise ValueError('Choose the interior of the wire; endpoints are already connected')
        state = self
        if junction is None:
            junction = _next_id('n', self.document.circuit.nodes)
            state = self.add_node(junction, x, y)
        else:
            if junction in self.terminal_owners() or junction in (wire.first, wire.second):
                raise ValueError('Choose an existing free junction inside the wire')
            existing = next((p for p in self.positions if p.node == junction), None)
            if existing is None or (existing.x, existing.y) != (x, y):
                raise ValueError('Existing junction must be at the split point')
        left, right = list(wire.bends[:segment]), list(wire.bends[segment:])
        while left and left[-1] == point:
            left.pop()
        while right and right[0] == point:
            right.pop(0)
        replacement = (Wire(name, wire.first, junction, left),
                       Wire(_next_id('W', {w.name for w in self.wires}), junction, wire.second, right))
        wires = tuple(part for w in self.wires for part in (replacement if w.name == name else (w,)))
        return replace(state, wires=wires)

    def set_reference(self, name):
        return replace(self, document=self._circuit(reference_node=name))

    def change_value(self, name, value):
        if name not in {e.name for e in self.document.circuit.elements}:
            raise ValueError('Select a component to edit')
        elements = tuple(type(e)(e.name, *terminals(e), value) if e.name == name else e
                         for e in self.document.circuit.elements)
        return replace(self, document=self._circuit(elements=elements))

    def delete(self, kind, name):
        circuit = self.document.circuit
        if kind == 'node':
            if name in self.terminal_owners():
                raise ValueError('Delete the component body; its terminals cannot be deleted independently')
            if name not in circuit.nodes:
                raise ValueError('Unknown junction')
            if len(circuit.nodes) == 1:
                raise ValueError('Keep at least one junction')
            nodes = tuple(n for n in circuit.nodes if n != name)
            elements = tuple(e for e in circuit.elements if name not in terminals(e))
            reference = None if circuit.reference_node == name else circuit.reference_node
            return Schematic(self._circuit(nodes=nodes, elements=elements, reference_node=reference),
                             tuple(p for p in self.positions if p.node != name),
                             tuple(w for w in self.wires if name not in (w.first, w.second)), self.placements)
        if kind == 'element' and name in {e.name for e in circuit.elements}:
            if name in {p.element for p in self.placements}:
                removed = set(terminals(next(e for e in circuit.elements if e.name == name)))
                nodes = tuple(n for n in circuit.nodes if n not in removed)
                if not nodes:
                    raise ValueError('Add a junction before deleting the last component')
                return Schematic(self._circuit(nodes=nodes,
                    elements=tuple(e for e in circuit.elements if e.name != name),
                    reference_node=None if circuit.reference_node in removed else circuit.reference_node),
                    tuple(p for p in self.positions if p.node not in removed),
                    tuple(w for w in self.wires if not removed.intersection((w.first, w.second))),
                    tuple(p for p in self.placements if p.element != name))
            return replace(self, document=self._circuit(elements=tuple(e for e in circuit.elements if e.name != name)))
        if kind == 'wire' and name in {w.name for w in self.wires}:
            return replace(self, wires=tuple(w for w in self.wires if w.name != name))
        raise ValueError('Select a junction, component or wire to delete')


class EditorSession:
    """Bounded undo/redo history and revision-scoped simulation results."""

    def __init__(self, state):
        self.state = state
        self.revision = 0
        self.result = None
        self._undo, self._redo = [], []

    def _invalidate(self):
        self.revision += 1
        self.result = None

    def apply(self, state):
        if type(state) is not Schematic:
            raise TypeError('Expected a Schematic')
        if state == self.state:
            return
        self._undo.append(self.state)
        self._undo = self._undo[-100:]
        self._redo.clear()
        self.state = state
        self._invalidate()

    def reset(self, state):
        """Start a new document boundary without reusing a worker revision."""
        if type(state) is not Schematic:
            raise TypeError('Expected a Schematic')
        self.state = state
        self._undo.clear()
        self._redo.clear()
        self._invalidate()

    def undo(self):
        if self._undo:
            self._redo.append(self.state)
            self.state = self._undo.pop()
            self._invalidate()

    def redo(self):
        if self._redo:
            self._undo.append(self.state)
            self.state = self._redo.pop()
            self._invalidate()

    def accept_result(self, revision, result):
        if revision != self.revision:
            return False
        self.result = result
        return True


def divider_example():
    circuit = Circuit(('g', 'in', 'out', 'return'), (
        VoltageSource('V1', 'in', 'g', 12), Resistor('R1', 'in', 'out', 1000),
        Resistor('R2', 'out', 'return', 2000)), 'g')
    return Schematic(CircuitDocument(circuit, '12 V divider'),
                     (Position('g', 160, 420), Position('in', 160, 160),
                      Position('out', 500, 160), Position('return', 500, 420)),
                     (Wire('W1', 'return', 'g'),))


def placed_divider_example():
    return (divider_example().place_component('V1', 160, 290, 90)
            .place_component('R1', 330, 160, 0).place_component('R2', 500, 290, 90))
