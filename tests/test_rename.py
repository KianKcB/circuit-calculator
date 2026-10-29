"""Identity edits preserve ordered topology, ownership and persistence."""

from dataclasses import replace
import importlib.util
import unittest

from circuit_calculator.circuit import Circuit, CurrentSource
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.project_io import SchematicProject, dumps_project, loads_project
from circuit_calculator.schematic import (Schematic, EditorSession, Waypoint, terminals,
                                         value_of, placed_divider_example, divider_example)


class RenameTests(unittest.TestCase):
    def test_component_rename_preserves_terminals_layout_routes_and_value(self):
        state = placed_divider_example().route_wire('W1', (Waypoint(400, 440),))
        for old, new in (('R1', 'مقاومت: ورودی'), ('V1', 'Source +'), ('R2', 'W1')):
            with self.subTest(old=old):
                edited = state.rename('element', old, new)
                original = next(e for e in state.document.circuit.elements if e.name == old)
                changed = next(e for e in edited.document.circuit.elements if e.name == new)
                self.assertEqual(terminals(original), terminals(changed))
                self.assertEqual(value_of(original), value_of(changed))
                self.assertEqual(edited.positions, state.positions)
                self.assertEqual(edited.wires, state.wires)
                self.assertEqual(edited.terminal_owners(),
                                 {n: new if owner == old else owner for n, owner in state.terminal_owners().items()})
                self.assertEqual(edited.rename('element', new, old), state)
                self.assertEqual(loads_project(dumps_project(SchematicProject(edited))).schematic, edited)

    def test_free_junction_rename_updates_all_references_in_place(self):
        state = placed_divider_example()
        for name in state.document.circuit.nodes[:4]:
            with self.subTest(name=name):
                edited = state.rename('node', name, 'new:نام')
                self.assertEqual(edited.rename('node', 'new:نام', name), state)
                self.assertEqual(len(edited.wires), len(state.wires))
                self.assertEqual(edited.placements, state.placements)
                if name == 'g':
                    self.assertEqual(edited.document.circuit.reference_node, 'new:نام')
                self.assertEqual(loads_project(dumps_project(SchematicProject(edited))).schematic, edited)

    def test_legacy_junction_rewrites_all_oriented_device_types(self):
        state = divider_example().add_element(CurrentSource('I1', 'out', 'g', -.001))
        edited = state.rename('node', 'g', 'ground')
        self.assertEqual(edited.document.circuit.nodes, ('ground', 'in', 'out', 'return'))
        self.assertEqual([terminals(e) for e in edited.document.circuit.elements],
                         [('in', 'ground'), ('in', 'out'), ('out', 'return'), ('out', 'ground')])
        self.assertEqual(edited.rename('node', 'ground', 'g'), state)

    def test_wire_rename_keeps_endpoints_bends_and_compilation(self):
        state = divider_example().route_wire('W1', (Waypoint(300, 460),))
        edited = state.rename('wire', 'W1', 'return: مسیر')
        self.assertEqual(edited.compile(), state.compile())
        self.assertEqual(edited.wires, (replace(state.wires[0], name='return: مسیر'),))
        self.assertEqual(loads_project(dumps_project(SchematicProject(edited))).schematic, edited)

    def test_namespaces_case_spaces_and_noop(self):
        state = divider_example()
        for kind, name in (('element', 'R1'), ('node', 'g'), ('wire', 'W1')):
            self.assertIs(state.rename(kind, name, name), state)
        self.assertEqual(state.rename('element', 'R1', 'g').document.circuit.elements[1].name, 'g')
        self.assertEqual(state.rename('element', 'R1', 'r2').document.circuit.elements[1].name, 'r2')
        self.assertEqual(state.rename('node', 'g', ' g ').document.circuit.nodes[0], ' g ')
        self.assertIsNone(Schematic.from_document(CircuitDocument(Circuit(('a',), ())))
                          .rename('node', 'a', 'b').document.circuit.reference_node)

    def test_collisions_unknown_names_kinds_and_invalid_text_are_atomic(self):
        state = placed_divider_example()
        for args in (('element', 'R1', 'R2'), ('node', 'g', 'in'),
                     ('wire', 'W1', 'W2'), ('element', 'missing', 'R9'),
                     ('node', 'missing', 'new'), ('wire', 'missing', 'new'),
                     ('terminal', 'g', 'new'), ('other', 'g', 'new')):
            with self.subTest(args=args), self.assertRaises(ValueError):
                state.rename(*args)
        for bad in ('', '  ', 'x' * 257, '\ud800', None, 5, True):
            with self.subTest(bad=repr(bad)), self.assertRaises(ValueError):
                state.rename('element', 'R1', bad)
        for node in state.terminal_owners():
            with self.assertRaisesRegex(ValueError, 'terminal identities'):
                state.rename('node', node, 'changed')
        self.assertEqual(state, placed_divider_example())

    def test_each_edit_is_one_history_entry_and_rejects_old_results(self):
        original = placed_divider_example()
        session = EditorSession(original)
        revision = session.revision
        session.accept_result(revision, object())
        session.apply(original.rename('element', 'R1', 'Rx'))
        self.assertIsNone(session.result)
        self.assertFalse(session.accept_result(revision, object()))
        renamed = session.state
        session.undo()
        self.assertEqual(session.state, original)
        session.redo()
        self.assertEqual(session.state, renamed)
        revision = session.revision
        result = object()
        session.accept_result(revision, result)
        session.apply(session.state.rename('element', 'Rx', 'Rx'))
        self.assertEqual(session.revision, revision)
        self.assertIs(session.result, result)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_analytical_solution_after_all_three_renames(self):
        from circuit_calculator.dc import solve_dc
        state = placed_divider_example().rename('node', 'g', 'ground').rename('element', 'V1', 'Supply')
        state = state.rename('wire', 'W1', 'Return')
        result = solve_dc(state.compile().circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 8)
        self.assertAlmostEqual(result.elements['Supply'].current_amperes, -.004)
        self.assertAlmostEqual(result.elements['Supply'].power_watts, -.048)


if __name__ == '__main__':
    unittest.main()
