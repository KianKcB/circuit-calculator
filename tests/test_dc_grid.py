"""Manufactured affine-voltage grids: independent DC accuracy/conservation oracle."""

from dataclasses import replace
import importlib.util
import math
import unittest

from circuit_calculator.circuit import Circuit, Resistor, VoltageSource
from circuit_calculator.dc import assemble_dc, solve_dc


def node(row, column):
    return f'n{row}_{column}'


def potential(row, column):
    return .5 * column - .25 * row


def boundary_current(size, row, column):
    neighbors = ((row - 1, column), (row + 1, column), (row, column - 1), (row, column + 1))
    return -math.fsum((potential(row, column) - potential(r, c)) / 1000
                     for r, c in neighbors if 0 <= r < size and 0 <= c < size)


def grid_reference(size):
    if type(size) is not int or not 2 <= size <= 12:
        raise ValueError('Reference grid size must be an integer from 2 to 12')
    nodes = ('g', *(node(r, c) for r in range(size) for c in range(size)))
    elements = []
    for r in range(size):
        for c in range(size):
            if c + 1 < size:
                elements.append(Resistor(f'Rh{r}_{c}', node(r, c), node(r, c + 1), 1000))
            if r + 1 < size:
                elements.append(Resistor(f'Rv{r}_{c}', node(r, c), node(r + 1, c), 1000))
            if r in (0, size - 1) or c in (0, size - 1):
                elements.append(VoltageSource(f'V{r}_{c}', node(r, c), 'g', potential(r, c)))
    return Circuit(nodes, elements, 'g')


def verify_grid(result, size, *, shift=0.):
    """Check the affine field and independent branch/KCL/power identities."""
    circuit = grid_reference(size)
    expected = {'g': -shift, **{node(r, c): potential(r, c) - shift for r in range(size) for c in range(size)}}
    if set(result.node_voltages) != set(expected) or set(result.elements) != {e.name for e in circuit.elements}:
        raise AssertionError('Grid result has missing/extra nodes or branches')

    def close(actual, target, tolerance, label):
        if not math.isfinite(actual) or not math.isclose(actual, target, rel_tol=0, abs_tol=tolerance):
            raise AssertionError(f'{label}: expected {target!r}, got {actual!r}')

    for name, value in expected.items():
        close(result.node_voltages[name], value, 1e-10, 'grid voltage ' + name)
    currents = {name: [] for name in circuit.nodes}
    current_errors, resistor_power, source_power = [], [], []
    for element in circuit.elements:
        actual = result.elements[element.name]
        if type(element) is Resistor:
            voltage = -.5 if element.name.startswith('Rh') else .25
            current = voltage / 1000
            first, second = element.node_a, element.node_b
            resistor_power.append(actual.power_watts)
        else:
            r, c = map(int, element.name[1:].split('_'))
            voltage, current = potential(r, c), boundary_current(size, r, c)
            first, second = element.plus_node, element.minus_node
            source_power.append(actual.power_watts)
        close(actual.voltage_volts, voltage, 1e-10, 'branch voltage ' + element.name)
        close(actual.current_amperes, current, 1e-12, 'branch current ' + element.name)
        close(actual.power_watts, voltage * current, 1e-12, 'branch power ' + element.name)
        current_errors.append(abs(actual.current_amperes - current))
        currents[first].append(actual.current_amperes)
        currents[second].append(-actual.current_amperes)
    independent_kcl = max(abs(math.fsum(values)) for values in currents.values())
    close(independent_kcl, 0, 1e-11, 'independent KCL')
    expected_power = size * (size - 1) * (.5 ** 2 + .25 ** 2) / 1000
    close(math.fsum(resistor_power), expected_power, 1e-11, 'total resistor power')
    close(math.fsum(source_power), -expected_power, 1e-11, 'total source power')
    close(result.power_balance_watts, 0, 1e-11, 'reported power balance')
    close(result.max_kcl_residual_amperes, 0, 1e-11, 'reported KCL')
    return {'max_node_voltage_error_volts': max(abs(result.node_voltages[n] - v) for n, v in expected.items()),
            'max_branch_current_error_amperes': max(current_errors),
            'independent_kcl_residual_amperes': independent_kcl,
            'resistor_power_watts': math.fsum(resistor_power),
            'expected_resistor_power_watts': expected_power}


class GridDCReferenceTests(unittest.TestCase):
    def test_reference_counts_size_guard_and_standard_library_assembly(self):
        for size in (2, 8, 12):
            circuit = grid_reference(size)
            self.assertEqual(len(circuit.nodes), size * size + 1)
            self.assertEqual(len(circuit.elements), 2 * size * (size - 1) + 4 * size - 4)
            unknowns = size * size + 4 * size - 4
            self.assertLessEqual(unknowns, 200)
            self.assertEqual(len(assemble_dc(circuit).matrix), unknowns)
        for size in (True, 1, 13, 4., '4'):
            with self.subTest(size=size), self.assertRaises(ValueError):
                grid_reference(size)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_affine_grids_all_branches_sources_and_power(self):
        for size in (2, 3, 5, 8, 12):
            with self.subTest(size=size):
                verify_grid(solve_dc(grid_reference(size)), size)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_grid_ordering_and_nonzero_reference_shift(self):
        size = 5
        circuit = grid_reference(size)
        verify_grid(solve_dc(replace(circuit, nodes=tuple(reversed(circuit.nodes)),
            elements=tuple(reversed(circuit.elements)))), size)
        shifted = replace(circuit, reference_node=node(0, size - 1))
        verify_grid(solve_dc(shifted), size, shift=potential(0, size - 1))


if __name__ == '__main__':
    unittest.main()
