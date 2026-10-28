"""Deterministic, full-precision SI-unit CSV export of existing DC results."""

from collections.abc import Mapping
import csv
import io
import math
from pathlib import Path

from .dc import DCResult, ElementResult
from ._document_io import atomic_write

MAX_BYTES = 8 * 1024 * 1024
HEADER = ('format_version', 'entity_type', 'identifier', 'quantity', 'value', 'unit')


def _identifier(kind, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Result identifiers must be non-empty text')
    return kind + ':' + name


def _value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError('Result values must be real numbers')
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError('Result values must be finite floats') from error
    if not math.isfinite(number):
        raise ValueError('Result values must be finite floats')
    return repr(number)


def dumps_results_csv(result):
    if type(result) is not DCResult:
        raise TypeError('result must be a DCResult')
    if not isinstance(result.node_voltages, Mapping) or not isinstance(result.elements, Mapping):
        raise TypeError('Result nodes/elements must be mappings')
    nodes = tuple(result.node_voltages.items())
    elements = tuple(result.elements.items())
    reference = _identifier('node', result.reference_node)
    node_values = {name: _value(value) for name, value in nodes}
    if result.reference_node not in node_values or float(node_values[result.reference_node]) != 0:
        raise ValueError('Result reference must be a declared zero-volt node')
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\r\n')
    writer.writerow(HEADER)
    writer.writerow((1, 'reference', reference, 'voltage', node_values[result.reference_node], 'V'))
    for name, value in nodes:
        writer.writerow((1, 'node', _identifier('node', name), 'voltage', node_values[name], 'V'))
    for name, element in elements:
        if type(element) is not ElementResult:
            raise TypeError('Result elements must be ElementResult values')
        identifier = _identifier('element', name)
        for quantity, value, unit in (('voltage', element.voltage_volts, 'V'),
                                      ('current', element.current_amperes, 'A'),
                                      ('power', element.power_watts, 'W')):
            writer.writerow((1, 'element', identifier, quantity, _value(value), unit))
    for quantity, value, unit in (('scaled_condition_number', result.scaled_condition_number, '1'),
                                  ('max_kcl_residual', result.max_kcl_residual_amperes, 'A'),
                                  ('power_balance', result.power_balance_watts, 'W')):
        writer.writerow((1, 'analysis', 'analysis', quantity, _value(value), unit))
    text = stream.getvalue()
    try:
        content = text.encode('utf-8')
    except UnicodeEncodeError as error:
        raise ValueError('Result identifiers must contain valid Unicode') from error
    if len(content) > MAX_BYTES:
        raise ValueError('Results CSV exceeds 8 MiB')
    return text


def save_results_csv(result, path, *, overwrite=False, protected_path=None):
    if type(overwrite) is not bool:
        raise TypeError('overwrite must be a bool')
    destination = Path(path)
    if protected_path is not None:
        protected = Path(protected_path)
        if destination.resolve() == protected.resolve() or (destination.exists() and protected.exists() and destination.samefile(protected)):
            raise ValueError('CSV output must differ from the protected input/project file')
    atomic_write(dumps_results_csv(result).encode('utf-8'), destination, overwrite=overwrite)
