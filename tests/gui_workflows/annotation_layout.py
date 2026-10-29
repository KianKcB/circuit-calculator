"""Measured layout, decorative guides, explicit fallback and transient state."""

from circuit_calculator.circuit import Circuit, Resistor, VoltageSource
from circuit_calculator.circuit_io import CircuitDocument
from circuit_calculator.schematic import Schematic, Position


class AnnotationLayoutMixin:
    def crowded_annotations(self):
        circuit = Circuit(('g', 'a', 'b'), (VoltageSource('V1', 'a', 'g', 12),
            Resistor('R1', 'a', 'b', 1000), Resistor('R2', 'b', 'g', 2000)), 'g')
        state = Schematic(CircuitDocument(circuit),
            (Position('g', 100, 100), Position('a', 120, 100), Position('b', 140, 100)))
        self.app._reset_document(state)
        self.app.annotation_button.invoke()
        self.app.component_annotation_button.invoke()
        self.app.simulate()
        self.wait_for_result()
        return state

    def test_overlap_reduction_moves_only_result_text_and_is_deterministic(self):
        self.settle_viewport()
        self.crowded_annotations()
        self.assertFalse(self.app.reduce_overlaps.get())
        canvas = self.app.canvas
        static = {item: canvas.coords(item) for item in canvas.find_withtag('circuit-content')}
        before, revision, result, dirty = self.app._snapshot(), self.app.session.revision, self.app.session.result, self.app.dirty
        original = [canvas.coords(item) for item in canvas.find_withtag('result-annotation')]
        self.app.overlap_button.invoke()
        moved = [canvas.coords(item) for item in canvas.find_withtag('result-annotation')]
        self.assertNotEqual(moved, original)
        self.assertEqual({item: canvas.coords(item) for item in static}, static)
        self.assertEqual(self.app._snapshot(), before)
        self.assertEqual(self.app.session.revision, revision)
        self.assertIs(self.app.session.result, result)
        self.assertEqual(self.app.dirty, dirty)
        layout = self.app.annotation_layout
        self.app._draw_annotations()
        self.assertEqual([canvas.coords(item) for item in canvas.find_withtag('result-annotation')], moved)
        self.assertEqual(self.app.annotation_layout, layout)
        self.app.overlap_button.invoke()
        self.assertEqual([canvas.coords(item) for item in canvas.find_withtag('result-annotation')], original)
        self.assertFalse(canvas.find_withtag('annotation-leader'))

    def test_overlap_guides_are_decorative_and_link_real_anchors_to_text_edges(self):
        self.crowded_annotations()
        self.app.overlap_button.invoke()
        canvas = self.app.canvas
        anchors = {(p.x * self.app.zoom, p.y * self.app.zoom) for p in self.app.session.state.positions}
        for item in canvas.find_withtag('component-label'):
            left, top, right, bottom = canvas.bbox(item)
            anchors.add(((left + right) / 2, (top + bottom) / 2))
        guides = canvas.find_withtag('annotation-leader')
        self.assertTrue(guides)
        rectangles = self.app.annotation_layout.rectangles
        for item in guides:
            self.assertEqual(canvas.gettags(item), ('annotation-leader',))
            x, y, target_x, target_y = canvas.coords(item)
            self.assertIn((x, y), anchors)
            self.assertTrue(any((target_x in (r.left, r.right) and r.top <= target_y <= r.bottom)
                                or (target_y in (r.top, r.bottom) and r.left <= target_x <= r.right)
                                for r in rectangles))

    def test_dense_overlap_fallback_is_visible_persistent_and_clears_with_results(self):
        self.settle_viewport()
        self.crowded_annotations()
        # Conservative bbox obstacle deliberately covers every bounded candidate.
        self.app.canvas.create_rectangle(-1000, -1000, 1000, 1000, tags=('circuit-content',))
        before = self.app._snapshot()
        self.app.overlap_button.invoke()
        self.root.update()
        self.assertTrue(self.app.annotation_layout.unresolved)
        self.assertTrue(self.app.annotation_note.winfo_ismapped())
        self.assertIn('may still overlap', self.app.annotation_note.cget('text'))
        self.app.result_tabs.select(self.app.probe_tab)
        self.root.update()
        self.assertTrue(self.app.annotation_note.winfo_ismapped())
        self.assertEqual(self.app._snapshot(), before)
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        self.root.update()
        self.assertFalse(self.app.annotation_note.winfo_ismapped())
        self.assertFalse(self.app.canvas.find_withtag('annotation-leader'))
        self.assertFalse(self.annotation_texts())

    def test_overlap_preference_without_labels_is_transient_and_safe_across_documents(self):
        self.settle_viewport()
        before = self.app._snapshot()
        self.app.overlap_button.invoke()
        self.assertIsNone(self.app.annotation_layout)
        self.assertFalse(self.app.canvas.find_withtag('annotation-leader'))
        self.assertEqual(self.app._snapshot(), before)
        self.app.fit_circuit()
        enabled_zoom = self.app.zoom
        self.app.overlap_button.invoke()
        self.app.set_zoom(1.)
        self.app.fit_circuit()
        self.assertAlmostEqual(self.app.zoom, enabled_zoom, delta=.0001)
        self.app.overlap_button.invoke()
        self.app._reset_document(self.app.session.state)
        self.assertTrue(self.app.reduce_overlaps.get())
        self.assertFalse(self.annotation_texts())
        self.assertFalse(self.app.annotation_note.winfo_ismapped())

    def test_overlap_fit_and_minimum_window_control_include_guides(self):
        self.settle_viewport()
        self.crowded_annotations()
        self.app.overlap_button.invoke()
        for zoom in (.4, 1., 2.5):
            self.app.set_zoom(zoom)
            self.app.fit_circuit()
            canvas = self.app.canvas
            bounds = canvas.bbox('circuit-content', 'result-annotation', 'annotation-leader')
            if self.app.zoom > .4001:
                self.assertGreaterEqual(bounds[0], canvas.canvasx(0) + 24)
                self.assertGreaterEqual(bounds[1], canvas.canvasy(0) + 24)
                self.assertLessEqual(bounds[2], canvas.canvasx(0) + canvas.winfo_width() - 24)
                self.assertLessEqual(bounds[3], canvas.canvasy(0) + canvas.winfo_height() - 24)
        self.root.geometry('900x600')
        self.settle_viewport()
        button = self.app.overlap_button
        self.assertTrue(button.winfo_ismapped())
        self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
        self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                             self.root.winfo_rootx() + self.root.winfo_width())

    def test_overlap_guides_and_feedback_clear_on_preview_pending_and_stale_results(self):
        from concurrent.futures import Future
        from unittest.mock import patch
        self.crowded_annotations()
        self.app.overlap_button.invoke()
        old = self.app.session.result
        self.app.draw(Position('a', 300, 300))
        self.assertFalse(self.annotation_texts())
        self.assertFalse(self.app.canvas.find_withtag('annotation-leader'))
        self.assertFalse(self.app._annotation_note_text)
        self.app.draw()
        self.assertTrue(self.app.canvas.find_withtag('annotation-leader'))
        pending = Future()
        with patch.object(self.app.worker, 'submit', return_value=pending):
            self.app.simulate()
        self.assertFalse(self.annotation_texts())
        self.assertFalse(self.app.canvas.find_withtag('annotation-leader'))
        self.app._apply(self.app.session.state.change_value('R1', 2000))
        pending.set_result(old)
        self.wait_for_result()
        self.assertFalse(self.annotation_texts())
        self.assertFalse(self.app.canvas.find_withtag('annotation-leader'))
        failure = Future()
        with patch.object(self.app.worker, 'submit', return_value=failure):
            self.app.simulate()
        failure.set_exception(ValueError('test failure'))
        with patch('tkinter.messagebox.showerror'):
            self.wait_for_result()
        self.assertFalse(self.app._annotation_note_text)
        self.app.simulate()
        self.wait_for_result()
        self.assertIsNotNone(self.app.annotation_layout)
        self.assertTrue(self.annotation_texts())

    def test_overlap_fit_handles_asymmetric_dense_and_coincident_geometry(self):
        self.settle_viewport()
        for variable in (self.app.node_voltages, self.app.component_results, self.app.reduce_overlaps):
            variable.set(True)
        circuit = Circuit(('g', 'a', 'b'), (VoltageSource('V1', 'a', 'g', 12),
            Resistor('R1', 'a', 'b', 1000), Resistor('R2', 'b', 'g', 2000)), 'g')
        cases = (((-600, -250), (100, -200), (300, 150)),
                 ((0, 0), (30, 15), (50, 20)),
                 ((0, 0), (-600, 10), (300, 15)),
                 ((0, 0), (-10, -650), (5, 500)),
                 ((0, 0), (0, 0), (0, 0)))
        for points in cases:
            state = Schematic(CircuitDocument(circuit),
                tuple(Position(node, *point) for node, point in zip(circuit.nodes, points)))
            self.app._reset_document(state)
            self.app.simulate()
            self.wait_for_result()
            result = self.app.session.result
            for zoom in (.4, 1., 2.5):
                with self.subTest(points=points, zoom=zoom):
                    self.app.set_zoom(zoom)
                    self.app.fit_circuit()
                    canvas = self.app.canvas
                    bounds = canvas.bbox('circuit-content', 'result-annotation', 'annotation-leader')
                    limited = (bounds[2] - bounds[0] > canvas.winfo_width() - 64
                               or bounds[3] - bounds[1] > canvas.winfo_height() - 64)
                    if limited:
                        self.assertAlmostEqual(self.app.zoom, .4, delta=.0001)
                        self.assertIn('Zoom limit reached', self.app.status.get())
                    else:
                        self.assertGreaterEqual(bounds[0], canvas.canvasx(0) + 24)
                        self.assertGreaterEqual(bounds[1], canvas.canvasy(0) + 24)
                        self.assertLessEqual(bounds[2], canvas.canvasx(0) + canvas.winfo_width() - 24)
                        self.assertLessEqual(bounds[3], canvas.canvasy(0) + canvas.winfo_height() - 24)
                    self.assertIs(self.app.session.result, result)
                    self.assertEqual(self.app.session.state, state)
