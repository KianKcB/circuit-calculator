"""Shortcuts workflows; loaded only by the opt-in GUI runner."""

import sys
from types import SimpleNamespace
from unittest.mock import patch


class ShortcutsMixin:
    def test_shortcuts_rotate_fit_and_history_from_canvas_and_results(self):
        before = self.app.session.state
        self.app.selected = ('element', 'R1')
        self.send_shortcut(self.app.canvas, 'r', 82, 0)
        rotated = self.app.session.state
        self.assertNotEqual(rotated, before)
        self.assertEqual(rotated.compile(), before.compile())
        self.send_shortcut(self.app.canvas, 'z', 90)
        self.assertEqual(self.app.session.state, before)
        self.send_shortcut(self.app.results, 'Z', 90, 5)
        self.assertEqual(self.app.session.state, rotated)
        self.send_shortcut(self.app.results, 'z', 90)
        self.assertEqual(self.app.session.state, before)
        self.send_shortcut(self.app.canvas, 'y', 89)
        self.assertEqual(self.app.session.state, rotated)
        with patch.object(self.app, 'fit_circuit') as fit:
            self.send_shortcut(self.app.canvas, 'f', 70, 0)
            fit.assert_called_once()
            self.send_shortcut(self.app.results, 'f', 70, 0)
            fit.assert_called_once()

    def test_shortcuts_save_save_as_open_dispatch_once_and_ignore_altgr(self):
        with patch.object(self.app, 'save_project') as save, \
             patch.object(self.app, 'save_project_as') as save_as, \
             patch.object(self.app, 'open_project') as open_project:
            self.send_shortcut(self.app.canvas, 's', 83)
            save.assert_called_once()
            self.send_shortcut(self.app.results, 'S', 83, 5)
            save_as.assert_called_once()
            save.assert_called_once()
            self.send_shortcut(self.app.canvas, 'o', 79)
            open_project.assert_called_once()
            self.send_shortcut(self.app.canvas, 's', 83, 12)
            self.send_shortcut(self.app.results, 's', 83, 0x20004)
            save.assert_called_once()
            save_as.assert_called_once()

    def test_rotate_shortcut_rotates_pending_paste_without_changing_graph(self):
        self.app.selected = ('element', 'R1')
        self.app.copy_selected()
        self.app.paste()
        before, template = self.app.session.state, self.app.clipboard
        self.send_shortcut(self.app.canvas, 'r', 82, 0)
        self.assertEqual(self.app.paste_template.rotation, 90)
        self.assertEqual(self.app.session.state, before)
        self.assertIs(self.app.clipboard, template)
        self.app.cancel()

    def test_global_shortcuts_do_not_escape_modal_form(self):
        def dialog_keys(dialog):
            with patch.object(self.app, 'undo') as undo, patch.object(self.app, 'save_project') as save:
                self.send_shortcut(dialog.title_entry, 'z', 90)
                self.send_shortcut(dialog.description, 's', 83)
                undo.assert_not_called()
                save.assert_not_called()
            dialog.cancel_button.invoke()
        self.drive_details(dialog_keys)

    def test_unhandled_result_copy_and_letters_do_not_change_document(self):
        self.app._text('A result to select')
        self.app.results.tag_add('sel', '1.0', '1.8')
        original, revision = self.app.session.state, self.app.session.revision
        # Returning None allows Tk's native Text copy/selection binding to run.
        self.assertIsNone(self.app._global_key(SimpleNamespace(keysym='c', keycode=67, state=4)))
        self.send_shortcut(self.app.results, 'r', 82, 0)
        self.assertEqual(self.app.session.state, original)
        self.assertEqual(self.app.session.revision, revision)
        self.assertEqual(self.app.results.get('sel.first', 'sel.last'), 'A result')

    def test_canvas_copy_paste_duplicate_keyboard_bindings(self):
        self.root.deiconify()
        self.root.update()
        self.app.canvas.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), self.app.canvas)
        def send(key, windows_keycode):
            identity = {'keycode': windows_keycode} if sys.platform == 'win32' else {'keysym': key}
            self.app.canvas.event_generate('<KeyPress>', state=4, when='tail', **identity)
            self.root.update()
        self.app.selected = ('element', 'R1')
        if sys.platform == 'win32':
            self.app.canvas.event_generate('<Control-Alt-KeyPress>', keycode=67, when='tail')
            self.root.update()
            self.assertIsNone(self.app.clipboard)
        send('c', 67)
        self.assertIsNotNone(self.app.clipboard)
        send('v', 86)
        self.assertEqual(self.app.mode, 'paste')
        self.app.click(self.point(700, 400))
        send('d', 68)
        self.assertEqual(len(self.app.session.state.document.circuit.elements), 5)
        self.assertEqual(self.app.selected, ('element', 'R4'))

    def test_clipboard_key_dispatch_ignores_altgr_and_other_commands(self):
        self.app.selected = ('element', 'R1')
        self.assertIsNone(self.app._canvas_key(SimpleNamespace(keysym='c', keycode=67, state=12)))
        self.assertIsNone(self.app._canvas_key(SimpleNamespace(keysym='c', keycode=67, state=0x20004)))
        self.assertIsNone(self.app._canvas_key(SimpleNamespace(keysym='z', keycode=90, state=4)))
        self.assertIsNone(self.app.clipboard)
