# KEYS-1: consistent shortcut dispatch

Design contract, 2026-10-29. Finish the existing shortcut workflow without changing
the electrical model, document schemas or dependencies. Keep application commands
separate from Tk key symbols and platform-specific keycodes.

The pure shortcuts.py resolver maps Tk event fields to a fixed command name.
Windows uses virtual letter codes for C/V/D/R/F/Z/Y/S/O as well as Latin key
symbols, so the observed non-Latin layout works. Other platforms use Latin key
symbols and keep their existing Tk behavior. Do not claim universal keyboard/IME
support. Alt/AltGr combinations return no command (X11 Mod1 and Windows Alt bits).
Shift/Caps Lock must not prevent ordinary letter shortcuts.

Canvas-only commands: R rotates a selected component or pending paste; F fits the
circuit; Ctrl+C/V/D copy, begin paste and duplicate. Application commands:
Ctrl+Z Undo, Ctrl+Y or Ctrl+Shift+Z Redo, Ctrl+S Save Project, Ctrl+Shift+S Save As,
Ctrl+O Open Project. Escape, F2, F5, Delete, Backspace and Space retain existing
bindings. Never intercept ordinary letters outside the canvas.

Global commands also work while the read-only results text has focus. Its native
selection/copy controls must keep working. Modal forms are separate Tk toplevels:
their text editing/Undo and Apply/Cancel bindings must not invoke document actions.
Dispatch a handled command once and stop propagation; unhandled events fall
through. All commands reuse existing validation, history, file confirmations and
dirty/result rules. No new file operation or extra confirmation is introduced.

Acceptance: pure mapping tests for Windows/non-Windows, both Alt masks, shifted
letters, command scope and unknown keys; actual Tk generated virtual-key events
under the active layout; rotate/paste/Fit/history/file dispatch; results-text focus
and copy preservation; modal isolation; fresh installed and source regressions.
Windows virtual codes follow [Microsoft's table](https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes).
