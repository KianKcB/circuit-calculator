"""Pure node/component labels from current accepted DC results; never solves."""

from .dc import DCResult
from .quantities import format_quantity
from .schematic import Schematic, terminals


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


def component_annotations(state, result=None):
    """Return exact component name -> oriented current/power display text."""
    if type(state) is not Schematic:
        raise TypeError('Expected a Schematic')
    if result is not None and type(result) is not DCResult:
        raise TypeError('Expected a current DCResult or None')
    if result is None:
        return {}
    labels = {}
    for element in state.document.circuit.elements:
        branch = result.elements.get(element.name)
        if branch is None:
            continue
        first, second = (state.endpoint_label(n) for n in terminals(element))
        current = format_quantity(branch.current_amperes, 'A', significant=9)
        power = format_quantity(branch.power_watts, 'W', significant=9)
        kind = 'absorbed' if branch.power_watts > 0 else 'delivered' if branch.power_watts < 0 else 'zero'
        labels[element.name] = f'I: {current}\n+I: {first} → {second}\nP: {power} ({kind})'
    return labels
