"""Descriptive metadata edits share native validation without changing circuitry."""

import importlib.util
import subprocess
import sys
import unittest

from circuit_calculator.circuit_io import dumps_document, loads_document
from circuit_calculator.project_io import SchematicProject, dumps_project, loads_project
from circuit_calculator.schematic import EditorSession, placed_divider_example


class ProjectDetailsTests(unittest.TestCase):
    def test_metadata_edit_keeps_exact_electrical_and_layout_objects(self):
        state = placed_divider_example()
        edited = state.set_metadata('  تقسیم ولتاژ — 12 V  ', 'First line\nخط دوم\n\n')
        self.assertEqual(edited.document.title, '  تقسیم ولتاژ — 12 V  ')
        self.assertEqual(edited.document.description, 'First line\nخط دوم\n\n')
        self.assertIs(edited.document.circuit, state.document.circuit)
        self.assertIs(edited.positions, state.positions)
        self.assertIs(edited.wires, state.wires)
        self.assertIs(edited.placements, state.placements)
        self.assertEqual(edited.compile().circuit, state.compile().circuit)

    def test_empty_boundary_unicode_and_exact_native_project_roundtrips(self):
        state = placed_divider_example()
        for title, description in (('', ''), ('ت' * 256, 'د' * 4096),
                                   ('name', 'first\r\nsecond\tvalue\n')):
            with self.subTest(title=title[:8]):
                edited = state.set_metadata(title, description)
                self.assertEqual(loads_document(dumps_document(edited.document)), edited.document)
                self.assertEqual(loads_project(dumps_project(SchematicProject(edited))).schematic, edited)
                self.assertEqual(edited.document.title, title)
                self.assertEqual(edited.document.description, description)

    def test_invalid_text_fails_before_replacement(self):
        state = placed_divider_example()
        for title, description in ((None, ''), ('', None), (True, ''), ('', 42),
                                   ('x' * 257, 'valid'), ('valid', 'x' * 4097),
                                   ('\ud800', ''), ('', '\ud800')):
            with self.subTest(title=repr(title)[:20]), self.assertRaises(ValueError):
                state.set_metadata(title, description)
        self.assertEqual(state, placed_divider_example())

    def test_atomic_history_noop_and_stale_results(self):
        state = placed_divider_example()
        session = EditorSession(state)
        revision, result = session.revision, object()
        session.accept_result(revision, result)
        session.apply(state.set_metadata(state.document.title, state.document.description))
        self.assertEqual(session.revision, revision)
        self.assertIs(session.result, result)
        session.apply(state.set_metadata('new', 'both fields together'))
        self.assertEqual(session.revision, revision + 1)
        self.assertIsNone(session.result)
        self.assertFalse(session.accept_result(revision, result))
        edited = session.state
        session.undo()
        self.assertIs(session.state, state)
        session.redo()
        self.assertIs(session.state, edited)

    def test_dialog_module_import_is_headless_and_tk_free(self):
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; import circuit_calculator.editor_dialogs; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)

    @unittest.skipUnless(importlib.util.find_spec('numpy'), 'NumPy optional')
    def test_metadata_does_not_change_any_solved_quantity(self):
        from circuit_calculator.dc import solve_dc
        state = placed_divider_example()
        before = solve_dc(state.compile().circuit)
        after = solve_dc(state.set_metadata('Supply example', 'Description only').compile().circuit)
        self.assertEqual(after, before)
        self.assertAlmostEqual(after.node_voltages['out'], 8)
        self.assertAlmostEqual(after.elements['V1'].power_watts, -.048)


if __name__ == '__main__':
    unittest.main()
