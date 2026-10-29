"""Independent current direction, passive power signs and annotation boundaries."""

from dataclasses import replace
import importlib.util
import math
import subprocess
import sys
import unittest

from circuit_calculator.annotations import component_annotations
from circuit_calculator.circuit import Circuit, Resistor, VoltageSource, CurrentSource
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.dc import DCResult, ElementResult
from circuit_calculator.project_io import SchematicProject, dumps_project
from circuit_calculator.results_io import dumps_results_csv
from circuit_calculator.schematic import Schematic, divider_example, placed_divider_example


def divider_result():
    return DCResult('g', {'g': 0., 'in': 12., 'out': 8.},
                    {'V1': ElementResult(12., -.004, -.048),
                     'R1': ElementResult(4., .004, .016),
                     'R2': ElementResult(8., .004, .032)}, 1., 0., 0.)


class ComponentAnnotationTests(unittest.TestCase):
    def test_analytical_divider_signed_current_and_delivered_source_power(self):
        labels = component_annotations(divider_example(), divider_result())
        self.assertEqual(labels['V1'], 'I: -4 mA\n+I: in → g\nP: -48 mW (delivered)')
        self.assertEqual(labels['R1'], 'I: 4 mA\n+I: in → out\nP: 16 mW (absorbed)')
        self.assertEqual(labels['R2'], 'I: 4 mA\n+I: out → return\nP: 32 mW (absorbed)')

    def test_owned_terminal_direction_survives_all_rotations(self):
        state = placed_divider_example()
        expected = component_annotations(state, divider_result())
        self.assertIn('+I: V1.+ → V1.−', expected['V1'])
        self.assertIn('+I: R1.a → R1.b', expected['R1'])
        for _ in range(4):
            state = state.rotate_component('R1').rotate_component('V1')
            self.assertEqual(component_annotations(state, divider_result()), expected)

    def test_missing_results_and_branches_never_annotate_wires_or_invent_zero(self):
        state = placed_divider_example()
        self.assertEqual(component_annotations(state), {})
        self.assertEqual(component_annotations(state, replace(divider_result(), elements={})), {})
        labels = component_annotations(state, replace(divider_result(), elements={'R1': divider_result().elements['R1']}))
        self.assertEqual(set(labels), {'R1'})
        self.assertNotIn('W1', labels)

    def test_exact_zero_and_tiny_power_are_classified_without_new_tolerance(self):
        state = divider_example()
        for current, power, classification in ((0., 0., 'zero'), (1e-30, 1e-30, 'absorbed'),
                                                (-1e-30, -1e-30, 'delivered')):
            result = replace(divider_result(), elements={'V1': ElementResult(1., current, power)})
            text = component_annotations(state, result)['V1']
            self.assertIn('(' + classification + ')', text)
            if current == 0:
                self.assertIn('I: 0 A', text)
            else:
                self.assertNotIn('I: 0 A', text)

    def test_nonfinite_current_or_power_is_rejected(self):
        for field in ('current_amperes', 'power_watts'):
            for value in (math.inf, -math.inf, math.nan):
                branch = replace(divider_result().elements['R1'], **{field: value})
                result = replace(divider_result(), elements={'R1': branch})
                with self.assertRaises(ValueError):
                    component_annotations(divider_example(), result)

    def test_annotations_leave_project_and_full_precision_csv_unchanged(self):
        state, result = placed_divider_example(), divider_result()
        before = dumps_project(SchematicProject(state)), dumps_results_csv(result)
        labels = component_annotations(state, result)
        labels.clear()
        self.assertEqual((dumps_project(SchematicProject(state)), dumps_results_csv(result)), before)

    def test_validation_and_optional_dependency_import_boundary(self):
        with self.assertRaises(TypeError):
            component_annotations(None)
        with self.assertRaises(TypeError):
            component_annotations(divider_example(), {})
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; from circuit_calculator.annotations import component_annotations; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_actual_current_source_and_reversed_resistor_orientation(self):
        from circuit_calculator.dc import solve_dc
        circuit = Circuit(('g', 'a'), (VoltageSource('V1', 'a', 'g', 10),
            Resistor('R1', 'g', 'a', 1000), CurrentSource('I1', 'a', 'g', -.003)), 'g')
        state = Schematic.from_document(CircuitDocument(circuit))
        labels = component_annotations(state, solve_dc(circuit))
        self.assertEqual(labels['I1'], 'I: -3 mA\n+I: a → g\nP: -30 mW (delivered)')
        self.assertEqual(labels['R1'], 'I: -10 mA\n+I: g → a\nP: 100 mW (absorbed)')
        self.assertEqual(labels['V1'], 'I: -7 mA\n+I: a → g\nP: -70 mW (delivered)')

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_actual_reference_and_reversed_voltage_source_invariance(self):
        from circuit_calculator.dc import solve_dc
        state = placed_divider_example()
        expected = component_annotations(state, solve_dc(state.compile().circuit))
        for reference in ('g', 'in', 'out'):
            shifted = state.set_reference(reference)
            self.assertEqual(component_annotations(shifted, solve_dc(shifted.compile().circuit)), expected)
        circuit = Circuit(('g', 'a'), (VoltageSource('V1', 'g', 'a', -10),
                                       Resistor('R1', 'a', 'g', 1000)), 'a')
        reversed_state = Schematic.from_document(CircuitDocument(circuit))
        self.assertEqual(component_annotations(reversed_state, solve_dc(circuit))['V1'],
                         'I: 10 mA\n+I: g → a\nP: -100 mW (delivered)')
