"""Bend edits and Manhattan conversion preserve electrical endpoint identities."""

import importlib.util
import unittest

from circuit_calculator.schematic import Waypoint, EditorSession, orthogonal_bends, placed_divider_example
from circuit_calculator.project_io import SchematicProject, dumps_project, loads_project


class BendEditingTests(unittest.TestCase):
    def test_hand_derived_horizontal_and_vertical_first_routes(self):
        anchors = ((0, 0), (20, 40), (100, 100))
        self.assertEqual(orthogonal_bends(anchors), (Waypoint(20, 0), Waypoint(20, 40), Waypoint(100, 40)))
        self.assertEqual(orthogonal_bends(anchors, horizontal_first=False),
                         (Waypoint(0, 40), Waypoint(20, 40), Waypoint(20, 100)))

    def test_duplicates_collinear_points_and_backtracking(self):
        self.assertEqual(orthogonal_bends(((0, 0), (0, 0), (20, 0), (50, 0), (100, 0))), ())
        self.assertEqual(orthogonal_bends(((0, 0), (100, 0), (20, 0), (200, 0))),
                         (Waypoint(100, 0), Waypoint(20, 0)))
        self.assertEqual(orthogonal_bends(((0, 0), (0, 100), (100, 100))), (Waypoint(0, 100),))
        self.assertEqual(orthogonal_bends(((2, 3), (2, 3))), ())

    def test_geometry_input_validation(self):
        for points in ((), ((0, 0),), ((0, 0), (True, 1)), ((0, 0), (float('inf'), 1)),
                       ((0, 0), (100001, 1))):
            with self.subTest(points=points), self.assertRaises((ValueError, TypeError)):
                orthogonal_bends(points)
        with self.assertRaises(TypeError):
            orthogonal_bends(((0, 0), (1, 1)), horizontal_first=1)

    def test_insert_move_remove_preserve_electrical_state_and_exact_endpoints(self):
        original = placed_divider_example()
        state = original.insert_wire_bend('W1', 0, 300, 420)
        self.assertEqual(state.wires[0].bends, (Waypoint(300, 420),))
        moved = state.move_wire_bend('W1', 0, 300, 500)
        self.assertEqual(moved.wires[0].bends, (Waypoint(300, 500),))
        self.assertEqual(moved.document, original.document)
        self.assertEqual(moved.compile(), original.compile())
        self.assertEqual(moved.remove_wire_bend('W1', 0), original)

    def test_bend_insert_order_at_first_middle_and_last_segment(self):
        state = placed_divider_example().route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500)))
        for index in range(3):
            edited = state.insert_wire_bend('W1', index, 300, 600)
            self.assertEqual(edited.wires[0].bends[index], Waypoint(300, 600))
            self.assertEqual(edited.remove_wire_bend('W1', index), state)

    def test_invalid_edit_indices_coordinates_and_endpoint_insert_rollback(self):
        state = placed_divider_example().route_wire('W1', (Waypoint(300, 500),))
        session = EditorSession(state)
        for edit in (lambda: state.move_wire_bend('W1', True, 0, 0),
                     lambda: state.move_wire_bend('W1', -1, 0, 0),
                     lambda: state.move_wire_bend('W1', 1, 0, 0),
                     lambda: state.move_wire_bend('missing', 0, 0, 0),
                     lambda: state.move_wire_bend('W1', 0, 100001, 0),
                     lambda: state.remove_wire_bend('W1', 1),
                     lambda: state.insert_wire_bend('W1', 2, 0, 0),
                     lambda: state.insert_wire_bend('W1', 0, 500, 420)):
            with self.assertRaises(ValueError):
                session.apply(edit())
            self.assertEqual(session.state, state)
            self.assertEqual(session.revision, 0)

    def test_colocated_bends_remain_legal_after_movement(self):
        state = placed_divider_example().route_wire('W1', (Waypoint(300, 500), Waypoint(160, 500)))
        moved = state.move_wire_bend('W1', 0, 160, 500)
        self.assertEqual(moved.wires[0].bends, (Waypoint(160, 500), Waypoint(160, 500)))
        self.assertEqual(moved.compile(), state.compile())

    def test_conversion_has_axis_aligned_segments_and_preserves_identity(self):
        state = placed_divider_example().route_wire('W1', (Waypoint(600, 550), Waypoint(100, 550)))
        for order in (True, False):
            converted = state.orthogonalize_wire('W1', horizontal_first=order)
            points = converted.wire_points('W1')
            self.assertTrue(all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:])))
            self.assertEqual((points[0], points[-1]), (state.wire_points('W1')[0], state.wire_points('W1')[-1]))
            self.assertEqual(converted.document, state.document)
            self.assertEqual(converted.compile(), state.compile())
            self.assertEqual(converted.orthogonalize_wire('W1', horizontal_first=order), converted)

    def test_conversion_failure_at_generated_bend_limit_is_atomic(self):
        bends = tuple(Waypoint(600 if i % 2 else 700, 200 + i * 10) for i in range(32))
        state = placed_divider_example().route_wire('W1', bends)
        session = EditorSession(state)
        with self.assertRaisesRegex(ValueError, '32 bends'):
            session.apply(state.orthogonalize_wire('W1'))
        with self.assertRaisesRegex(ValueError, '32 bends'):
            session.apply(state.insert_wire_bend('W1', 0, 900, 700))
        self.assertEqual(session.state, state)
        self.assertEqual(session.revision, 0)

    def test_conversion_is_geometry_not_a_persistent_constraint(self):
        state = placed_divider_example().move_node('g', 180, 460).orthogonalize_wire('W1')
        moved = state.move_node('g', 200, 480)
        self.assertEqual(moved.wires, state.wires)
        self.assertEqual(moved.compile(), state.compile())
        self.assertNotEqual(moved.wire_points('W1')[-2][0], moved.wire_points('W1')[-1][0])
        self.assertNotEqual(moved.wire_points('W1')[-2][1], moved.wire_points('W1')[-1][1])

    def test_history_and_existing_v3_round_trip(self):
        state = placed_divider_example().route_wire('W1', (Waypoint(300, 500),))
        session = EditorSession(state)
        session.apply(state.move_wire_bend('W1', 0, 300, 600))
        moved = session.state
        session.apply(moved.orthogonalize_wire('W1'))
        converted = session.state
        self.assertEqual(loads_project(dumps_project(SchematicProject(converted))).schematic, converted)
        session.undo()
        self.assertEqual(session.state, moved)
        session.undo()
        self.assertEqual(session.state, state)
        session.redo()
        session.redo()
        self.assertEqual(session.state, converted)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_independent_divider_after_all_bend_operations(self):
        from circuit_calculator.dc import solve_dc
        state = placed_divider_example().insert_wire_bend('W1', 0, 300, 500)
        state = state.move_wire_bend('W1', 0, 300, 600).orthogonalize_wire('W1')
        result = solve_dc(state.compile().circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 8)
        self.assertAlmostEqual(result.elements['V1'].power_watts, -.048)
        self.assertAlmostEqual(result.power_balance_watts, 0)


if __name__ == '__main__':
    unittest.main()
