"""Opt-in Tk workflows. Source: python -B scripts/check_gui.py
Installed: python -I -B scripts/check_gui.py --installed
Product origins are checked before loading test-only helpers.
"""

import importlib.util
from pathlib import Path
import sys
import unittest

if '--installed' in sys.argv:
    sys.argv.remove('--installed')
    if not sys.flags.isolated:
        raise RuntimeError('Installed GUI checks require Python -I isolation')
    for module in ('circuit_calculator', 'circuit_calculator.gui', 'circuit_calculator.canvas_renderer',
                   'circuit_calculator.viewport', 'circuit_calculator.results_io', 'circuit_calculator.quantities',
                   'circuit_calculator.editor_dialogs', 'circuit_calculator.shortcuts', 'circuit_calculator.inspection',
                   'circuit_calculator.navigation',
                   'circuit_calculator.schematic', 'circuit_calculator.dc', 'circuit_calculator.project_io'):
        spec = importlib.util.find_spec(module)
        if spec is None or spec.origin is None or not Path(spec.origin).resolve().is_relative_to(Path(sys.prefix).resolve()):
            raise RuntimeError('GUI module did not come from installed environment: ' + module)
    print('Installed GUI module origins verified.', flush=True)
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Only test helpers are added in installed mode; never the product checkout root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from gui_workflows import base, clipboard, documents, editing, navigation, results, routing, shortcuts, viewport


class TkWorkflowTests(
    clipboard.ClipboardMixin,
    documents.DocumentsMixin,
    editing.EditingMixin,
    navigation.NavigationMixin,
    results.ResultsMixin,
    routing.RoutingMixin,
    shortcuts.ShortcutsMixin,
    viewport.ViewportMixin,
    base.WorkflowCase,
):
    """Retain the established CLI test IDs and alphabetical execution order."""


if __name__ == '__main__':
    unittest.main()
