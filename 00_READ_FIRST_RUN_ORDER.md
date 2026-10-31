# Ordered entry points — V167

Run `01_START_ETABS_TO_OPENSEES.py` for the integrated workflow. The numbered
files below are direct launchers or focused utilities, not a script that must
be run from top to bottom. Keep the complete package together; component
modules and versioned `OpenSees_*.py` files are imported by the launchers and
should not be renamed.

| Order | Entry point | Purpose |
|---|---|---|
| 01 | `01_START_ETABS_TO_OPENSEES.py` | Start the main ETABS-to-OpenSeesPy GUI. |
| 02 | `02_MODEL_INPUTS_AND_READINESS.py` | Review model inputs and readiness evidence. |
| 03 | `03_GRAVITY.py` | Inspect gravity loads and reactions. |
| 04 | `04_MODAL_ULS_SLS.py` | Run and compare modal ULS/SLS cases. |
| 05 | `05_EQUIVALENT_STATIC.py` | Calculate and run equivalent-static cases. |
| 06 | `06_RESPONSE_SPECTRUM.py` | Run response-spectrum analysis and review. |
| 07 | `07_LINEAR_TIME_HISTORY.py` | Run linear time-history analysis. |
| 08 | `08_BUILDING_NONLINEAR_TRIAL.py` | Exploratory nonlinear frames with elastic walls; short trial first. |
| 09 | `09_NONLINEAR_REVIEWED_MODEL.py` | Reviewed nonlinear workflow; readiness and calibrated inputs are required. |
| 10 | `10_WALL_VALIDATION.py` | Run the wall-validation workflow. |
| 11 | `11_MATERIAL_DEVICE_VALIDATION.py` | Review nonlinear material and device validation. |
| 12 | `12_NONLINEAR_PERFORMANCE.py` | Review nonlinear performance criteria and outputs. |
| 13 | `13_STEEL02_CALIBRATION.py` | Open Steel02 calibration. |
| 14 | `14_MATERIAL_PARAMETER_SETUP.py` | Configure material parameter studies. |
| 15 | `15_LITERATURE_MATERIAL_PROFILES.py` | Inspect literature material profiles and their limits. |
| 16 | `16_COMPONENT_RESULTS.py` | View component-validation results. |
| 17 | `17_LITERATURE_COMPONENT_DEMO.py` | Launch the independent published-parameter component demo. |
| 18 | `18_BUILDING_FULL_NONLINEAR.py` | Run the exploratory full-wall building trial; not design acceptance. |
| 20 | `20_AUDIT_LOAD_CONNECTIONS.py <export-folder>` | Write read-only load/connectivity evidence for an assembled export. |

There is no step 19 in this release. `RUN_ETABS_TO_OPENSEES.py` remains the
compatibility target of launcher 01. `RUN_LITERATURE_DEMO.py` remains a
compatibility alias for launcher 17. Do not mix the preserved runtime under
`Saved_Project_V156/` with modules from another release; refresh/rebuild an
export from the complete current package before new analyses.

Suggested analysis progression: reconcile the ETABS export and input inventory;
check gravity/load paths and modal behavior; compare equivalent-static, response
spectrum, and linear histories; then run short nonlinear diagnostic trials.
Only treat nonlinear results as research evidence after component/material
benchmarks, model-specific readiness review, full-record convergence, and
response checks are complete. A literature template or a successful short
solver trial does not validate the building.
