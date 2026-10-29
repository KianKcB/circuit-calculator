# TESTS-1: organize the opt-in GUI harness

Design contract, 2026-10-29. The GUI runner has grown beyond 1,800 lines. Split
its workflows by feature while keeping the existing command, TkWorkflowTests
class, method names, alphabetical execution order and all assertions.
Implemented and locally VERIFIED as TESTS-1; exact counts/evidence are in TESTING.md.

Use tests/gui_workflows/ for non-test-prefixed mixin modules plus a shared base.
Its initializer must import no Tk or application code. Standard unittest discovery
may traverse the package but must not load GUI modules or require a display.
scripts/check_gui.py stays the opt-in launcher and assembles one TestCase class.
Mixins themselves must not derive from unittest.TestCase or create duplicate runs.

Keep installed-mode origin checks before loading helpers. Only the tests directory
may be added to sys.path in isolated installed mode; the application checkout root
must stay excluded. Source mode retains its explicit product-root import path.
Source archives must include helper Python files and their README; wheels continue
to contain only application/compatibility modules.

Move method bodies mechanically. Preserve worker join, window destruction and
main-thread gc.collect cleanup order. Replace the two script-relative workspace
lookups by one shared REPO_ROOT constant, anchored to the helper's actual path.
Every other function's normalized AST must remain identical. Verify unique names,
test count and ordering, source/core discovery and installed GUI regressions.

This is a test-only maintenance batch. No application version/schema/dependency,
solver, model or feature behavior change is intended. Keep direct focused calls
such as `python -B scripts/check_gui.py TkWorkflowTests.test_find_no_match_query_limit_and_correction_keep_dialog_open` working.
