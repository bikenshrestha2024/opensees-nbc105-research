# V133 method decisions and primary sources

## Earthquake basis

[NBC 105:2025 official PDF](https://ebps.kathmandu.gov.np/UploadFiles/NBC_105_2025_Sesmic_Design.pdf) is the governing reference. Relevant locations are section 4 spectra, 5.1 periods, 5.4 irregularity, 5.5.3 drift, section 6 ESM, and section 7 MRSM. Printed page numbers differ from PDF viewer indices.

The implementation keeps the static/dynamic spectral branches distinct. MRSM force scaling increases a deficient modal base shear to its static reference and leaves MRSM displacement/drift unscaled by that multiplier. These are separate from ULS displacement amplification and ESM kd.

Irregularity screens use the official 2025 numbering. Capacities, discontinuity/load-path assessment and plan projections require evidence; a partial screen is not a regularity certificate. The direct drift limits used are 0.025 ULS and 0.006 SLS. The application records the editorial cross-reference discrepancies already noted in the inherited method guide.

## OpenSees and CQC

[Official responseSpectrumAnalysis documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/responseSpectrumAnalysis.html) describes mode-specific responses and a CQC example. [modalProperties](https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/modalProperties.html) documents participation factors, effective masses and eigenvector normalization.

For each mode, nodal displacement is phi times Gamma times Sa divided by lambda. Gamma includes the ordinary directional contribution plus the selected eccentric floor torque projection divided by generalized mass. Generalized mass is independently summed over the assembled lumped translational nodal masses and eigenvectors. The current assembled model has zero element density and explicit nodal mass, so no element mass is silently omitted from that sum.

The equal-damping CQC correlation uses frequency ratio b=omega_j/omega_i:

rho_ij = 8*zeta^2*(1+b)*b^(3/2) / [(1-b^2)^2 + 4*zeta^2*b*(1+b)^2].

Combined response is sqrt(sum_i sum_j rho_ij*r_i*r_j). Tests cover one mode, closely spaced modes and native acceleration units. Negative generalized participation is retained in responses; only the nonnegative spectral ordinate supplied to the native command is used, with the required sign restored afterward.

A one-percent relevant modal force-equilibrium threshold is an implementation diagnostic, not a tolerance prescribed by NBC. Native member-force increments and reactions are compared with modal inertia forces. The gravity-preloaded geometric model showed residuals up to about 0.143 percent in the exercised cases. Review these diagnostics and the member-force/model assumptions before design use.

Known modes at or above 33 Hz stop this MRSM engine pending a reviewed missing-mass correction. This release does not silently discard them. The exercised 40-mode model exceeded 90 percent horizontal mass without any returned mode at/above 33 Hz.

[OpenSees rigidDiaphragm](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/mp_constraint/rigidDiaphragm.html) supplies the small-rotation relation used for floor-edge displacement. A rigid-diaphragm assumption itself remains a project modeling decision.

## Units and workbook references

[NIST standard gravity](https://physics.nist.gov/cgi-bin/cuu/Value?gn) supplies 9.80665 m/s2. The MRSM engine uses kN-m-s assembled data, not an unlabelled ETABS scale-factor number. Existing ETABS case scale factors can already contain function/unit multipliers; they are not copied blindly into acceleration units.

The three user-supplied workbooks are packaged unchanged in Project_Input_Workbooks. WORKBOOK_SCALING_REVIEW_V132.csv records scaling-summary cells, the raw target/modal ratio, and the non-reducing force multiplier. The SERVICE workbook's ratios below one are reported rather than adopted as a force reduction. Its target refers to a governing ETABS P-Delta case; it is not automatically substituted for the current assembled model's own ESM reference.

The adopted-period reference comes from SCALING SUMMARY C14/C15 with provenance. The optional seismic-weight input in NBC Calculator B18 is blank in the inspected copies. No matching mass reconciliation is inferred from that blank field or from similar periods. Differences between ETABS reference forces and assembled forces must be reconciled through load/mass sources, overlap conventions and the governing case.

## Other parameters

[IS 16700:2023 Table 5](https://www.services.bis.gov.in/tmp/CED20920094_14092023_1.pdf) remains the implemented slab bending-modifier basis: SLS 0.35, ULS 0.25, with membrane stiffness and physical self-weight preserved. See LOAD_PATH_AND_DIAPHRAGM.md.

[SFI-MVLEM-3D](https://kkolozvari.github.io/SFI-MVLEM-3D/) and [E-SFI-MVLEM-3D](https://kkolozvari.github.io/E-SFI-MVLEM-3D/) remain distinct RC-wall formulations. The implemented nonlinear wall template uses the latter; neither reference supplies this project's calibrated wall or brace parameters. See CHANGES_V131.md and the current parameter register. Constitutive templates retain their calibration status.


## Transient lifecycle and performance

[OpenSees wipeAnalysis](https://opensees.github.io/OpenSeesDocumentation/user/manual/misc/wipeAnalysis.html) removes analysis objects. V133 uses it when switching from gravity to transient analysis, then retains constraints, numberer, system, integrator and analysis objects while advancing time. Convergence recovery changes the test and algorithm; it does not re-create the complete analysis stack on every successful interval. Native cyclic yielding checks compare the old and new lifecycles to numerical tolerance.

[OpenSees Linear algorithm](https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/algorithm/LinearAlgorithm.html) is a one-iteration algorithm and requires no convergence test. The redundant linear test command was removed. Its factorOnce option is not enabled: the model includes P-Delta effects and a constant effective tangent has not been established. Removing a factorization without establishing its validity could change the result. The nonlinear runner retains convergence tests and bounded recovery. No record/time-step bound is enlarged for performance.

The last linear interval is bounded by the remaining physical record duration, matching the nonlinear runner. Accepted nonlinear adaptive substeps are recorded immediately, including intermediate drift peaks. Case timing reports stage wall time; solver/recording are not represented as separate native CPU counters. Progressive CSV saving retains accepted samples after later failures; metadata explicitly marks incomplete runs.

## Nonlinear damping choices and the external review

[Official modalDamping documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/damping/modalDamping.html) requires an iterative solver. V133 offers this only in the nonlinear runner, which uses Newton-family algorithms. Damping is assigned to the initially computed modes; uncomputed modes are not claimed to receive the target ratio. Select and review enough modes, including relevant torsional modes. The baseline/default committed-stiffness Rayleigh option remains available for compatibility, with its initial-mode check clearly labelled. Ratios can change as the committed stiffness changes during yielding.

[Official Rayleigh documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/damping/rayleigh.html) distinguishes current, initial and committed terms and warns about concentrated-plasticity models. [Chopra and McKenna (2016), doi:10.1002/eqe.2622](https://onlinelibrary.wiley.com/doi/abs/10.1002/eqe.2622) discusses spurious damping and recommends modal superposition. It does not establish a universal project damping percentage or certify arbitrary initial-stiffness Rayleigh damping. Five percent remains a code limit, not a measured property of this building. Explicit FVD damping is separate; no 2%/3% material/project assumption was invented.

The pasted external review's SRSS-scaling proposal was checked against the official NBC text. Section 9.3.2.2(d) specifies determining both component factors and using the lower for both motions. The existing NBC component procedure is retained. A plotted input pseudo-spectrum is a diagnostic, not spectrum matching or proof of site/record-set adequacy.

## Playback and source gravity charts

The [rigidDiaphragm relation](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/mp_constraint/rigidDiaphragm.html) gives ux=Ux-dy*Rz and uy=Uy+dx*Rz. At an intermediate elevation V133 interpolates the two adjacent floor point-displacement vectors, each using its own floor center. This corrects a reconstruction issue when the two floor centers differ. Geometry fingerprints are checked for newly generated histories. Legacy histories without such metadata are not represented as fingerprint-verified.

Plot display decimation uses per-bin minimum and maximum samples. It affects screen rendering only; drift, numeric pages and exports use accepted full-resolution samples. Gravity charts read the exact existing ledger rather than recomputing or redistributing loads. Shell load transfer, source overlap conventions and slab/diaphragm assumptions retain their prior engineering qualifications.


## Numerical controls versus material properties

The nonlinear NormDispIncr tolerance of 1e-7 in model displacement units, iteration cap of 40 and maximum five bisection levels are implementation controls retained from the existing runner; NBC does not prescribe these numbers. Four recovery algorithms are numerical choices, not experimentally calibrated properties. Their adequacy requires convergence/time-step sensitivity checks for the selected model and units; a converged return code alone is not such a study. The one-percent MRSM equilibrium diagnostic is likewise an implementation review threshold. New performance ETA uses elapsed wall time and does not assign a literature-derived nonlinear/linear duration ratio.
