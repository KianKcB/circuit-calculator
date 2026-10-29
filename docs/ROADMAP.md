# Development roadmap

Statuses are local verification claims, not claims about committed or released
versions. Updated 2026-10-29. The user's long-term phases remain the product
direction; research items require a separate feasibility decision.

| Phase | Status | Scope, dependency and acceptance gate |
| --- | --- | --- |
| 0 Audit | VERIFIED | All six source/document/test files plus ignore rules and Git state inspected; 59 baseline tests passed; findings in PROJECT_STATUS.md. |
| 1 Foundation | IN PROGRESS | NUM-1 numerical repairs verified. PKG-1 package and fresh core/DC installations verified on Windows Python 3.11/3.14. CI configured for Windows/Linux 3.11-3.14; hosted runs pending. |
| 2 Circuit model | VERIFIED for current DC subset | Immutable nodes and R/V/I components, explicit orientation and declared reference. Solver adds topology checks. Native persistence is implemented in phase 5; hierarchy and multi-terminal components remain planned. |
| 3 Linear DC | VERIFIED for documented small-network subset | MNA, node voltages, branch currents/power, topology/numerical diagnostics and analytical conservation checks. Affine resistor grids now verify 28/92/188-unknown cases and reference/order invariance. No arbitrary-range/large-network claim. See DC_VALIDATION.md. |
| 4 Advanced DC | NOT STARTED | Controlled sources, native Circuit wire/zero-ohm elements (GUI wires already contract), equivalent ports, superposition, floating-subnetwork policy and broader conditioning study; depend on phase 3. Each needs independent references and uniqueness tests. |
| 5 Persistence/netlists | VERIFIED for native JSON v1 | Metadata, deterministic round trips, strict size/schema validation and atomic no-clobber saves pass source and installed tests. SPICE/text netlist interoperability remains future work. |
| 6 First GUI | IN PROGRESS | Scoped names/values, isolated copies, engineering units project title/description editing and item search/reveal are implemented. Fit, zoom, bend/placement/routing/file workflows remain available; project v3 is unchanged. Broader editing and usability remain incremental. See IDENTITY_EDITING.md and PROJECT_DETAILS.md. |
| 7 Results/visualization | IN PROGRESS | Structured DC API/JSON, Tk results, SI engineering input/display and full-precision SI CSV export implemented. Exports preserve units/signs and reject stale GUI results. Selected component/net inspection is implemented; per-wire current is not reported. Plots and schematic annotations remain planned. See RESULT_INSPECTION.md. |
| 8 Dynamic model | NOT STARTED | Capacitors, inductors, initial conditions and analysis-specific steady-state rules; validate constitutive laws before AC/transient. |
| 9 AC | NOT STARTED | Complex MNA, phasor convention, frequency sweeps and Bode plots; depends on phase 8. Gate: analytical RC/RL/RLC references and limiting cases. |
| 10 Transient | NOT STARTED | Begin with linear backward Euler/trapezoidal comparison, time-step convergence, stiffness and initial-condition consistency; depends on phase 8. Gate: analytic waveforms and refinement tests. |
| 11 Nonlinear | NOT STARTED | Diodes then selected semiconductor models, Newton convergence safeguards; decide native vs established backend first. Explicit educational vs physical model fidelity. |
| 12 Advanced analyses | NOT STARTED | Sweeps, sensitivity, Monte Carlo, optimization, power efficiency and reports; depends on relevant validated engine. Deterministic seeds and independent sensitivity checks. |
| 13 Subcircuits/libraries | NOT STARTED | Scoped names, terminal mapping, parameterized hierarchy and symbols; depends on persistence. Reject recursion and validate flattened equivalence. |
| 14 GUI maturity | IN PROGRESS | Bounded Undo/Redo, stale-result protection, graphical project saves, explicit routing, unsaved-change protection single-component in-app Copy/Paste/Duplicate and Find item implemented. Multi-selection, richer routing, probes, accessibility, autosave and multiple projects remain planned. |
| 15 SPICE interoperability | NOT STARTED | Selected syntax and external benchmark suite; backend/version/license review first. Reject unsupported directives and document model differences. |
| 16 Specialized analysis | DEFERRED | Small-signal, noise, pole-zero, distortion, multiport, thermal and transmission-line features each require a separate mathematical specification and references. |
| 17 Research extensions | DEFERRED | Mixed-signal, RF/distributed, multiphysics, fitting, optimization, plugins and external APIs; feasibility and maintenance assessment before approval. |
| 18 Distribution/maintenance | IN PROGRESS | Local package 0.16.0, project v3/backward loading and CSV results v1. Isolated installed Tk checks and Linux display CI configured; hosted evidence pending. Bounded grid timing/accuracy script available. Publishing, licensing, releases and broader benchmarks remain planned. |

## Next reviewable batches

1. Review KEYS-1 (`4a632ad`), RESULTS-2 (`7a97197`) and GUI-10; verification is
   recorded in PROJECT_STATUS.md. Full GUI maturity remains in progress.
2. Organize the opt-in Tk suite by feature, retaining the runner, names/order,
   headless discovery and installed isolation. See TK_TEST_LAYOUT.md.
3. Inspect hosted CI evidence after a user push; local success is not hosted proof.

PERSIST-1/GUI-1 are committed as c4a13dd and REORG-1 as 992fbac. GUI-2 project
persistence is committed as f68462d, GUI-3 as c0951d8, and GUI-4 as 9dc4c4c.
The user authorized staging/committing completed batches on 2026-10-28; no push
authorization was given. Preserve unrelated changes and use explicit staged paths.
The complete GUI milestone is not marked verified.

Advanced DC can proceed independently where a concrete user circuit needs it.
Do not require all controlled devices or semiconductor models before a useful GUI.
