"""Pure command mapping for Tk event fields, with no GUI/runtime dependency."""

import sys

_WINDOWS_LETTERS = {67: 'c', 86: 'v', 68: 'd', 82: 'r', 70: 'f',
                    90: 'z', 89: 'y', 83: 's', 79: 'o'}


def shortcut_action(keysym, keycode, state, *, scope, platform=None):
    """Return an allowed editor method name or None for an unhandled event."""
    if scope not in ('canvas', 'application'):
        raise ValueError('Shortcut scope must be canvas or application')
    if state & 0x20008:  # X11 Mod1 or Tk's Windows Alt bit (including AltGr).
        return None
    key = keysym.lower()
    if (sys.platform if platform is None else platform) == 'win32':
        key = _WINDOWS_LETTERS.get(keycode, key)
    if state & 4:  # Control
        if scope == 'canvas':
            return {'c': 'copy_selected', 'v': 'paste', 'd': 'duplicate'}.get(key)
        if key == 'z':
            return 'redo' if state & 1 else 'undo'
        if key == 's':
            return 'save_project_as' if state & 1 else 'save_project'
        return {'y': 'redo', 'o': 'open_project'}.get(key)
    if scope == 'canvas':
        return {'r': 'rotate', 'f': 'fit_circuit'}.get(key)
    return None
