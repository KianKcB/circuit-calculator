# Compatibility adapters

These small modules are installed as the historical flat import paths, such as
`from circuit import Circuit`. They alias the corresponding `circuit_calculator`
module so domain classes and patch targets have one identity, not duplicate code.
`main` also retains `python -m main` for installed users.

Application code belongs in `circuit_calculator/`; do not add implementations here.
New source-checkout code should use imports such as
`from circuit_calculator.circuit import Circuit`. Flat imports work after a normal
or editable installation. The root `main.py` is the retained checkout launcher.
