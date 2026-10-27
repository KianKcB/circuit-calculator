"""Compatibility import; new code should use circuit_calculator.dc."""

import sys
from circuit_calculator import dc as _implementation

sys.modules[__name__] = _implementation
