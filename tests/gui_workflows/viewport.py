"""Viewport workflows; loaded only by the opt-in GUI runner."""

from unittest.mock import patch
from circuit_calculator.schematic import Waypoint, Position, Schematic
from circuit_calculator.circuit import Circuit
from circuit_calculator.circuit_io import CircuitDocument


class ViewportMixin:
    def test_action_buttons_are_reachable_at_minimum_window_size(self):
        self.root.deiconify()
        self.root.geometry('900x600')
        self.root.update()
        for name, button in self.app.buttons.items():
            with self.subTest(button=name):
                self.assertTrue(button.winfo_ismapped())
                self.assertGreaterEqual(button.winfo_rootx(), self.root.winfo_rootx())
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                     self.root.winfo_rootx() + self.root.winfo_width())
                self.assertGreater(button.winfo_width(), 40)
        self.assertGreater(self.app.canvas.winfo_height(), 150)

    def test_fit_uses_actual_circuit_bounds_and_keeps_labels_visible(self):
        self.settle_viewport()
        original, revision = self.app.session.state, self.app.session.revision
        self.app.fit_circuit()
        canvas = self.app.canvas
        bounds = canvas.bbox('circuit-content')
        left, top = canvas.canvasx(0), canvas.canvasy(0)
        self.assertGreaterEqual(bounds[0], left + 27)
        self.assertGreaterEqual(bounds[1], top + 27)
        self.assertLessEqual(bounds[2], left + canvas.winfo_width() - 27)
        self.assertLessEqual(bounds[3], top + canvas.winfo_height() - 27)
        self.assertGreater(canvas.bbox('all')[2], bounds[2], 'Decorative grid must not determine fit bounds')
        self.assertEqual(self.app.session.state, original)
        self.assertEqual(self.app.session.revision, revision)

    def test_zoom_and_100_percent_preserve_viewed_world_center(self):
        self.settle_viewport()
        original = self.world_center()
        self.app.change_zoom(1.25)
        for before, after in zip(original, self.world_center()):
            self.assertAlmostEqual(before, after, delta=3)
        self.app.set_zoom(1)
        for before, after in zip(original, self.world_center()):
            self.assertAlmostEqual(before, after, delta=3)
        before = self.app._snapshot()
        for factor in (True, 0, -1, float('nan'), float('inf')):
            self.app.change_zoom(factor)
            self.assertEqual(self.app._snapshot(), before)

    def test_resize_preserves_world_center_and_initial_layout_is_clean(self):
        self.settle_viewport()
        self.assertFalse(self.app.dirty)
        original = self.world_center()
        self.root.geometry('1050x700')
        self.settle_viewport()
        for before, after in zip(original, self.world_center()):
            self.assertAlmostEqual(before, after, delta=3)

    def test_fit_signed_and_extreme_geometry_has_bounded_zoom(self):
        self.settle_viewport()
        state = Schematic(CircuitDocument(Circuit(('a',), (), 'a')), (Position('a', -4000, -3000),))
        self.app._reset_document(state)
        self.app.fit_circuit()
        bounds = self.app._content_bounds
        center = self.world_center()
        self.assertLess(center[0], 0)
        self.assertLess(center[1], 0)
        self.assertAlmostEqual(center[0], (bounds[0] + bounds[2]) / 2 / self.app.zoom, delta=3)
        self.assertEqual(self.app.session.state, state)
        large = Schematic(CircuitDocument(Circuit(('a', 'b'), (), 'a')),
                          (Position('a', -100000, -100000), Position('b', 100000, 100000)))
        self.app._reset_document(large)
        self.app.fit_circuit()
        self.assertEqual(self.app.zoom, .4)
        self.assertIn('limit', self.app.status.get())
        self.assertEqual(self.app.session.state, large)

    def test_camera_actions_preserve_results_and_geometry_history(self):
        self.settle_viewport()
        self.app.simulate()
        self.wait_for_result()
        original, result, revision = self.app.session.state, self.app.session.result, self.app.session.revision
        self.app.fit_circuit()
        self.app.change_zoom(.8)
        self.app.set_zoom(1)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.session.revision, revision)
        self.app.undo()
        self.assertEqual(self.app.session.state, original)
        self.assertIs(self.app.session.result, result)

    def test_handles_and_pending_preview_do_not_change_content_bounds(self):
        self.settle_viewport()
        self.app._apply(self.app.session.state.route_wire('W1', (Waypoint(300, 500),)))
        original_bounds, region = self.app._content_bounds, self.app.canvas.cget('scrollregion')
        self.app.selected = ('wire', 'W1')
        self.app.draw()
        self.assertEqual(self.app._content_bounds, original_bounds)
        self.assertEqual(self.app.canvas.cget('scrollregion'), region)
        self.app.click(self.point(300, 500))
        self.app.motion(self.point(3000, 3000))
        self.assertEqual(self.app._content_bounds, original_bounds)
        self.assertEqual(self.app.canvas.cget('scrollregion'), region)
        self.app.cancel()

    def test_fit_view_project_round_trip(self):
        self.settle_viewport()
        self.app.fit_circuit()
        expected = self.app._snapshot()
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.assertTrue(self.app.save_project())
        self.app.set_zoom(.4)
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesnocancel', return_value=False):
            self.app.open_project()
        self.assertEqual(self.app.zoom, expected.view.zoom)
        self.assertAlmostEqual(self.app.canvas.xview()[0], expected.view.scroll_x, delta=.002)
        self.assertAlmostEqual(self.app.canvas.yview()[0], expected.view.scroll_y, delta=.002)
        self.assertFalse(self.app.dirty)

    def test_edit_controls_fit_minimum_window_width(self):
        self.root.geometry('900x600')
        self.root.deiconify()
        self.root.update()
        right = self.root.winfo_rootx() + self.root.winfo_width()
        for name, button in self.app.buttons.items():
            with self.subTest(button=name):
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), right)

    def test_zoom_keeps_electrical_document_and_updates_hit_targets(self):
        original = self.app.session.state
        self.app.change_zoom(1.25)
        self.app.click(self.node('out'))
        self.assertEqual(self.app.selected, ('node', 'out'))
        self.assertEqual(self.app.session.state, original)

    def test_undo_to_saved_state_clears_dirty_and_camera_changes_preserve_results(self):
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.save_project()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.assertTrue(self.app.dirty)
        self.app.undo()
        self.assertFalse(self.app.dirty)
        self.app.redo()
        self.assertTrue(self.app.dirty)
        self.app.undo()
        self.app.simulate()
        self.wait_for_result()
        result = self.app.session.result
        self.app.change_zoom(1.25)
        self.assertTrue(self.app.dirty)
        self.assertIs(self.app.session.result, result)
