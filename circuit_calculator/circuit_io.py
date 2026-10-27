"""Strict versioned JSON persistence; see CIRCUIT_FORMAT.md for the contract."""

from dataclasses import dataclass
from decimal import Decimal, DecimalException
import json
import os
from pathlib import Path
import tempfile

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource

MAX_BYTES = 1_048_576
MAX_DEPTH = 16
MAX_NODES = 10_000
MAX_ELEMENTS = 20_000
MAX_NAME_LENGTH = 256


class CircuitFormatError(ValueError):
    """Malformed, unsupported or unrepresentable native circuit document."""


def _string(value, field, limit):
    if not isinstance(value, str):
        raise CircuitFormatError(f'{field} must be a string')
    if len(value) > limit:
        raise CircuitFormatError(f'{field} exceeds {limit} characters')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as error:
        raise CircuitFormatError(f'{field} must contain valid Unicode') from error
    return value


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
    if not isinstance(value, dict):
        raise CircuitFormatError(f'{field} must be an object')
    missing = set(expected) - value.keys()
    unknown = value.keys() - set(expected)
    if missing or unknown:
        raise CircuitFormatError(
            f'{field}: missing fields {sorted(missing)}; unknown fields {sorted(unknown)}')


def _document_from_data(data):
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


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CircuitFormatError(f'duplicate JSON object key: {key!r}')
        result[key] = value
    return result


def _reject_constant(value):
    raise CircuitFormatError(f'non-finite JSON number is not supported: {value}')


def _check_text(text):
    if not isinstance(text, str):
        raise TypeError('document text must be a string')
    if len(text) > MAX_BYTES:
        raise CircuitFormatError(f'document exceeds {MAX_BYTES} UTF-8 bytes')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeEncodeError as error:
        raise CircuitFormatError('document must contain valid Unicode') from error
    if size > MAX_BYTES:
        raise CircuitFormatError(f'document exceeds {MAX_BYTES} UTF-8 bytes')
    depth = 0
    quoted = escaped = False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in '[{':
            depth += 1
            if depth > MAX_DEPTH:
                raise CircuitFormatError(f'JSON nesting exceeds {MAX_DEPTH}')
        elif char in ']}':
            depth -= 1


def loads_document(text: str) -> CircuitDocument:
    """Load strict JSON text without evaluating expressions or resolving files."""
    _check_text(text)
    try:
        data = json.loads(text, object_pairs_hook=_unique_object,
                          parse_float=Decimal, parse_constant=_reject_constant)
    except json.JSONDecodeError as error:
        raise CircuitFormatError(f'invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}') from error
    except (ValueError, RecursionError, DecimalException) as error:
        if isinstance(error, CircuitFormatError):
            raise
        raise CircuitFormatError(f'invalid JSON: {error}') from error
    return _document_from_data(data)


def dumps_document(document: CircuitDocument) -> str:
    """Produce deterministic version-1 JSON, applying the same limits as loading."""
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
    _document_from_data(data)
    text = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + '\n'
    _check_text(text)
    return text


def load_document(path) -> CircuitDocument:
    """Read a size-bounded UTF-8 local document. Filesystem errors remain OSError."""
    with Path(path).open('rb') as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise CircuitFormatError(f'document exceeds {MAX_BYTES} UTF-8 bytes')
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError as error:
        raise CircuitFormatError('document file must be UTF-8') from error
    return loads_document(text)


def save_document(document: CircuitDocument, path, *, overwrite=False) -> None:
    """Atomically create a document; existing paths require explicit overwrite=True."""
    if type(overwrite) is not bool:
        raise TypeError('overwrite must be a bool')
    content = dumps_document(document).encode('utf-8')
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.circuit-',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
