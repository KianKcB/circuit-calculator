"""Strict versioned JSON persistence; see CIRCUIT_FORMAT.md for the contract."""

from dataclasses import dataclass
from decimal import Decimal

from ._document_io import (string_field, object_fields, loads_json, dumps_json,
                           read_utf8, atomic_write)

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource

MAX_BYTES = 1_048_576
MAX_DEPTH = 16
MAX_NODES = 10_000
MAX_ELEMENTS = 20_000
MAX_NAME_LENGTH = 256


class CircuitFormatError(ValueError):
    """Malformed, unsupported or unrepresentable native circuit document."""


def _string(value, field, limit):
    return string_field(value, field, limit, CircuitFormatError)


@dataclass(frozen=True)
class CircuitDocument:
    circuit: Circuit
    title: str = ''
    description: str = ''

    def __post_init__(self):
        if type(self.circuit) is not Circuit:
            raise TypeError('circuit must be a Circuit (subclasses are not serialized)')
        _string(self.title, 'metadata.title', 256)
        _string(self.description, 'metadata.description', 4096)


_ELEMENTS = {
    'resistor': (Resistor, ('name', 'node_a', 'node_b', 'resistance_ohms')),
    'voltage_source': (VoltageSource, ('name', 'plus_node', 'minus_node', 'voltage_volts')),
    'current_source': (CurrentSource, ('name', 'from_node', 'to_node', 'current_amperes')),
}


def _fields(value, expected, field):
    object_fields(value, expected, field, CircuitFormatError)


def document_from_data(data):
    """Validate native v1 JSON data (also used inside schematic projects)."""
    _fields(data, ('format', 'version', 'metadata', 'circuit'), 'document')
    if data['format'] != 'circuit-calculator':
        raise CircuitFormatError('document.format must be circuit-calculator')
    if type(data['version']) is not int or data['version'] != 1:
        raise CircuitFormatError('document.version must be the supported integer 1')
    metadata = data['metadata']
    _fields(metadata, ('title', 'description'), 'metadata')
    _string(metadata['title'], 'metadata.title', 256)
    _string(metadata['description'], 'metadata.description', 4096)
    network = data['circuit']
    _fields(network, ('nodes', 'elements', 'reference_node'), 'circuit')
    nodes = network['nodes']
    elements = network['elements']
    if not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES:
        raise CircuitFormatError(f'circuit.nodes must be an array of 1 to {MAX_NODES} names')
    if not isinstance(elements, list) or len(elements) > MAX_ELEMENTS:
        raise CircuitFormatError(f'circuit.elements must be an array of at most {MAX_ELEMENTS} elements')
    for index, node in enumerate(nodes):
        _string(node, f'circuit.nodes[{index}]', MAX_NAME_LENGTH)
    reference = network['reference_node']
    if reference is not None:
        _string(reference, 'circuit.reference_node', MAX_NAME_LENGTH)
    parsed = []
    for index, element in enumerate(elements):
        field = f'circuit.elements[{index}]'
        if not isinstance(element, dict):
            raise CircuitFormatError(f'{field} must be an object')
        kind = element.get('type')
        if not isinstance(kind, str) or kind not in _ELEMENTS:
            raise CircuitFormatError(f'{field}.type is unsupported; expected {list(_ELEMENTS)}')
        constructor, fields = _ELEMENTS[kind]
        _fields(element, ('type', *fields), field)
        for name in fields[:-1]:
            _string(element[name], f'{field}.{name}', MAX_NAME_LENGTH)
        number = element[fields[-1]]
        if isinstance(number, bool) or not isinstance(number, (int, float, Decimal)):
            raise CircuitFormatError(f'{field}.{fields[-1]} must be a JSON number')
        try:
            parsed.append(constructor(**{name: element[name] for name in fields}))
        except (TypeError, ValueError) as error:
            raise CircuitFormatError(f'{field}: {error}') from error
    try:
        circuit = Circuit(nodes, parsed, reference)
    except (TypeError, ValueError) as error:
        raise CircuitFormatError(f'circuit: {error}') from error
    return CircuitDocument(circuit, **metadata)


def loads_document(text: str) -> CircuitDocument:
    """Load strict JSON text without evaluating expressions or resolving files."""
    return document_from_data(loads_json(text, MAX_BYTES, MAX_DEPTH, CircuitFormatError))


def document_to_data(document: CircuitDocument) -> dict:
    """Return owned, validated native v1 JSON data for export or embedding."""
    if type(document) is not CircuitDocument:
        raise TypeError('document must be a CircuitDocument')
    if len(document.circuit.nodes) > MAX_NODES or len(document.circuit.elements) > MAX_ELEMENTS:
        raise CircuitFormatError('circuit exceeds document node/element limits')
    elements = []
    for element in document.circuit.elements:
        for kind, (constructor, fields) in _ELEMENTS.items():
            if type(element) is constructor:
                elements.append({'type': kind, **{name: getattr(element, name) for name in fields}})
                break
        else:
            raise CircuitFormatError(f'unsupported element type: {type(element).__name__}')
    data = {'format': 'circuit-calculator', 'version': 1,
            'metadata': {'title': document.title, 'description': document.description},
            'circuit': {'nodes': list(document.circuit.nodes), 'elements': elements,
                        'reference_node': document.circuit.reference_node}}
    document_from_data(data)
    return data


def dumps_document(document: CircuitDocument) -> str:
    """Produce deterministic version-1 JSON, applying the same limits as loading."""
    return dumps_json(document_to_data(document), MAX_BYTES, MAX_DEPTH, CircuitFormatError)


def load_document(path) -> CircuitDocument:
    """Read a size-bounded UTF-8 local document. Filesystem errors remain OSError."""
    return loads_document(read_utf8(path, MAX_BYTES, CircuitFormatError))


def save_document(document: CircuitDocument, path, *, overwrite=False) -> None:
    """Atomically create a document; existing paths require explicit overwrite=True."""
    if type(overwrite) is not bool:
        raise TypeError('overwrite must be a bool')
    atomic_write(dumps_document(document).encode('utf-8'), path, overwrite=overwrite)
