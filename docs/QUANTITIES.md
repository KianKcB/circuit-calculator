# UNITS-1: engineering input and display

Design contract, 2026-10-29. Add explicit SI engineering prefixes to GUI component
creation/value editing and readable Canvas/results display. Keep model/solver
parameters, JSON and CSV in full-precision base SI units. Do not change standalone
formula-menu parsing or accept arbitrary expressions or SPICE suffix semantics.

## Accepted input

`parse_quantity(text, unit)` returns a Decimal in base units, with no rounding
through the caller's Decimal context. Accept an ASCII decimal/scientific number,
optionally followed by an engineering prefix and/or matching unit. Bare numbers
retain existing base-unit meaning. Strip outer whitespace and permit whitespace
between number and suffix, but not within the suffix. Limit input to 256 characters.

The accepted engineering prefixes are q/r/y/z/a/f/p/n/u/µ/μ/m/k/M/G/T/P/E/Z/Y/R/Q,
for powers -30 through +30 in steps of three. `u` and Greek `μ` are input aliases
for the SI micro sign `µ`. Prefixes are case-sensitive: m is milli, M is mega,
and k is kilo. Reject K, meg, compound prefixes and SPICE embedded-decimal forms
such as 4k7. Prefix factors follow the [BIPM SI-prefix table](https://www.bipm.org/en/measurement-units/si-prefixes).

Resistance accepts ohm or Ω; voltage accepts V; current A; power W is available
to the shared formatter/parser but is not an editable component parameter.
Examples: 4.7k, 4.7 kohm, 4.7kΩ -> 4700 ohm; -2mA -> -0.002 A;
3.3 V -> 3.3 V; 1M and 1m differ by nine orders of magnitude.
Wrong-dimensional suffixes, NaN/Infinity, booleans, expressions and malformed
numbers produce clear validation errors. Parsing is not physical validation:
existing component constructors still reject nonpositive resistance, float
overflow and nonzero-to-zero conversion. Source signs and true zero remain valid.

This bounded grammar deliberately rejects Python Decimal-specific underscore
and Unicode-digit spellings that were accepted incidentally by the old dialog;
enter ordinary ASCII digits instead. Existing decimal/scientific base-unit values
and all saved numeric data retain their meaning. No file parser changes.

## Display and precision

`format_quantity(value, unit, significant=6)` accepts finite built-in int/float
values, validates precision, and chooses a power-of-three prefix with an ordinary
coefficient between 1 and 1000. Promote a coefficient rounded to 1000 into the
next prefix. Outside the supported engineering range, use scientific base units.
Preserve the sign of signed zero. This is rounded presentation, not an exact
serialization or an accuracy guarantee. Component labels use six significant
digits; result values use nine; residuals use three. Do not parse formatted result
text back into an electrical model or export.

Edit dialogs initialize with the complete base-unit float representation so merely
accepting the displayed field does not replace a value by a rounded label. Store
and export only the validated normalized base-unit parameter. No prefixes,
presentation preferences or cached results are added to electrical v1/project v3.
CSV v1 remains full precision in V/A/W and dimensionless diagnostics.

## Separation and acceptance

Keep the parser/formatter in a pure standard-library quantities.py, imported by
the GUI/renderer without Tk or NumPy at import time. Reuse model validation rather
than inventing new physical limits. A shared table makes input/display consistent;
a general dimensional algebra or expression evaluator is unnecessary here.

Acceptance: every prefix and alias, signs/zero/exponents, wrong units/case,
resource limits and malformed input, context-independent exact decimal scaling,
underflow/overflow handling, prefix rounding thresholds, subnormal/max-float
display, complete numeric dialog no-op, known-answer prefixed divider, and exact
unchanged model/JSON/CSV data. Source and installed Tk/headless regressions must
pass before this batch is marked verified.
