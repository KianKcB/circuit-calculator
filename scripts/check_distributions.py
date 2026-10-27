"""Check a built wheel in a fresh venv, first core-only and then with DC.

Usage: python scripts/check_distributions.py
Uses only stdlib orchestration; pip downloads the pinned optional dependency.
Existing environments are never modified. Temporary files stay in .build-check.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main():
    root = Path(__file__).resolve().parents[1]
    # Select the declared version so old, user-retained build artifacts cannot
    # be mistaken for this release's wheel.
    import tomllib
    metadata = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    version = metadata['project']['version']
    wheels = list((root / 'dist').glob(f'circuit_calculator-{version}-*.whl'))
    if len(wheels) != 1:
        raise RuntimeError(f'Expected exactly one wheel for version {version} in dist')
    scratch = root / '.build-check'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='environment-', dir=scratch) as folder:
        environment = Path(folder)
        venv.EnvBuilder(with_pip=True).create(environment)
        executable = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')

        def run(*args):
            subprocess.run([str(executable), *map(str, args)], cwd=root, check=True)

        run('-m', 'pip', 'install', '--no-deps', wheels[0])
        run('-B', root / 'scripts/verify_install.py')
        run('-m', 'pip', 'install', '-c', root / 'requirements/ci-constraints.txt',
            '--only-binary=:all:', str(wheels[0]) + '[dc]')
        run('-m', 'pip', 'check')
        run('-B', root / 'scripts/verify_install.py', '--dc')
        # An editable install must work outside the checkout as well; do not use
        # the wheel verifier's site-packages-origin requirement for source links.
        run('-m', 'pip', 'install', '--no-deps', '--editable', root)
        smoke = '''
import importlib
from pathlib import Path
import sys
import circuit_calculator.circuit as canonical
if not Path(canonical.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve()):
    raise RuntimeError('Editable install did not load source package')
for old, new in (('calculations', 'calculations'), ('circuit', 'circuit'),
                 ('circuit_io', 'circuit_io'), ('dc', 'dc'), ('main', 'cli'),
                 ('gui', 'gui'), ('schematic', 'schematic')):
    if importlib.import_module(old) is not importlib.import_module('circuit_calculator.' + new):
        raise RuntimeError('Editable compatibility alias failed: ' + old)
print('Editable canonical and legacy imports verified outside checkout.')
'''
        subprocess.run([str(executable), '-I', '-B', '-c', smoke, str(root)],
                       cwd=environment, check=True)
        subprocess.run([str(executable), '-I', '-m', 'circuit_calculator', 'gui', '--help'],
                       cwd=environment, check=True)


if __name__ == '__main__':
    main()
