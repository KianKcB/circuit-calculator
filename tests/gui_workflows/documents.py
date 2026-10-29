"""Documents workflows; loaded only by the opt-in GUI runner."""

from concurrent.futures import Future
from pathlib import Path
import tempfile
from unittest.mock import patch
import tkinter as tk
from circuit_calculator.circuit_io import load_document
from circuit_calculator.dc import solve_dc
from circuit_calculator.gui import CircuitEditor
from circuit_calculator.schematic import divider_example
from circuit_calculator.project_io import load_project, save_project, SchematicProject
from .base import REPO_ROOT


class DocumentsMixin:
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

    def test_export_and_reopen_keep_physics_and_reset_layout(self):
        scratch = REPO_ROOT / '.build-check'
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
