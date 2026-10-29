"""Navigation workflows; loaded only by the opt-in GUI runner."""

from unittest.mock import patch
from circuit_calculator.schematic import Waypoint, divider_example
from circuit_calculator.project_io import load_project


class NavigationMixin:
    def test_find_dialog_disambiguates_equal_namespaces(self):
        self.app._apply(self.app.session.state.rename('element', 'V1', 'g').rename('wire', 'W1', 'g'))
        original, revision = self.app.session.state, self.app.session.revision
        def choose(dialog):
            dialog.query.set('g')
            rows = dialog.tree.get_children()
            self.assertEqual([dialog.tree.item(row, 'values')[0] for row in rows], ['Component', 'Junction', 'Wire'])
            dialog.tree.selection_set(rows[1])
            dialog.show_button.invoke()
        self.drive_find(choose)
        self.assertEqual(self.app.selected, ('node', 'g'))
        self.assertIs(self.app.session.state, original)
        self.assertEqual(self.app.session.revision, revision)

    def test_find_no_match_query_limit_and_correction_keep_dialog_open(self):
        def choose(dialog):
            dialog.query.set('no such thing')
            self.assertFalse(dialog.tree.get_children())
            self.assertTrue(dialog.show_button.instate(['disabled']))
            dialog.ok()
            self.assertTrue(dialog.winfo_exists())
            dialog.query.set('x' * 257)
            self.assertIn('256', dialog.status.get())
            dialog.query.set('R1')
            self.assertEqual(len(dialog.tree.get_children()), 1)
            self.assertFalse(dialog.show_button.instate(['disabled']))
            dialog.show_button.invoke()
        self.drive_find(choose)
        self.assertEqual(self.app.selected, ('element', 'R1'))

    def test_find_cancel_preserves_view_result_selection_and_clipboard(self):
        self.root.deiconify()
        self.root.update()
        self.select_component('R1')
        self.app.copy_selected()
        self.app.simulate()
        self.wait_for_result()
        before, result, clipboard, revision = self.app._snapshot(), self.app.session.result, self.app.clipboard, self.app.session.revision
        def cancel(dialog):
            dialog.query.set('R2')
            dialog.cancel_button.focus_force()
            self.root.update()
            dialog.cancel_button.event_generate('<Return>', when='tail')
            self.root.update()
        self.drive_find(cancel)
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.selected, ('element', 'R1'))
        self.assertIs(self.app.session.result, result)
        self.assertIs(self.app.clipboard, clipboard)
        self.assertEqual(self.app.session.revision, revision)

    def test_find_reveal_centers_existing_node_without_circuit_history(self):
        self.root.deiconify()
        self.root.update()
        self.app._apply(self.app.session.state.move_node('out', 2000, 160))
        self.app.simulate()
        self.wait_for_result()
        original, result, revision, zoom = self.app.session.state, self.app.session.result, self.app.session.revision, self.app.zoom
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.save_project()
        def choose(dialog):
            dialog.query.set('out')
            dialog.entry.focus_force()
            self.root.update()
            dialog.entry.event_generate('<Return>', when='tail')
            self.root.update()
        self.drive_find(choose)
        self.assertEqual(self.app.selected, ('node', 'out'))
        self.assertIs(self.app.session.state, original)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.session.revision, revision)
        self.assertEqual(self.app.zoom, zoom)
        self.assertAlmostEqual(self.app.canvas.canvasx(self.app.canvas.winfo_width() / 2) / zoom, 2000, delta=2/zoom)
        self.assertAlmostEqual(self.app.canvas.canvasy(self.app.canvas.winfo_height() / 2) / zoom, 160, delta=2/zoom)
        self.assertTrue(self.app.dirty)
        self.assertIn('Net voltage: 8 V', self.inspection_text())
        found = self.app._snapshot()
        self.app.reveal_item(('node', 'out'))
        self.assertEqual(self.app._snapshot(), found)
        self.app.save_project()
        self.assertEqual(load_project(path).schematic, original)
        self.app.undo()
        self.assertEqual(self.app.session.state, divider_example())

    def test_find_revalidates_current_state_and_unknown_selection_keeps_pending_copy(self):
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        self.app.paste()
        before = self.app._snapshot()
        with patch('circuit_calculator.editor_dialogs.ask_find_item', return_value=('node', 'missing')):
            self.app.find_item()
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.mode, 'paste')
        def changed(parent, state):
            self.app._apply(state.rename('node', 'out', 'output'))
            return ('node', 'output')
        with patch('circuit_calculator.editor_dialogs.ask_find_item', side_effect=changed):
            self.app.find_item()
        self.assertEqual(self.app.selected, ('node', 'output'))
        self.assertIn('output', self.app.session.state.document.circuit.nodes)
        self.assertNotIn('out', self.app.session.state.document.circuit.nodes)

    def test_find_wire_reveal_centers_polyline_and_cancels_pending_route(self):
        self.root.deiconify()
        self.root.update()
        self.app._apply(self.app.session.state.route_wire('W1', (Waypoint(700, 420), Waypoint(700, 700), Waypoint(160, 700))))
        self.app.simulate()
        self.wait_for_result()
        result, original = self.app.session.result, self.app.session.state
        self.mode('wire')
        self.app.click(self.node('out'))
        self.app.reveal_item(('wire', 'W1'))
        # Path length 200+280+540+280=1300; halfway is 170 left of (700,700).
        self.assertAlmostEqual(self.app.canvas.canvasx(self.app.canvas.winfo_width()/2)/self.app.zoom, 530, delta=2/self.app.zoom)
        self.assertAlmostEqual(self.app.canvas.canvasy(self.app.canvas.winfo_height()/2)/self.app.zoom, 700, delta=2/self.app.zoom)
        self.assertEqual(self.app.mode, 'select')
        self.assertIsNone(self.app.pending)
        self.assertIs(self.app.session.result, result)
        self.assertIs(self.app.session.state, original)

    def test_find_special_names_keyboard_list_and_shortcut_scope(self):
        name = '[R] && !x || قطعه ' + 'Z' * 200
        self.app._apply(self.app.session.state.rename('element', 'R1', name))
        def choose(dialog):
            dialog.query.set('&&')
            self.assertEqual(len(dialog.tree.get_children()), 1)
            dialog.tree.column('name', width=1800)
            self.root.update_idletasks()
            dialog.tree.xview_moveto(1)
            self.root.update()
            self.assertGreater(dialog.tree.xview()[0], 0)
            dialog.entry.focus_force()
            self.root.update()
            dialog.entry.event_generate('<Down>', when='tail')
            self.root.update()
            self.assertIs(dialog.focus_get(), dialog.tree)
            dialog.tree.event_generate('<Return>', when='tail')
            self.root.update()
        self.drive_find(choose)
        self.assertEqual(self.app.selected, ('element', name))
        self.assertIn(name, self.inspection_text())
        with patch.object(self.app, 'find_item') as find:
            self.send_shortcut(self.app.canvas, 'f', 70)
            self.send_shortcut(self.app.inspection, 'f', 70)
            self.assertEqual(find.call_count, 2)
            self.send_shortcut(self.app.canvas, 'f', 70, 0x20004)
            self.assertEqual(find.call_count, 2)
