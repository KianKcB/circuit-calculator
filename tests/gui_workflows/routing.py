"""Routing workflows; loaded only by the opt-in GUI runner."""

from unittest.mock import patch
from circuit_calculator.circuit_io import load_document
from circuit_calculator.schematic import Waypoint, divider_example
from circuit_calculator.project_io import load_project


class RoutingMixin:
    def test_bend_handle_drag_preview_commit_and_undo(self):
        self.bend_wire()
        original, revision = self.app.session.state, self.app.session.revision
        region = self.app.canvas.cget('scrollregion')
        self.assertEqual(self.app._hit(self.point(500, 500)), ('bend', ('W1', 0)))
        self.app.click(self.point(500, 500))
        self.app.motion(self.point(560, 540))
        self.assertEqual(self.app.session.state, original)
        self.assertEqual(self.app.canvas.cget('scrollregion'), region)
        self.app.release(self.point(560, 540))
        self.assertEqual(self.app.session.revision, revision + 1)
        self.assertEqual(self.app.session.state.wires[0].bends[0], Waypoint(560, 540))
        self.assertEqual(self.app.session.state.compile(), original.compile())
        self.app.undo()
        self.assertEqual(self.app.session.state, original)

    def test_bend_cancel_invalid_release_and_off_grid_click_preserve_state(self):
        self.bend_wire()
        original = self.app._snapshot()
        self.app.click(self.point(500, 500))
        self.app.motion(self.point(2000, 2000))
        self.app.cancel()
        self.assertEqual(self.app._snapshot(), original)
        self.app.selected = ('wire', 'W1')
        self.app.draw()
        self.app.click(self.point(500, 500))
        self.app.motion(self.point(560, 540))
        self.app.release(self.point(100100, 540))
        self.assertEqual(self.app._snapshot(), original)
        self.app._apply(self.app.session.state.move_wire_bend('W1', 0, 501.5, 500.25))
        off_grid, revision = self.app.session.state, self.app.session.revision
        point = self.point(501.5, 500.25)
        self.app.click(point)
        self.app.release(point)
        self.assertEqual(self.app.session.state, off_grid)
        self.assertEqual(self.app.session.revision, revision)

    def test_shift_insert_and_delete_bend_preserve_wire_and_undo(self):
        original = self.app.session.state
        self.app.click(self.point(330, 420))
        self.assertEqual(self.app.selected, ('wire', 'W1'))
        self.app.insert_bend_at(self.point(330, 423))
        self.assertEqual(self.app.session.state.wires[0].bends, (Waypoint(330, 420),))
        self.assertEqual(self.app.session.state.compile(), original.compile())
        self.app.delete()
        self.assertEqual(self.app.session.state, original)
        self.app.undo()
        self.assertEqual(self.app.session.state.wires[0].bends, (Waypoint(330, 420),))
        before = self.app.session.state
        self.app.selected = ('wire', 'W1')
        self.app.insert_bend_at(self.point(800, 800))
        self.assertEqual(self.app.session.state, before)

    def test_colon_unicode_bend_tags_and_zoomed_hit_target(self):
        name = 'wire:مدار:1'
        self.bend_wire(name)
        self.app.change_zoom(1.25)
        self.assertEqual(self.app._hit(self.point(500, 500)), ('bend', (name, 0)))
        self.app.click(self.point(500, 500))
        self.app.motion(self.point(540, 540))
        self.app.release(self.point(540, 540))
        self.assertEqual(self.app.session.state.wires[0].bends[0], Waypoint(540, 540))

    def test_right_angle_preview_matches_completion_and_does_not_connect_elbow_dot(self):
        self.angle_document()
        original = self.app._snapshot()
        self.app.click(self.node('a'))
        self.app.route_motion(self.node('b'))
        preview = self.app.canvas.coords(self.app.canvas.find_withtag('route-preview')[0])
        self.assertEqual(preview, [100, 100, 300, 100, 300, 300])
        self.assertEqual(self.app._snapshot(), original)
        self.app.click(self.node('b'))
        state = self.app.session.state
        self.assertEqual(state.wires[0].bends, (Waypoint(300, 100),))
        self.assertNotEqual(state.net_names()['unconnected'], state.net_names()['a'])
        self.assertEqual(self.app.canvas.coords(self.app.canvas.find_withtag('entity:wire:W1')[0]), preview)

    def test_space_changes_pending_elbow_order_without_committing(self):
        self.angle_document()
        self.app.click(self.node('a'))
        original = self.app.session.state
        self.app.toggle_route_order()
        self.assertFalse(self.app.horizontal_first)
        self.assertEqual(self.app.session.state, original)
        self.app.click(self.node('b'))
        self.assertEqual(self.app.session.state.wires[0].bends, (Waypoint(100, 300),))

    def test_routing_preference_preserves_saved_state_and_results(self):
        self.app.simulate()
        self.wait_for_result()
        original, result = self.app._snapshot(), self.app.session.result
        self.app.orthogonal.set(True)
        self.app.routing_style_changed()
        self.assertEqual(self.app._snapshot(), original)
        self.assertFalse(self.app.dirty)
        self.assertIs(self.app.session.result, result)

    def test_orthogonalize_selected_wire_and_generated_limit_rollback(self):
        self.app._apply(self.app.session.state.route_wire('W1', (Waypoint(300, 500),)))
        original = self.app.session.state
        self.app.selected = ('wire', 'W1')
        self.app.orthogonalize()
        points = self.app.session.state.wire_points('W1')
        self.assertTrue(all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:])))
        self.assertEqual(self.app.session.state.compile(), original.compile())
        self.app.undo()
        self.assertEqual(self.app.session.state, original)
        bends = tuple(Waypoint(600 if i % 2 else 700, 200 + i * 10) for i in range(32))
        self.app._apply(original.route_wire('W1', bends))
        before = self.app.session.state
        self.app.selected = ('wire', 'W1')
        self.app.orthogonalize()
        self.assertEqual(self.app.session.state, before)
        self.assertIn('32 bends', self.app.status.get())
        self.angle_document()
        before = self.app.session.state
        self.app.click(self.node('a'))
        for i in range(17):
            self.app.click(self.point(800 + (i % 2) * 20, 80 + i * 20))
        self.app.click(self.node('b'))
        self.assertEqual(self.app.session.state, before)
        self.assertEqual(self.app.pending, 'a')
        self.assertEqual(len(self.app.route_bends), 17)
        self.assertIn('32 bends', self.app.status.get())

    def test_route_bends_preview_completion_and_one_step_undo(self):
        original = self.app.session.state
        self.mode('wire')
        self.app.click(self.node('in'))
        self.app.click(self.point(300, 80))
        self.app.route_motion(self.point(500, 80))
        self.assertTrue(self.app.canvas.find_withtag('route-preview'))
        self.assertEqual(self.app.session.state, original)
        self.assertFalse(self.app.dirty)
        self.app.click(self.point(500, 80))
        self.app.click(self.node('out'))
        wire = self.app.session.state.wires[-1]
        self.assertEqual(wire.bends, (Waypoint(300, 80), Waypoint(500, 80)))
        self.assertIsNone(self.app.pending)
        self.assertFalse(self.app.canvas.find_withtag('route-preview'))
        coords = self.app.canvas.coords(self.app.canvas.find_withtag('entity:wire:' + wire.name)[0])
        self.assertEqual(len(coords), 8)
        self.app.undo()
        self.assertEqual(self.app.session.state, original)

    def test_cancel_and_backspace_preserve_saved_graph_view_and_result(self):
        self.app.simulate()
        self.wait_for_result()
        original, result = self.app._snapshot(), self.app.session.result
        self.mode('wire')
        self.app.click(self.node('in'))
        self.app.click(self.point(300, 80))
        self.app.click(self.point(400, 80))
        self.app.remove_bend()
        self.assertEqual(self.app.route_bends, [Waypoint(300, 80)])
        # A distant preview must never expand the persistent scroll region.
        self.app.route_motion(self.point(10000, 10000))
        self.app.cancel()
        self.assertEqual(self.app._snapshot(), original)
        self.assertIs(self.app.session.result, result)
        self.assertFalse(self.app.dirty)
        self.assertFalse(self.app.canvas.find_withtag('route-preview'))

    def test_reroute_straighten_and_wrong_end_preserve_connections(self):
        original = self.app.session.state
        self.app.selected = ('wire', 'W1')
        self.app.reroute_wire()
        self.app.click(self.point(500, 500))
        self.app.click(self.point(160, 500))
        self.app.click(self.node('in'))
        self.assertEqual(self.app.session.state, original)
        self.assertEqual(self.app.routing_wire, 'W1')
        self.assertIn('original ending', self.app.status.get())
        self.app.click(self.node('g'))
        self.assertEqual(self.app.session.state.compile(), original.compile())
        self.assertEqual(self.app.session.state.wires[0].bends, (Waypoint(500, 500), Waypoint(160, 500)))
        self.app.straighten_wire()
        self.assertEqual(self.app.session.state, original)
        self.app.undo()
        self.assertEqual(len(self.app.session.state.wires[0].bends), 2)

    def test_bend_limit_keeps_pending_route_and_document_unchanged(self):
        original = self.app.session.state
        self.mode('wire')
        self.app.click(self.node('in'))
        for i in range(32):
            self.app.click(self.point(800 + (i % 2) * 20, 80))
        self.app.click(self.point(900, 80))
        self.assertEqual(len(self.app.route_bends), 32)
        self.assertEqual(self.app.pending, 'in')
        self.assertEqual(self.app.session.state, original)
        self.assertIn('32 bends', self.app.status.get())
        self.app.cancel()

    def test_split_one_wire_at_crossing_then_explicitly_join_other(self):
        self.crossing()
        original = self.app.session.state
        self.mode('split')
        self.app.click(self.point(300, 300))
        self.assertEqual(self.app.session.state, original, 'Ambiguous split must not choose a wire')
        self.assertIn('intended wire', self.app.status.get())
        self.mode('select')
        self.app.click(self.point(200, 300))
        self.assertEqual(self.app.selected, ('wire', 'H'))
        self.mode('split')
        self.app.click(self.point(300, 300))
        first = self.app.session.state
        junction = first.document.circuit.nodes[-1]
        self.assertEqual(first.compile(), original.compile())
        self.assertNotEqual(first.net_names()['a'], first.net_names()['c'])
        self.mode('select')
        self.app.click(self.point(300, 200))
        self.assertEqual(self.app.selected, ('wire', 'V'))
        self.mode('split')
        self.app.click(self.node(junction))
        self.assertEqual(set(self.app.session.state.net_names().values()), {'a'})
        self.app.undo()
        self.assertEqual(self.app.session.state, first)
        self.app.undo()
        self.assertEqual(self.app.session.state, original)

    def test_split_bent_wire_zoomed_away_from_nodes_and_bend_hit(self):
        self.app._apply(self.app.session.state.route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500))))
        original = self.app.session.state.compile()
        self.app.change_zoom(1.25)
        self.mode('split')
        self.app.click(self.point(300, 503))
        self.assertEqual(self.app.session.state.compile(), original)
        junction = self.app.session.state.positions[-1]
        self.assertAlmostEqual(junction.x, 300)
        self.assertAlmostEqual(junction.y, 500)
        self.mode('select')
        self.app.click(self.point(500, 500))
        self.assertEqual(self.app.selected, ('wire', 'W1'))

    def test_split_at_endpoint_rejected_and_component_terminal_protected(self):
        self.crossing()
        original = self.app.session.state
        self.mode('split')
        self.app.click(self.node('a'))
        self.assertEqual(self.app.session.state, original)
        self.assertIn('endpoints', self.app.status.get())
        self.app._apply(original.add_placed_component('resistor', 'R', 360, 300, 1))
        original = self.app.session.state
        terminal = original.document.circuit.elements[0].node_a
        self.app.click(self.node(terminal))
        self.assertEqual(self.app.session.state, original)
        self.assertIn('component terminal', self.app.status.get())

    def test_deleting_wire_cancels_pending_reroute(self):
        self.app.selected = ('wire', 'W1')
        self.app.reroute_wire()
        self.app.delete()
        self.assertIsNone(self.app.routing_wire)
        self.assertIsNone(self.app.pending)
        self.app.click(self.node('out'))
        self.assertEqual(self.app.pending, 'out')

    def test_routed_split_project_reopen_and_electrical_export(self):
        self.app._apply(self.app.session.state.route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500))))
        self.mode('split')
        self.app.click(self.point(300, 500))
        expected = self.app.session.state
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.assertTrue(self.app.save_project())
        self.assertEqual(load_project(path).schematic, expected)
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
            self.app.open_project()
        self.assertEqual(self.app.session.state, expected)
        self.assertFalse(self.app.dirty)
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('out: 8', self.app.results.get('1.0', 'end'))
        exported = path.with_name('electrical.json')
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(exported)):
            self.app.export()
        self.assertEqual(load_document(exported), divider_example().compile())
