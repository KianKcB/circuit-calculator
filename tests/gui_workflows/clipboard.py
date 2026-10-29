"""Clipboard workflows; loaded only by the opt-in GUI runner."""

from concurrent.futures import Future
from unittest.mock import patch
from circuit_calculator.dc import solve_dc
from circuit_calculator.project_io import load_project


class ClipboardMixin:
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
