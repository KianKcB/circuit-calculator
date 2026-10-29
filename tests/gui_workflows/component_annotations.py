"""Opt-in component measurement placement, signs, Fit and freshness workflows."""

from concurrent.futures import Future
from unittest.mock import patch

from circuit_calculator.circuit import Circuit, Resistor, VoltageSource, CurrentSource
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.schematic import Schematic, placed_divider_example, Position


class ComponentAnnotationsMixin:
    def component_annotation_texts(self):
        canvas = self.app.canvas
        return [canvas.itemcget(item, 'text') for item in canvas.find_withtag('component-annotation')]

    def test_component_annotations_independent_toggles_preserve_camera_and_document(self):
        self.settle_viewport()
        self.assertFalse(self.app.component_results.get())
        self.app.component_annotation_button.invoke()
        self.assertFalse(self.component_annotation_texts())
        before, revision, dirty = self.app._snapshot(), self.app.session.revision, self.app.dirty
        self.app.simulate()
        self.wait_for_result()
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.dirty, dirty)
        self.assertIn('P: -48 mW (delivered)', '\n'.join(self.component_annotation_texts()))
        result = self.app.session.result
        self.app.annotation_button.invoke()
        self.assertEqual(len(self.annotation_texts()), len(self.app.session.state.document.circuit.nodes) + 3)
        self.app.component_annotation_button.invoke()
        self.assertFalse(self.component_annotation_texts())
        self.assertTrue(self.annotation_texts())
        self.app.annotation_button.invoke()
        self.assertFalse(self.annotation_texts())
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.session.revision, revision)
        self.assertIs(self.app.session.result, result)

    def test_component_annotation_blocks_follow_all_four_actual_label_anchors(self):
        self.settle_viewport()
        self.app._reset_document(placed_divider_example())
        self.app.component_annotation_button.invoke()
        for rotation in (0, 90, 180, 270):
            self.app._apply(self.app.session.state.place_component('R1', 330, 160, rotation))
            self.app.simulate()
            self.wait_for_result()
            canvas = self.app.canvas
            body = canvas.find_withtag('component-label')[1]
            block = canvas.find_withtag('component-annotation')[1]
            old, new = canvas.bbox(body), canvas.bbox(block)
            self.assertEqual(canvas.itemcget(body, 'anchor'), {0: 'n', 90: 'e', 180: 's', 270: 'w'}[rotation])
            if rotation == 180:
                self.assertLessEqual(new[3], old[1] - 2)
            else:
                self.assertGreaterEqual(new[1], old[3] + 2)
            edge = 2 if rotation == 90 else 0
            self.assertAlmostEqual(new[edge], old[edge], delta=2)
            self.assertEqual(canvas.itemcget(block, 'text'),
                             'I: 4 mA\n+I: R1.a → R1.b\nP: 16 mW (absorbed)')
            self.assertEqual(canvas.gettags(block), ('result-annotation', 'component-annotation'))

    def test_component_annotations_legacy_parallel_and_special_names_use_actual_boxes(self):
        names = ('R && : الف', 'R || : ب')
        circuit = Circuit(('g', 'in'), (VoltageSource('V1', 'in', 'g', 10),
            Resistor(names[0], 'in', 'g', 1000), Resistor(names[1], 'in', 'g', 2000)), 'g')
        self.app._reset_document(Schematic.from_document(CircuitDocument(circuit)))
        self.app.component_annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        canvas = self.app.canvas
        boxes = [canvas.bbox(item) for item in canvas.find_withtag('component-annotation')]
        self.assertEqual(len(set(boxes)), 3)
        texts = self.component_annotation_texts()
        self.assertIn('I: 10 mA', texts[1])
        self.assertIn('P: 100 mW (absorbed)', texts[1])
        self.assertIn('I: 5 mA', texts[2])
        self.assertIn('P: 50 mW (absorbed)', texts[2])
        for body, block in zip(canvas.find_withtag('component-label'), canvas.find_withtag('component-annotation')):
            old, new = canvas.bbox(body), canvas.bbox(block)
            if canvas.itemcget(body, 'anchor') == 's':
                self.assertLess(new[3], old[1])
            else:
                self.assertGreater(new[1], old[3])

    def test_component_annotations_fit_and_minimum_window_controls(self):
        self.settle_viewport()
        self.app.component_annotation_button.invoke()
        self.app.annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        for zoom in (.4, 1., 2.5):
            self.app.set_zoom(zoom)
            self.app.fit_circuit()
            canvas = self.app.canvas
            bounds = canvas.bbox('circuit-content', 'result-annotation')
            self.assertGreaterEqual(bounds[0], canvas.canvasx(0) + 25)
            self.assertGreaterEqual(bounds[1], canvas.canvasy(0) + 25)
            self.assertLessEqual(bounds[2], canvas.canvasx(0) + canvas.winfo_width() - 25)
            self.assertLessEqual(bounds[3], canvas.canvasy(0) + canvas.winfo_height() - 25)
        self.root.geometry('900x600')
        self.settle_viewport()
        for button in (self.app.annotation_button, self.app.component_annotation_button):
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())

    def test_component_annotations_previews_suppress_values_without_invalidating_result(self):
        self.app.component_annotation_button.invoke()
        self.app.annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        result = self.app.session.result
        self.app.draw(Position('out', 900, 300))
        self.assertFalse(self.annotation_texts())
        self.app.draw()
        self.assertTrue(self.component_annotation_texts())
        self.assertIs(self.app.session.result, result)

    def test_component_annotations_edit_history_reset_pending_failed_and_stale_results(self):
        self.app.component_annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        old, future = self.app.session.result, Future()
        with patch.object(self.app.worker, 'submit', return_value=future):
            self.app.simulate()
        self.assertFalse(self.component_annotation_texts())
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        future.set_result(old)
        self.wait_for_result()
        self.assertFalse(self.component_annotation_texts())
        self.app.undo()
        self.app.redo()
        self.app._reset_document(self.app.session.state)
        self.assertFalse(self.component_annotation_texts())
        failure = Future()
        with patch.object(self.app.worker, 'submit', return_value=failure):
            self.app.simulate()
        failure.set_exception(ValueError('test failure'))
        with patch('tkinter.messagebox.showerror'):
            self.wait_for_result()
        self.assertFalse(self.component_annotation_texts())
        self.app.simulate()
        self.wait_for_result()
        self.assertIn('P: 18 mW (absorbed)', '\n'.join(self.component_annotation_texts()))

    def test_component_annotations_current_source_negative_current_and_delivered_power(self):
        circuit = Circuit(('g', 'a'), (VoltageSource('V1', 'a', 'g', 10),
            Resistor('R1', 'a', 'g', 1000), CurrentSource('I1', 'a', 'g', -.003)), 'g')
        self.app._reset_document(Schematic.from_document(CircuitDocument(circuit)))
        self.app.component_annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        self.assertEqual(self.component_annotation_texts()[2],
                         'I: -3 mA\n+I: a → g\nP: -30 mW (delivered)')

    def test_component_annotation_refresh_handles_deletion_and_empty_document(self):
        for enabled in (False, True):
            self.app._reset_document(placed_divider_example())
            self.app.component_results.set(enabled)
            self.app.toggle_annotations()
            self.app.simulate()
            self.wait_for_result()
            for name in ('R1', 'V1', 'R2'):
                self.app._apply(self.app.session.state.delete('element', name))
                self.assertFalse(self.component_annotation_texts())
                self.assertIsNone(self.app.session.result)
            self.assertFalse(self.app.canvas.find_withtag('component-label'))
