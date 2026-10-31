# V167 — current baseline and handoff

This V167 handoff identifies the current project baseline and validation status; it does not claim that the full building model is validated. The working folder was previously labeled V166, but the available top-level release note was V165 and the root README still referenced V134. Older files and run evidence are retained rather than silently removed.

## Entry points

- Main ETABS-to-OpenSeesPy workflow: `01_START_ETABS_TO_OPENSEES.py` and `RUN_ETABS_TO_OPENSEES.py`.
- Ordered launchers and the recommended analysis progression: `00_READ_FIRST_RUN_ORDER.md`.
- Building exploratory nonlinear time-history GUI: `18_BUILDING_FULL_NONLINEAR.py`.
- Independent literature component demonstration: `17_LITERATURE_COMPONENT_DEMO.py` (`RUN_LITERATURE_DEMO.py` remains a compatibility alias).
- Building research implementation: `components/nonlinear_time_history/building_exploratory.py`.
- Research building material assignments: `components/nonlinear_time_history/research_building_materials.py`.
- Component/device mechanics: `components/sections/devices.py`.
- Current modeling and material-specific literature gates: `Research_Components/02_MODELLING_BASIS.md`.
- Preserved assembled export and runtime: `Saved_Project_V156/`.

Refresh/rebuild the runtime from the current source before a production-sized study. Do not mix scripts, GUI modules, or runtime copies from different historical versions. Read each run's assumptions/configuration report and preserve the source export unchanged.

## What this release establishes

- The modeling basis now separates RC beam, RC column, RC core wall, conventional steel outrigger, BRB, and FVD validation requirements.
- A source-traced paper parameter or a successful material/element command check is not an experimental reproduction and is not project calibration.
- Regression checks in the available Python environment passed: `python -m compileall -q components`, `python tests\verify_v133.py` (10 tests; one native OpenSeesPy test skipped because the package is unavailable), and `python tests\verify_v150.py` (6 tests).
- `components/sections/mapping_audit.py` records the prior gravity preload as converged and the Kobe transient as failed at its first step with return code `-3`.

## Do not interpret as validated

- The full earthquake history has not been completed or verified here. The first transient failure remains unresolved.
- OpenSeesPy is unavailable in the validation environment; no new native solver result was produced for this handoff.
- The PEER wall material values are a specimen-level reference card, not calibrated project values. The configured PEER full-wall building history has not been shown to reproduce a tested wall specimen.
- There is no selected/reproduced RC beam experiment in the current evidence set. Column, wall, steel outrigger, BRB, and FVD sources are benchmarks to reproduce, not permission to transfer their values blindly.
- Do not select or rank a “best” outrigger combination until component checks, project input reconciliation, full-record convergence, device demand outputs, and independent building checks pass.

## Run order for validation

1. Reconcile exported geometry, section/reinforcement assignments, loads, masses, supports, and units against the ETABS source.
2. Select a specimen-specific benchmark for each material/component and reproduce its geometry, loading protocol, and measured response. Keep fitted and held-out comparisons distinct.
3. Check nonlinear frame, wall, steel brace, BRB, and FVD behavior independently before transferring parameter cards to the building.
4. Diagnose the existing transient failure without changing material, mesh, loading, and solver settings simultaneously. Verify a complete record and time-step sensitivity before reading performance conclusions.
5. Add and verify per-device force, relative stroke, velocity, and dissipated-energy histories before comparing FVD/BRB alternatives.
6. Preserve per-run assumptions, input hashes, solver settings, convergence status, and complete raw histories. Exclude failed/incomplete runs from any optimum ranking.

See `RELEASE_NOTES_V167.md` for the scope of this handoff. The project is research software, not a design certification.
