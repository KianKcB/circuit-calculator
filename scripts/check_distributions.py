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
    wheels = list((root / 'dist').glob('*.whl'))
    if len(wheels) != 1:
        raise RuntimeError('Expected exactly one wheel in dist; use a clean build directory')
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
        run('-m', 'pip', 'install', '-c', root / 'constraints-ci.txt',
            '--only-binary=:all:', str(wheels[0]) + '[dc]')
        run('-m', 'pip', 'check')
        run('-B', root / 'scripts/verify_install.py', '--dc')


if __name__ == '__main__':
    main()
