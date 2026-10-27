"""Compatibility launcher; prefer python -m circuit_calculator."""

import sys
from circuit_calculator import cli as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())
else:
    sys.modules[__name__] = _implementation
