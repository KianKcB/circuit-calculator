"""Compatibility import; new code should use circuit_calculator.gui."""

import sys
from circuit_calculator import gui as _implementation

sys.modules[__name__] = _implementation
