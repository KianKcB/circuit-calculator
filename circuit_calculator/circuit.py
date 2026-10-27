"""Small, validated data structures for describing electrical circuits."""

from dataclasses import dataclass
from decimal import Decimal
import math
from numbers import Number
from typing import Iterable, Optional, Tuple, Union


def _validated_name(value, label):
    """Return a non-empty name, rejecting non-string and whitespace-only values."""
    if not isinstance(value, str):
        raise TypeError("{} must be a string".format(label))
    if not value.strip():
        raise ValueError("{} must not be empty".format(label))
    return value


def _validated_finite_real(value, label, strictly_positive=False):
    """Validate a finite real number and normalize it to a built-in float."""
    if isinstance(value, bool) or not (
        isinstance(value, Number) or isinstance(value, Decimal)
    ) or isinstance(value, complex):
        raise TypeError("{} must be a real numeric value".format(label))

    try:
        finite = value.is_finite() if isinstance(value, Decimal) else math.isfinite(value)
    except (TypeError, ValueError, OverflowError):
        finite = False
    if not finite:
        raise ValueError("{} must be finite".format(label))

    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("{} must be representable as a finite number".format(label)) from error
    if not math.isfinite(result):
        raise ValueError("{} must be representable as a finite number".format(label))
    if result == 0 and value != 0:
        raise ValueError("{} must be representable as a nonzero number".format(label))
    if strictly_positive and result <= 0:
        raise ValueError("{} must be strictly positive".format(label))
    return result


@dataclass(frozen=True)
class Resistor:
    """A resistor between two distinct circuit nodes, with resistance in ohms."""

    name: str
    node_a: str
    node_b: str
    resistance_ohms: float

    def __post_init__(self):
        _validated_name(self.name, "element name")
        _validated_name(self.node_a, "node_a")
        _validated_name(self.node_b, "node_b")
        if self.node_a == self.node_b:
            raise ValueError("a two-terminal element must connect two distinct nodes")
        object.__setattr__(
            self,
            "resistance_ohms",
            _validated_finite_real(self.resistance_ohms, "resistance_ohms", True),
        )


@dataclass(frozen=True)
class VoltageSource:
    """Ideal voltage source in volts: V(plus_node) - V(minus_node) = voltage_volts."""

    name: str
    plus_node: str
    minus_node: str
    voltage_volts: float

    def __post_init__(self):
        _validated_name(self.name, "element name")
        _validated_name(self.plus_node, "plus_node")
        _validated_name(self.minus_node, "minus_node")
        if self.plus_node == self.minus_node:
            raise ValueError("a two-terminal element must connect two distinct nodes")
        object.__setattr__(
            self, "voltage_volts", _validated_finite_real(self.voltage_volts, "voltage_volts")
        )


@dataclass(frozen=True)
class CurrentSource:
    """Ideal current source in amperes; positive current flows from from_node to to_node."""

    name: str
    from_node: str
    to_node: str
    current_amperes: float

    def __post_init__(self):
        _validated_name(self.name, "element name")
        _validated_name(self.from_node, "from_node")
        _validated_name(self.to_node, "to_node")
        if self.from_node == self.to_node:
            raise ValueError("a two-terminal element must connect two distinct nodes")
        object.__setattr__(
            self,
            "current_amperes",
            _validated_finite_real(self.current_amperes, "current_amperes"),
        )


Element = Union[Resistor, VoltageSource, CurrentSource]


@dataclass(frozen=True)
class Circuit:
    """Declared nodes, connected elements, and an optional reference node.

    ``nodes`` and ``elements`` accept iterables and are stored as immutable
    tuples. Element names must be unique, and every endpoint must be declared.
    A reference node, when supplied, is simply the node whose voltage is zero.
    """

    nodes: Tuple[str, ...]
    elements: Tuple[Element, ...]
    reference_node: Optional[str] = None

    def __post_init__(self):
        if isinstance(self.nodes, (str, bytes)):
            raise TypeError("nodes must be an iterable of names, not a string")
        try:
            nodes = tuple(self.nodes)
        except TypeError as error:
            raise TypeError("nodes must be an iterable of names") from error
        if not nodes:
            raise ValueError("circuit must declare at least one node")
        for node in nodes:
            _validated_name(node, "node name")
        if len(set(nodes)) != len(nodes):
            raise ValueError("node names must be unique")

        if isinstance(self.elements, (str, bytes)):
            raise TypeError("elements must be an iterable of circuit elements, not a string")
        try:
            elements = tuple(self.elements)
        except TypeError as error:
            raise TypeError("elements must be an iterable of circuit elements") from error

        declared_nodes = set(nodes)
        element_names = set()
        for element in elements:
            if not isinstance(element, (Resistor, VoltageSource, CurrentSource)):
                raise TypeError("elements must be Resistor, VoltageSource, or CurrentSource values")
            if element.name in element_names:
                raise ValueError("element names must be unique")
            element_names.add(element.name)

            if isinstance(element, Resistor):
                endpoints = (element.node_a, element.node_b)
            elif isinstance(element, VoltageSource):
                endpoints = (element.plus_node, element.minus_node)
            else:
                endpoints = (element.from_node, element.to_node)
            for endpoint in endpoints:
                if endpoint not in declared_nodes:
                    raise ValueError("element '{}' references undeclared node '{}'".format(
                        element.name, endpoint
                    ))

        if self.reference_node is not None:
            _validated_name(self.reference_node, "reference_node")
            if self.reference_node not in declared_nodes:
                raise ValueError("reference_node must be one of the declared nodes")

        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "elements", elements)
