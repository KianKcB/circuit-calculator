# RESULTS-1: DC results CSV v1

Contract, 2026-10-28. Export existing validated results; no solver/model changes.

UTF-8 CSV with standard quoting and CRLF record endings. Header:
`format_version,entity_type,identifier,quantity,value,unit`.
Each row has version 1. Reference row identifies the zero-volt reference, node
rows give analyzed net voltages, element rows give voltage/current/power, and
analysis rows give scaled condition number, maximum KCL residual and power balance.
Units are V, A, W or 1 (dimensionless). Values use round-trippable finite float
text in base SI units, with no display rounding or SI prefixes. Signed source
currents and absorbed-positive/delivered-negative power are retained.

Identifiers use literal `node:` / `element:` prefixes, with `analysis` for
diagnostics. Strip only the known prefix to recover the exact original name;
Unicode, quotes, commas and line breaks are preserved by CSV quoting. Prefixes
also keep arbitrary circuit names from becoming leading spreadsheet expressions.
No metadata/title or user-supplied expression is evaluated. Reference is duplicated
as an explicit row; GUI aliases of a compiled net are not duplicated as new nets.
Import as UTF-8 in spreadsheet programs. Size limit: 8 MiB; never truncate.

APIs in results_io.py: dumps_results_csv(result), save_results_csv(result, path,
overwrite=False, protected_path=None). Require DCResult and finite values,
ElementResult entries, valid identifiers, a declared zero-volt reference and
ordinary mappings. Serialize before touching the destination. Reuse atomic
no-clobber/replacement primitives; failures preserve destination and clean temp
files. An optional protected input/project path rejects same resolved paths,
symlinks and existing hard-link aliases before writing. Ordinary filesystem
errors remain OSError subclasses. Same hard-link/durability limits as project saves.

CLI: `dc INPUT.json --csv OUTPUT.csv [--overwrite-csv]`. Default JSON stdout is
unchanged; requested CSV is written after a successful solve and before JSON.
Never replace the input circuit, even with overwrite. Existing output requires
the explicit flag. A CSV failure yields error/exit 1 with no JSON output; bad
arguments use exit 2. Stdout and a file are not a single atomic transaction.

GUI Export CSV is enabled only for the current accepted result. Edits, history,
document boundaries and a new simulation disable it; camera-only changes retain
valid results. Export/Cancel/failure do not change graph, dirty state, history or
results. Ask before replacing an existing output, protect the open project file,
and never export an old worker result. No cached result is loaded from disk.

Acceptance: independent divider values/signs, exact float recovery, deterministic
rows, Unicode/control/quote round trips, literal identifiers, malformed/nonfinite
data rejection, atomic file preservation/failure cleanup, path-alias protection,
CLI modes/error ordering, GUI current/stale/cancel/failure/view behavior and fresh
core/DC installed commands. Package 0.9.0; circuit v1/project v3 unchanged.
