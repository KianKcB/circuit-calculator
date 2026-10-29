"""Opt-in probe integration, freshness and transient-state workflows."""

from concurrent.futures import Future
from unittest.mock import patch


class ProbeMixin:
    def choose_probe(self, a='in', b='out'):
        panel = self.app.probe
        self.app.result_tabs.select(self.app.probe_tab)
        for picker, node in zip(panel.pickers, (a, b)):
            picker.current(panel.nodes.index(node))
            picker.event_generate('<<ComboboxSelected>>')
        self.root.update()

    def probe_output(self):
        return self.app.probe.output.get('1.0', 'end-1c')

    def test_probe_solve_swap_clear_and_same_endpoint_are_read_only(self):
        self.settle_viewport()
        snapshot, revision = self.app._snapshot(), self.app.session.revision
        self.choose_probe()
        self.assertIn('No current DC result', self.probe_output())
        self.app.simulate()
        self.wait_for_result()
        self.assertEqual(self.app.result_tabs.select(), str(self.app.probe_tab))
        self.assertIn('Voltage difference: 4 V', self.probe_output())
        result = self.app.session.result
        self.app.probe.swap_button.invoke()
        self.assertIn('Voltage difference: -4 V', self.probe_output())
        self.choose_probe('out', 'out')
        self.assertIn('Voltage difference: 0 V', self.probe_output())
        self.app.probe.clear_button.invoke()
        self.assertEqual(self.app.probe.endpoints(), (None, None))
        self.assertIn('Choose endpoint', self.probe_output())
        self.assertEqual(self.app._snapshot(), snapshot)
        self.assertEqual(self.app.session.revision, revision)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(str(self.app.probe.output['state']), 'disabled')

    def test_probe_edits_history_and_document_reset_clear_choices(self):
        self.app.simulate()
        self.wait_for_result()
        self.choose_probe()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.assertEqual(self.app.probe.endpoints(), (None, None))
        self.choose_probe()
        self.assertNotIn('Voltage difference:', self.probe_output())
        self.app.undo()
        self.assertEqual(self.app.probe.endpoints(), (None, None))
        self.choose_probe()
        self.app.redo()
        self.assertEqual(self.app.probe.endpoints(), (None, None))
        self.choose_probe()
        self.app._reset_document(self.app.session.state)
        self.assertEqual(self.app.probe.endpoints(), (None, None))

    def test_probe_pending_stale_failure_and_camera_changes(self):
        self.app.simulate()
        self.wait_for_result()
        self.choose_probe()
        self.app.change_zoom(.8)
        self.app.fit_circuit()
        self.assertIn('Voltage difference: 4 V', self.probe_output())
        old, future = self.app.session.result, Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.assertIn('Solving DC', self.probe_output())
        self.assertNotIn('Voltage difference:', self.probe_output())
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.choose_probe()
        self.assertIn('No current DC result', self.probe_output())
        future.set_result(old)
        self.wait_for_result()
        self.assertNotIn('Voltage difference:', self.probe_output())
        failed = Future()
        with patch.object(self.app.worker, 'submit', return_value=failed):
            self.app.simulate()
        failed.set_exception(ValueError('test solve failure'))
        with patch('tkinter.messagebox.showerror'):
            self.wait_for_result()
        self.assertIn('No current DC result', self.probe_output())

    def test_probe_labels_are_not_used_as_node_identity(self):
        state = self.app.session.state.rename('node', 'in', 'R1.a')
        state = state.place_component('R1', 330, 160, 0)
        self.app._reset_document(state)
        terminal = state.document.circuit.elements[1].node_a
        self.assertEqual(state.endpoint_label(terminal), 'R1.a')
        self.app.simulate()
        self.wait_for_result()
        self.choose_probe('R1.a', terminal)
        self.assertIn('Voltage difference: 0 V', self.probe_output())
        self.assertNotEqual(self.app.probe.pickers[0].get(), self.app.probe.pickers[1].get())
        self.app.probe.clear_button.invoke()
        self.app.probe.swap_button.invoke()
        self.assertEqual(self.app.probe.endpoints(), (None, None))

    def test_probe_minimum_window_controls_and_text_remain_accessible(self):
        self.root.geometry('900x600')
        self.settle_viewport()
        self.choose_probe()
        self.app.simulate()
        self.wait_for_result()
        panel = self.app.probe
        for widget in (*panel.pickers, panel.swap_button, panel.clear_button, panel.output):
            self.assertTrue(widget.winfo_ismapped())
            self.assertGreater(widget.winfo_width(), 20)
            self.assertGreater(widget.winfo_height(), 10)
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                 self.root.winfo_rooty() + self.root.winfo_height())
        self.assertIn('Voltage difference: 4 V', self.probe_output())
        panel.output.yview_moveto(1)
        self.root.update()
        self.assertEqual(panel.output.yview()[1], 1.)
        with patch('circuit_calculator.editor_dialogs.ask_find_item', return_value=None) as find:
            self.root.deiconify()
            panel.output.focus_force()
            self.root.update()
            import sys
            identity = {'keycode': 70} if sys.platform == 'win32' else {'keysym': 'f'}
            panel.output.event_generate('<KeyPress>', state=4, when='tail', **identity)
            self.root.update()
            find.assert_called_once()
