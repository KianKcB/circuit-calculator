"""Read-only two-point measurements from an accepted DC result. Never solves."""

import math

from .dc import DCResult
from .quantities import format_quantity
from .schematic import Schematic


def voltage_between(state, first, second, result):
    """Return V(first) - V(second). Caller guarantees result revision is current."""
    if type(state) is not Schematic or type(result) is not DCResult:
        raise TypeError('Expected a Schematic and current DCResult')
    for endpoint in (first, second):
        if not isinstance(endpoint, str) or endpoint not in state.document.circuit.nodes:
            raise ValueError('Choose two existing junctions or component terminals')
    nets = state.net_names()
    try:
        a, b = (result.node_voltages[nets[n]] for n in (first, second))
    except KeyError:
        raise ValueError('No current voltage for the selected endpoints') from None
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError('Endpoint voltage is outside the finite numeric range')
    difference = a - b
    if not math.isfinite(difference):
        raise ValueError('Voltage difference is outside the finite numeric range')
    return difference


def probe_text(state, first, second, result=None, *, solving=False):
    """Format a transient probe; no inferred currents or saved measurements."""
    if type(state) is not Schematic:
        raise TypeError('Expected a Schematic')
    if result is not None and type(result) is not DCResult:
        raise TypeError('Expected a current DCResult or None')
    if type(solving) is not bool:
        raise TypeError('solving must be a bool')
    if any(not isinstance(n, str) or n not in state.document.circuit.nodes for n in (first, second)):
        return 'Choose endpoint A and endpoint B. The probe measures V(A) − V(B).'
    lines = [f'A (+): {state.endpoint_label(first)}', f'B (−): {state.endpoint_label(second)}',
             '', 'Polarity: V(A) − V(B)', '']
    if result is None:
        lines.append('Solving DC… No current result yet.' if solving else
                     'No current DC result. Run Simulate DC (F5).')
    else:
        try:
            value = voltage_between(state, first, second, result)
        except ValueError as error:
            lines.append(str(error))
        else:
            lines.append('Voltage difference: ' + format_quantity(value, 'V', significant=9))
    return '\n'.join(lines)
