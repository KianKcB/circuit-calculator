# Development workflow

Read PROJECT_STATUS.md, ARCHITECTURE.md and ROADMAP.md, then inspect current Git
status; recorded status is not a substitute for live inspection. Preserve staged
and unstaged user changes. Do not commit, push, reset or switch branches without
the user's authorization.

The repository currently runs directly from its root. The formula CLI needs only
the standard library. For DC solving in a separate environment:

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dc.txt
.venv\Scripts\python -m unittest -v
```

The above setup is guidance, not a claim a fresh installation was tested.
Local verification used Python 3.11.9 and pre-existing NumPy 1.26.4. README's
Python 3.7 minimum is historical; compatibility is not verified on that runtime.
Avoid newer syntax until a minimum-version decision is made.

Before each feature, document scope, physical laws, units, sign conventions,
degenerate cases, API, compatibility, alternatives and acceptance tests. Keep
domain data, numerical algorithms and I/O separate. Run focused tests, then
the full suite. Record exact outcomes and unresolved limitations. Stop at a
coherent review checkpoint and update the next action in PROJECT_STATUS.md.

No lint/type-check/CI or packaging configuration exists yet. Add a minimal
toolchain in a distinct foundation batch; do not claim these checks have run.
