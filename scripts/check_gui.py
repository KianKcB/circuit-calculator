"""Opt-in real Tk widget/workflow tests. Requires a desktop display and [dc].

Run: python -B scripts/check_gui.py
This script is separate from headless discovery so an optional GUI/display does
not turn core-only installations into skipped-test failures.
"""

from concurrent.futures import Future
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk
from circuit_io import load_document
from dc import solve_dc
from gui import CircuitEditor
from schematic import divider_example


class TkWorkflowTests(unittest.TestCase):
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
            with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)):
                self.app.export()
            self.assertEqual(load_document(path), divider_example().compile())
            self.assertIn('Layout is not saved', self.app.status.get())
            with patch('tkinter.filedialog.askopenfilename', return_value=str(path)):
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


if __name__ == '__main__':
    unittest.main()
