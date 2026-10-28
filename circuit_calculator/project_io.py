"""Strict schematic-project v1/v2/v3 loading and v3 saving."""

from dataclasses import dataclass, field
from decimal import Decimal
import math

from ._document_io import (string_field, object_fields, loads_json, dumps_json,
                           read_utf8, atomic_write)
from .circuit_io import document_from_data, document_to_data, CircuitFormatError
from .schematic import (Schematic, Position, Wire, Waypoint, ComponentPlacement,
                        MAX_NODES, MAX_JUNCTIONS, MAX_ELEMENTS, MAX_WIRES, MAX_BENDS)

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
    if type(data['version']) is not int or data['version'] not in (1, 2, 3):
        raise ProjectFormatError('project.version must be the supported integer 1, 2 or 3')
    version = data['version']
    try:
        document = document_from_data(data['document'])
    except (CircuitFormatError, TypeError) as error:
        raise ProjectFormatError(f'project.document: {error}') from error
    node_limit = MAX_JUNCTIONS if version == 1 else MAX_NODES
    if len(document.circuit.nodes) > node_limit or len(document.circuit.elements) > MAX_ELEMENTS:
        raise ProjectFormatError('project exceeds editor junction/component limits')
    layout = data['layout']
    _fields(layout, ('positions', 'wires') if version == 1 else ('positions', 'wires', 'placements'), 'layout')
    placements = layout.get('placements', [])
    if not isinstance(placements, list) or len(placements) > MAX_ELEMENTS:
        raise ProjectFormatError('layout.placements must be an array of at most 200 placements')
    if not placements and len(document.circuit.nodes) > MAX_JUNCTIONS:
        raise ProjectFormatError('project exceeds editor free-junction limit')
    positions, wires = layout['positions'], layout['wires']
    if not isinstance(positions, list) or len(positions) != len(document.circuit.nodes):
        raise ProjectFormatError('layout.positions must contain exactly one position per junction')
    wire_limit = 400 if version == 1 else MAX_WIRES
    if not isinstance(wires, list) or len(wires) > wire_limit:
        raise ProjectFormatError(f'layout.wires must be an array of at most {wire_limit} wires')
    parsed_positions, parsed_wires, parsed_placements = [], [], []
    for index, position in enumerate(positions):
        label = f'layout.positions[{index}]'
        _fields(position, ('node', 'x', 'y'), label)
        _name(position['node'], label + '.node')
        try:
            parsed_positions.append(Position(position['node'], _number(position['x'], label + '.x'),
                                             _number(position['y'], label + '.y')))
        except (ValueError, TypeError) as error:
            raise ProjectFormatError(f'{label}: {error}') from error
    for index, placement in enumerate(placements):
        label = f'layout.placements[{index}]'
        _fields(placement, ('element', 'x', 'y', 'rotation'), label)
        _name(placement['element'], label + '.element')
        try:
            parsed_placements.append(ComponentPlacement(placement['element'],
                _number(placement['x'], label + '.x'), _number(placement['y'], label + '.y'), placement['rotation']))
        except (ValueError, TypeError) as error:
            raise ProjectFormatError(f'{label}: {error}') from error
    for index, wire in enumerate(wires):
        label = f'layout.wires[{index}]'
        _fields(wire, ('name', 'first', 'second', 'bends') if version == 3 else ('name', 'first', 'second'), label)
        for name in ('name', 'first', 'second'):
            _name(wire[name], label + '.' + name)
        try:
            bends = wire.get('bends', [])
            if not isinstance(bends, list) or len(bends) > MAX_BENDS:
                raise ProjectFormatError(f'{label}.bends must be an array of at most {MAX_BENDS} bends')
            parsed_bends = []
            for index, bend in enumerate(bends):
                bend_label = f'{label}.bends[{index}]'
                _fields(bend, ('x', 'y'), bend_label)
                parsed_bends.append(Waypoint(_number(bend['x'], bend_label + '.x'),
                                             _number(bend['y'], bend_label + '.y')))
            parsed_wires.append(Wire(wire['name'], wire['first'], wire['second'], parsed_bends))
        except (ValueError, TypeError) as error:
            raise ProjectFormatError(f'{label}: {error}') from error
    _fields(data['view'], ('zoom', 'scroll_x', 'scroll_y'), 'view')
    try:
        schematic = Schematic(document, parsed_positions, parsed_wires, parsed_placements)
        return SchematicProject(schematic, ViewState(**data['view']))
    except (ValueError, TypeError) as error:
        raise ProjectFormatError(f'project: editor validation failed: {error}') from error


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
    data = {'format': 'circuit-calculator-project', 'version': 3, 'document': document,
            'layout': {
                'positions': [{'node': p.node, 'x': _number(p.x, 'position.x'), 'y': _number(p.y, 'position.y')}
                              for p in schematic.positions],
                'wires': [{'name': w.name, 'first': w.first, 'second': w.second,
                           'bends': [{'x': _number(p.x, 'bend.x'), 'y': _number(p.y, 'bend.y')} for p in w.bends]}
                          for w in schematic.wires],
                'placements': [{'element': p.element, 'x': _number(p.x, 'placement.x'),
                                'y': _number(p.y, 'placement.y'), 'rotation': p.rotation}
                               for p in schematic.placements]},
            'view': {'zoom': project.view.zoom, 'scroll_x': project.view.scroll_x, 'scroll_y': project.view.scroll_y}}
    _from_data(data)
    return dumps_json(data, MAX_BYTES, MAX_DEPTH, ProjectFormatError)


def load_project(path) -> SchematicProject:
    return loads_project(read_utf8(path, MAX_BYTES, ProjectFormatError))


def save_project(project: SchematicProject, path, *, overwrite=False) -> None:
    if type(overwrite) is not bool:
        raise TypeError('overwrite must be a bool')
    atomic_write(dumps_project(project).encode('utf-8'), path, overwrite=overwrite)
