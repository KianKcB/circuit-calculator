"""Compatibility import; new code should use circuit_calculator.circuit."""

import sys
from circuit_calculator import circuit as _implementation

sys.modules[__name__] = _implementation
