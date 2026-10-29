"""Independent polarity, alias, reference and numeric-range probe checks."""

from dataclasses import replace
import importlib.util
import math
import subprocess
import sys
import unittest

from circuit_calculator.circuit import Circuit, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.dc import DCResult
from circuit_calculator.probe import voltage_between, probe_text
from circuit_calculator.schematic import divider_example, placed_divider_example, Schematic


def divider_result():
    return DCResult('g', {'g': 0., 'in': 12., 'out': 8.}, {}, 1., 0., 0.)


class ProbeTests(unittest.TestCase):
    def test_polarity_same_endpoint_and_negative_voltage(self):
        state, result = divider_example(), divider_result()
        for a, b, expected in (('in', 'out', 4.), ('out', 'in', -4.),
                               ('out', 'out', 0.), ('g', 'out', -8.)):
            self.assertEqual(voltage_between(state, a, b, result), expected)
        text = probe_text(state, 'out', 'in', result)
        self.assertIn('A (+): out', text)
        self.assertIn('B (−): in', text)
        self.assertIn('Polarity: V(A) − V(B)', text)
        self.assertIn('Voltage difference: -4 V', text)

    def test_owned_terminal_and_wire_aliases_resolve_to_same_net(self):
        state, result = placed_divider_example(), divider_result()
        resistor = state.document.circuit.elements[1]
        self.assertEqual(voltage_between(state, resistor.node_a, resistor.node_b, result), 4.)
        self.assertEqual(voltage_between(state, 'return', 'g', result), 0.)
        self.assertIn('R1.a', probe_text(state, resistor.node_a, resistor.node_b, result))

    def test_absent_pending_deleted_and_incomplete_results_do_not_invent_zero(self):
        state = divider_example()
        self.assertIn('Choose endpoint', probe_text(state, None, 'g', divider_result()))
        self.assertIn('Choose endpoint', probe_text(state, 'deleted', 'g', divider_result()))
        self.assertIn('No current DC result', probe_text(state, 'in', 'out'))
        self.assertIn('Solving DC', probe_text(state, 'in', 'out', solving=True))
        missing = replace(divider_result(), node_voltages={})
        self.assertIn('No current voltage', probe_text(state, 'g', 'g', missing))

    def test_finite_subtraction_guard_and_tiny_values_without_new_tolerance(self):
        state = divider_example()
        for a, b in ((1e308, -1e308), (math.inf, 1.), (math.nan, 1.)):
            result = replace(divider_result(), node_voltages={'in': a, 'out': b})
            with self.assertRaisesRegex(ValueError, 'finite numeric range'):
                voltage_between(state, 'in', 'out', result)
            self.assertNotIn('Voltage difference:', probe_text(state, 'in', 'out', result))
        result = replace(divider_result(), node_voltages={'in': 5e-324, 'out': 0.})
        self.assertEqual(voltage_between(state, 'in', 'out', result), 5e-324)
        self.assertEqual(voltage_between(state, 'out', 'in', result), -5e-324)

    def test_validation_and_headless_dependency_boundary(self):
        state, result = divider_example(), divider_result()
        for a in (None, 1, [], 'missing'):
            with self.assertRaises(ValueError):
                voltage_between(state, a, 'g', result)
        for args in ((None, 'g', 'in', result), (state, 'g', 'in', None)):
            with self.assertRaises(TypeError):
                voltage_between(*args)
        with self.assertRaises(TypeError):
            probe_text(state, 'in', 'g', solving=1)
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; import circuit_calculator.probe, circuit_calculator.probe_panel; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_real_solutions_reference_and_order_invariance(self):
        from circuit_calculator.dc import solve_dc
        # A 12 V source feeding 1k + 2k: I=4mA, upper drop=4V.
        elements = (VoltageSource('s', 'in', 'g', 12), Resistor('a', 'in', 'out', 1000),
                    Resistor('b', 'out', 'g', 2000))
        for reference in ('g', 'in', 'out'):
            for nodes, parts in ((('g', 'in', 'out'), elements),
                                  (('out', 'in', 'g'), tuple(reversed(elements)))):
                circuit = Circuit(nodes, parts, reference)
                state = Schematic.from_document(CircuitDocument(circuit))
                result = solve_dc(circuit)
                self.assertAlmostEqual(voltage_between(state, 'in', 'out', result), 4.)
                self.assertAlmostEqual(voltage_between(state, 'out', 'in', result), -4.)
                self.assertAlmostEqual(voltage_between(state, 'g', 'out', result), -8.)
