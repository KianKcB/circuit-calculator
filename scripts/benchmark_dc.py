"""Bounded affine-grid DC timing/accuracy report; run from a checkout or sdist.

Example: python -B scripts/benchmark_dc.py --sizes 4 8 12 --repeats 3 --output report.json
This is a local small-network diagnostic, not a performance guarantee.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from circuit_calculator import dc
from circuit_calculator._document_io import atomic_write
from tests.test_dc_grid import grid_reference, verify_grid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', type=int, nargs='+', default=[4, 8, 12])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, help='new JSON output path; never replaces an existing file')
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20 or any(not 2 <= n <= 12 for n in args.sizes):
        parser.error('Use grid sizes 2..12 and repeats 1..20')
    try:
        import numpy as np
        measurements = []
        for size in args.sizes:
            circuit = grid_reference(size)
            verify_grid(dc.solve_dc(circuit), size)  # Warm up, and validate before timing.
            samples = []
            for _ in range(args.repeats):
                started = time.perf_counter()
                result = dc.solve_dc(circuit)
                samples.append(time.perf_counter() - started)
                metrics = verify_grid(result, size)
            measurements.append({'grid_size': size, 'nodes': len(circuit.nodes),
                'elements': len(circuit.elements), 'unknowns': size * size + 4 * size - 4,
                'solve_seconds_samples': samples, 'median_solve_seconds': statistics.median(samples),
                'scaled_condition_number': float(result.scaled_condition_number),
                'reported_kcl_residual_amperes': float(result.max_kcl_residual_amperes),
                'power_balance_watts': float(result.power_balance_watts), **metrics})
        version = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
        report = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'package_version': version,
            'python': platform.python_version(), 'numpy': np.__version__, 'platform': platform.platform(),
            'engine_sha256': hashlib.sha256(Path(dc.__file__).read_bytes()).hexdigest(),
            'reference_sha256': hashlib.sha256((ROOT / 'tests/test_dc_grid.py').read_bytes()).hexdigest(),
            'timing_scope': 'solve_dc including validation/assembly/condition/residual checks; one warmup per size',
            'measurements': measurements}
        text = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + '\n'
        if args.output is not None:
            atomic_write(text.encode('utf-8'), args.output)
        print(text, end='')
    except ImportError:
        print('Error: The grid benchmark requires NumPy; install the project [dc] extra.', file=sys.stderr)
        return 1
    except (ValueError, OSError, AssertionError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
