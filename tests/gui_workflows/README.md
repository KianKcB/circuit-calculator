# Opt-in GUI workflows

Run `python -B scripts/check_gui.py -v` from the project root. A display, Tk and
the optional NumPy DC dependency are required. Focused calls retain the original
class name, for example:

```text
python -B scripts/check_gui.py TkWorkflowTests.test_find_no_match_query_limit_and_correction_keep_dialog_open
```

Feature modules define plain mixins, not TestCase subclasses. The launcher
assembles one TkWorkflowTests class so names, count and alphabetical execution
order stay stable. Put shared fixtures/lifecycle helpers in base.py. Keep its
worker join -> window destroy -> main-thread gc.collect cleanup order intact.

Module filenames deliberately omit the `test_` prefix. This package's initializer
loads nothing, so ordinary headless unittest discovery never imports Tk or runs
these workflows. Do not add GUI imports to __init__.py or rename these files to
match default discovery without redesigning the opt-in boundary.

Installed mode (`python -I -B scripts/check_gui.py --installed`) verifies every
product module origin before adding only the tests directory for these helpers.
It must not add the application checkout root. Tests use REPO_ROOT from base.py
for fixtures/scratch paths, whether running from a checkout or extracted sdist.

Groups: clipboard; document files/details; component/identity editing; item
navigation; voltage probes; node-voltage annotations; result/quantity presentation;
wire routing; shortcuts; viewport/layout.
No helpers or GUI test modules are included in the application wheel.
