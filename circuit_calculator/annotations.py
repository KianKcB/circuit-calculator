"""Pure node-voltage labels from current accepted DC results; never solves."""

from .dc import DCResult
from .quantities import format_quantity
from .schematic import Schematic


def node_voltage_annotations(state, result=None):
    """Return raw endpoint -> display text. Caller guarantees result is current."""
    if type(state) is not Schematic:
        raise TypeError('Expected a Schematic')
    if result is not None and type(result) is not DCResult:
        raise TypeError('Expected a current DCResult or None')
    if result is None:
        return {}
    nets = state.net_names()
    reference = nets.get(state.document.circuit.reference_node)
    labels = {}
    for endpoint, net in nets.items():
        if net in result.node_voltages:
            text = format_quantity(result.node_voltages[net], 'V', significant=9)
            labels[endpoint] = text + (' (ref)' if net == reference else '')
    return labels
