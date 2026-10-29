"""Verify the installed distribution away from source modules.

Run with a fresh environment's Python, after installing the wheel or sdist:
    python scripts/verify_install.py [--dc]
Tests are copied to an ignored temporary project directory, then an isolated
subprocess checks installed imports, console/module entry points and the suite.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dc', action='store_true', help='require NumPy and no skipped tests')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    scratch = root / '.build-check'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='installed-', dir=scratch) as folder:
        folder = Path(folder)
        tests = sorted((root / 'tests').glob('test_*.py'))
        if not tests:
            raise RuntimeError('No test files found in distribution/source tree')
        for path in tests:
            shutil.copy2(path, folder / path.name)
        # -I excludes the checkout, PYTHONPATH and user site-packages. Only test
        # files are added back; product imports must come from the environment.
        program = r'''
import importlib.metadata
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

folder = Path(sys.argv[1]).resolve()
require_dc = sys.argv[2] == 'dc'
environment = Path(sys.prefix).resolve()
for name in ('circuit_calculator', 'circuit_calculator.calculations',
             'circuit_calculator.circuit', 'circuit_calculator.circuit_io',
             'circuit_calculator.dc', 'circuit_calculator.cli',
             'circuit_calculator.schematic', 'circuit_calculator.gui',
             'circuit_calculator.project_io', 'circuit_calculator._document_io',
             'circuit_calculator.canvas_renderer', 'circuit_calculator.viewport',
             'circuit_calculator.results_io', 'circuit_calculator.quantities',
             'circuit_calculator.editor_dialogs', 'circuit_calculator.shortcuts', 'circuit_calculator.inspection',
             'circuit_calculator.navigation', 'circuit_calculator.probe', 'circuit_calculator.probe_panel',
             'circuit_calculator.annotations', 'circuit_calculator.label_layout'):
    spec = importlib.util.find_spec(name)
    if spec is None or not Path(spec.origin).resolve().is_relative_to(environment):
        raise RuntimeError('Module did not come from installed environment: ' + name)
has_numpy = importlib.util.find_spec('numpy') is not None
if has_numpy != require_dc:
    raise RuntimeError('Expected fresh ' + ('DC' if require_dc else 'formula-only') + ' environment')
metadata = importlib.metadata.metadata('circuit-calculator')
print('Installed:', metadata['Name'], metadata['Version'], 'Python', sys.version.split()[0], flush=True)
if metadata['Requires-Python'] != '>=3.11':
    raise RuntimeError('Unexpected Python requirement')
command = Path(sys.executable).parent / ('circuit-calculator.exe' if sys.platform == 'win32' else 'circuit-calculator')
completed = subprocess.run([str(command), 'gui', '--help'], text=True, encoding='utf-8',
                           capture_output=True, check=True, cwd=folder, timeout=30)
if '--example' not in completed.stdout:
    raise RuntimeError('Installed GUI command help missing')
for argv in ([str(command)], [sys.executable, '-I', '-m', 'main'],
             [sys.executable, '-I', '-m', 'circuit_calculator']):
    completed = subprocess.run(argv, input='2\n1e-320\n\n6\n', text=True,
                               encoding='utf-8', capture_output=True, check=True,
                               cwd=folder, timeout=30)
    if '1e-320' not in completed.stdout or 'Goodbye.' not in completed.stdout:
        raise RuntimeError('Installed CLI failed: ' + completed.stdout)
from circuit_calculator.circuit import Circuit, Resistor, VoltageSource
from circuit_calculator.dc import solve_dc
from circuit_calculator.circuit_io import CircuitDocument, save_document, load_document
from circuit_calculator.project_io import SchematicProject, ViewState, save_project, load_project
from circuit_calculator.schematic import Waypoint, placed_divider_example
state = placed_divider_example().rotate_component('R1').route_wire('W1', (Waypoint(500, 500), Waypoint(160, 500)))
state = state.split_wire('W1', 1, 300, 500)
state = state.move_wire_bend('W1', 0, 540, 540).orthogonalize_wire('W1')
project = SchematicProject(state, ViewState(1.25, .2, .3))
project_path = folder / 'installed-example.ccproj.json'
save_project(project, project_path)
if load_project(project_path) != project:
    raise RuntimeError('Installed project persistence round trip failed')
# Installed legacy modules are aliases, not duplicate copies of domain classes.
import importlib
for old, new in (('calculations', 'calculations'), ('circuit', 'circuit'),
                 ('circuit_io', 'circuit_io'), ('dc', 'dc'), ('main', 'cli'),
                 ('gui', 'gui'), ('schematic', 'schematic')):
    if importlib.import_module(old) is not importlib.import_module('circuit_calculator.' + new):
        raise RuntimeError('Legacy import does not alias canonical module: ' + old)
example = Circuit(('g', 'a'), (VoltageSource('V', 'a', 'g', 6), Resistor('R', 'a', 'g', 3)), 'g')
document_path = folder / 'installed-example.json'
save_document(CircuitDocument(example, 'Installed example'), document_path)
if load_document(document_path).circuit != example:
    raise RuntimeError('Installed persistence round trip failed')
for index, argv in enumerate(([str(command), 'dc', str(document_path)],
             [sys.executable, '-I', '-m', 'main', 'dc', str(document_path)],
             [sys.executable, '-I', '-m', 'circuit_calculator', 'dc', str(document_path)])):
    csv_path = folder / f'installed-results-{index}.csv'
    argv = [*argv, '--csv', str(csv_path)]
    completed = subprocess.run(argv, text=True, encoding='utf-8', capture_output=True,
                               cwd=folder, timeout=30)
    if require_dc:
        import json
        if completed.returncode != 0 or abs(json.loads(completed.stdout)['node_voltages_volts']['a'] - 6) > 1e-12:
            raise RuntimeError('Installed DC command failed: ' + completed.stderr)
        import csv
        with csv_path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        current = next(r for r in rows if r['identifier'] == 'element:R' and r['quantity'] == 'current')
        if abs(float(current['value']) - 2) > 1e-12 or current['unit'] != 'A':
            raise RuntimeError('Installed results CSV value/units failed')
    elif completed.returncode != 1 or '[dc]' not in completed.stderr:
        raise RuntimeError('Installed DC command did not report missing optional dependency')
    elif csv_path.exists():
        raise RuntimeError('CSV was created without a successful solve')
if not require_dc:
    try:
        solve_dc(example)
    except ImportError as error:
        if '[dc]' not in str(error) or 'pip install "numpy' not in str(error):
            raise
    else:
        raise RuntimeError('Solver did not report missing optional dependency')
else:
    result = solve_dc(example)
    if abs(result.elements['R'].current_amperes - 2) > 1e-12:
        raise RuntimeError('Installed solver returned incorrect current')
sys.path.insert(0, str(folder))
suite = unittest.defaultTestLoader.discover(str(folder))
result = unittest.TextTestRunner(verbosity=1).run(suite)
if not result.wasSuccessful() or (require_dc and result.skipped):
    raise SystemExit(1)
if not require_dc and not result.skipped:
    raise RuntimeError('Formula-only check did not exercise optional solver skips')
'''
        subprocess.run([sys.executable, '-I', '-B', '-c', program, str(folder),
                        'dc' if args.dc else 'core'], check=True, cwd=folder)


if __name__ == '__main__':
    main()
