"""Placed geometry must never implicitly change electrical connectivity."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import unittest

from circuit_calculator.circuit import Circuit, CurrentSource, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.schematic import (ComponentPlacement, EditorSession, Position, Schematic,
                                          Wire, divider_example, placed_divider_example, terminals)
from circuit_calculator.project_io import SchematicProject, ProjectFormatError, dumps_project, loads_project, load_project


class ComponentEditingTests(unittest.TestCase):
    def test_free_placement_allocates_stable_dedicated_nodes(self):
        state = Schematic.from_document(CircuitDocument(Circuit(('terminal_1',), ())))
        state = state.add_placed_component('resistor', 'R1', 300, 200, 1000)
        element = state.document.circuit.elements[0]
        self.assertEqual(terminals(element), ('terminal_2', 'terminal_3'))
        self.assertEqual(state.endpoint_label('terminal_2'), 'R1.a')
        self.assertEqual(state.placements[0].terminal_coordinates(), ((240, 200), (360, 200)))
        self.assertEqual(state.wires, ())

    def test_four_rotations_preserve_terminals_wires_and_polarity(self):
        state = placed_divider_example()
        original = state
        for angle in (90, 180, 270, 0):
            state = state.rotate_component('R1')
            self.assertEqual(state.component_placement('R1').rotation, angle)
            self.assertEqual(state.wires, original.wires)
            self.assertEqual(state.document, original.document)
            self.assertEqual(state.compile(), original.compile())
        self.assertEqual(state, original)

    def test_move_keeps_wires_attached_and_coordinate_collisions_do_not_connect(self):
        state = placed_divider_example()
        moved = state.move_component('R1', 160, 290)
        self.assertEqual(moved.wires, state.wires)
        self.assertEqual(moved.compile(), state.compile())
        first, second = terminals(moved.document.circuit.elements[1])
        positions = {p.node: (p.x, p.y) for p in moved.positions}
        self.assertEqual(positions[first], (100, 290))
        self.assertEqual(positions[second], (220, 290))
        self.assertNotEqual(moved.net_names()[first], moved.net_names()[second])

    def test_existing_component_conversion_preserves_all_source_orientations(self):
        circuit = Circuit(('g', 'a', 'b'), (VoltageSource('V', 'a', 'g', -5),
            Resistor('R', 'a', 'b', 2), CurrentSource('I', 'g', 'b', -1)), 'g')
        original = Schematic.from_document(CircuitDocument(circuit))
        state = original
        for index, name in enumerate(('V', 'R', 'I')):
            state = state.move_component(name, 200 + index * 160, 200)
            self.assertEqual(state.compile(), original.compile())
        self.assertEqual(len(state.wires), 6)

    def test_invalid_geometry_and_shared_terminals_are_rejected(self):
        for rotation in (True, 90.0, -90, 45, 360):
            with self.subTest(rotation=rotation), self.assertRaises(ValueError):
                ComponentPlacement('R', 0, 0, rotation)
        state = placed_divider_example()
        with self.assertRaisesRegex(ValueError, 'geometry'):
            replace(state, placements=(replace(state.placements[0], x=200), *state.placements[1:]))
        with self.assertRaises(ValueError):
            state.move_component('R1', 100000, 0)
        first = terminals(state.document.circuit.elements[0])[0]
        with self.assertRaisesRegex(ValueError, 'dedicated'):
            state.add_element(Resistor('shared', first, 'g', 2))

    def test_terminals_cannot_be_moved_or_deleted_independently(self):
        state = placed_divider_example()
        first = terminals(state.document.circuit.elements[0])[0]
        with self.assertRaisesRegex(ValueError, 'component body'):
            state.move_node(first, 0, 0)
        with self.assertRaisesRegex(ValueError, 'component body'):
            state.delete('node', first)

    def test_editor_limits_include_two_terminals_per_placed_component(self):
        state = Schematic.from_document(CircuitDocument(Circuit(tuple(f'n{i}' for i in range(100)), ())))
        for i in range(200):
            state = state.add_placed_component('resistor', f'R{i}', 200, 200, 1)
        self.assertEqual(len(state.document.circuit.nodes), 500)
        self.assertEqual(loads_project(dumps_project(SchematicProject(state))).schematic, state)
        with self.assertRaisesRegex(ValueError, 'limit'):
            state.add_node('extra', 0, 0)
        with self.assertRaisesRegex(ValueError, 'limit'):
            state.add_placed_component('resistor', 'extra', 200, 200, 1)

    def test_conversion_failure_at_wire_limit_is_atomic(self):
        state = Schematic.from_document(CircuitDocument(Circuit(tuple(f'n{i}' for i in range(100)),
            (Resistor('R', 'n0', 'n1', 1),))))
        pairs = [(f'n{i}', f'n{j}') for i in range(100) for j in range(i + 1, 100)][:800]
        state = replace(state, wires=tuple(Wire(f'W{i}', *pair) for i, pair in enumerate(pairs)))
        session = EditorSession(state)
        with self.assertRaisesRegex(ValueError, 'limit'):
            session.apply(state.rotate_component('R'))
        self.assertEqual(session.state, state)
        self.assertEqual(session.revision, 0)

    def test_last_component_deletion_requires_a_remaining_node(self):
        state = Schematic.from_document(CircuitDocument(Circuit(('n',), ())))
        state = state.add_placed_component('resistor', 'R', 200, 200, 1).delete('node', 'n')
        with self.assertRaisesRegex(ValueError, 'Add a junction'):
            state.delete('element', 'R')

    def test_delete_placed_component_removes_owned_nodes_wires_and_reference(self):
        state = placed_divider_example()
        removed = set(terminals(state.document.circuit.elements[0]))
        state = state.set_reference(next(iter(removed)))
        result = state.delete('element', 'V1')
        self.assertFalse(removed.intersection(result.document.circuit.nodes))
        self.assertIsNone(result.document.circuit.reference_node)
        self.assertTrue(all(not removed.intersection((w.first, w.second)) for w in result.wires))
        self.assertNotIn('V1', {p.element for p in result.placements})

    def test_conversion_and_move_undo_restore_exact_previous_state(self):
        session = EditorSession(divider_example())
        original = session.state
        session.apply(session.state.move_component('V1', 300, 300))
        session.undo()
        self.assertEqual(session.state, original)
        session.redo()
        self.assertEqual(session.state.compile(), original.compile())

    def test_v1_loading_preserves_graph_and_saves_as_current_version(self):
        fixture = Path(__file__).resolve().parents[1] / 'examples/divider.ccproj.json'
        # Installed verification copies tests away from the checkout: construct
        # the v1 shape as a fallback instead of requiring installed example data.
        v1 = json.loads(dumps_project(SchematicProject(divider_example())))
        del v1['layout']['placements']
        v1['version'] = 1
        for wire in v1['layout']['wires']:
            del wire['bends']
        project = loads_project(json.dumps(v1))
        self.assertEqual(project.schematic, divider_example())
        if fixture.exists():
            self.assertEqual(load_project(fixture).schematic, divider_example())
        self.assertEqual(json.loads(dumps_project(project))['version'], 3)
        for change in ('placements', 'wire_limit'):
            invalid = json.loads(json.dumps(v1))
            if change == 'placements':
                invalid['layout']['placements'] = []
            else:
                invalid['layout']['wires'] *= 401
            with self.subTest(change=change), self.assertRaises(ProjectFormatError):
                loads_project(json.dumps(invalid))

    def test_current_round_trip_preserves_placements_and_rejects_invalid_records(self):
        project = SchematicProject(placed_divider_example())
        text = dumps_project(project)
        self.assertEqual(loads_project(text), project)
        self.assertEqual(dumps_project(loads_project(text)), text)
        for change in ('missing', 'duplicate', 'unknown', 'rotation', 'extra', 'geometry'):
            data = json.loads(text)
            placements = data['layout']['placements']
            if change == 'missing':
                del data['layout']['placements']
            elif change == 'duplicate':
                placements.append(placements[0].copy())
            elif change == 'unknown':
                placements[0]['element'] = 'missing'
            elif change == 'rotation':
                placements[0]['rotation'] = 90.0
            elif change == 'extra':
                placements[0]['unexpected'] = 1
            else:
                placements[0]['x'] += 20
            with self.subTest(change=change), self.assertRaises(ProjectFormatError):
                loads_project(json.dumps(data))

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_placed_rotated_project_retains_analytical_divider(self):
        from circuit_calculator.dc import solve_dc
        state = placed_divider_example().rotate_component('V1').move_component('R2', 600, 400)
        result = solve_dc(loads_project(dumps_project(SchematicProject(state))).schematic.compile().circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 8)
        self.assertAlmostEqual(result.elements['V1'].power_watts, -.048)
        self.assertAlmostEqual(result.power_balance_watts, 0)


if __name__ == '__main__':
    unittest.main()
