"""Opt-in real Tk widget/workflow tests. Requires a desktop display and [dc].

Run source: python -B scripts/check_gui.py
Run installed: python -I -B scripts/check_gui.py --installed
This script is separate from headless discovery so an optional GUI/display does
not turn core-only installations into skipped-test failures.
"""

from concurrent.futures import Future
import csv
import gc
import importlib.util
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

if '--installed' in sys.argv:
    sys.argv.remove('--installed')
    if not sys.flags.isolated:
        raise RuntimeError('Installed GUI checks require Python -I isolation')
    for module in ('circuit_calculator', 'circuit_calculator.gui', 'circuit_calculator.canvas_renderer',
                   'circuit_calculator.viewport', 'circuit_calculator.results_io', 'circuit_calculator.quantities',
                   'circuit_calculator.editor_dialogs', 'circuit_calculator.shortcuts', 'circuit_calculator.inspection',
                   'circuit_calculator.navigation',
                   'circuit_calculator.schematic', 'circuit_calculator.dc', 'circuit_calculator.project_io'):
        spec = importlib.util.find_spec(module)
        if spec is None or spec.origin is None or not Path(spec.origin).resolve().is_relative_to(Path(sys.prefix).resolve()):
            raise RuntimeError('GUI module did not come from installed environment: ' + module)
    print('Installed GUI module origins verified.', flush=True)
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk
from circuit_calculator.circuit_io import load_document
from circuit_calculator.dc import solve_dc
from circuit_calculator.gui import CircuitEditor
from circuit_calculator.schematic import Wire, Waypoint, Position, Schematic, divider_example
from circuit_calculator.circuit import Circuit
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.project_io import load_project, save_project, SchematicProject


class TkWorkflowTests(unittest.TestCase):
    def drive_find(self, action):
        self.drive_dialog('Find item', action)

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

    def select_component(self, name):
        position = self.app.session.state.component_placement(name)
        point = self.point(position.x, position.y)
        self.app.click(point)
        self.app.release(point)
        self.assertEqual(self.app.selected, ('element', name))

    def inspection_text(self):
        return self.app.inspection.get('1.0', 'end')

    def test_inspector_selection_then_solve_shows_oriented_component_results(self):
        before, revision = self.app._snapshot(), self.app.session.revision
        self.select_component('R1')
        self.assertEqual(self.app.result_tabs.select(), str(self.app.inspection_tab))
        self.assertIn('Resistance: 1 kΩ', self.inspection_text())
        self.assertIn('V(in) - V(out)', self.inspection_text())
        self.assertIn('No current DC result', self.inspection_text())
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.session.revision, revision)
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('Current: 4 mA', self.inspection_text())
        self.assertIn('Power: 16 mW (absorbed)', self.inspection_text())
        self.select_component('V1')
        self.assertIn('Current: -4 mA', self.inspection_text())
        self.assertIn('Power: -48 mW (delivered)', self.inspection_text())

    def test_inspector_edit_history_new_and_open_never_reuse_old_numbers(self):
        self.select_component('R1')
        self.app.simulate()
        self.wait_for_result()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.assertIn('Resistance: 2 kΩ', self.inspection_text())
        self.assertIn('No current DC result', self.inspection_text())
        self.assertNotIn('Power:', self.inspection_text())
        self.app.undo()
        self.assertIn('Select a component', self.inspection_text())
        self.select_component('R1')
        self.assertIn('No current DC result', self.inspection_text())
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.save_project()
        self.app.simulate()
        self.wait_for_result()
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
            self.app.open_project()
        self.assertIn('Select a component', self.inspection_text())
        self.assertIsNone(self.app.session.result)
        self.app.new()
        self.assertIn('Select a component', self.inspection_text())

    def test_inspector_pending_and_stale_worker_do_not_show_previous_result(self):
        self.select_component('R1')
        self.app.simulate()
        self.wait_for_result()
        result, future = self.app.session.result, Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.assertIn('Solving DC', self.inspection_text())
        self.assertNotIn('Power:', self.inspection_text())
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.assertIn('No current DC result', self.inspection_text())
        future.set_result(result)
        self.wait_for_result()
        self.assertNotIn('Power:', self.inspection_text())
        self.assertIsNone(self.app.session.result)

    def test_inspector_terminal_alias_and_wire_current_policy(self):
        self.app._apply(self.app.session.state.place_component('R1', 330, 160, 0))
        terminal = self.app.session.state.document.circuit.elements[1].node_a
        self.app.click(self.node(terminal))
        self.assertIn('Terminal: R1.a', self.inspection_text())
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('Resolved net: in', self.inspection_text())
        self.assertIn('Net voltage: 12 V', self.inspection_text())
        self.app.click(self.point(330, 420))
        self.assertEqual(self.app.selected, ('wire', 'W1'))
        self.assertIn('Net voltage: 0 V', self.inspection_text())
        self.assertIn('Wire current: not resolved', self.inspection_text())

    def test_inspector_camera_tabs_and_copy_preview_preserve_current_text(self):
        self.select_component('R1')
        self.app.simulate()
        self.wait_for_result()
        result, revision, text = self.app.session.result, self.app.session.revision, self.inspection_text()
        self.app.inspection.tag_add('sel', '1.0', '1.8')
        self.app.change_zoom(.8)
        self.assertEqual(self.inspection_text(), text)
        self.assertEqual(self.app.inspection.get('sel.first', 'sel.last'), 'Resistor')
        self.app.copy_selected()
        self.app.paste()
        self.app.route_motion(self.point(700, 400))
        self.assertEqual(self.inspection_text(), text)
        self.app.cancel()
        self.app.result_tabs.select(self.app.all_results_tab)
        self.app.result_tabs.select(self.app.inspection_tab)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.session.revision, revision)
        self.send_shortcut(self.app.inspection, 'z', 90)
        self.assertEqual(self.app.session.revision, revision)  # no history entry

    def test_result_views_scroll_and_tab_selection_is_not_project_data(self):
        self.root.deiconify()
        self.root.geometry('900x600')
        self.root.update()
        self.app.simulate()
        self.wait_for_result()
        before = self.app._snapshot()
        self.app.results.yview_moveto(1)
        self.root.update()
        self.assertGreaterEqual(self.app.results.yview()[1], .999)
        self.assertGreater(self.app.results.yview()[0], 0)
        self.app.result_tabs.select(self.app.inspection_tab)
        self.assertEqual(self.app._snapshot(), before)

    def send_shortcut(self, widget, key, windows_code, state=4):
        if widget is self.app.results:
            self.app.result_tabs.select(self.app.all_results_tab)
        elif widget is self.app.inspection:
            self.app.result_tabs.select(self.app.inspection_tab)
        self.root.deiconify()
        self.root.update()
        widget.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), widget)
        identity = {'keycode': windows_code} if sys.platform == 'win32' else {'keysym': key}
        widget.event_generate('<KeyPress>', state=state, when='tail', **identity)
        self.root.update()

    def test_shortcuts_rotate_fit_and_history_from_canvas_and_results(self):
        before = self.app.session.state
        self.app.selected = ('element', 'R1')
        self.send_shortcut(self.app.canvas, 'r', 82, 0)
        rotated = self.app.session.state
        self.assertNotEqual(rotated, before)
        self.assertEqual(rotated.compile(), before.compile())
        self.send_shortcut(self.app.canvas, 'z', 90)
        self.assertEqual(self.app.session.state, before)
        self.send_shortcut(self.app.results, 'Z', 90, 5)
        self.assertEqual(self.app.session.state, rotated)
        self.send_shortcut(self.app.results, 'z', 90)
        self.assertEqual(self.app.session.state, before)
        self.send_shortcut(self.app.canvas, 'y', 89)
        self.assertEqual(self.app.session.state, rotated)
        with patch.object(self.app, 'fit_circuit') as fit:
            self.send_shortcut(self.app.canvas, 'f', 70, 0)
            fit.assert_called_once()
            self.send_shortcut(self.app.results, 'f', 70, 0)
            fit.assert_called_once()

    def test_shortcuts_save_save_as_open_dispatch_once_and_ignore_altgr(self):
        with patch.object(self.app, 'save_project') as save, \
             patch.object(self.app, 'save_project_as') as save_as, \
             patch.object(self.app, 'open_project') as open_project:
            self.send_shortcut(self.app.canvas, 's', 83)
            save.assert_called_once()
            self.send_shortcut(self.app.results, 'S', 83, 5)
            save_as.assert_called_once()
            save.assert_called_once()
            self.send_shortcut(self.app.canvas, 'o', 79)
            open_project.assert_called_once()
            self.send_shortcut(self.app.canvas, 's', 83, 12)
            self.send_shortcut(self.app.results, 's', 83, 0x20004)
            save.assert_called_once()
            save_as.assert_called_once()

    def test_rotate_shortcut_rotates_pending_paste_without_changing_graph(self):
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        self.app.paste()
        before, template = self.app.session.state, self.app.clipboard
        self.send_shortcut(self.app.canvas, 'r', 82, 0)
        self.assertEqual(self.app.paste_template.rotation, 90)
        self.assertEqual(self.app.session.state, before)
        self.assertIs(self.app.clipboard, template)
        self.app.cancel()

    def test_global_shortcuts_do_not_escape_modal_form(self):
        def dialog_keys(dialog):
            with patch.object(self.app, 'undo') as undo, patch.object(self.app, 'save_project') as save:
                self.send_shortcut(dialog.title_entry, 'z', 90)
                self.send_shortcut(dialog.description, 's', 83)
                undo.assert_not_called()
                save.assert_not_called()
            dialog.cancel_button.invoke()
        self.drive_details(dialog_keys)

    def test_unhandled_result_copy_and_letters_do_not_change_document(self):
        self.app._text('A result to select')
        self.app.results.tag_add('sel', '1.0', '1.8')
        original, revision = self.app.session.state, self.app.session.revision
        # Returning None allows Tk's native Text copy/selection binding to run.
        self.assertIsNone(self.app._global_key(SimpleNamespace(keysym='c', keycode=67, state=4)))
        self.send_shortcut(self.app.results, 'r', 82, 0)
        self.assertEqual(self.app.session.state, original)
        self.assertEqual(self.app.session.revision, revision)
        self.assertEqual(self.app.results.get('sel.first', 'sel.last'), 'A result')

    def drive_details(self, action):
        self.drive_dialog('Project details', action)

    def drive_dialog(self, title, action):
        """Exercise the real modal form with a bounded cleanup on assertion failure."""
        self.root.deiconify()
        self.root.update()
        failures = []
        def dialog():
            candidates = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)
                          and w.title() == title]
            self.assertEqual(len(candidates), 1)
            return candidates[0]
        def respond():
            try:
                action(dialog())
            except BaseException as error:
                failures.append(error)
                for child in self.root.winfo_children():
                    if isinstance(child, tk.Toplevel):
                        child.cancel()
        def timeout():
            failures.append(AssertionError(title + ' dialog did not finish in five seconds'))
            for child in self.root.winfo_children():
                if isinstance(child, tk.Toplevel):
                    child.cancel()
        timer = self.root.after(5000, timeout)
        self.root.after(80, respond)
        try:
            self.app.buttons[title].invoke()
        finally:
            self.root.after_cancel(timer)
        if failures:
            raise failures[0]

    def test_real_project_details_apply_and_single_undo(self):
        before = self.app.session.state
        def enter(dialog):
            self.assertEqual(dialog.title_entry.get(), before.document.title)
            dialog.title_entry.delete(0, 'end')
            dialog.title_entry.insert(0, 'تقسیم ولتاژ')
            dialog.description.insert('end', 'Line 1\nخط دوم\n')
            dialog.apply_button.invoke()
        self.drive_details(enter)
        edited = self.app.session.state
        self.assertEqual(edited.document.title, 'تقسیم ولتاژ')
        self.assertEqual(edited.document.description, 'Line 1\nخط دوم\n')
        self.assertTrue(self.app.dirty)
        self.app.undo()
        self.assertEqual(self.app.session.state, before)
        self.app.redo()
        self.assertEqual(self.app.session.state, edited)
        self.app.simulate()
        self.wait_for_result()
        self.assertAlmostEqual(self.app.session.result.node_voltages['out'], 8)

    def test_real_project_details_cancel_and_noop_preserve_result(self):
        self.root.deiconify()
        self.root.update()
        self.app.simulate()
        self.wait_for_result()
        before, result, revision = self.app._snapshot(), self.app.session.result, self.app.session.revision
        def cancel(dialog):
            dialog.title_entry.insert('end', 'discard this')
            dialog.cancel_button.invoke()
        self.drive_details(cancel)
        self.drive_details(lambda dialog: dialog.apply_button.invoke())
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.session.revision, revision)
        self.assertIs(self.app.session.result, result)

    def test_real_project_details_invalid_fields_stay_open_and_can_be_corrected(self):
        revision = self.app.session.revision
        def validate(dialog):
            dialog.title_entry.delete(0, 'end')
            dialog.title_entry.insert(0, 'x' * 257)
            dialog.description.insert('end', 'keep this')
            dialog.apply_button.invoke()
            self.assertTrue(dialog.winfo_exists())
            self.assertIn('256', dialog.error.get())
            self.assertEqual(dialog.description.get('1.0', 'end-1c'), 'keep this')
            self.assertEqual(self.app.session.revision, revision)
            dialog.title_entry.delete(0, 'end')
            dialog.title_entry.insert(0, 'correct')
            dialog.description.delete('1.0', 'end')
            dialog.description.insert('1.0', 'x' * 4097)
            dialog.apply_button.invoke()
            self.assertIn('4096', dialog.error.get())
            self.assertEqual(dialog.title_entry.get(), 'correct')
            dialog.description.delete('1.0', 'end')
            dialog.apply_button.invoke()
        self.drive_details(validate)
        self.assertEqual(self.app.session.state.document.title, 'correct')
        self.assertEqual(self.app.session.state.document.description, '')
        self.assertEqual(self.app.session.revision, revision + 1)

    def test_real_project_details_description_enter_and_control_enter(self):
        def keyboard(dialog):
            dialog.description.focus_force()
            self.root.update()
            dialog.description.insert('1.0', 'first')
            dialog.description.mark_set('insert', 'end-1c')
            dialog.description.event_generate('<Return>', when='tail')
            self.root.update()
            self.assertTrue(dialog.winfo_exists())
            self.assertEqual(dialog.description.get('1.0', 'end-1c'), 'first\n')
            dialog.description.insert('insert', 'second')
            dialog.description.event_generate('<Control-Return>', when='tail')
            self.root.update()
        self.drive_details(keyboard)
        self.assertEqual(self.app.session.state.document.description, 'first\nsecond')

    def test_real_project_details_keyboard_focus_and_enter_on_cancel(self):
        before, revision = self.app.session.state, self.app.session.revision
        def keyboard(dialog):
            dialog.title_entry.focus_force()
            self.root.update()
            dialog.title_entry.event_generate('<Tab>', when='tail')
            self.root.update()
            self.assertIs(dialog.focus_get(), dialog.description)
            dialog.description.event_generate('<Control-Tab>', when='tail')
            self.root.update()
            self.assertIs(dialog.focus_get(), dialog.apply_button)
            dialog.cancel_button.focus_force()
            self.root.update()
            dialog.cancel_button.event_generate('<Return>', when='tail')
            self.root.update()
        self.drive_details(keyboard)
        self.assertEqual(self.app.session.state, before)
        self.assertEqual(self.app.session.revision, revision)

    def test_project_details_save_reopen_export_and_stale_worker(self):
        result, future = solve_dc(self.app.session.state.compile().circuit), Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        with patch('circuit_calculator.editor_dialogs.ask_project_details', return_value=('new title', 'new\nnotes')):
            self.app.edit_details()
        future.set_result(result)
        self.wait_for_result()
        self.assertIsNone(self.app.session.result)
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.save_project()
        self.assertEqual(load_project(path).schematic.document.title, 'new title')
        self.app._apply(self.app.session.state.set_metadata('temporary', ''))
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesnocancel', return_value=False):
            self.app.open_project()
        self.assertEqual(self.app.session.state.document.description, 'new\nnotes')
        self.assertFalse(self.app.dirty)
        exported = path.with_name('circuit.json')
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(exported)):
            self.app.export()
        self.assertEqual(load_document(exported).title, 'new title')

    def test_prefixed_value_edit_solves_known_divider_and_exports_base_units(self):
        self.app.selected = ('element', 'R1')
        with patch('tkinter.simpledialog.askstring', return_value='2kΩ'):
            self.app.edit_value()
        self.assertEqual(self.app.session.state.document.circuit.elements[1].resistance_ohms, 2000)
        self.app.simulate()
        self.wait_for_result()
        result = self.app.session.result
        self.assertAlmostEqual(result.node_voltages['out'], 6)
        self.assertAlmostEqual(result.elements['R1'].current_amperes, .003)
        self.assertAlmostEqual(result.elements['V1'].power_watts, -.036)
        text = self.app.results.get('1.0', 'end')
        self.assertIn('out: 6 V', text)
        self.assertIn('I 3 mA', text)
        self.assertIn('P -36 mW', text)
        path = self.project_path().with_suffix('.csv')
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.export_results()
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        current = next(r for r in rows if r['identifier'] == 'element:R1' and r['quantity'] == 'current')
        self.assertEqual(current['unit'], 'A')
        self.assertEqual(float(current['value']), result.elements['R1'].current_amperes)

    def test_prefixed_component_creation_uses_same_parser_for_free_and_junction_modes(self):
        self.mode('current')
        with patch('tkinter.simpledialog.askstring', side_effect=['I2', '-250uA']):
            self.app.click(self.point(800, 400))
        current = self.app.session.state.document.circuit.elements[-1]
        self.assertEqual(current.current_amperes, -.00025)
        self.mode('resistor')
        with patch('tkinter.simpledialog.askstring', side_effect=['Rx', '4.7 kohm']):
            self.app.click(self.node('out'))
            self.app.click(self.node('g'))
        self.assertEqual(self.app.session.state.document.circuit.elements[-1].resistance_ohms, 4700)

    def test_prefixed_editor_rejects_wrong_units_and_preserves_complete_initial_value(self):
        self.app._apply(self.app.session.state.change_value('R1', 1234.567891234567))
        self.app.simulate()
        self.wait_for_result()
        before, result, revision = self.app._snapshot(), self.app.session.result, self.app.session.revision
        self.app.selected = ('element', 'R1')
        for text in ('2mA', '2KΩ', '4k7', '1e-400Ω', '1e400kΩ'):
            with self.subTest(text=text), patch('tkinter.simpledialog.askstring', return_value=text):
                self.app.edit_value()
            self.assertEqual(self.app._snapshot(), before)
            self.assertIs(self.app.session.result, result)
            self.assertEqual(self.app.session.revision, revision)
        with patch('tkinter.simpledialog.askstring', side_effect=lambda *args, **kwargs: kwargs['initialvalue']) as dialog:
            self.app.edit_value()
            self.assertEqual(dialog.call_args.kwargs['initialvalue'], '1234.567891234567')
        self.assertEqual(self.app._snapshot(), before)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.session.revision, revision)

    def test_canvas_results_and_copy_preview_use_readable_quantities(self):
        labels = [self.app.canvas.itemcget(i, 'text') for i in self.app.canvas.find_withtag('entity:element:R1')
                  if self.app.canvas.type(i) == 'text']
        self.assertTrue(any('1 kΩ' in label for label in labels))
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('I 4 mA', self.app.results.get('1.0', 'end'))
        self.assertIn('P -48 mW', self.app.results.get('1.0', 'end'))
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        self.app.paste()
        self.app.route_motion(self.point(700, 400))
        labels = [self.app.canvas.itemcget(i, 'text') for i in self.app.canvas.find_withtag('paste-preview')
                  if self.app.canvas.type(i) == 'text']
        self.assertTrue(any('1 kΩ' in label for label in labels))
        self.app.cancel()

    def test_paste_rotation_changes_only_pending_copy(self):
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        original, template = self.app.session.state, self.app.clipboard
        self.app.paste()
        self.app.route_motion(self.point(700, 400))
        self.app.rotate()
        self.assertEqual(self.app.paste_template.rotation, 90)
        self.assertEqual(self.app.session.state, original)
        self.assertIs(self.app.clipboard, template)
        self.app.click(self.point(700, 400))
        self.assertEqual(self.app.session.state.placements[-1].rotation, 90)
        self.app.paste()
        self.assertEqual(self.app.paste_template.rotation, 0)
        self.app.cancel()

    def test_paste_tool_change_history_and_open_cancel_preview(self):
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        self.app._apply(self.app.session.state.change_value('R1', 500))
        self.app.paste()
        self.app.route_motion(self.point(700, 400))
        self.app.undo()
        self.assertEqual(self.app.mode, 'select')
        self.assertFalse(self.app.canvas.find_withtag('paste-preview'))
        self.app.paste()
        self.app.route_motion(self.point(700, 400))
        self.mode('wire')
        self.assertIsNone(self.app.paste_template)
        self.assertFalse(self.app.canvas.find_withtag('paste-preview'))
        self.app.paste()
        self.app.route_motion(self.point(700, 400))
        self.app.new()
        self.assertIsNone(self.app.paste_position)
        self.assertIsNone(self.app.paste_template)
        self.assertIsNotNone(self.app.clipboard)

    def test_canvas_copy_paste_duplicate_keyboard_bindings(self):
        self.root.deiconify()
        self.root.update()
        self.app.canvas.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), self.app.canvas)
        def send(key, windows_keycode):
            identity = {'keycode': windows_keycode} if sys.platform == 'win32' else {'keysym': key}
            self.app.canvas.event_generate('<KeyPress>', state=4, when='tail', **identity)
            self.root.update()
        self.app.selected = ('element', 'R1')
        if sys.platform == 'win32':
            self.app.canvas.event_generate('<Control-Alt-KeyPress>', keycode=67, when='tail')
            self.root.update()
            self.assertIsNone(self.app.clipboard)
        send('c', 67)
        self.assertIsNotNone(self.app.clipboard)
        send('v', 86)
        self.assertEqual(self.app.mode, 'paste')
        self.app.click(self.point(700, 400))
        send('d', 68)
        self.assertEqual(len(self.app.session.state.document.circuit.elements), 5)
        self.assertEqual(self.app.selected, ('element', 'R4'))

    def test_clipboard_key_dispatch_ignores_altgr_and_other_commands(self):
        self.app.selected = ('element', 'R1')
        self.assertIsNone(self.app._canvas_key(SimpleNamespace(keysym='c', keycode=67, state=12)))
        self.assertIsNone(self.app._canvas_key(SimpleNamespace(keysym='c', keycode=67, state=0x20004)))
        self.assertIsNone(self.app._canvas_key(SimpleNamespace(keysym='z', keycode=90, state=4)))
        self.assertIsNone(self.app.clipboard)

    def test_component_copy_preview_cancel_preserves_result_history_and_scroll(self):
        self.app.simulate()
        self.wait_for_result()
        before, revision, result = self.app._snapshot(), self.app.session.revision, self.app.session.result
        bounds = self.app.canvas.cget('scrollregion')
        self.app.selected = ('element', 'R1')
        self.app.buttons['Copy'].invoke()
        self.app.buttons['Paste'].invoke()
        self.app.route_motion(self.point(800, 400))
        items = self.app.canvas.find_withtag('paste-preview')
        self.assertTrue(items)
        self.assertTrue(all('circuit-content' not in self.app.canvas.gettags(i) for i in items))
        self.assertTrue(all(not any(tag.startswith('entity:') for tag in self.app.canvas.gettags(i)) for i in items))
        self.assertEqual(self.app.canvas.cget('scrollregion'), bounds)
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.session.revision, revision)
        self.assertIs(self.app.session.result, result)
        self.app.cancel()
        self.assertFalse(self.app.canvas.find_withtag('paste-preview'))
        self.assertEqual(self.app._snapshot(), before)
        self.assertIs(self.app.session.result, result)

    def test_paste_click_fresh_endpoints_selection_save_and_single_undo(self):
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        before = self.app.session.state
        self.app.paste()
        self.app.click(self.point(703, 403))
        state = self.app.session.state
        self.assertEqual(self.app.mode, 'select')
        self.assertEqual(self.app.selected, ('element', 'R3'))
        self.assertEqual((state.placements[-1].x, state.placements[-1].y), (700, 400))
        self.assertEqual(state.wires, before.wires)
        self.assertEqual(len(state.document.circuit.nodes), len(before.document.circuit.nodes) + 2)
        self.assertTrue(self.app.dirty)
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.save_project()
        self.assertEqual(load_project(path).schematic, state)
        self.app.undo()
        self.assertEqual(self.app.session.state, before)
        self.app.redo()
        self.assertEqual(self.app.session.state, state)

    def test_clipboard_snapshot_survives_source_edit_delete_and_document_boundary(self):
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        template = self.app.clipboard
        self.app._apply(self.app.session.state.change_value('R1', 222))
        self.app.delete()
        self.assertIs(self.app.clipboard, template)
        with patch('tkinter.messagebox.askyesnocancel', return_value=False):
            self.app.new()
        self.app.paste()
        self.app.click(self.point(400, 300))
        copied = self.app.session.state.document.circuit.elements[-1]
        self.assertEqual(copied.resistance_ohms, 1000)
        self.assertEqual(copied.name, 'R1')
        self.assertIs(self.app.clipboard, template)
        self.app.paste()
        self.app.click(self.point(400, 300))
        self.assertEqual(self.app.session.state.document.circuit.elements[-1].name, 'R2')

    def test_duplicate_offsets_selects_fresh_copy_without_changing_clipboard(self):
        self.app.selected = ('element', 'V1')
        self.app.copy_selected()
        template = self.app.clipboard
        self.app.selected = ('element', 'R2')
        self.app._apply(self.app.session.state.place_component('R2', 500, 300, 270))
        before = self.app.session.state
        self.app.buttons['Duplicate'].invoke()
        after = self.app.session.state
        self.assertEqual(self.app.selected, ('element', 'R3'))
        self.assertEqual((after.placements[-1].x, after.placements[-1].y, after.placements[-1].rotation), (540, 340, 270))
        self.assertIs(self.app.clipboard, template)
        self.assertEqual(after.wires, before.wires)
        self.app.undo()
        self.assertEqual(self.app.session.state, before)

    def test_copy_paste_duplicate_failures_are_atomic(self):
        before, revision = self.app._snapshot(), self.app.session.revision
        self.app.paste()
        self.assertEqual(self.app.mode, 'select')
        for selection in (None, ('node', 'out'), ('wire', 'W1')):
            self.app.selected = selection
            self.app.copy_selected()
            self.app.duplicate()
            self.assertIsNone(self.app.clipboard)
            self.assertEqual(self.app._snapshot(), before)
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        self.app.paste()
        self.app.route_motion(self.point(100000, 500))
        self.app.click(self.point(100000, 500))
        self.assertEqual(self.app.session.revision, revision)
        self.assertEqual(self.app._snapshot(), before)
        self.assertFalse(self.app.canvas.find_withtag('paste-preview'))
        self.app.cancel()
        self.app._apply(self.app.session.state.place_component('R1', 99940, 300, 0))
        before, revision = self.app._snapshot(), self.app.session.revision
        self.app.selected = ('element', 'R1')
        self.app.duplicate()
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.session.revision, revision)

    def test_committed_copy_rejects_pending_worker_result(self):
        result, future = solve_dc(self.app.session.state.compile().circuit), Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.app.selected = ('element', 'R1')
        self.app.duplicate()
        future.set_result(result)
        self.wait_for_result()
        self.assertIsNone(self.app.session.result)
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))

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

    def test_value_editor_reports_units_and_rejects_invalid_values_atomically(self):
        self.app.simulate()
        self.wait_for_result()
        before, result, revision = self.app._snapshot(), self.app.session.result, self.app.session.revision
        self.app.selected = ('element', 'R1')
        for text in (None, '', 'NaN', 'Infinity', '0', '-1', '1e-1000', '1e1000', '1000'):
            with self.subTest(text=text), patch('tkinter.simpledialog.askstring', return_value=text) as dialog:
                self.app.edit_value()
                self.assertIn('ohms', dialog.call_args.args[1])
            self.assertEqual(self.app._snapshot(), before)
            self.assertIs(self.app.session.result, result)
            self.assertEqual(self.app.session.revision, revision)
        self.app.selected = ('element', 'V1')
        with patch('tkinter.simpledialog.askstring', return_value='-12') as dialog:
            self.app.edit_value()
            self.assertIn('V(+) - V(-)', dialog.call_args.args[1])
        self.assertEqual(self.app.session.state.document.circuit.elements[0].voltage_volts, -12)
        self.app.undo()
        self.assertEqual(self.app.session.state, before.schematic)

    def test_rename_component_updates_canvas_history_and_saved_project(self):
        self.app._apply(self.app.session.state.place_component('R1', 320, 160, 0))
        self.app.simulate()
        self.wait_for_result()
        before = self.app.session.state
        self.app.selected = ('element', 'R1')
        with patch('tkinter.simpledialog.askstring', return_value='مقاومت: input'):
            self.app.buttons['Rename'].invoke()
        self.assertEqual(self.app.selected, ('element', 'مقاومت: input'))
        self.assertTrue(self.app.canvas.find_withtag('entity:element:مقاومت: input'))
        self.assertIsNone(self.app.session.result)
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))
        self.assertTrue(self.app.dirty)
        changed = self.app.session.state
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.save_project()
        self.assertEqual(load_project(path).schematic, changed)
        self.app.undo()
        self.assertEqual(self.app.session.state, before)
        self.app.redo()
        self.assertEqual(self.app.session.state, changed)
        self.app.simulate()
        self.wait_for_result()
        self.assertAlmostEqual(self.app.session.result.node_voltages['out'], 8)

    def test_rename_cancel_invalid_duplicate_and_noop_preserve_result_revision(self):
        self.app.simulate()
        self.wait_for_result()
        before, result, revision = self.app._snapshot(), self.app.session.result, self.app.session.revision
        self.app.selected = ('element', 'R1')
        for text in (None, '', 'R2', 'x' * 257, 'R1'):
            with self.subTest(text=text), patch('tkinter.simpledialog.askstring', return_value=text):
                self.app.rename()
            self.assertEqual(self.app._snapshot(), before)
            self.assertIs(self.app.session.result, result)
            self.assertEqual(self.app.session.revision, revision)
            self.assertEqual(self.app.selected, ('element', 'R1'))

    def test_rename_junction_ground_wire_and_owned_terminal(self):
        self.app.selected = ('node', 'g')
        with patch('tkinter.simpledialog.askstring', return_value='ground'):
            self.app.rename()
        self.assertEqual(self.app.session.state.document.circuit.reference_node, 'ground')
        self.app.selected = ('wire', 'W1')
        self.app.selected_bend = ('W1', 0)
        with patch('tkinter.simpledialog.askstring', return_value='return: wire'):
            self.app.rename()
        self.assertIsNone(self.app.selected_bend)
        self.assertTrue(self.app.canvas.find_withtag('entity:wire:return: wire'))
        self.app._apply(self.app.session.state.place_component('R1', 320, 160, 0))
        self.app.selected = ('terminal', next(iter(self.app.session.state.terminal_owners())))
        with patch('tkinter.simpledialog.askstring') as dialog:
            self.app.rename()
            dialog.assert_not_called()

    def test_rename_rejects_pending_worker_result(self):
        result, future = solve_dc(self.app.session.state.compile().circuit), Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.app.selected = ('element', 'R1')
        with patch('tkinter.simpledialog.askstring', return_value='Rnew'):
            self.app.rename()
        future.set_result(result)
        self.wait_for_result()
        self.assertIsNone(self.app.session.result)
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))

    def test_csv_export_current_result_preserves_document_view_and_numbers(self):
        self.app.simulate()
        self.wait_for_result()
        self.assertFalse(self.app.buttons['Export CSV'].instate(['disabled']))
        self.app.change_zoom(1.25)
        original, result, revision = self.app._snapshot(), self.app.session.result, self.app.session.revision
        path = self.project_path().with_suffix('.csv')
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.export_results()
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertAlmostEqual(float(next(r['value'] for r in rows if r['identifier'] == 'node:out')), 8)
        self.assertAlmostEqual(float(next(r['value'] for r in rows if r['identifier'] == 'element:V1' and r['quantity'] == 'power')), -.048)
        self.assertEqual(self.app._snapshot(), original)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.session.revision, revision)

    def test_csv_unavailable_before_solve_after_edit_undo_and_during_new_solve(self):
        with patch('tkinter.filedialog.asksaveasfilename') as dialog:
            self.app.export_results()
            dialog.assert_not_called()
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))
        self.app.simulate()
        self.wait_for_result()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))
        self.app.undo()
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))
        self.app.simulate()
        self.wait_for_result()
        result, future = self.app.session.result, Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))
        future.set_result(result)
        self.wait_for_result()
        self.assertFalse(self.app.buttons['Export CSV'].instate(['disabled']))

    def test_csv_cancel_decline_replace_and_failure_preserve_file_and_result(self):
        self.app.simulate()
        self.wait_for_result()
        path = self.project_path().with_suffix('.csv')
        path.write_bytes(b'original')
        original, result = self.app._snapshot(), self.app.session.result
        with patch('tkinter.filedialog.asksaveasfilename', return_value=''):
            self.app.export_results()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesno', return_value=False):
            self.app.export_results()
        self.assertEqual(path.read_bytes(), b'original')
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)), \
             patch('circuit_calculator.results_io.save_results_csv', side_effect=PermissionError('simulated')):
            self.app.export_results()
        self.assertEqual(path.read_bytes(), b'original')
        self.assertEqual(self.app._snapshot(), original)
        self.assertIs(self.app.session.result, result)
        self.assertFalse(self.app.buttons['Export CSV'].instate(['disabled']))
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesno', return_value=True):
            self.app.export_results()
        self.assertTrue(path.read_bytes().startswith(b'format_version,'))

    def test_csv_export_protects_open_project_file(self):
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.save_project()
        content = path.read_bytes()
        self.app.simulate()
        self.wait_for_result()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesno') as replace:
            self.app.export_results()
            replace.assert_not_called()
        self.assertIn('protected', self.app.status.get())
        self.assertEqual(path.read_bytes(), content)

    def test_csv_cannot_export_old_worker_result_after_document_edit(self):
        result = solve_dc(self.app.session.state.compile().circuit)
        future = Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        future.set_result(result)
        self.wait_for_result()
        self.assertTrue(self.app.buttons['Export CSV'].instate(['disabled']))
        with patch('tkinter.filedialog.asksaveasfilename') as dialog:
            self.app.export_results()
            dialog.assert_not_called()

    def settle_viewport(self):
        self.root.deiconify()
        self.root.update()
        self.root.update_idletasks()
        self.app._ensure_viewport()

    def world_center(self):
        canvas = self.app.canvas
        return (canvas.canvasx(canvas.winfo_width() / 2) / self.app.zoom,
                canvas.canvasy(canvas.winfo_height() / 2) / self.app.zoom)

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

    def bend_wire(self, name='W1'):
        self.app._apply(self.app.session.state.route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500))))
        if name != 'W1':
            from dataclasses import replace
            state = self.app.session.state
            self.app._apply(replace(state, wires=tuple(replace(w, name=name) if w.name == 'W1' else w for w in state.wires)))
        self.mode('select')
        self.app.selected = ('wire', name)
        self.app.draw()

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

    def angle_document(self):
        self.app._reset_document(Schematic(CircuitDocument(Circuit(('a', 'b', 'unconnected'), (), 'a')),
            (Position('a', 100, 100), Position('b', 300, 300), Position('unconnected', 300, 100))))
        self.app.orthogonal.set(True)
        self.app.routing_style_changed()
        self.mode('wire')

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

    def test_edit_controls_fit_minimum_window_width(self):
        self.root.geometry('900x600')
        self.root.deiconify()
        self.root.update()
        right = self.root.winfo_rootx() + self.root.winfo_width()
        for name, button in self.app.buttons.items():
            with self.subTest(button=name):
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), right)

    def crossing(self):
        self.app._reset_document(Schematic(CircuitDocument(Circuit(('a', 'b', 'c', 'd'), (), 'a')),
            (Position('a', 100, 300), Position('b', 500, 300), Position('c', 300, 100), Position('d', 300, 500)),
            (Wire('H', 'a', 'b'), Wire('V', 'c', 'd'))))

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

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = CircuitEditor(self.root, divider_example())
        self.root.update_idletasks()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if not self.app.closed:
            self.app.closed = True
            self.app.worker.shutdown(wait=True, cancel_futures=True)
            self.root.destroy()
        # Dispose all prior Tk cycles on their owning thread, before a later
        # NumPy worker allocation can trigger cyclic GC on another thread.
        del self.app, self.root
        gc.collect()

    def point(self, x, y):
        canvas = self.app.canvas
        return SimpleNamespace(x=x * self.app.zoom - canvas.canvasx(0),
                               y=y * self.app.zoom - canvas.canvasy(0))

    def node(self, name):
        p = next(p for p in self.app.session.state.positions if p.node == name)
        return self.point(p.x, p.y)

    def mode(self, mode):
        self.app.tool.set(mode)
        self.app.change_mode()

    def project_path(self):
        scratch = Path(__file__).resolve().parents[1] / '.build-check'
        scratch.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name) / 'test.ccproj.json'

    def wait_for_result(self):
        deadline = time.monotonic() + 5
        while self.app.future is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertIsNone(self.app.future, 'GUI solve did not complete in five seconds')

    def test_canvas_select_move_and_undo_preserve_connectivity(self):
        original = self.app.session.state.compile()
        self.app.click(self.node('out'))
        self.assertEqual(self.app.selected, ('node', 'out'))
        self.app.motion(self.point(560, 200))
        self.app.release(self.point(560, 200))
        self.assertEqual(self.app.session.state.compile(), original)
        self.assertTrue(self.app.dirty)
        self.app.undo()
        self.assertEqual(self.app.session.state, divider_example())
        self.app.redo()
        self.assertEqual(next(p.x for p in self.app.session.state.positions if p.node == 'out'), 560)
        before = self.app.session.state
        self.app.click(self.node('out'))
        self.app.motion(self.point(600, 220))
        self.app.release(self.point(100_100, 220))
        self.assertEqual(self.app.session.state, before)
        oval = next(item for item in self.app.canvas.find_withtag('entity:node:out')
                    if self.app.canvas.type(item) == 'oval')
        x1, _, x2, _ = self.app.canvas.coords(oval)
        self.assertEqual((x1 + x2) / 2, 560 * self.app.zoom)

    def test_component_creation_from_explicit_junction_clicks(self):
        self.mode('resistor')
        with patch('tkinter.simpledialog.askstring', side_effect=['R3', '3000']):
            self.app.click(self.node('out'))
            self.app.click(self.node('g'))
        self.assertEqual(self.app.session.state.document.circuit.elements[-1].name, 'R3')
        self.assertIsNone(self.app.pending)
        self.assertTrue(self.app.canvas.find_withtag('entity:element:R3'))

    def place_resistor(self):
        self.mode('resistor')
        with patch('tkinter.simpledialog.askstring', side_effect=['R3', '3000']):
            self.app.click(self.point(800, 300))
        self.mode('select')
        return self.app.session.state.document.circuit.elements[-1]

    def test_blank_placement_terminal_wiring_and_reference(self):
        element = self.place_resistor()
        self.assertEqual(self.app.session.state.component_placement('R3').rotation, 0)
        self.assertEqual(self.app._hit(self.node(element.node_a)), ('terminal', element.node_a))
        self.mode('wire')
        self.app.click(self.node(element.node_a))
        self.app.click(self.node('out'))
        wire = self.app.session.state.wires[-1]
        self.assertEqual((wire.first, wire.second), (element.node_a, 'out'))
        self.mode('ground')
        self.app.click(self.node(element.node_b))
        self.assertEqual(self.app.session.state.document.circuit.reference_node, element.node_b)
        self.assertIn('R3.b', self.app.status.get())
        self.mode('resistor')
        with patch('tkinter.simpledialog.askstring') as dialog:
            self.app.click(self.node(element.node_a))
            dialog.assert_not_called()
        self.assertIn('Use Wire', self.app.status.get())

    def test_body_drag_rotate_undo_and_invalid_drag(self):
        self.place_resistor()
        self.app._apply(self.app.session.state.add_wire(Wire('W2', 'terminal_1', 'out')))
        original = self.app.session.state
        self.app.click(self.point(800, 300))
        self.assertEqual(self.app.selected, ('element', 'R3'))
        self.app.motion(self.point(840, 340))
        self.assertEqual(self.app.session.state, original, 'Preview must not create history')
        self.app.release(self.point(840, 340))
        moved = self.app.session.state
        self.assertEqual(moved.compile(), original.compile())
        self.assertEqual((moved.component_placement('R3').x, moved.component_placement('R3').y), (840, 340))
        self.app.rotate()
        self.assertEqual(self.app.session.state.component_placement('R3').rotation, 90)
        self.assertEqual(self.app.session.state.compile(), original.compile())
        self.app.undo()
        self.assertEqual(self.app.session.state, moved)
        self.app.undo()
        self.assertEqual(self.app.session.state, original)
        self.app.redo()
        self.app.click(self.point(840, 340))
        self.app.motion(self.point(880, 380))
        self.app.release(self.point(100_100, 380))
        self.assertEqual(self.app.session.state, moved)

    def test_legacy_rotation_preserves_dc_and_one_step_undo(self):
        original = self.app.session.state
        self.app.selected = ('element', 'V1')
        self.app.rotate()
        state = self.app.session.state
        self.assertEqual(state.compile(), original.compile())
        self.assertEqual(len(state.wires), len(original.wires) + 2)
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('out: 8', self.app.results.get('1.0', 'end'))
        self.assertIn('V1.+', self.app.results.get('1.0', 'end'))
        self.app.undo()
        self.assertEqual(self.app.session.state, original)

    def test_selecting_off_grid_body_does_not_move_or_convert_it(self):
        original = self.app.session.state
        placement = original.component_placement('R1')
        point = self.point(placement.x, placement.y)
        self.app.click(point)
        self.assertEqual(self.app.selected, ('element', 'R1'))
        self.app.release(point)
        self.assertEqual(self.app.session.state, original)
        self.assertFalse(self.app.dirty)

    def test_terminal_delete_protected_and_body_delete_cleans_owned_nodes(self):
        element = self.place_resistor()
        self.app.selected = ('terminal', element.node_a)
        before = self.app.session.state
        self.app.delete()
        self.assertEqual(self.app.session.state, before)
        self.assertIn('component body', self.app.status.get())
        self.app.selected = ('element', 'R3')
        self.app.delete()
        self.assertNotIn(element.node_a, self.app.session.state.document.circuit.nodes)
        self.app.undo()
        self.assertEqual(self.app.session.state, before)

    def test_placed_project_save_and_reopen(self):
        self.place_resistor()
        self.app.selected = ('element', 'R3')
        self.app.rotate()
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.assertTrue(self.app.save_project())
        expected = self.app.session.state
        self.app.rotate()
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesnocancel', return_value=False):
            self.app.open_project()
        self.assertEqual(self.app.session.state, expected)
        self.assertFalse(self.app.dirty)
        self.assertTrue(self.app.canvas.find_withtag('entity:terminal:terminal_1'))

    def test_rejected_edit_leaves_document_unchanged(self):
        original = self.app.session.state
        self.mode('resistor')
        with patch('tkinter.simpledialog.askstring', side_effect=['R3', '-5']):
            self.app.click(self.node('out'))
            self.app.click(self.node('g'))
        self.assertEqual(self.app.session.state, original)
        self.assertIn('positive', self.app.status.get())

    def test_reference_selection_delete_and_undo(self):
        self.mode('ground')
        self.app.click(self.node('return'))
        self.assertEqual(self.app.session.state.document.circuit.reference_node, 'return')
        self.app.selected = ('node', 'return')
        self.app.delete()
        self.assertFalse(self.app.canvas.find_withtag('entity:node:return'))
        self.app.undo()
        self.assertEqual(self.app.session.state.document.circuit.reference_node, 'return')
        self.assertTrue(self.app.canvas.find_withtag('entity:node:return'))

    def test_async_dc_results_and_edit_invalidation(self):
        self.app.simulate()
        self.wait_for_result()
        self.assertAlmostEqual(self.app.session.result.node_voltages['out'], 8)
        self.assertIn('out: 8', self.app.results.get('1.0', 'end'))
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.assertIsNone(self.app.session.result)
        self.assertIn('cleared', self.app.results.get('1.0', 'end'))

    def test_pending_old_result_is_not_displayed_after_edit(self):
        future = Future()
        result = solve_dc(self.app.session.state.compile().circuit)
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        future.set_result(result)
        self.wait_for_result()
        self.assertIsNone(self.app.session.result)
        self.assertIn('changed while solving', self.app.status.get())

    def test_solver_error_is_presented_without_current_result(self):
        self.app._apply(self.app.session.state.set_reference(None))
        self.app.simulate()
        self.wait_for_result()
        self.assertIsNone(self.app.session.result)
        self.assertIn('reference_node', self.app.status.get())

    def test_export_and_reopen_keep_physics_and_reset_layout(self):
        scratch = Path(__file__).resolve().parents[1] / '.build-check'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            path = Path(folder) / 'editor.json'
            self.app._apply(self.app.session.state.move_node('out', 560, 220))
            self.assertTrue(self.app.dirty)
            with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
                self.app.export()
            self.assertTrue(self.app.dirty, 'Electrical export must not mark the graphical project saved')
            self.assertEqual(load_document(path), divider_example().compile())
            self.assertIn('Layout is not saved', self.app.status.get())
            with patch('tkinter.filedialog.askopenfilename', return_value=str(path)), \
                 patch('tkinter.messagebox.askyesnocancel', return_value=False):
                self.app.open()
            self.assertEqual(self.app.session.state.compile(), divider_example().compile())
            self.assertEqual(self.app.session.state.wires, ())
            self.assertFalse(self.app.dirty)

    def test_zoom_keeps_electrical_document_and_updates_hit_targets(self):
        original = self.app.session.state
        self.app.change_zoom(1.25)
        self.app.click(self.node('out'))
        self.assertEqual(self.app.selected, ('node', 'out'))
        self.assertEqual(self.app.session.state, original)

    def test_save_and_reopen_project_restore_graph_layout_and_view(self):
        path = self.project_path()
        self.app._apply(self.app.session.state.move_node('out', 560, 220))
        self.app.change_zoom(1.25)
        self.app._scroll('x', 'moveto', .2)
        self.app._scroll('y', 'moveto', .15)
        expected = self.app._snapshot()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.assertTrue(self.app.save_project())
        self.assertEqual(load_project(path), expected)
        self.assertFalse(self.app.dirty)
        # The CLI launches a fresh editor with a preloaded project, rather than
        # using Open Project on an existing window. Cover that constructor path.
        other_root, other = tk.Tk(), None
        other_root.withdraw()
        try:
            other = CircuitEditor(other_root, project=load_project(path), project_path=path)
            self.assertEqual(other.session.state, expected.schematic)
            self.assertEqual(other.project_path, path)
            self.assertEqual(other.zoom, expected.view.zoom)
            self.assertFalse(other.dirty)
        finally:
            if other is not None:
                other.worker.shutdown(wait=True, cancel_futures=True)
            other_root.destroy()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesnocancel', return_value=False):
            self.app.open_project()
        self.assertEqual(self.app.session.state, expected.schematic)
        self.assertEqual(self.app.project_path, path)
        self.assertAlmostEqual(self.app.zoom, expected.view.zoom)
        self.assertAlmostEqual(self.app.canvas.xview()[0], expected.view.scroll_x, delta=.002)
        self.assertAlmostEqual(self.app.canvas.yview()[0], expected.view.scroll_y, delta=.002)
        self.assertFalse(self.app.dirty)
        self.assertIsNone(self.app.session.result)

    def test_canceling_save_as_preserves_dirty_document(self):
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        state = self.app.session.state
        with patch('tkinter.filedialog.asksaveasfilename', return_value=''):
            self.assertFalse(self.app.save_project())
        self.assertEqual(self.app.session.state, state)
        self.assertTrue(self.app.dirty)
        self.assertIsNone(self.app.project_path)

    def test_declining_replacement_preserves_file_and_unsaved_state(self):
        path = self.project_path()
        path.write_bytes(b'original')
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)), \
             patch('tkinter.messagebox.askyesno', return_value=False):
            self.assertFalse(self.app.save_project_as())
        self.assertEqual(path.read_bytes(), b'original')
        self.assertTrue(self.app.dirty)
        self.assertIsNone(self.app.project_path)

    def test_save_reuses_path_and_failed_save_does_not_clear_dirty(self):
        path = self.project_path()
        with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.assertTrue(self.app.save_project())
        original = path.read_bytes()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        with patch('circuit_calculator.gui.write_project', side_effect=PermissionError('simulated')), \
             patch('tkinter.filedialog.asksaveasfilename') as dialog:
            self.assertFalse(self.app.save_project())
            dialog.assert_not_called()
        self.assertTrue(self.app.dirty)
        self.assertEqual(path.read_bytes(), original)
        with patch('tkinter.filedialog.asksaveasfilename') as dialog:
            self.assertTrue(self.app.save_project())
            dialog.assert_not_called()
        self.assertFalse(self.app.dirty)
        self.assertEqual(load_project(path).schematic, self.app.session.state)

    def test_unsaved_dialog_cancel_and_save_cancel_keep_document_open(self):
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        for answer in (None, True):
            with self.subTest(answer=answer), \
                 patch('tkinter.messagebox.askyesnocancel', return_value=answer), \
                 patch('tkinter.filedialog.asksaveasfilename', return_value=''):
                self.app.close()
            self.assertFalse(self.app.closed)
            self.assertTrue(self.app.dirty)

    def test_saving_before_new_document_succeeds_then_resets_history(self):
        path = self.project_path()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        expected = self.app.session.state
        revision = self.app.session.revision
        with patch('tkinter.messagebox.askyesnocancel', return_value=True), \
             patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
            self.app.new()
        self.assertEqual(load_project(path).schematic, expected)
        self.assertGreater(self.app.session.revision, revision)
        new_state = self.app.session.state
        self.app.undo()
        self.assertEqual(self.app.session.state, new_state)
        self.assertIsNone(self.app.project_path)

    def test_bad_project_load_leaves_current_document_view_and_result(self):
        path = self.project_path()
        path.write_text('{bad}', encoding='utf-8')
        self.app.simulate()
        self.wait_for_result()
        before, result, revision = self.app._snapshot(), self.app.session.result, self.app.session.revision
        with patch('tkinter.filedialog.askopenfilename', return_value=''), \
             patch.object(self.app, '_discard') as discard:
            self.app.open_project()
            discard.assert_not_called()
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
            self.app.open_project()
        self.assertEqual(self.app._snapshot(), before)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.session.revision, revision)
        self.assertFalse(self.app.dirty)

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

    def test_project_open_rejects_pending_result_even_for_identical_graph(self):
        path = self.project_path()
        save_project(SchematicProject(self.app.session.state), path)
        future = Future()
        result = solve_dc(self.app.session.state.compile().circuit)
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
            self.app.open_project()
        future.set_result(result)
        self.wait_for_result()
        self.assertIsNone(self.app.session.result)


if __name__ == '__main__':
    unittest.main()
