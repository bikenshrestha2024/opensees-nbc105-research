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

Run `21_TRACE_FAILED_ELEMENT.py <failed_run_folder> --tag 110280` to map a reported solver tag to its ETABS source object using that run's element-map file. A first nonfinite response after failure can be a downstream symptom.

Interpretation:
- Gravity complete + eigen complete is **not** proof of transient stability.
- ZERO passes, earthquake fails: examine inertial forcing, mass/constraints, wall tangent, and material behavior.
- ZERO fails: investigate the dynamic initialization/effective matrix independently of earthquake strength.
- SparseGeneral succeeds but UmfPack fails: compare actual responses and tangent/conditioning; solver switching is not physical calibration.
- Do not lower strengths or change reinforcement simply to obtain convergence.

Known limitations: this change does not independently compute tangent matrix rank, verify the actual FSAM cyclic parameters, add a standalone X/Y GUI switch, or perform full-record model validation. The existing post-failure localForce check may encounter contaminated trial state.
