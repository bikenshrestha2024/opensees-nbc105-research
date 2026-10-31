# V132 method decisions and primary sources

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
