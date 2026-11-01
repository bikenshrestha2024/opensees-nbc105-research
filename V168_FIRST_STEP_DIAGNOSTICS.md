# V168 — first-step NLTHA isolation probes

This diagnostic update preserves the ordinary XY/YX run unless optional settings are supplied in the exploratory RunConfig. It does **not** repair the root cause of an OpenSees tangent-system failure or validate the structural model.

New optional JSON keys:

- `"diagnostic_excitation": "XY"` (default): original behavior.
- `"diagnostic_excitation": "X"`: real X excitation, Y record replaced by zero.
- `"diagnostic_excitation": "Y"`: real Y excitation, X record replaced by zero.
- `"diagnostic_excitation": "ZERO"`: both records replaced by zero.
- `"diagnostic_zero_damping": true`: temporarily sets all Rayleigh coefficients to zero.
- `"diagnostic_mass_damping": true`: existing separate mass-proportional damping probe. Do not combine with zero damping.
- `"transient_system": "SparseGeneral"` and `"gravity_system": "SparseGeneral"`: pivoting solver alternatives already supported in V167.

Example additions to a **copy** of a config file:

```json
{
  "diagnostic_excitation": "ZERO",
  "diagnostic_zero_damping": true,
  "transient_system": "SparseGeneral",
  "gravity_system": "SparseGeneral"
}
```

Run each diagnostic in a **new isolated model and distinct output directory**; do not reuse a domain after a nonfinite solver failure. Start ULS only and a short trial, then compare ZERO, X, Y and XY with consistent material settings. Every probe still runs gravity and eigenanalysis and applies both UniformExcitation patterns (with zero-valued records on inactive axes). The existing XY/YX mapping is retained, so X and Y denote global excitation directions.

Run `21_TRACE_FAILED_ELEMENT.py <failed_run_folder> --tag 110280` to map a reported solver tag to its ETABS source object. When a gravity failure occurs before the element-map file is written, the tool uses the assembly's deterministic frame/shell tag ranges and labels the result as a fallback. A first nonfinite response after failure can be a downstream symptom.

Exploratory failures now write `INCOMPLETE.json` with the selected profile, failing stage, exception type/message, traceback, run configuration, and solver/probe context. Transient failures also write the same evidence to each orientation's `FAILED.json`, including accepted-history row count and solver retry diagnostics. When a failed step returns non-finite responses, `First_Step_Failure_Evidence.json` records bounded node/element response evidence and maps element tags to source ETABS areas when the element map is available; these post-failure values are clues, not proof of the cause. Evidence from a step recovered by a solver fallback is removed. The GUI writes `Process_Exit.json` alongside `Run.log`, preserving the subprocess exit code and whether the expected summary was produced, including when a native process terminates before Python can write its own failure report. Run outputs must remain outside the source export folder.

Interpretation:
- Gravity complete + eigen complete is **not** proof of transient stability.
- ZERO passes, earthquake fails: examine inertial forcing, mass/constraints, wall tangent, and material behavior.
- ZERO fails: investigate the dynamic initialization/effective matrix independently of earthquake strength.
- SparseGeneral succeeds but UmfPack fails: compare actual responses and tangent/conditioning; solver switching is not physical calibration.
- Do not lower strengths or change reinforcement simply to obtain convergence.

Observed on 2026-11-01 with the saved building export: full-wall gravity passed and the 20-mode eigen solve completed. A zero-motion, zero-damping 0.005 s step passed; a Kobe X-only, zero-damping 0.005 s step failed. Post-failure evidence found non-finite element forces at tags 110280 and 112778, mapped to `AREA:354` and `AREA:482`. Both are `Wall 600` / M45 shell panels in the global X-Z plane, at x=6.0–6.4 m, z=2.3–3.8 m, and y=6 m / 12 m; each is 0.4 m wide, 0.6 m thick, and 1.5 m high. No nodal displacement was non-finite. This localizes the trigger to the X-excited nonlinear wall response, but the post-failure element values may be contaminated and do not establish the constitutive or geometric root cause. The full record remains unresolved.

Known limitations: this change does not independently compute tangent matrix rank, verify the actual FSAM cyclic parameters, add a standalone X/Y GUI switch, or perform full-record model validation. The existing post-failure localForce check may encounter contaminated trial state.
