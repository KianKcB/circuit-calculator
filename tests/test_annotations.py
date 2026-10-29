"""Analytical node voltage/reference labels, separate from geometric rendering."""

from dataclasses import replace
import importlib.util
import math
import subprocess
import sys
import unittest

from circuit_calculator.annotations import node_voltage_annotations
from circuit_calculator.dc import DCResult
from circuit_calculator.schematic import divider_example, placed_divider_example
from circuit_calculator.project_io import SchematicProject, dumps_project


def result():
    return DCResult('g', {'g': 0., 'in': 12., 'out': 8.}, {}, 1., 0., 0.)


class AnnotationTests(unittest.TestCase):
    def test_analytical_divider_and_reference_aliases(self):
        state = placed_divider_example()
        labels = node_voltage_annotations(state, result())
        self.assertEqual(labels['in'], '12 V')
        self.assertEqual(labels['out'], '8 V')
        self.assertEqual(labels['g'], '0 V (ref)')
        self.assertEqual(labels['return'], '0 V (ref)')
        resistor = state.document.circuit.elements[1]
        self.assertEqual(labels[resistor.node_a], '12 V')
        self.assertEqual(labels[resistor.node_b], '8 V')
        self.assertEqual(set(labels), set(state.document.circuit.nodes))

    def test_missing_result_or_net_never_fabricates_zero(self):
        state = divider_example()
        self.assertEqual(node_voltage_annotations(state), {})
        self.assertEqual(node_voltage_annotations(state, replace(result(), node_voltages={})), {})
        self.assertEqual(node_voltage_annotations(state, replace(result(), node_voltages={'out': -0.001})),
                         {'out': '-1 mV'})

    def test_finite_display_rounding_and_invalid_values(self):
        state = divider_example()
        for value in (math.inf, -math.inf, math.nan):
            with self.assertRaises(ValueError):
                node_voltage_annotations(state, replace(result(), node_voltages={'out': value}))
        labels = node_voltage_annotations(state, replace(result(), node_voltages={'out': 1.23456789123}))
        self.assertEqual(labels, {'out': '1.23456789 V'})

    def test_labels_do_not_mutate_or_serialize_results(self):
        state, snapshot = placed_divider_example(), result()
        before = dumps_project(SchematicProject(state))
        labels = node_voltage_annotations(state, snapshot)
        labels.clear()
        self.assertEqual(dumps_project(SchematicProject(state)), before)
        self.assertEqual(snapshot.node_voltages['out'], 8.)
        self.assertEqual(node_voltage_annotations(state, snapshot)['out'], '8 V')

    def test_validation_and_headless_imports(self):
        with self.assertRaises(TypeError):
            node_voltage_annotations(None)
        with self.assertRaises(TypeError):
            node_voltage_annotations(divider_example(), {})
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; import circuit_calculator.annotations; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_actual_nonzero_reference_changes_node_values_but_not_probe_difference(self):
        from circuit_calculator.dc import solve_dc
        from circuit_calculator.probe import voltage_between
        from circuit_calculator.circuit_io import CircuitDocument
        from circuit_calculator.schematic import Schematic
        circuit = divider_example().compile().circuit
        for reference, expected in (('g', {'g': '0 V (ref)', 'in': '12 V', 'out': '8 V'}),
                                    ('in', {'g': '-12 V', 'in': '0 V (ref)', 'out': '-4 V'}),
                                    ('out', {'g': '-8 V', 'in': '4 V', 'out': '0 V (ref)'})):
            circuit = replace(circuit, reference_node=reference)
            state = Schematic.from_document(CircuitDocument(circuit))
            solved = solve_dc(circuit)
            self.assertEqual(node_voltage_annotations(state, solved), expected)
            self.assertAlmostEqual(voltage_between(state, 'in', 'out', solved), 4.)
