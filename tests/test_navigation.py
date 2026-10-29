"""Stable search identities and geometry-only reveal points."""

from dataclasses import FrozenInstanceError, replace
import subprocess
import sys
import unittest

from circuit_calculator.circuit import Circuit
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.navigation import catalog_items, filter_items, selection_position
from circuit_calculator.project_io import SchematicProject, dumps_project
from circuit_calculator.schematic import Schematic, Wire, Waypoint, Position, placed_divider_example, divider_example


class NavigationTests(unittest.TestCase):
    def test_catalog_preserves_namespaces_order_and_immutable_identity(self):
        state = divider_example().rename('element', 'V1', 'g').rename('wire', 'W1', 'g')
        items = catalog_items(state)
        self.assertEqual([item.selection for item in items[:3]], [('element', 'g'), ('element', 'R1'), ('element', 'R2')])
        self.assertEqual([item.selection for item in filter_items(items, 'g')], [('element', 'g'), ('node', 'g'), ('wire', 'g')])
        with self.assertRaises(FrozenInstanceError):
            items[0].name = 'changed'
        self.assertEqual(filter_items(items, ''), items)

    def test_unicode_casefold_spaces_and_special_characters_are_literal(self):
        state = divider_example().rename('element', 'R1', 'Straße && ![قطعه]: 1')
        items = catalog_items(state)
        for query in ('STRASSE', '&&', '![', 'قطعه', ': 1', ' '):
            self.assertEqual([i.selection for i in filter_items(items, query)], [('element', 'Straße && ![قطعه]: 1')])
        self.assertEqual(filter_items(items, '^.*$'), ())
        self.assertEqual(filter_items(items, 'no such item'), ())

    def test_terminal_display_labels_do_not_replace_owned_node_identity(self):
        state = placed_divider_example()
        item, = filter_items(catalog_items(state), 'R1.a')
        self.assertEqual(item.kind, 'terminal')
        self.assertEqual(item.name, state.document.circuit.elements[1].node_a)
        self.assertNotEqual(item.name, item.label)
        self.assertEqual(selection_position(state, item.selection), state.placements[1].terminal_coordinates()[0])

    def test_component_and_node_positions_match_existing_geometry(self):
        for state in (divider_example(), placed_divider_example()):
            for element in state.document.circuit.elements:
                placement = state.component_placement(element.name)
                self.assertEqual(selection_position(state, ('element', element.name)), (placement.x, placement.y))
            for position in state.positions:
                kind = 'terminal' if position.node in state.terminal_owners() else 'node'
                self.assertEqual(selection_position(state, (kind, position.node)), (position.x, position.y))

    def test_wire_reveal_is_half_arc_length_not_bounding_box_center(self):
        state = Schematic(CircuitDocument(Circuit(('a', 'b'), ())),
                          (Position('a', 0, 0), Position('b', 100, 100)),
                          (Wire('W', 'a', 'b', (Waypoint(100, 0),)),))
        self.assertEqual(selection_position(state, ('wire', 'W')), (100, 0))
        state = state.route_wire('W', (Waypoint(0, 0), Waypoint(30, 40)))
        # 50-unit diagonal followed by sqrt(70**2+60**2); midpoint is on segment 2.
        x, y = selection_position(state, ('wire', 'W'))
        self.assertGreater(x, 30)
        self.assertGreater(y, 40)
        self.assertAlmostEqual((x - 30) / 70, (y - 40) / 60)

    def test_zero_length_paths_and_segments_have_defined_positions(self):
        state = Schematic(CircuitDocument(Circuit(('a', 'b'), ())),
                          (Position('a', 10, 20), Position('b', 10, 20)),
                          (Wire('W', 'a', 'b', (Waypoint(10, 20),)),))
        self.assertEqual(selection_position(state, ('wire', 'W')), (10, 20))
        state = state.move_node('b', 30, 20)
        self.assertEqual(selection_position(state, ('wire', 'W')), (20, 20))

    def test_unknown_malformed_and_wrong_owned_terminal_kind_are_rejected(self):
        state = placed_divider_example()
        terminal = next(iter(state.terminal_owners()))
        for selection in (None, [], ('node', 'missing'), ('element', 'missing'),
                          ('wire', 'missing'), ('node', terminal), ('terminal', 'g')):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                selection_position(state, selection)
        with self.assertRaises(TypeError):
            catalog_items(None)

    def test_query_bounds_and_unicode_validation(self):
        items = catalog_items(divider_example())
        for query in ('x' * 257, '\ud800'):
            with self.assertRaises(ValueError):
                filter_items(items, query)
        for query in (None, True, 3):
            with self.assertRaises(TypeError):
                filter_items(items, query)
        self.assertEqual(filter_items(items, 'x' * 256), ())

    def test_catalog_and_filter_work_at_current_editor_resource_limits(self):
        state = Schematic.from_document(CircuitDocument(Circuit(tuple(f'n{i}' for i in range(100)), ())))
        for index in range(1, 201):
            state = state.add_placed_component('resistor', f'R{index}', 1000 + index * 20, 2000, 1000)
        nodes = state.document.circuit.nodes
        pairs = list(zip(nodes, nodes[1:])) + list(zip(nodes[:301], nodes[2:303]))
        state = replace(state, wires=tuple(Wire(f'W{i}', *pair) for i, pair in enumerate(pairs)))
        items = catalog_items(state)
        self.assertEqual(len(state.document.circuit.nodes), 500)
        self.assertEqual(len(state.wires), 800)
        self.assertEqual(len(items), 1500)
        terminal, = filter_items(items, 'R200.a')
        self.assertEqual(terminal.kind, 'terminal')
        self.assertEqual(len(filter_items(items, 'R200')), 3)
        self.assertEqual(selection_position(state, ('element', 'R200')), (5000, 2000))

    def test_search_and_reveal_math_do_not_change_serialization_or_import_gui(self):
        state = placed_divider_example()
        serialized = dumps_project(SchematicProject(state))
        for item in catalog_items(state):
            selection_position(state, item.selection)
        self.assertEqual(dumps_project(SchematicProject(state)), serialized)
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; import circuit_calculator.navigation; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)


if __name__ == '__main__':
    unittest.main()
