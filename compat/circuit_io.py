"""Compatibility import; new code should use circuit_calculator.circuit_io."""

import sys
from circuit_calculator import circuit_io as _implementation

sys.modules[__name__] = _implementation
