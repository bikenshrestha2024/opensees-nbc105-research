# V132 executed validation

## Automated and interface checks

37 regression checks cover inherited behavior plus CQC limits, native response-spectrum acceleration units, the static comparison eligibility flag, service/ultimate workbook selection, numerical adopted-period provenance, drift limits and the history edge/deformation exporter. All implementation Python files are parsed and root loaders imported for packaging.

The main, gravity, modal, spectrum, ESM, linear and nonlinear interfaces were exercised through their constructors/input population paths. Both history forms filled model/interpreter/output/story paths, T1 X/Y, Tn X/Y and damping calibration periods. SLS/ULS references remain separated. No calibration/readiness confirmation was automatically signed.

The ESM GUI exported and syntax-checked 24 runners: two limit states, two directions, two force signs and E0/E+/E- cases. One full ULS X+ E0 comparison solver case was executed; exporting a runner is not a claim that all 24 were solved.

## Supplied-model runs on a workspace copy

The 25-storey assembled model retained 1,612 frame segments, 3,300 shells and full floor-diaphragm membership. Gravity total was 286,447.788933 kN. Four signed initial P-Delta reference checks converged before the ULS comparison.

The ULS X+ E0 static comparison applied 24,923.345025 kN and returned -24,923.345025 kN horizontal base reaction; equilibrium error was about 1.17e-13 percent. Its ULS ESM design-ineligibility remark remained visible. This does not turn the comparison into an eligible design method.

Full MRSM runs covered SLS/ULS, X/Y and centered/positive/negative eccentric inertia cases: 12 response cases. Forty eigenmodes exceeded 90 percent directional mass; no returned mode was at/above 33 Hz.

| State / direction | Centered modal base shear before force scale, kN | Force scale |
|---|---:|---:|
| ULS X | 32,965.195 | 1.000000 |
| ULS Y | 23,952.304 | 1.103660 |
| SLS X | 27,285.005 | 1.000000 |
| SLS Y | 19,718.913 | 1.094824 |

Maximum relevant per-mode native force-equilibrium residual across these runs was approximately 0.143 percent. The reported residuals are retained. The maximum computed edge design drift among the ULS cases was about 0.0048265; among SLS cases it was about 0.0011161. These response screens lie below the implemented drift thresholds; they do not establish member capacity, valid cracked-wall calibration or global design acceptance.

## History pipeline check

A deliberately synthetic 0.045-second paired input ran nine requested integration steps in both XY and YX orientations on the supplied elastic model. It exercised gravity-offset subtraction, floor rotation recording, per-storey/edge drift, summaries and deformation export. Its small acceleration and two-percent damping are software-test inputs, not a project motion or recommended design damping. The test summary is labelled SYNTHETIC_PIPELINE_ONLY.

No full earthquake ensemble or calibrated nonlinear full-building earthquake run was performed for this release. Nonlinear readiness remains gated. Shared postprocessing and existing nonlinear input/readiness tests were exercised.

## Provenance and file interpretation

Worked_Example_V132 contains selected final outputs and input-population evidence. Modal cache JSON records are the numerical reference; their elapsed_seconds field measures the modal stage. The timing histories are curated to the final completed stage entries. Formatting/export duration is distinct from gravity/eigen/solver duration.

The function inventory covers 454 implementation functions. It is a source-location/hash inventory, not a claim that every branch and possible structure is validated. Source workbooks and live D: exports were not overwritten.
