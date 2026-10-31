# V132 implementation changes

## Interface and available inputs

Corrupted UTF-8/cp1252 source spans were repaired. Child Python analysis processes now use explicit UTF-8 I/O; decoding UTF-8 in the parent is insufficient when the child prints with a different encoding. Source workbook files are retained unchanged.

Autofill covers the main analysis forms: gravity supports/load total; ESM project/period references; modal model, height, wall indices and project system; site spectra; model MRSM; linear and nonlinear time history. SLS uses the supplied SERVICE scaling workbook; ULS uses the ULTIMATE workbook. Workbook cached values are inputs with file/sheet/cell provenance. Uncached formulas are not evaluated or silently treated as zero.

The nonlinear form receives its nonlinear builder path, story-node CSV, available readiness manifest and baseline period references. Autofill does not enable execution, sign readiness items or invent constitutive/device parameters. Baseline eigenperiod references do not establish the calibrated nonlinear model's initial stiffness.

## Equivalent static and section 6

Eligible design cases and ineligible comparison cases remain distinguishable in JSON, figures and logs. Section 6 coefficient, seismic weight/base shear, height distribution exponent, floor force distribution, signed accidental torque, design displacement amplification and Table 6-1 kd are retained. Default exports now include E0 centered cases for torsion review, as well as E+ and E- cases. Both force signs and both limit states/directions generate 24 runners with the default options. Disable centered cases when only the eccentric cases are wanted.

The exported solver still checks gravity, signed initial P-Delta evidence, node availability, convergence and lateral equilibrium. Ineligibility is not a reason to suppress a requested reference calculation, and it is not converted into eligibility by running it.

## Model response spectrum

components/response_spectrum/model_analysis.py builds the elastic assembled model and uses OpenSees responseSpectrumAnalysis mode by mode. CQC combines signed modal responses before taking the response envelope. Drift differences are formed within each mode before combination; subtracting two independently combined displacement envelopes would be incorrect.

The dynamic Table 4-1 curve is used. Dimensionless design Cd is multiplied by 9.80665 m/s2 in the kN-m-s model, giving inertia actions in kN. Force scaling is max(1,V_ESM/V_MRSM). This force multiplier is not applied to displacement/drift; ESM kd is not applied to MRSM. ULS design displacement uses the ULS ductility amplification; SLS uses its service spectrum and overstrength treatment.

Centered and signed 5-percent eccentric inertia cases use the same eigenbasis. Floor torque contributes to the generalized modal excitation through the floor master rotation, with each floor's mass and perpendicular breadth. This is a documented lumped-floor eccentric-influence model, not a claim that the mass matrix has been physically relocated and re-diagonalized. See the method document for equations and scope.

Outputs include modal/base-force data, CQC global member-force envelopes, support-reaction envelopes, per-mode force-equilibrium diagnostics, edge/master drift checks, profiles and 3D deformation envelopes. Component-wise CQC maxima are not a simultaneous physical deformed shape or a set of concurrent member interaction actions.

## Drift and geometry

A shared exporter writes master/edge drift tables and graphical profiles for ESM, MRSM, linear history and nonlinear history. History displacements are referenced to the gravity-preloaded position, and recorded floor RZ participates in rigid-floor edge drift. Threshold screens do not establish the validity of the underlying model.

ESM saves actual converged nodal displacements. History 3D snapshots reconstruct rigid-floor translations/rotation and interpolate between floors; they do not resolve wall/frame curvature or vertical deformation. Full recorded floor histories remain available in the time-history inspector.

The irregularity module screens mass and LFRS extent changes, accepts reviewed strength/stiffness input, and exports centered-static torsional ratios and soft-story screens. It does not infer lateral strength from elastic stiffness. Missing discontinuity/re-entrant/capacity evidence remains explicit.
