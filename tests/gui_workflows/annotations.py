"""Opt-in current-result annotations, camera and entity isolation checks."""

from concurrent.futures import Future
from unittest.mock import patch


class AnnotationsMixin:
    def annotation_texts(self):
        return [self.app.canvas.itemcget(item, 'text')
                for item in self.app.canvas.find_withtag('result-annotation')]

    def test_annotations_toggle_real_values_preserves_document_camera_and_result(self):
        self.settle_viewport()
        self.assertFalse(self.app.node_voltages.get())
        self.app.annotation_button.invoke()
        self.assertFalse(self.annotation_texts())
        self.app.simulate()
        self.wait_for_result()
        self.assertEqual(set(self.annotation_texts()), {'0 V (ref)', '12 V', '8 V'})
        before, revision, result = self.app._snapshot(), self.app.session.revision, self.app.session.result
        dirty = self.app.dirty
        for _ in range(2):
            self.app.annotation_button.invoke()
            self.assertFalse(self.annotation_texts())
            self.app.annotation_button.invoke()
            self.assertIn('8 V', self.annotation_texts())
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.session.revision, revision)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.dirty, dirty)

    def test_annotations_fit_includes_fixed_size_values_at_multiple_zooms(self):
        self.root.geometry('900x600')
        self.settle_viewport()
        self.app.annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        for zoom in (.4, 1., 2.5):
            self.app.set_zoom(zoom)
            self.app.fit_circuit()
            canvas = self.app.canvas
            bounds = canvas.bbox('circuit-content', 'result-annotation')
            left, top = canvas.canvasx(0), canvas.canvasy(0)
            self.assertGreaterEqual(bounds[0], left + 25)
            self.assertGreaterEqual(bounds[1], top + 25)
            self.assertLessEqual(bounds[2], left + canvas.winfo_width() - 25)
            self.assertLessEqual(bounds[3], top + canvas.winfo_height() - 25)
        button = self.app.annotation_button
        self.assertTrue(button.winfo_ismapped())
        self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                             self.root.winfo_rootx() + self.root.winfo_width())

    def test_annotations_are_decorative_and_drag_previews_suppress_values(self):
        self.settle_viewport()
        self.app.annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        canvas = self.app.canvas
        base = canvas.bbox('circuit-content')
        for item in canvas.find_withtag('result-annotation'):
            self.assertEqual(canvas.gettags(item), ('result-annotation',))
        self.assertEqual(self.app._content_bounds, base)
        from circuit_calculator.schematic import Position
        self.app.draw(Position('out', 900, 300))
        self.assertFalse(self.annotation_texts())
        self.app.draw()
        self.assertIn('8 V', self.annotation_texts())
        self.assertIsNotNone(self.app.session.result)

    def test_annotations_edit_history_document_reset_and_reference_freshness(self):
        self.app.annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.assertFalse(self.annotation_texts())
        self.app.undo()
        self.assertFalse(self.annotation_texts())
        self.app.redo()
        self.assertFalse(self.annotation_texts())
        self.app._reset_document(self.app.session.state)
        self.assertFalse(self.annotation_texts())
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('6 V', self.annotation_texts())

    def test_annotations_new_pending_stale_and_failed_solves_remove_old_values(self):
        self.app.annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        result, future = self.app.session.result, Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.assertFalse(self.annotation_texts())

        self.app._apply(self.app.session.state.change_value('R1', 2000))
        future.set_result(result)
        self.wait_for_result()
        self.assertFalse(self.annotation_texts())
        failure = Future()
        with patch.object(self.app.worker, 'submit', return_value=failure):
            self.app.simulate()
        failure.set_exception(ValueError('test failure'))
        with patch('tkinter.messagebox.showerror'):
            self.wait_for_result()
        self.assertFalse(self.annotation_texts())

    def test_annotations_placed_aliases_and_changed_reference_are_explicit(self):
        from circuit_calculator.schematic import placed_divider_example
        state = placed_divider_example().rename('node', 'out', 'خروجی && out')
        self.app._reset_document(state)
        self.app.annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        self.assertEqual(len(self.annotation_texts()), len(state.document.circuit.nodes))
        labels = self.annotation_texts()
        expected_references = sum(net == state.net_names()['g'] for net in state.net_names().values())
        self.assertEqual(labels.count('0 V (ref)'), expected_references)
        self.app._apply(state.set_reference('خروجی && out'))
        self.assertFalse(self.annotation_texts())
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('-8 V', self.annotation_texts())
        self.assertIn('4 V', self.annotation_texts())
        self.assertIn('0 V (ref)', self.annotation_texts())
