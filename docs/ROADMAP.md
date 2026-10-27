# Development roadmap

Statuses are local verification claims, not claims about committed or released
versions. Updated 2026-10-27. The user's long-term phases remain the product
direction; research items require a separate feasibility decision.

| Phase | Status | Scope, dependency and acceptance gate |
| --- | --- | --- |
| 0 Audit | VERIFIED | All six source/document/test files plus ignore rules and Git state inspected; 59 baseline tests passed; findings in PROJECT_STATUS.md. |
| 1 Foundation | IN PROGRESS | NUM-1 numerical repairs verified. PKG-1 package and fresh core/DC installations verified on Windows Python 3.11/3.14. CI configured for Windows/Linux 3.11-3.14; hosted runs pending. |
| 2 Circuit model | VERIFIED for current DC subset | Immutable nodes and R/V/I components, explicit orientation and declared reference. Solver adds topology checks. Persistence, hierarchy and multi-terminal components remain planned. |
| 3 Linear DC | VERIFIED for documented small-network subset | MNA, node voltages, all branch currents/power, topology and numerical diagnostics. Analytical examples and conservation tests required. No claim of arbitrary-range or large-network reliability. |
| 4 Advanced DC | NOT STARTED | Controlled sources, wires/zero-ohm contraction, equivalent ports, superposition, floating-subnetwork policy and broader conditioning study; depend on phase 3. Each needs independent references and uniqueness tests. |
| 5 Persistence/netlists | VERIFIED for native JSON v1 | Metadata, deterministic round trips, strict size/schema validation and atomic no-clobber saves pass source and installed tests. SPICE/text netlist interoperability remains future work. |
| 6 First GUI | IN PROGRESS | GUI-3 adds independent R/V/I placement, body movement/rotation and explicit terminal wiring with project-v2 persistence and v1 loading. Junction-based editing, safe file workflows and async results remain available. Multi-segment routing/splitting remain planned. See COMPONENT_EDITING.md and SCHEMATIC_FORMAT.md. |
| 7 Results/visualization | IN PROGRESS | Structured DC API/JSON command and Tk node/branch results implemented. GUI formats values for display without changing numerical results. SI prefixes, CSV, plots and schematic result annotations remain planned. |
| 8 Dynamic model | NOT STARTED | Capacitors, inductors, initial conditions and analysis-specific steady-state rules; validate constitutive laws before AC/transient. |
| 9 AC | NOT STARTED | Complex MNA, phasor convention, frequency sweeps and Bode plots; depends on phase 8. Gate: analytical RC/RL/RLC references and limiting cases. |
| 10 Transient | NOT STARTED | Begin with linear backward Euler/trapezoidal comparison, time-step convergence, stiffness and initial-condition consistency; depends on phase 8. Gate: analytic waveforms and refinement tests. |
| 11 Nonlinear | NOT STARTED | Diodes then selected semiconductor models, Newton convergence safeguards; decide native vs established backend first. Explicit educational vs physical model fidelity. |
| 12 Advanced analyses | NOT STARTED | Sweeps, sensitivity, Monte Carlo, optimization, power efficiency and reports; depends on relevant validated engine. Deterministic seeds and independent sensitivity checks. |
| 13 Subcircuits/libraries | NOT STARTED | Scoped names, terminal mapping, parameterized hierarchy and symbols; depends on persistence. Reject recursion and validate flattened equivalence. |
| 14 GUI maturity | IN PROGRESS | Bounded Undo/Redo, stale-result protection, graphical project saves and unsaved-change protection implemented. Copy/paste, routing, labels, probes, accessibility, autosave and multiple projects remain planned. |
| 15 SPICE interoperability | NOT STARTED | Selected syntax and external benchmark suite; backend/version/license review first. Reject unsupported directives and document model differences. |
| 16 Specialized analysis | DEFERRED | Small-signal, noise, pole-zero, distortion, multiport, thermal and transmission-line features each require a separate mathematical specification and references. |
| 17 Research extensions | DEFERRED | Mixed-signal, RF/distributed, multiphysics, fitting, optimization, plugins and external APIs; feasibility and maintenance assessment before approval. |
| 18 Distribution/maintenance | IN PROGRESS | Local package 0.5.0 adds project-v2 placements with v1 loading and compatible command/import paths. CI configured; hosted evidence pending. Publishing, licensing, releases, benchmarks and broader migrations remain planned. |

## Next reviewable batches

1. Inspect first hosted CI run after the user pushes; local package checks are complete.
2. Review GUI-3 placement, movement, rotation, terminal wiring and project-v2 saves.
3. Specify multi-segment wire geometry and explicit segment splitting/junction
   creation. Preserve crossing/proximity semantics, define the next schema decision,
   and extend merge/split/Undo/GUI tests. Add display-enabled CI when practical.

PERSIST-1/GUI-1 are committed as c4a13dd and REORG-1 as 992fbac. GUI-2 project
persistence is committed as f68462d. GUI-3 is the local review batch.
Review/commit remains the user's action.
The complete GUI milestone is not marked verified.

Advanced DC can proceed independently where a concrete user circuit needs it.
Do not require all controlled devices or semiconductor models before a useful GUI.
