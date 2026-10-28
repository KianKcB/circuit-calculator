"""Opt-in real Tk widget/workflow tests. Requires a desktop display and [dc].

Run: python -B scripts/check_gui.py
This script is separate from headless discovery so an optional GUI/display does
not turn core-only installations into skipped-test failures.
"""

from concurrent.futures import Future
import gc
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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
