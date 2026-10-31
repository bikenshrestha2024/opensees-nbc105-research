# V133 capabilities and limits

The feature pass implements the controls and inspections listed in START_HERE.md and maps all earlier requests in REQUEST_COVERAGE_V133.md. Actual verification is listed in VALIDATION_V133.md.

Still requiring engineering evidence:

- Project wall/frame/brace/device constitutive calibration, rebar/detailing, wall/coupling-member representation and outrigger/gusset offsets. Unsupported structural offsets remain blockers; geometry is not invented.
- Geotechnical site-class evidence, independent ETABS story load/mass reconciliation, physical overlap conventions, cracked stiffness/mesh convergence and support/foundation assumptions.
- Weak-storey capacities and reviewed plan/load-path discontinuity evidence. Screens remain INCOMPLETE where absent.
- Actual nonlinear readiness and building-wide earthquake suite assessment. Synthetic examples test software only.

Analysis boundaries:

- MRSM uses the documented fixed-eigenbasis eccentric-influence cases. Known high-frequency modes require a missing-mass treatment that is not implemented here. Member component envelopes do not constitute concurrent member interaction/design combinations.
- Modal classifications are candidates. Modal damping requires iterative solution and review of its included initial modal basis. Committed-Rayleigh checks are initial-state checks, not a guarantee against later spurious damping or a substitute for FVD energy assessment.
- Playback is recorded floor translation/rotation reconstruction, not full FE curvature/vertical animation. Partial histories remain partial.
- Benchmark calibration overlays and a device/wall energy-partition research study require appropriate experimental/response data. No such completed study is claimed.
- No comprehensive independent line-by-line mathematical certification, completed member design or blanket NBC approval is claimed by an import check or test count.

No live D: inputs/results were modified. Existing releases were preserved. Root historical module names are compatibility surfaces; actual implementations remain in components/.
