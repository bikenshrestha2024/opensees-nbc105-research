# V148 - result coverage, settings audit and ETABS comparison

Start 01_START_ETABS_TO_OPENSEES.py. Use the validation buttons in Section / Material Review: NBC settings audit; ETABS comparison; Wall validation. Run 10_WALL_VALIDATION.py directly for wall diagnostics. Root stage launchers are entry points; numbered internal helpers are not a list of scripts to run.

## Changes addressing the latest comments
1. NBC settings audit exposes configured gravity/mass/slab values and unresolved wall stiffness. AS_CONFIGURED DL+0.3LL is a preload, not proof that every design load combination was solved. ULS/SLS stiffness context and load-combination factors are distinct.
2. ETABS comparison reads saved modal, ESM response and MRSM results. It exports normalized CSVs, a case/unit/basis template and differences; select a row to plot its exact case and metric. Fill ETABS values from matching exports. No automatic percent-error acceptance threshold. Duplicate case keys are rejected rather than silently combining runs. This is a comparison interface, not an ETABS reinforcement-design engine.
3. Deflection and section tabs now expose recorded vertical displacement and concurrent gravity member end actions where available. No capacity or limit is invented. Gravity totals are not DL-only increments and cannot be superposed again with a preloaded seismic result. Actual reinforcement, capacity interaction, stability, detailing and project deflection criteria remain necessary.
4. ESM finite-input checks added; tested weight calculation and force balance. Ineligible ULS ESM remains a clearly identified comparison reference, not an eligible design method. Calculating floor forces does not run the structural solver. Run exported cases to obtain displacement and stiffness.
5. Modal subprocess output streams live into the log, with rebuild/gravity, eigenmode and export stages described.
6. MRSM Both runs ULS then SLS, explicitly logging the batch plan and each state. Each state contains X/Y and centered/positive/negative eccentricity cases. New MRSM story results include elastic/design displacement. NBC 7.5 force scaling is not applied to displacement/drift.
7. Matching saved centered static stiffness results are reused for soft-storey screening, without duplicate rows. Otherwise Calculate stiffness + torsion performs the required lateral solve. Modal periods alone do not establish storey stiffness. Weak storey needs strength, not stiffness. Diaphragm discontinuity and out-of-plane offset remain explicitly pending where evidence is absent.
8. Wall validation has a labelled validation section and direct launcher. Preserved V147 diagnostics and source provenance; no new experimental validation is claimed.

## Material limitation found during this review
Production elastic wall shells currently retain source gross in-plane membrane stiffness. NBC Table 3-1 effective wall EI (cracked ULS/SLS 0.50/0.70; uncracked 0.80/0.90) is NOT automatically represented by changing a slab out-of-plane bending factor. Do not interpret current wall-model periods or lateral results as verified effective-stiffness design results. A justified wall idealization and ETABS match remain required. No silent change of wall E, axial stiffness or shear stiffness was made to imitate an EI modifier. This finding is shown in the settings audit, design open items and MRSM log.

Conventional slab bending inputs 0.25 ULS / 0.35 SLS retain their recorded IS16700:2023 basis, subject to verifying the slab type and the original standard. NBC flat-slab values 0.25/0.50 are a separate idealization. The IS source has not been independently authenticated in this release.

## Code/reference cross-check
NBC105:2025 official DUDBC PDF: https://giwmscdnone.gov.np/media/files/NBC_105_2025_Seismic%20Design%20of%20Buildings%20in%20Nepal_lqqvx6a.pdf
- 3.6 load combinations: 1.2DL+1.5LL; conditional actions; DL+lambdaLL +/-E; 0.9DL +/-E. Lambda 0.6 storage, otherwise 0.3. Do not label 3.7 working-stress design as synonymous with SLS stiffness context.
- Table 3-1: beam EI ULS/SLS 0.35/0.70, column 0.70/0.90; wall factors above. Steel gross properties.
- Table 4-1 / Figures 4-1 and 4-2: ESM/dynamic spectrum branches remain separate; dynamic acceleration in g is converted once to m/s2 with 9.80665. Record amplitude scaling is separate and must be audited per record.
- 5.1: lesser of Rayleigh design period and 1.25 empirical period; eigenperiod is a comparison. Table5-2 RC dual wall system Rmu=3.5, OmegaU=1.4, OmegaS=1.2; applicability requires project confirmation. Wall-only system is different.
- Table5-1: Wi=DL+0.6 storage LL+0.3 other LL; roof LL excluded from seismic mass, not automatically from every gravity design combination.
- 5.4 soft storey: K below 0.7 above OR 0.8 mean of three above. Weak-storey capacity threshold 0.8. Torsion ratios require centered floor-edge response, not modal mass alone.
- 5.5.1/5.5.3: ULS elastic displacement amplified by Rmu; drift limits ULS0.025/SLS0.006. ESM6.5 kd is distinct from MRSM7.5 force scaling.
- 7.3/7.5: modal mass coverage and force scaling are necessary checks, not member capacity approval. Missing-mass correction at/above33Hz is not implemented; MRSM rejects that condition.

## Research citations and validation status
Kolozvari, Lopez & Massone (2023), Engineering Structures294,116700, doi:10.1016/j.engstruct.2023.116700; authors' E-SFI documentation https://kkolozvari.github.io/E-SFI-MVLEM-3D/. Distinct from Kolozvari et al.(2021), Journal of Building Engineering44,102946, SFI-MVLEM-3D https://kkolozvari.github.io/SFI-MVLEM-3D/.
Lu et al.(2015), Finite Elements in Analysis and Design98,14-25, doi:10.1016/j.finel.2015.01.006; official Python example https://openseespydoc.readthedocs.io/en/latest/src/RCshearwall.html. Included files retain source manifest hashes.
See WALL_VALIDATION_V147.md: small native E-SFI and Lu diagnostics completed previously; full Lu cyclic run failed convergence; SD-06 reproduction is pending actual specimen data. Published specimen values are not calibration for this core. Rigid macro-element end kinematics do not imply physical beams or confined boundary elements in the project.

## Verification and remaining scope
V148 tests: Python syntax; restored main GUI and new settings/comparison GUI construction; finite ESM input rejection, seismic weight and floor-force balance; CQC identity/symmetry; comparison unit mismatch; repeated stiffness-import deduplication; existing displacement/action inventory; design-report export. These do not constitute a full building rerun or experimental validation. Live D: files were read only. Existing packaged analysis results are historical, not regenerated V148 building results. Rerun selected current-model cases after changes and review fingerprints.

Readiness remains model-specific. Available files are evidence references, not automatically approved checks. No material, reinforcement, FSAM mapping, design capacity or final engineering approval is fabricated. Package includes relevant runtime/source/data/docs, including earlier benchmark outcomes. All quantities cannot honestly be certified correct while these project inputs and effective-wall-stiffness checks remain unresolved.
