"""Command scope and platform/modifier semantics without a display."""

import subprocess
import sys
import unittest

from circuit_calculator.shortcuts import shortcut_action


class ShortcutTests(unittest.TestCase):
    def test_canvas_letters_and_control_actions_on_each_platform(self):
        for platform in ('win32', 'linux', 'darwin'):
            for key, code, state, expected in (('r', 82, 0, 'rotate'), ('R', 82, 1, 'rotate'),
                    ('f', 70, 2, 'fit_circuit'), ('c', 67, 4, 'copy_selected'),
                    ('v', 86, 4, 'paste'), ('D', 68, 5, 'duplicate')):
                with self.subTest(platform=platform, key=key):
                    self.assertEqual(shortcut_action(key, code, state, scope='canvas', platform=platform), expected)

    def test_windows_virtual_keys_work_without_latin_symbols(self):
        for code, state, scope, expected in ((82, 0, 'canvas', 'rotate'), (70, 0, 'canvas', 'fit_circuit'),
                (67, 4, 'canvas', 'copy_selected'), (86, 4, 'canvas', 'paste'), (68, 4, 'canvas', 'duplicate'),
                (90, 4, 'application', 'undo'), (89, 4, 'application', 'redo'),
                (83, 4, 'application', 'save_project'), (83, 5, 'application', 'save_project_as'),
                (79, 4, 'application', 'open_project')):
            with self.subTest(code=code, state=state):
                self.assertEqual(shortcut_action('unmapped', code, state, scope=scope, platform='win32'), expected)
                self.assertIsNone(shortcut_action('unmapped', code, state, scope=scope, platform='linux'))

    def test_application_actions_shift_redo_and_caps_lock(self):
        for key, code, state, expected in (('z', 90, 4, 'undo'), ('Z', 90, 5, 'redo'),
                ('y', 89, 6, 'redo'), ('s', 83, 6, 'save_project'),
                ('S', 83, 7, 'save_project_as'), ('o', 79, 4, 'open_project')):
            with self.subTest(key=key, state=state):
                self.assertEqual(shortcut_action(key, code, state, scope='application', platform='linux'), expected)

    def test_alt_altgr_and_scope_do_not_dispatch_unrelated_commands(self):
        for mask in (8, 0x20000):
            for scope in ('application', 'canvas'):
                for key, code in (('c', 67), ('r', 82), ('s', 83), ('z', 90)):
                    self.assertIsNone(shortcut_action(key, code, 4 | mask, scope=scope, platform='win32'))
        for key, code, state, scope in (('z', 90, 4, 'canvas'), ('r', 82, 0, 'application'),
                ('f', 70, 4, 'canvas'), ('c', 67, 4, 'application'), ('s', 83, 0, 'application'),
                ('F5', 116, 0, 'canvas'), ('Escape', 27, 0, 'application')):
            self.assertIsNone(shortcut_action(key, code, state, scope=scope, platform='win32'))
        with self.assertRaises(ValueError):
            shortcut_action('r', 82, 0, scope='dialog')

    def test_import_needs_neither_tk_nor_numpy(self):
        subprocess.run([sys.executable, '-B', '-c',
            'import sys; import circuit_calculator.shortcuts; '
            'assert "tkinter" not in sys.modules; assert "numpy" not in sys.modules'], check=True)


if __name__ == '__main__':
    unittest.main()
