"""Read-only selection text for current accepted editor results; never solves."""

from .circuit import Resistor, VoltageSource, CurrentSource
from .dc import DCResult
from .quantities import format_quantity
from .schematic import Schematic, terminals, value_of


def selection_text(state, selection, result=None, *, solving=False):
    """Caller supplies a current accepted result, not an arbitrary state/result pair."""
    if type(state) is not Schematic:
        raise TypeError('Expected a Schematic')
    if result is not None and type(result) is not DCResult:
        raise TypeError('Expected a current DCResult or None')
    if type(solving) is not bool:
        raise TypeError('solving must be a bool')
    choose = 'Select a component, junction, terminal or wire on the canvas.'
    if type(selection) is not tuple or len(selection) != 2 or not all(isinstance(v, str) for v in selection):
        return choose
    kind, name = selection
    absent = 'Selection no longer exists. ' + choose
    unavailable = 'Solving DC… No current result yet.' if solving else 'No current DC result. Run Simulate DC (F5).'
    circuit = state.document.circuit
    if kind == 'element':
        element = next((e for e in circuit.elements if e.name == name), None)
        if element is None:
            return absent
        first, second = (state.endpoint_label(n) for n in terminals(element))
        label, parameter, unit = {Resistor: ('Resistor', 'Resistance', 'ohm'),
            VoltageSource: ('Voltage source', 'Source voltage', 'V'),
            CurrentSource: ('Current source', 'Source current', 'A')}[type(element)]
        lines = [f'{label}: {name}', f'{parameter}: {format_quantity(value_of(element), unit)}', '',
                 f'Voltage convention: V({first}) - V({second})',
                 f'Positive current: {first} → {second}', '']
        branch = result.elements.get(name) if result is not None else None
        if branch is None:
            return '\n'.join([*lines, unavailable])
        power = 'absorbed' if branch.power_watts > 0 else 'delivered' if branch.power_watts < 0 else 'zero'
        return '\n'.join([*lines, 'Current DC result',
            f'Voltage: {format_quantity(branch.voltage_volts, "V", significant=9)}',
            f'Current: {format_quantity(branch.current_amperes, "A", significant=9)}',
            f'Power: {format_quantity(branch.power_watts, "W", significant=9)} ({power})'])
    if kind in ('node', 'terminal'):
        if name not in circuit.nodes:
            return absent
        owner = state.terminal_owners().get(name)
        lines = [f'{"Terminal" if owner is not None else "Junction"}: {state.endpoint_label(name)}']
        if owner is not None:
            lines.append(f'Component: {owner}')
        endpoint = name
    elif kind == 'wire':
        wire = next((w for w in state.wires if w.name == name), None)
        if wire is None:
            return absent
        lines = [f'Wire: {name}', f'Endpoints: {state.endpoint_label(wire.first)} ↔ {state.endpoint_label(wire.second)}',
                 f'Bends: {len(wire.bends)}', 'Wire current: not resolved by this DC model.']
        endpoint = wire.first
    else:
        return choose
    nets = state.net_names()
    net = nets[endpoint]
    lines += ['', f'Resolved net: {state.endpoint_label(net)}',
              f'Reference net: {"yes" if circuit.reference_node is not None and net == nets[circuit.reference_node] else "no"}', '']
    if result is None or net not in result.node_voltages:
        lines.append(unavailable)
    else:
        lines.append(f'Net voltage: {format_quantity(result.node_voltages[net], "V", significant=9)}')
    return '\n'.join(lines)
