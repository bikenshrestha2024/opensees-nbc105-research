# V150 startup and nonlinear performance review

Start **01_START_ETABS_TO_OPENSEES.py** after extracting the entire ZIP. Use **12_NONLINEAR_PERFORMANCE.py**, the main Performance assessment menu, or the nonlinear-history window's Performance objectives / component acceptance button.

## Startup
The unmodified V149 fresh child stayed alive during a ten-second opening test here; the reported user crash was not reproduced. V149 hid child stderr. V150 retains stdout/stderr in `99_Runtime_Automatic/Startup_Logs`, with `LATEST.txt` pointing to the current log, and displays nonzero child exits. GUI callback errors are logged separately. Test-only OPENSEES_STARTUP_SMOKE=1 exercises construction/event loop/clean shutdown. No claim is made that an unobserved platform-specific crash cause was identified.

## Nonlinear performance
Editable ULS/SLS criteria include objective, model SHA256, expected pair IDs, units, force/deformation control, acceptance limit, source/clause and review state. Metric demand CSVs identify pair, XY/YX orientation, completion, model and result file. Pair orientations are enveloped before suite statistics. Missing/failed/truncated cases cannot be omitted to obtain PASS. Fewer than three pairs on the torsion-sensitive 3D route remain a trial. Exactly seven records remains an interpretation item. An optional MAXIMUM aggregation can retain a conservative component envelope; default NBC_SUITE follows the selected suite rule. The program does not generate unrecorded component demands.

Drift screens: ULS 0.025 and SLS 0.006, NBC 5.5.3. The nonlinear drift cross-reference at 9.3.3.1 points to 5.6 in the published edition; review that discrepancy. Nonlinear member deformation acceptance refers to material standards under 9.3.3.2. Generic IO/LS/CP rotation/strain values are deliberately not assigned to this core. Residual drift, plastic rotation, concrete/steel strains, wall/joint shear, BRB ductility and FVD force/stroke have explicit unset project limits. Give member/station/axis-specific metric names when necessary. All default criteria require review.

Corrected a conflict in the nonlinear summary AND workbook: the elastic-history Rmu member-action reduction instruction was incorrectly repeated there. Nonlinear acceptance now uses its own material-standard basis.

Steps: create state template; specify objective and actual assembly-data SHA256; list complete expected pairs; enter cited limits for actual reinforcement/axial load and devices; export metric CSV template; populate completed full-record evidence; load demands; assess/export JSON. A supplied-criteria PASS does not certify whole-building adequacy. GUI criteria files are user-saved; they do not change constitutive models or automatically rewrite analysis settings.

## Evidence and remaining limits
59 regression tests passed, covering export/load equilibrium, units, diaphragms, spectra, inputs and performance guards. Static parse/duplicate-top-level-definition scan covered all 69 current component Python modules with no duplicate names. This is not a line-by-line independent structural audit of every historical artifact. Historical versioned wrappers remain intentionally for import compatibility. The old synthetic mesh test was updated from a fixed two-cell assumption to positive-cell area conservation; synthetic extraction metadata now meets the current production input contract. Production extraction gates were retained.

Concrete01, Steel02, FVD and idealized BRB numerical diagnostics completed again. E-SFI and Lu short smoke tests completed; experimental reproduction remains incomplete. Original SFI_MVLEM_3D gravity still fails with default UmfPack. Alternative backends passed gravity but subsequent transient steps failed; no physical singularity or calibrated solution is claimed. The original SFI attempt now runs in an isolated native subprocess with its own log, preventing native termination from losing the desktop/material results.

Existing important project limitations remain: production elastic wall gross in-plane stiffness is not automatically the NBC effective wall EI; section capacities, reinforcement, wall FSAM mappings, unconfined-core calibration, degradation/pinching and independent wall validation require evidence. Saved previous results are not recalculated by upgrading. Do not label the building NBC-compliant from numerical checks alone. Live D: project exports were not changed.

## Sources
- [Official NBC 105:2025, second revision](https://giwmscdnone.gov.np/media/files/NBC_105_2025_Seismic%20Design%20of%20Buildings%20in%20Nepal_lqqvx6a.pdf), accessed 27 October 2026; sections 5.5.3 and 9.3.2–9.3.3.
- [NIST GCR 17-917-46v1, nonlinear structural analysis guidance](https://nvlpubs.nist.gov/nistpubs/gcr/2017/NIST.GCR.17-917-46v1.pdf), 2017. Modelling, acceptance basis and uncertainty.
- [NIST GCR 17-917-46v3, reinforced concrete moment frames](https://nvlpubs.nist.gov/nistpubs/gcr/2017/NIST.GCR.17-917-46v3.pdf), 2017. Frame component guidance; not automatic unconfined core-wall limits.
- [Original SFI-MVLEM-3D](https://kkolozvari.github.io/SFI-MVLEM-3D/) and [E-SFI-MVLEM-3D](https://kkolozvari.github.io/E-SFI-MVLEM-3D/). Distinct formulations; neither short diagnostic establishes project validation.
