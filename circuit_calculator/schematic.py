"""GUI-independent junction editor state and explicit wire/net resolution."""

from dataclasses import dataclass, replace
import math

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument

MAX_NODES = 100
MAX_ELEMENTS = 200
MAX_WIRES = 400


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
class Wire:
    name: str
    first: str
    second: str

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError('Wire name must be non-empty text')
        if self.first == self.second:
            raise ValueError('A wire must join distinct junctions')


@dataclass(frozen=True)
class Schematic:
    document: CircuitDocument
    positions: tuple
    wires: tuple = ()

    def __post_init__(self):
        if type(self.document) is not CircuitDocument:
            raise TypeError('Expected a CircuitDocument')
        circuit = self.document.circuit
        positions, wires = tuple(self.positions), tuple(self.wires)
        if len(circuit.nodes) > MAX_NODES or len(circuit.elements) > MAX_ELEMENTS or len(wires) > MAX_WIRES:
            raise ValueError('Editor limit: 100 junctions, 200 components, 400 wires')
        if not all(type(position) is Position for position in positions):
            raise TypeError('Positions must be Position values')
        if len(positions) != len(circuit.nodes) or {p.node for p in positions} != set(circuit.nodes):
            raise ValueError('Exactly one position is required per junction')
        for element in circuit.elements:
            terminals(element)
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

    @classmethod
    def from_document(cls, document):
        if type(document) is not CircuitDocument:
            raise TypeError('Expected a CircuitDocument')
        if len(document.circuit.nodes) > MAX_NODES or len(document.circuit.elements) > MAX_ELEMENTS:
            raise ValueError('Editor limit: 100 junctions, 200 components, 400 wires')
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

    def add_node(self, name, x, y):
        return Schematic(self._circuit(nodes=(*self.document.circuit.nodes, name)),
                         (*self.positions, Position(name, x, y)), self.wires)

    def move_node(self, name, x, y):
        if name not in self.document.circuit.nodes:
            raise ValueError('Unknown junction')
        return replace(self, positions=tuple(Position(name, x, y) if p.node == name else p
                                             for p in self.positions))

    def add_element(self, element):
        return replace(self, document=self._circuit(elements=(*self.document.circuit.elements, element)))

    def add_wire(self, wire):
        return replace(self, wires=(*self.wires, wire))

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
            if name not in circuit.nodes:
                raise ValueError('Unknown junction')
            if len(circuit.nodes) == 1:
                raise ValueError('Keep at least one junction')
            nodes = tuple(n for n in circuit.nodes if n != name)
            elements = tuple(e for e in circuit.elements if name not in terminals(e))
            reference = None if circuit.reference_node == name else circuit.reference_node
            return Schematic(self._circuit(nodes=nodes, elements=elements, reference_node=reference),
                             tuple(p for p in self.positions if p.node != name),
                             tuple(w for w in self.wires if name not in (w.first, w.second)))
        if kind == 'element' and name in {e.name for e in circuit.elements}:
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
