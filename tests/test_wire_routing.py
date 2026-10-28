"""Route geometry never implies connectivity; explicit splits own net changes."""

from dataclasses import FrozenInstanceError, replace
import importlib.util
import json
from pathlib import Path
import unittest

from circuit_calculator.circuit import Circuit
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.schematic import (Schematic, Position, Wire, Waypoint, EditorSession,
    divider_example, placed_divider_example)
from circuit_calculator.project_io import SchematicProject, ProjectFormatError, dumps_project, loads_project, load_project


def crossing():
    return Schematic(CircuitDocument(Circuit(('a', 'b', 'c', 'd'), (), 'a')),
        (Position('a', 0, 100), Position('b', 200, 100), Position('c', 100, 0), Position('d', 100, 200)),
        (Wire('H', 'a', 'b'), Wire('V', 'c', 'd')))


class WireRoutingTests(unittest.TestCase):
    def test_bends_are_owned_immutable_and_bounded(self):
        bends = [Waypoint(20, 40)]
        wire = Wire('W', 'a', 'b', bends)
        bends.clear()
        self.assertEqual(wire.bends, (Waypoint(20, 40),))
        with self.assertRaises(FrozenInstanceError):
            wire.bends[0].x = 2
        for bends in ('bad', [object()], [[1, 2]]):
            with self.subTest(bends=bends), self.assertRaises(TypeError):
                Wire('W', 'a', 'b', bends)
        for value in (True, '1', float('inf'), float('nan'), 100001, 10**1000):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                Waypoint(value, 0)
        self.assertEqual(len(Wire('W', 'a', 'b', [Waypoint(0, 0)] * 32).bends), 32)
        with self.assertRaisesRegex(ValueError, '32 bends'):
            Wire('W', 'a', 'b', [Waypoint(0, 0)] * 33)

    def test_reroute_and_straighten_preserve_endpoint_identity_and_physics(self):
        state = divider_example()
        routed = state.route_wire('W1', (Waypoint(600, 500), Waypoint(100, 500)))
        self.assertEqual(routed.compile(), state.compile())
        self.assertEqual(routed.document, state.document)
        self.assertEqual((routed.wires[0].first, routed.wires[0].second), ('return', 'g'))
        self.assertEqual(routed.wire_points('W1'), ((500, 420), (600, 500), (100, 500), (160, 420)))
        self.assertEqual(routed.route_wire('W1', ()), state)
        with self.assertRaisesRegex(ValueError, 'existing wire'):
            state.route_wire('missing', ())

    def test_movement_changes_only_endpoints_not_bends_or_connectivity(self):
        state = placed_divider_example().route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500)))
        moved = state.move_node('g', 200, 460).rotate_component('V1').move_component('R1', 400, 200)
        self.assertEqual(moved.wires, state.wires)
        self.assertEqual(moved.compile(), state.compile())
        self.assertEqual(moved.wire_points('W1')[-1], (200, 460))
        self.assertEqual(moved.wire_points('W1')[1:-1], ((500, 500), (160, 500)))

    def test_new_split_preserves_net_names_reference_and_exact_route(self):
        state = divider_example().route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500)))
        result = state.split_wire('W1', 1, 300, 500)
        junction = result.document.circuit.nodes[-1]
        self.assertEqual(junction, 'n1')
        self.assertEqual(result.wire_points('W1'), ((500, 420), (500, 500), (300, 500)))
        self.assertEqual(result.wire_points('W2'), ((300, 500), (160, 500), (160, 420)))
        self.assertEqual(result.compile(), state.compile())
        self.assertEqual(result.net_names()[junction], 'g')
        self.assertEqual(result.document.circuit.reference_node, 'g')

    def test_splitting_at_an_interior_bend_avoids_duplicate_bend(self):
        state = crossing().route_wire('H', (Waypoint(50, 100), Waypoint(50, 150)))
        for segment in (0, 1):
            result = state.split_wire('H', segment, 50, 100)
            self.assertEqual(result.wires[0].bends, ())
            self.assertEqual(result.wires[1].bends, (Waypoint(50, 150),))
            self.assertEqual(result.compile(), state.compile())

    def test_nearest_segment_handles_diagonal_and_degenerate_segments(self):
        state = crossing().route_wire('H', (Waypoint(0, 100), Waypoint(100, 200)))
        segment, point, distance = state.nearest_wire_segment('H', 60, 150)
        self.assertEqual(segment, 1)
        self.assertAlmostEqual(point[0], 55)
        self.assertAlmostEqual(point[1], 155)
        self.assertAlmostEqual(distance, 50 ** .5)
        split = state.split_wire('H', segment, *point)
        self.assertEqual(split.compile(), state.compile())
        with self.assertRaisesRegex(ValueError, 'endpoints'):
            state.split_wire('H', 1, 0, 100)
        zero = crossing().move_node('b', 0, 100)
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            zero.nearest_wire_segment('H', 0, 100)

    def test_crossings_and_coincident_dots_do_not_merge_without_reuse(self):
        state = crossing().add_node('existing', 100, 100)
        result = state.split_wire('H', 0, 100, 100)
        new_node = result.document.circuit.nodes[-1]
        self.assertNotEqual(new_node, 'existing')
        self.assertNotEqual(result.net_names()['existing'], result.net_names()[new_node])
        self.assertNotEqual(result.net_names()['c'], result.net_names()['a'])

    def test_explicit_crossing_join_and_delete_split(self):
        first = crossing().split_wire('H', 0, 100, 100)
        self.assertEqual(first.compile(), crossing().compile())
        junction = first.document.circuit.nodes[-1]
        joined = first.split_wire('V', 0, 100, 100, junction=junction)
        self.assertEqual(set(joined.net_names().values()), {'a'})
        separated = joined.delete('wire', 'V')
        self.assertNotEqual(separated.net_names()['c'], separated.net_names()['d'])
        self.assertEqual(separated.net_names()['a'], separated.net_names()['d'])

    def test_invalid_split_is_atomic(self):
        state = crossing()
        session = EditorSession(state)
        for name, segment, x, y, junction in (('bad', 0, 100, 100, None),
            ('H', True, 100, 100, None), ('H', -1, 100, 100, None), ('H', 1, 100, 100, None),
            ('H', 0, 100, 110, None), ('H', 0, 0, 100, None), ('H', 0, 200, 100, None),
            ('H', 0, 100, 100, 'missing'), ('H', 0, 100, 100, 'c'), ('H', 0, 0, 100, 'a')):
            with self.subTest(args=(name, segment, x, y, junction)), self.assertRaises(ValueError):
                session.apply(state.split_wire(name, segment, x, y, junction=junction))
            self.assertEqual(session.state, state)
            self.assertEqual(session.revision, 0)

    def test_split_cannot_reuse_component_terminal(self):
        state = crossing().add_placed_component('resistor', 'R', 160, 100, 1)
        terminal = state.document.circuit.elements[0].node_a
        with self.assertRaisesRegex(ValueError, 'free junction'):
            state.split_wire('H', 0, 100, 100, junction=terminal)

    def test_split_at_junction_and_wire_limits_rolls_back(self):
        state = Schematic.from_document(CircuitDocument(Circuit(tuple(f'n{i}' for i in range(100)), ())))
        state = state.add_wire(Wire('W', 'n0', 'n1'))
        with self.assertRaisesRegex(ValueError, 'limit'):
            state.split_wire('W', 0, 200, 140)
        pairs = [(f'n{i}', f'n{j}') for i in range(100) for j in range(i + 1, 100)][:800]
        state = replace(state, wires=tuple(Wire(f'W{i}', *pair) for i, pair in enumerate(pairs)))
        # Reuse a free node at the first wire's midpoint; no node-limit failure.
        state = state.move_node('n99', 240, 140)
        with self.assertRaisesRegex(ValueError, 'limit'):
            state.split_wire('W0', 0, 240, 140, junction='n99')
        self.assertEqual(len(state.wires), 800)

    def test_undo_redo_route_and_split_restores_exact_snapshots_and_invalidates_result(self):
        original = crossing()
        session = EditorSession(original)
        session.accept_result(0, object())
        session.apply(original.route_wire('H', (Waypoint(100, 100),)))
        routed = session.state
        session.apply(routed.split_wire('H', 0, 50, 100))
        split = session.state
        self.assertIsNone(session.result)
        session.undo()
        self.assertEqual(session.state, routed)
        session.undo()
        self.assertEqual(session.state, original)
        session.redo()
        session.redo()
        self.assertEqual(session.state, split)
        self.assertFalse(session.accept_result(0, object()))

    def test_v1_v2_load_without_bends_and_v3_round_trip(self):
        for version, state, fixture in ((1, divider_example(), 'divider.ccproj.json'),
            (2, placed_divider_example(), 'placed-divider.ccproj.json')):
            data = json.loads(dumps_project(SchematicProject(state)))
            data['version'] = version
            if version == 1:
                del data['layout']['placements']
            for wire in data['layout']['wires']:
                del wire['bends']
            loaded = loads_project(json.dumps(data))
            self.assertEqual(loaded.schematic, state)
            path = Path(__file__).resolve().parents[1] / 'examples' / fixture
            if path.exists():
                self.assertEqual(load_project(path).schematic, state)
            data['layout']['wires'][0]['bends'] = []
            with self.assertRaises(ProjectFormatError):
                loads_project(json.dumps(data))
        project = SchematicProject(placed_divider_example().route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500))))
        text = dumps_project(project)
        self.assertEqual(json.loads(text)['version'], 3)
        self.assertEqual(loads_project(text), project)
        self.assertEqual(dumps_project(loads_project(text)), text)

    def test_strict_bend_schema_and_numeric_failures(self):
        for bad in (None, 'bends', {}, [{'x': 1}], [{'x': 1, 'y': 2, 'extra': 3}],
            [{'x': True, 'y': 0}], [{'x': 100001, 'y': 0}], [{'x': float('nan'), 'y': 0}],
            [{'x': 0, 'y': 0}] * 33):
            data = json.loads(dumps_project(SchematicProject(divider_example())))
            data['layout']['wires'][0]['bends'] = bad
            with self.subTest(bad=bad), self.assertRaises(ProjectFormatError):
                loads_project(json.dumps(data))
        text = dumps_project(SchematicProject(divider_example().route_wire('W1', (Waypoint(1, 2),))))
        with self.assertRaises(ProjectFormatError):
            loads_project(text.replace('"x": 1.0', '"x": 1e-1000'))
        data = json.loads(text)
        del data['layout']['wires'][0]['bends']
        with self.assertRaises(ProjectFormatError):
            loads_project(json.dumps(data))

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'optional NumPy DC dependency missing')
    def test_routed_split_save_load_preserves_independent_divider_answer(self):
        from circuit_calculator.dc import solve_dc
        state = placed_divider_example().route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500)))
        state = state.split_wire('W1', 1, 300, 500)
        result = solve_dc(loads_project(dumps_project(SchematicProject(state))).schematic.compile().circuit)
        self.assertAlmostEqual(result.node_voltages['out'], 8)
        self.assertAlmostEqual(result.elements['R1'].current_amperes, .004)
        self.assertAlmostEqual(result.elements['V1'].power_watts, -.048)
        self.assertAlmostEqual(result.power_balance_watts, 0)


if __name__ == '__main__':
    unittest.main()
