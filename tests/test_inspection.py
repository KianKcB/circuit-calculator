"""Read-only presentation, source orientation and alias/net inspection."""

from dataclasses import replace
import importlib.util
from types import MappingProxyType
import subprocess
import sys
import unittest

from circuit_calculator.circuit import Circuit, Resistor, VoltageSource, CurrentSource
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.dc import DCResult, ElementResult
from circuit_calculator.inspection import selection_text
from circuit_calculator.project_io import SchematicProject, dumps_project
from circuit_calculator.results_io import dumps_results_csv
from circuit_calculator.schematic import Schematic, placed_divider_example, divider_example


def analytical_divider():
    return DCResult('g', MappingProxyType({'g': 0., 'in': 12., 'out': 8.}),
        MappingProxyType({'V1': ElementResult(12., -.004, -.048),
                          'R1': ElementResult(4., .004, .016),
                          'R2': ElementResult(8., .004, .032)}), 1., 0., 0.)


class InspectionTests(unittest.TestCase):
    def test_component_polarity_current_and_power_match_analytical_divider(self):
        state, result = divider_example(), analytical_divider()
        source = selection_text(state, ('element', 'V1'), result)
        self.assertIn('Voltage convention: V(in) - V(g)', source)
        self.assertIn('Positive current: in → g', source)
        self.assertIn('Current: -4 mA', source)
        self.assertIn('Power: -48 mW (delivered)', source)
        resistor = selection_text(state, ('element', 'R1'), result)
        self.assertIn('Resistance: 1 kΩ', resistor)
        self.assertIn('Voltage: 4 V', resistor)
        self.assertIn('Power: 16 mW (absorbed)', resistor)

    def test_current_source_sign_zero_and_tiny_power_have_no_new_tolerance(self):
        state = Schematic.from_document(CircuitDocument(Circuit(('g', 'a'),
            (CurrentSource('I1', 'a', 'g', -.003),), 'g')))
        for power, label in ((-.03, 'delivered'), (0., 'zero'), (1e-30, 'absorbed')):
            result = DCResult('g', {'g': 0., 'a': 10.}, {'I1': ElementResult(10., -.003, power)}, 1., 0., 0.)
            text = selection_text(state, ('element', 'I1'), result)
            self.assertIn('Source current: -3 mA', text)
            self.assertIn('Positive current: a → g', text)
            self.assertIn('Current: -3 mA', text)
            self.assertIn('(' + label + ')', text)

    def test_owned_terminal_labels_and_alias_reference_are_explicit(self):
        state, result = placed_divider_example(), analytical_divider()
        reference_terminal = state.document.circuit.elements[0].minus_node
        text = selection_text(state, ('terminal', reference_terminal), result)
        self.assertIn('Terminal: V1.−', text)
        self.assertIn('Resolved net: g', text)
        self.assertIn('Reference net: yes', text)
        self.assertIn('Net voltage: 0 V', text)
        text = selection_text(state, ('node', 'return'), result)
        self.assertIn('Resolved net: g', text)
        self.assertIn('Reference net: yes', text)
        self.assertIn('Net voltage: 0 V', text)
        text = selection_text(state, ('element', 'R1'), result)
        self.assertIn('V(R1.a) - V(R1.b)', text)

    def test_wire_reports_net_voltage_but_never_invents_branch_current_or_power(self):
        state, result = placed_divider_example(), analytical_divider()
        text = selection_text(state, ('wire', 'W1'), result)
        self.assertIn('Wire: W1', text)
        self.assertIn('Bends: 0', text)
        self.assertIn('Net voltage: 0 V', text)
        self.assertIn('Wire current: not resolved', text)
        self.assertNotIn('Power:', text)
        self.assertNotIn('Current: 0', text)

    def test_unsolved_pending_and_unfinished_states_have_no_placeholder_values(self):
        state = divider_example()
        for selection in (('element', 'R1'), ('wire', 'W1'), ('node', 'out')):
            text = selection_text(state, selection)
            self.assertIn('No current DC result', text)
            self.assertNotIn('Current DC result', text)
            self.assertNotIn('Net voltage:', text)
            self.assertIn('Solving DC', selection_text(state, selection, solving=True))
        # Wire-shortened devices may be saved/inspected although solving rejects them.
        from circuit_calculator.schematic import Wire
        shorted = state.add_wire(Wire('short', 'in', 'out'))
        self.assertIn('No current DC result', selection_text(shorted, ('element', 'R1')))

    def test_absent_deleted_unknown_or_malformed_selections_are_safe(self):
        state, result = divider_example(), analytical_divider()
        for selection in (None, (), 'R1', ('element',), ('node', None), ('unknown', 'R1')):
            self.assertIn('Select a component', selection_text(state, selection, result))
        for selection in (('element', 'deleted'), ('wire', 'deleted'), ('node', 'deleted')):
            self.assertIn('Selection no longer exists', selection_text(state, selection, result))
        missing = replace(result, elements={})
        self.assertIn('No current DC result', selection_text(state, ('element', 'R1'), missing))
        self.assertIn('No current DC result', selection_text(state, ('node', 'out'), replace(result, node_voltages={})))

    def test_inspection_never_changes_state_result_or_serialized_exports(self):
        state, result = placed_divider_example(), analytical_divider()
        project, csv = dumps_project(SchematicProject(state)), dumps_results_csv(result)
        for selection in (('element', 'V1'), ('node', 'g'), ('wire', 'W1')):
            selection_text(state, selection, result)
        self.assertEqual(dumps_project(SchematicProject(state)), project)
        self.assertEqual(dumps_results_csv(result), csv)

    def test_invalid_inputs_and_import_boundary(self):
        state = divider_example()
        with self.assertRaises(TypeError):
            selection_text(None, None)
        with self.assertRaises(TypeError):
            selection_text(state, None, object())
        with self.assertRaises(TypeError):
            selection_text(state, None, solving=1)
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; import circuit_calculator.inspection; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_real_current_source_circuit_matches_analytical_power_and_direction(self):
        from circuit_calculator.dc import solve_dc
        circuit = Circuit(('g', 'a'), (VoltageSource('V1', 'a', 'g', 10),
                          Resistor('R1', 'a', 'g', 1000), CurrentSource('I1', 'a', 'g', -.003)), 'g')
        state = Schematic.from_document(CircuitDocument(circuit))
        result = solve_dc(circuit)
        self.assertAlmostEqual(result.elements['V1'].current_amperes, -.007)
        self.assertIn('Power: -30 mW (delivered)', selection_text(state, ('element', 'I1'), result))
        self.assertIn('Power: 100 mW (absorbed)', selection_text(state, ('element', 'R1'), result))
        self.assertIn('Power: -70 mW (delivered)', selection_text(state, ('element', 'V1'), result))


if __name__ == '__main__':
    unittest.main()
