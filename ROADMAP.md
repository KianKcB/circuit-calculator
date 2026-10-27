# Development roadmap

Statuses are local verification claims, not claims about committed or released
versions. Updated 2026-10-27. The user's long-term phases remain the product
direction; research items require a separate feasibility decision.

| Phase | Status | Scope, dependency and acceptance gate |
| --- | --- | --- |
| 0 Audit | VERIFIED | All six source/document/test files plus ignore rules and Git state inspected; 59 baseline tests passed; findings in PROJECT_STATUS.md. |
| 1 Foundation | IN PROGRESS | Preserve CLI/core split; documentation and optional dependency declared. Next: repair legacy numerical defects with compatibility tests. Packaging, CI and version matrix remain planned. |
| 2 Circuit model | VERIFIED for current DC subset | Immutable nodes and R/V/I components, explicit orientation and declared reference. Solver adds topology checks. Persistence, hierarchy and multi-terminal components remain planned. |
| 3 Linear DC | VERIFIED for documented small-network subset | MNA, node voltages, all branch currents/power, topology and numerical diagnostics. Analytical examples and conservation tests required. No claim of arbitrary-range or large-network reliability. |
| 4 Advanced DC | NOT STARTED | Controlled sources, wires/zero-ohm contraction, equivalent ports, superposition, floating-subnetwork policy and broader conditioning study; depend on phase 3. Each needs independent references and uniqueness tests. |
| 5 Persistence/netlists | NOT STARTED | Versioned safe native format, strict input limits and deterministic round trips; depend on model and DC conventions. Reject unknown constructs; never evaluate file content. |
| 6 First GUI | NOT STARTED | After persistence and DC, compare frameworks/licensing and implement explicit electrical junctions, placement/editing/wiring, simulation and save/reload. Accept only model-equivalent end-to-end workflows. |
| 7 Results/visualization | IN PROGRESS | Structured DC results implemented. Engineering formatting, tables, SI units, CSV, plots and annotations planned; separate display rounding from calculations. |
| 8 Dynamic model | NOT STARTED | Capacitors, inductors, initial conditions and analysis-specific steady-state rules; validate constitutive laws before AC/transient. |
| 9 AC | NOT STARTED | Complex MNA, phasor convention, frequency sweeps and Bode plots; depends on phase 8. Gate: analytical RC/RL/RLC references and limiting cases. |
| 10 Transient | NOT STARTED | Begin with linear backward Euler/trapezoidal comparison, time-step convergence, stiffness and initial-condition consistency; depends on phase 8. Gate: analytic waveforms and refinement tests. |
| 11 Nonlinear | NOT STARTED | Diodes then selected semiconductor models, Newton convergence safeguards; decide native vs established backend first. Explicit educational vs physical model fidelity. |
| 12 Advanced analyses | NOT STARTED | Sweeps, sensitivity, Monte Carlo, optimization, power efficiency and reports; depends on relevant validated engine. Deterministic seeds and independent sensitivity checks. |
| 13 Subcircuits/libraries | NOT STARTED | Scoped names, terminal mapping, parameterized hierarchy and symbols; depends on persistence. Reject recursion and validate flattened equivalence. |
| 14 GUI maturity | NOT STARTED | Undo/redo, copy/paste, routing, labels, probes, accessibility, autosave and multiple projects; depends on first GUI and explicit command model. Test connectivity after edits and recovery. |
| 15 SPICE interoperability | NOT STARTED | Selected syntax and external benchmark suite; backend/version/license review first. Reject unsupported directives and document model differences. |
| 16 Specialized analysis | DEFERRED | Small-signal, noise, pole-zero, distortion, multiport, thermal and transmission-line features each require a separate mathematical specification and references. |
| 17 Research extensions | DEFERRED | Mixed-signal, RF/distributed, multiphysics, fitting, optimization, plugins and external APIs; feasibility and maintenance assessment before approval. |
| 18 Distribution/maintenance | NOT STARTED | Installable package, entry points, releases, platform matrix, benchmarks, migrations and notices; incrementally introduce before user distribution, not only at roadmap end. |

## Next reviewable batches

1. Repair standalone numerical calculations: reproduce overflow/underflow and
   mixed numeric behavior, define compatibility policy, implement regression fixes.
2. Strengthen installation/CI reproducibility and test the declared Python range.
3. Native versioned JSON persistence plus a programmatic DC example/CLI workflow;
   round-trip and malformed-input tests before GUI work.
4. Decide GUI framework, then build the first supported DC editing vertical slice.

Advanced DC can proceed independently where a concrete user circuit needs it.
Do not require all controlled devices or semiconductor models before a useful GUI.
