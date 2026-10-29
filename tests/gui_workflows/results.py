"""Results workflows; loaded only by the opt-in GUI runner."""

from concurrent.futures import Future
import csv
from unittest.mock import patch
from circuit_calculator.dc import solve_dc


class ResultsMixin:
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
