"""Compatibility import; new code should use circuit_calculator.calculations."""

import sys
from circuit_calculator import calculations as _implementation

sys.modules[__name__] = _implementation
