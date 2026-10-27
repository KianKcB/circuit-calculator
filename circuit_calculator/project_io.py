"""Strict schematic-project v1 persistence; see docs/SCHEMATIC_FORMAT.md."""

from dataclasses import dataclass, field
from decimal import Decimal
import math

from ._document_io import (string_field, object_fields, loads_json, dumps_json,
                           read_utf8, atomic_write)
from .circuit_io import document_from_data, document_to_data, CircuitFormatError
from .schematic import Schematic, Position, Wire, MAX_NODES, MAX_ELEMENTS, MAX_WIRES

MAX_BYTES = 1_048_576
MAX_DEPTH = 16


class ProjectFormatError(ValueError):
    """Malformed, unsupported or unrepresentable schematic project."""


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ProjectFormatError(f'{label} must be a JSON number')
    try:
        result = float(value)
    except (ValueError, OverflowError) as error:
        raise ProjectFormatError(f'{label} must be a finite representable number') from error
    if not math.isfinite(result):
        raise ProjectFormatError(f'{label} must be finite')
    if result == 0 and value != 0:
        raise ProjectFormatError(f'{label} must be representable as a nonzero number')
    return result


def _fields(value, expected, label):
    object_fields(value, expected, label, ProjectFormatError)


def _name(value, label):
    return string_field(value, label, 256, ProjectFormatError)


@dataclass(frozen=True)
class ViewState:
    zoom: float = 1.0
    scroll_x: float = 0.0
    scroll_y: float = 0.0

    def __post_init__(self):
        for name, low, high in (('zoom', .4, 2.5), ('scroll_x', 0, 1), ('scroll_y', 0, 1)):
            value = _number(getattr(self, name), 'view.' + name)
            if not low <= value <= high:
                raise ProjectFormatError(f'view.{name} must be between {low} and {high}')
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class SchematicProject:
    schematic: Schematic
    view: ViewState = field(default_factory=ViewState)

    def __post_init__(self):
        if type(self.schematic) is not Schematic or type(self.view) is not ViewState:
            raise TypeError('project requires a Schematic and ViewState')


def _from_data(data):
    _fields(data, ('format', 'version', 'document', 'layout', 'view'), 'project')
    if data['format'] != 'circuit-calculator-project':
        raise ProjectFormatError('project.format must be circuit-calculator-project; use Import Circuit for electrical documents')
    if type(data['version']) is not int or data['version'] != 1:
        raise ProjectFormatError('project.version must be the supported integer 1')
    try:
        document = document_from_data(data['document'])
    except (CircuitFormatError, TypeError) as error:
        raise ProjectFormatError(f'project.document: {error}') from error
    if len(document.circuit.nodes) > MAX_NODES or len(document.circuit.elements) > MAX_ELEMENTS:
        raise ProjectFormatError('project exceeds editor junction/component limits')
    layout = data['layout']
    _fields(layout, ('positions', 'wires'), 'layout')
    positions, wires = layout['positions'], layout['wires']
    if not isinstance(positions, list) or len(positions) != len(document.circuit.nodes):
        raise ProjectFormatError('layout.positions must contain exactly one position per junction')
    if not isinstance(wires, list) or len(wires) > MAX_WIRES:
        raise ProjectFormatError(f'layout.wires must be an array of at most {MAX_WIRES} wires')
    parsed_positions, parsed_wires = [], []
    for index, position in enumerate(positions):
        label = f'layout.positions[{index}]'
        _fields(position, ('node', 'x', 'y'), label)
        _name(position['node'], label + '.node')
        try:
            parsed_positions.append(Position(position['node'], _number(position['x'], label + '.x'),
                                             _number(position['y'], label + '.y')))
        except (ValueError, TypeError) as error:
            raise ProjectFormatError(f'{label}: {error}') from error
    for index, wire in enumerate(wires):
        label = f'layout.wires[{index}]'
        _fields(wire, ('name', 'first', 'second'), label)
        for name in ('name', 'first', 'second'):
            _name(wire[name], label + '.' + name)
        try:
            parsed_wires.append(Wire(**wire))
        except (ValueError, TypeError) as error:
            raise ProjectFormatError(f'{label}: {error}') from error
    _fields(data['view'], ('zoom', 'scroll_x', 'scroll_y'), 'view')
    try:
        schematic = Schematic(document, parsed_positions, parsed_wires)
        return SchematicProject(schematic, ViewState(**data['view']))
    except (ValueError, TypeError) as error:
        raise ProjectFormatError(f'project: {error}') from error


def loads_project(text: str) -> SchematicProject:
    return _from_data(loads_json(text, MAX_BYTES, MAX_DEPTH, ProjectFormatError))


def dumps_project(project: SchematicProject) -> str:
    if type(project) is not SchematicProject:
        raise TypeError('project must be a SchematicProject')
    schematic = project.schematic
    try:
        document = document_to_data(schematic.document)
    except (ValueError, TypeError) as error:
        raise ProjectFormatError(f'project.document: {error}') from error
    data = {'format': 'circuit-calculator-project', 'version': 1, 'document': document,
            'layout': {
                'positions': [{'node': p.node, 'x': _number(p.x, 'position.x'), 'y': _number(p.y, 'position.y')}
                              for p in schematic.positions],
                'wires': [{'name': w.name, 'first': w.first, 'second': w.second} for w in schematic.wires]},
            'view': {'zoom': project.view.zoom, 'scroll_x': project.view.scroll_x, 'scroll_y': project.view.scroll_y}}
    _from_data(data)
    return dumps_json(data, MAX_BYTES, MAX_DEPTH, ProjectFormatError)


def load_project(path) -> SchematicProject:
    return loads_project(read_utf8(path, MAX_BYTES, ProjectFormatError))


def save_project(project: SchematicProject, path, *, overwrite=False) -> None:
    if type(overwrite) is not bool:
        raise TypeError('overwrite must be a bool')
    atomic_write(dumps_project(project).encode('utf-8'), path, overwrite=overwrite)
