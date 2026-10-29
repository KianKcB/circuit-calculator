"""Component clipboard snapshots create fresh, explicitly unconnected devices."""

from dataclasses import FrozenInstanceError
import importlib.util
import unittest

from circuit_calculator.circuit import CurrentSource
from circuit_calculator.project_io import SchematicProject, dumps_project, loads_project
from circuit_calculator.schematic import (ComponentTemplate, EditorSession, Wire,
                                         divider_example, placed_divider_example,
                                         terminals, value_of)


class ComponentCopyTests(unittest.TestCase):
    def test_every_kind_orientation_and_signed_value_has_fresh_terminals(self):
        for kind, value in (('resistor', 1e-3), ('voltage', -12), ('voltage', 0),
                            ('current', -.004), ('current', 0)):
            for rotation in (0, 90, 180, 270):
                with self.subTest(kind=kind, value=value, rotation=rotation):
                    original = placed_divider_example().add_placed_component(kind, 'original', 700, 500, value, rotation)
                    template = original.copy_component('original')
                    self.assertEqual(template, ComponentTemplate(kind, value, rotation))
                    copied = original.paste_component(template, 700, 500)
                    circuit = original.document.circuit
                    element = copied.document.circuit.elements[-1]
                    self.assertNotEqual(element.name, 'original')
                    self.assertEqual(value_of(element), value)
                    self.assertTrue(set(terminals(element)).isdisjoint(circuit.nodes))
                    self.assertEqual(copied.document.circuit.elements[:-1], circuit.elements)
                    self.assertEqual(copied.document.circuit.nodes[:-2], circuit.nodes)
                    self.assertEqual(copied.document.circuit.reference_node, circuit.reference_node)
                    self.assertEqual(copied.positions[:-2], original.positions)
                    self.assertEqual(copied.wires, original.wires)
                    self.assertEqual(copied.placements[-1].rotation, rotation)
                    self.assertEqual(tuple(copied.terminal_owners()[n] for n in terminals(element)), (element.name,) * 2)
                    self.assertEqual(loads_project(dumps_project(SchematicProject(copied))).schematic, copied)

    def test_component_and_terminal_allocator_handles_adversarial_collisions(self):
        state = divider_example().add_node('terminal_1', 700, 100).add_node('terminal_3', 700, 200)
        state = state.rename('element', 'V1', 'R3')
        copied = state.paste_component(ComponentTemplate('resistor', 250), 600, 400)
        element = copied.document.circuit.elements[-1]
        self.assertEqual(element.name, 'R4')
        self.assertEqual(terminals(element), ('terminal_2', 'terminal_4'))
        again = copied.paste_component(ComponentTemplate('resistor', 250), 600, 400)
        self.assertEqual(again.document.circuit.elements[-1].name, 'R5')
        self.assertEqual(terminals(again.document.circuit.elements[-1]), ('terminal_5', 'terminal_6'))

    def test_snapshot_is_immutable_and_independent_of_source_changes_deletion(self):
        state = placed_divider_example()
        template = state.copy_component('R1')
        with self.assertRaises(FrozenInstanceError):
            template.value = 5
        changed = state.change_value('R1', 500).rotate_component('R1').rename('element', 'R1', 'input').delete('element', 'input')
        copied = changed.paste_component(template, 700, 400)
        self.assertEqual(value_of(copied.document.circuit.elements[-1]), 1000)
        self.assertEqual(copied.placements[-1].rotation, 0)

    def test_legacy_capture_does_not_convert_or_copy_incident_wires(self):
        state = divider_example().add_element(CurrentSource('I1', 'out', 'g', -.002))
        # V1 runs from in=(160,160) to g=(160,420), downward in Canvas coordinates.
        for name, rotation in (('R1', 0), ('V1', 90), ('R2', 90), ('I1', 180)):
            with self.subTest(name=name):
                copied = state.duplicate_component(name, 700, 400)
                self.assertEqual(len(copied.placements), 1)
                self.assertEqual(copied.placements[-1].rotation, rotation)
                self.assertEqual(copied.wires, state.wires)
                self.assertEqual(copied.document.circuit.elements[:-1], state.document.circuit.elements)
        self.assertEqual(state.placements, ())

    def test_invalid_templates_and_unknown_components(self):
        for args in (('bad', 5, 0), ('resistor', 0, 0), ('resistor', -1, 0),
                     ('voltage', float('inf'), 0), ('current', True, 0),
                     ('resistor', 5, 45), ('voltage', 1, True), ('current', 2, 90.0)):
            with self.subTest(args=args), self.assertRaises((TypeError, ValueError)):
                ComponentTemplate(*args)
        state = divider_example()
        with self.assertRaisesRegex(ValueError, 'existing component'):
            state.copy_component('missing')
        for bad in (None, 'resistor', {'kind': 'resistor'}, state.document.circuit.elements[0]):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                state.paste_component(bad, 500, 500)

    def test_coordinate_failures_and_component_limit_leave_original_unchanged(self):
        state = placed_divider_example()
        for x, y in ((100000, 0), (-100000, 0), (float('nan'), 0), (True, 0), (0, 10**1000)):
            with self.subTest(x=x, y=y), self.assertRaises((ValueError, TypeError)):
                state.paste_component(ComponentTemplate('resistor', 1), x, y)
        for index in range(197):
            state = state.add_element(CurrentSource(f'extra{index}', 'in', 'out', 0))
        self.assertEqual(len(state.document.circuit.elements), 200)
        with self.assertRaisesRegex(ValueError, '200 components'):
            state.duplicate_component('R1', 600, 600)
        self.assertEqual(len(state.document.circuit.elements), 200)

    def test_duplication_is_one_history_entry_and_original_solved_graph_recovers(self):
        original = placed_divider_example()
        session = EditorSession(original)
        session.accept_result(session.revision, object())
        session.apply(original.duplicate_component('R1', 700, 400))
        copied = session.state
        self.assertIsNone(session.result)
        self.assertEqual(len(copied.document.circuit.elements), 4)
        session.undo()
        self.assertEqual(session.state, original)
        session.redo()
        self.assertEqual(session.state, copied)
        deleted = copied.delete('element', copied.document.circuit.elements[-1].name)
        self.assertEqual(deleted, original)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_explicitly_wired_copy_matches_independent_parallel_resistor_solution(self):
        from circuit_calculator.dc import solve_dc
        state = placed_divider_example()
        state = state.paste_component(state.copy_component('R2'), 740, 280)
        name = state.document.circuit.elements[-1].name
        first, second = terminals(state.document.circuit.elements[-1])
        # A second 2k resistor explicitly across R2 gives 1k lower resistance:
        # out = 12 * 1000/(1000+1000) = 6 V, each lower branch = 3 mA.
        state = state.add_wire(Wire('copy_a', first, 'out')).add_wire(Wire('copy_b', second, 'g'))
        result = solve_dc(state.compile().circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 6)
        self.assertAlmostEqual(result.elements[name].current_amperes, .003)
        self.assertAlmostEqual(result.elements['V1'].power_watts, -.072)
        self.assertAlmostEqual(result.power_balance_watts, 0, places=12)


if __name__ == '__main__':
    unittest.main()
