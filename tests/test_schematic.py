"""Editor topology and revision behavior, without a display or Tk dependency."""

from dataclasses import FrozenInstanceError
import importlib.util
import io
from contextlib import redirect_stderr, redirect_stdout
import unittest
from unittest.mock import patch

from circuit_calculator.circuit import Circuit, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument, dumps_document, loads_document
from circuit_calculator.schematic import (Schematic, Position, Wire, EditorSession, component,
                       divider_example, terminals, value_of)


class SchematicTests(unittest.TestCase):
    def test_wires_merge_only_explicit_junctions_and_preserve_orientation(self):
        state = divider_example()
        compiled = state.compile().circuit
        self.assertEqual(compiled.nodes, ('g', 'in', 'out'))
        self.assertEqual(compiled.reference_node, 'g')
        self.assertEqual(terminals(compiled.elements[2]), ('out', 'g'))
        self.assertEqual(value_of(compiled.elements[2]), 2000)

    def test_geometry_and_crossings_have_no_electrical_effect(self):
        state = divider_example()
        original = state.compile()
        moved = state.move_node('return', 160, 160).move_node('out', 160, 160)
        self.assertEqual(moved.compile(), original)
        circuit = Circuit(('a', 'b', 'c', 'd'), (), 'a')
        crossing = Schematic(CircuitDocument(circuit),
            (Position('a', 0, 0), Position('b', 100, 100), Position('c', 0, 100), Position('d', 100, 0)),
            (Wire('W1', 'a', 'b'), Wire('W2', 'c', 'd')))
        self.assertEqual(crossing.net_names(), {'a': 'a', 'b': 'a', 'c': 'c', 'd': 'c'})

    def test_wire_order_direction_and_cycles_do_not_change_net_names(self):
        state = Schematic.from_document(CircuitDocument(Circuit(('a', 'b', 'c'), (), 'c')))
        first = Schematic(state.document, state.positions,
                          (Wire('W1', 'b', 'c'), Wire('W2', 'b', 'a')))
        second = Schematic(state.document, state.positions,
                           (Wire('W3', 'a', 'b'), Wire('W4', 'c', 'b'), Wire('W5', 'a', 'c')))
        self.assertEqual(first.compile(), second.compile())
        self.assertEqual(first.compile().circuit.reference_node, 'a')

    def test_wire_shorting_device_is_actionable(self):
        state = divider_example().add_wire(Wire('W2', 'in', 'out'))
        with self.assertRaisesRegex(ValueError, 'shorts both terminals of R1'):
            state.compile()

    def test_invalid_wires_are_rejected(self):
        state = divider_example()
        for wire in (Wire('W1', 'in', 'out'), Wire('other', 'g', 'return'), Wire('bad', 'g', 'missing')):
            with self.subTest(wire=wire), self.assertRaises(ValueError):
                state.add_wire(wire)
        with self.assertRaises(ValueError):
            Wire('W', 'g', 'g')
        with self.assertRaises(ValueError):
            Wire('', 'g', 'in')

    def test_layout_has_exactly_one_valid_position_per_node(self):
        state = divider_example()
        with self.assertRaises(ValueError):
            Schematic(state.document, state.positions[:-1])
        with self.assertRaises(ValueError):
            Position('g', float('nan'), 0)
        with self.assertRaises(ValueError):
            Position('g', 100001, 0)
        with self.assertRaises(ValueError):
            Position('g', 10**1000, 0)
        with self.assertRaises(TypeError):
            Position('g', True, 0)
        with self.assertRaises(FrozenInstanceError):
            state.positions = ()

    def test_deleting_reference_junction_removes_incident_items(self):
        state = divider_example().delete('node', 'g')
        self.assertIsNone(state.document.circuit.reference_node)
        self.assertEqual([e.name for e in state.document.circuit.elements], ['R1', 'R2'])
        self.assertEqual(state.wires, ())
        with self.assertRaises(ValueError):
            Schematic.from_document(CircuitDocument(Circuit(('a',), ()))).delete('node', 'a')

    def test_delete_wire_splits_net_and_delete_component_keeps_nodes(self):
        state = divider_example()
        split = state.delete('wire', 'W1').compile().circuit
        self.assertEqual(split.nodes, ('g', 'in', 'out', 'return'))
        removed = state.delete('element', 'R1')
        self.assertEqual(removed.document.circuit.nodes, state.document.circuit.nodes)
        self.assertEqual(len(removed.document.circuit.elements), 2)

    def test_creation_edit_validation_and_element_order(self):
        state = Schematic.from_document(CircuitDocument(Circuit(('a',), ()))).add_node('b', 40, 40)
        state = state.add_element(component('current', 'I', 'a', 'b', -2))
        state = state.add_element(component('voltage', 'V', 'b', 'a', 3))
        state = state.change_value('I', 4).set_reference('b')
        self.assertEqual(value_of(state.document.circuit.elements[0]), 4)
        self.assertEqual(terminals(state.document.circuit.elements[0]), ('a', 'b'))
        with self.assertRaises(ValueError):
            state.add_element(Resistor('I', 'a', 'b', 1))
        with self.assertRaises(ValueError):
            state.move_node('missing', 0, 0)
        with self.assertRaises(ValueError):
            state.change_value('missing', 1)
        with self.assertRaises(ValueError):
            state.add_node('a', 10, 10)

    def test_import_limits_are_checked_before_rendering(self):
        for count in (101, 10000):
            circuit = Circuit(tuple(f'n{i}' for i in range(count)), ())
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, 'Editor limit'):
                Schematic.from_document(CircuitDocument(circuit))

    def test_native_export_preserves_electrical_topology_not_layout(self):
        original = divider_example()
        document = loads_document(dumps_document(original.compile()))
        imported = Schematic.from_document(document)
        self.assertEqual(imported.compile(), original.compile())
        self.assertNotEqual(imported.positions, original.positions)
        self.assertEqual(imported.wires, ())

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_editor_export_load_solve_matches_independent_divider(self):
        from circuit_calculator.dc import solve_dc
        state = divider_example()
        loaded = loads_document(dumps_document(state.compile()))
        result = solve_dc(loaded.circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 8)
        self.assertAlmostEqual(result.elements['V1'].power_watts, -.048)
        self.assertAlmostEqual(result.power_balance_watts, 0)


class EditorSessionTests(unittest.TestCase):
    def test_undo_redo_restores_deleted_topology_and_clears_results(self):
        original = divider_example()
        session = EditorSession(original)
        session.accept_result(session.revision, object())
        session.apply(original.delete('node', 'g'))
        self.assertIsNone(session.result)
        session.undo()
        self.assertEqual(session.state, original)
        session.redo()
        self.assertNotIn('g', session.state.document.circuit.nodes)

    def test_old_worker_results_are_rejected_even_after_undo(self):
        session = EditorSession(divider_example())
        revision = session.revision
        session.apply(session.state.move_node('out', 100, 100))
        session.undo()
        self.assertFalse(session.accept_result(revision, object()))
        self.assertIsNone(session.result)
        self.assertTrue(session.accept_result(session.revision, object()))

    def test_new_edit_after_undo_clears_redo_and_noops_preserve_result(self):
        session = EditorSession(divider_example())
        marker = object()
        session.accept_result(session.revision, marker)
        session.apply(session.state)
        self.assertIs(session.result, marker)
        session.apply(session.state.move_node('out', 100, 100))
        session.undo()
        session.apply(session.state.change_value('R1', 500))
        expected = session.state
        session.redo()
        self.assertEqual(session.state, expected)

    def test_history_is_bounded(self):
        session = EditorSession(divider_example())
        for i in range(110):
            session.apply(session.state.move_node('out', i, 0))
        for _ in range(110):
            session.undo()
        self.assertEqual(next(p.x for p in session.state.positions if p.node == 'out'), 9)


class GUICommandTests(unittest.TestCase):
    def test_gui_command_passes_example_to_lazy_launcher_without_importing_tk(self):
        from circuit_calculator.cli import main
        with patch('circuit_calculator.gui.launch') as launch:
            self.assertEqual(main(['gui', '--example']), 0)
        self.assertEqual(launch.call_args.args[0], divider_example())

    def test_missing_tk_and_missing_display_are_clean_command_errors(self):
        from circuit_calculator.cli import main
        for failure in (ImportError('no Tk'), ValueError('Cannot initialize a Tk display')):
            output, errors = io.StringIO(), io.StringIO()
            with self.subTest(failure=failure), patch('circuit_calculator.gui.launch', side_effect=failure), redirect_stdout(output), redirect_stderr(errors):
                self.assertEqual(main(['gui']), 1)
            self.assertEqual(output.getvalue(), '')
            self.assertIn('Tk', errors.getvalue())
            self.assertNotIn('Traceback', errors.getvalue())


if __name__ == '__main__':
    unittest.main()
