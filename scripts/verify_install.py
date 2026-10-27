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
        tests = sorted(root.glob('test_*.py'))
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
for name in ('calculations', 'circuit', 'dc', 'main'):
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
for argv in ([str(command)], [sys.executable, '-I', '-m', 'main']):
    completed = subprocess.run(argv, input='2\n1e-320\n\n6\n', text=True,
                               encoding='utf-8', capture_output=True, check=True,
                               cwd=folder, timeout=30)
    if '1e-320' not in completed.stdout or 'Goodbye.' not in completed.stdout:
        raise RuntimeError('Installed CLI failed: ' + completed.stdout)
from circuit import Circuit, Resistor, VoltageSource
from dc import solve_dc
example = Circuit(('g', 'a'), (VoltageSource('V', 'a', 'g', 6), Resistor('R', 'a', 'g', 3)), 'g')
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
