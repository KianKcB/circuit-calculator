"""Editing workflows; loaded only by the opt-in GUI runner."""

from concurrent.futures import Future
from unittest.mock import patch
from circuit_calculator.dc import solve_dc
from circuit_calculator.schematic import Wire, divider_example
from circuit_calculator.project_io import load_project


class EditingMixin:
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
