"""Compatibility import; new code should use circuit_calculator.schematic."""

import sys
from circuit_calculator import schematic as _implementation

sys.modules[__name__] = _implementation
