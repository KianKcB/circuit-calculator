"""Source-only bounded annotation-layout diagnostics. No timing pass/fail gate."""

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from circuit_calculator.label_layout import Rect, place_labels, MAX_LABELS, MAX_OBSTACLES, MAX_CHECKS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, choices=range(1, 11), default=3)
    args = parser.parse_args()
    sparse = tuple(Rect((i % 35) * 80, (i // 35) * 80,
                        (i % 35) * 80 + 30, (i // 35) * 80 + 14) for i in range(MAX_LABELS))
    pattern = tuple(Rect(x - 60, y - 60, x + 60, y + 60)
                    for x in range(-300, 301, 100) for y in range(-200, 201, 100))
    cases = (('sparse-limit', sparse, ()),
             ('crowded', (Rect(0, 0, 100, 40),) * 100, (Rect(0, 0, 50, 50),)),
             ('global-obstacle-limit', sparse,
              (Rect(-1e12, 100000, 1e12, 100010),) * MAX_OBSTACLES),
             ('covering-obstacle-limit', sparse,
              (Rect(-1e12, -1e12, 1e12, 1e12),) * MAX_OBSTACLES),
             ('dense-local-bucket-limit', (Rect(0, 0, 100, 40),) * MAX_LABELS,
              tuple(pattern[i % len(pattern)] for i in range(MAX_OBSTACLES))))
    results = []
    for name, labels, obstacles in cases:
        elapsed, layouts = [], []
        for _ in range(args.repeats):
            start = time.perf_counter()
            layout = place_labels(labels, obstacles)
            elapsed.append(time.perf_counter() - start)
            layouts.append(layout)
        assert all(layout == layouts[0] for layout in layouts), 'Nondeterministic layout'
        layout = layouts[0]
        assert len(layout.rectangles) == len(labels)
        assert layout.checks <= MAX_CHECKS
        for old, new in zip(labels, layout.rectangles):
            assert old.right - old.left == new.right - new.left
            assert old.bottom - old.top == new.bottom - new.top
            assert abs(new.left - old.left) <= 224 and abs(new.top - old.top) <= 160
        if name == 'sparse-limit':
            assert layout.rectangles == labels and not layout.unresolved and not layout.exhausted
        if name == 'global-obstacle-limit':
            assert layout.exhausted and layout.checks == MAX_CHECKS
        if name in ('covering-obstacle-limit', 'dense-local-bucket-limit'):
            assert layout.rectangles == labels and len(layout.unresolved) == len(labels)
            assert not layout.exhausted
        results.append({'case': name, 'labels': len(labels), 'obstacles': len(obstacles),
                        'checks': layout.checks, 'unresolved_placements': len(layout.unresolved),
                        'exhausted': layout.exhausted, 'seconds_min': min(elapsed),
                        'seconds_median': statistics.median(elapsed), 'seconds_max': max(elapsed)})
    print(json.dumps({'python': platform.python_version(), 'platform': platform.platform(),
                      'repeats': args.repeats, 'timing_gate': False,
                      'unresolved_is_collision_count': False, 'cases': results}, indent=2))


if __name__ == '__main__':
    main()
