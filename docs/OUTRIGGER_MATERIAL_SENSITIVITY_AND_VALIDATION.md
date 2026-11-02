# Outrigger materials, sensitivity, and response-history evidence

This note explains the exploratory nonlinear building route and the evidence
needed before comparing outrigger locations or device configurations. It
complements [the recorder catalog](RESPONSE_RECORDING.md) and
[the NBC period/material provenance note](NBC105_PERIODS_AND_MATERIAL_PROVENANCE.md).
It is a research workflow, not design approval.

## What the current nonlinear model represents

The ordinary structural-steel outrigger braces use the ETABS-exported section
area and elastic modulus in a corotational axial truss with OpenSees `Steel01`.
The default yield stress is **345 MPa**, as specified for this study; the
hardening ratio defaults to `b=0.01`. The yield stress is converted once from
MPa to the model's kN/m² stress units. Confirm that 345 MPa matches the actual
steel grade certificate and applicable expected-strength basis before design
use. It is not a value claimed to have been calibrated from the outrigger
papers.

This ordinary brace model is an axial, tension/compression idealization. It
does not simulate flexural/local buckling, fracture, low-cycle fatigue, or
connection slip. It must not be interpreted as a qualified BRB. A BRB device
uses a separate cyclic material/device configuration whose yield strength,
core area, post-yield response, ductility, and connections must come from the
actual device specification or representative tests. Likewise, an FVD's
`Cd`, velocity exponent, and series/support stiffness require device data.
OpenSees command examples are implementation references, not device-property
sources.

The optional E-SFI-MVLEM-3D route uses the PEER 2015/12 Appendix B.3 web
material card as a **benchmark starting profile** and the 2023 paper for the
three-dimensional element formulation. It does not claim to reproduce the
paper's SD-06 specimen or the project's core. The existing wall reinforcement
layout remains an explicit assumed template; core boundary confinement,
openings, reinforcement schedules, axial loads, and coupling behavior require
project evidence. RC beam/column curves similarly use an OpenSees example's
unconfined Concrete01 shape, nominal Fe500 reinforcement, and an assumed
Steel02 hardening ratio, not project coupon tests. These transfer limits are
preserved in each generated `Research_Material_Assignment_V161.json`.

The previously reviewed Excel shear-wall `Aw` remains the NBC period input.
Export-derived segment geometry is an independent audit estimate and does not
silently replace the workbook value.

## One-factor sensitivity workflow

The nonlinear building GUI accepts one supported parameter and two to twelve
candidate values, then runs the candidates serially with the same model,
records, scale, duration, orientation, state, solver, damping rule, and
convergence policy. Only the selected material parameter changes. Enter values
in the units or sign convention shown by the parameter name:

| Parameter | Input meaning |
| --- | --- |
| `brace.fy_mpa` | Ordinary axial brace yield stress, MPa. Default 345 MPa. |
| `brace.E_mpa` | Ordinary brace elastic modulus, MPa. If omitted, the ETABS-exported modulus is retained. |
| `brace.b` | Ordinary brace Steel01 post-yield hardening ratio. |
| `frame.cover_fc_mpa`, `frame.core_fcc_mpa`, `frame.cover_fcu_mpa`, `frame.core_fpcu_mpa` | RC fiber cover/core peak and residual compressive strength magnitudes, MPa. |
| `frame.cover_epsc0`, `frame.core_epsc0`, `frame.cover_epsU`, `frame.core_epsU` | RC fiber concrete peak and ultimate compressive strains; enter negative strains. |
| `frame.rebar_fy_mpa` | Nominal longitudinal reinforcement yield stress, MPa. |
| `frame.E0_mpa`, `frame.steel_b`, `frame.steel_R0`, `frame.steel_cR1`, `frame.steel_cR2` | RC reinforcement Steel02 modulus (MPa), hardening ratio, and transition parameters. |
| `wall.fpcc_mpa`, `wall.ft_mpa` | Signed (negative) ConcreteCM compression peak and positive tensile strength, MPa. |
| `wall.Ec_mpa`, `wall.epcc`, `wall.et` | ConcreteCM elastic modulus (MPa), signed peak compression strain, and positive tension strain. |
| `wall.rc`, `wall.xcrn`, `wall.rt`, `wall.xcrp` | ConcreteCM compression/tension curve shape and transition parameters. |
| `wall.fyp_mpa`, `wall.fyn_mpa`, `wall.E0_mpa` | SteelMPF positive/negative yield and modulus inputs, MPa, using the card's sign convention. |
| `wall.bp`, `wall.bn`, `wall.R0`, `wall.cR1`, `wall.cR2`, `wall.a1`–`wall.a4` | SteelMPF hardening, transition, and isotropic hardening parameters. |
| `wall.rho_x`, `wall.rho_y`, `wall.fsam_nu`, `wall.fsam_alpha` | Directional FSAM reinforcement ratios and FSAM shear-transfer parameters. |

Supported values are range-checked and exported in `RunConfig.json`,
`ASSUMPTIONS_NOT_DESIGN.json`, and (for the E-SFI route) the assigned-material
JSON. The GUI's 310.5, 345, and 379.5 MPa brace examples are a transparent
±10% screening bracket around the user-specified 345 MPa baseline; they are
**not** three literature-prescribed grades or a code acceptance range.
Likewise, parameter sweeps are user-selected controlled comparisons, not
automatic calibration or an optimum search. Include the current baseline value
as one candidate if you want direct baseline-relative effects. The run's
`duration_s=0` means every candidate runs the full input record; a multi-case
full-record sweep can be expensive.

Outputs are written under the selected output folder:

* `Material_Sensitivity_Comparison.csv` records the tested value, state,
  orientation, completion status, record coverage, peak and terminal roof
  displacement, maximum master and floor-edge drift, base shear, and peak
  relative floor acceleration. Residual roof displacement is present only for
  a completed full record.
* `Material_Sensitivity_Summary.json` records progress, tested values, and
  output locations. A failed candidate leaves its failure report and a partial
  summary; the batch does not report a successful completion.
* Each candidate retains its regular analysis logs, assumptions, and response
  recorders. No sensitivity result is automatically labeled “best.”

Change one parameter at a time for screening. This does not capture
interactions such as wall strength × reinforcement ratio or brace yield ×
outrigger elevation. Use a designed factorial/response-surface study only
after a stable baseline, verified inputs, and a documented analysis budget
exist. Values outside the supported table are rejected rather than silently
clipped. BRB/FVD device calibration parameters are deliberately not included in
this building-material sweep.

## Selected member and device response history

`tracked_frame_tag` and the optional `tracked_element_tags` list select
assembled frame solver tags, including mapped outrigger brace/device members.
`Frame_Solver_Tag_Catalog.csv` maps these tags back to ETABS source objects,
category, section property, end nodes, and release flags so the next run can
select specific outrigger/device members without guessing tag arithmetic.
For each accepted nonlinear state,
`Tracked_Element_Force_Displacement.csv` records local force component 1,
gravity-relative projected axial extension, the element's local force vector,
source object, and solver tag. The local vector is retained in native
OpenSees end-force ordering because beam vectors contain both force and moment
components. Review the element map and device local-axis orientation before
interpreting the force–extension sign or calling it a device-axis response.
The existing tracked beam moment-curvature and wall panel stress-strain files
remain separate. All-story displacement, rotation, relative acceleration,
master drift, support-reaction/base-shear, synchronized roof/base-shear path,
and reconstructed floor-edge drift outputs remain available.

The per-case summary distinguishes peak from end-of-record roof displacement.
Floor acceleration is relative acceleration under `UniformExcitation`, not
absolute acceleration. The final-frame-action table remains a final-state
snapshot; it is not an all-element time history. Selected tags provide
time-history demand only for members chosen before the run.

For location/configuration comparisons, hold the record suite and scaling,
gravity/mass, damping, time-step screen, recovery limits, and performance
definitions constant. Compare peak and residual displacement, center and
edge drift, torsion, acceleration, base shear, and local device/member
demand. A smaller peak roof displacement alone does not establish an optimum.
The cited literature supports studying elevation and system stiffness
together; it does not prescribe a universal best floor for this asymmetric
25-storey building.

## Research references and why they apply

* Smith, B. S. (1981), “Parameter Study of Outrigger-Braced Tall Building
  Structures,” *Journal of the Structural Division*, 107(10), 2001–2014,
  [doi:10.1061/JSDEAG.0005798](https://doi.org/10.1061/JSDEAG.0005798).
  Foundational placement/stiffness parametric study; use for problem framing,
  not a project-specific optimum.
* Smith, R. J., & Willford, M. R. (2007), “The damped outrigger concept for
  tall buildings,” *The Structural Design of Tall and Special Buildings*,
  16(4), 501–517, [doi:10.1002/tal.413](https://doi.org/10.1002/tal.413).
  Damped-outrigger concept; its reported damping improvement is not a
  transferable multiplier.
* Chen, Y., McFarland, D. M., Wang, Z., Spencer, B. F., & Bergman, L. A.
  (2010), “Analysis of Tall Buildings with Damped Outriggers,” *Journal of
  Structural Engineering*, 136(11), 1435–1443,
  [doi:10.1061/(ASCE)ST.1943-541X.0000247](https://doi.org/10.1061/(ASCE)ST.1943-541X.0000247).
  Analytical screening for FVD placement and size; simplified model, not
  project validation.
* Huang, B., & Takeuchi, T. (2017), “Dynamic Response Evaluation of
  Damped-Outrigger Systems with Various Heights,” *Earthquake Spectra*, 33(2),
  665–685, [doi:10.1193/051816EQS082M](https://doi.org/10.1193/051816EQS082M).
  Elevation/damper-size screening method; analytical/member-model comparison,
  not an experimental validation of this building.
* Lin, P.-C., Takeuchi, T., & Matsui, R. (2018), “Seismic performance
  evaluation of single damped-outrigger system incorporating
  buckling-restrained braces,” *Earthquake Engineering & Structural Dynamics*,
  47(12), 2343–2365, [doi:10.1002/eqe.3072](https://doi.org/10.1002/eqe.3072).
  Supports coupled elevation, stiffness, and nonlinear history comparison;
  its building heights and system assumptions differ from this project.
* Lin, P.-C., Takeuchi, T., & Matsui, R. (2019), “Optimal design of multiple
  damped-outrigger system incorporating buckling-restrained braces,”
  *Engineering Structures*, 194, 441–457,
  [doi:10.1016/j.engstruct.2019.05.078](https://doi.org/10.1016/j.engstruct.2019.05.078).
  Relevant multiple-elevation design methodology; numerical recommendations
  are not directly transferable.
* Lin, P.-C., & Takeuchi, T. (2019), “Seismic performance of
  buckling-restrained brace outrigger system in various configurations,”
  *Japan Architectural Review*, 2(4), 392–408,
  [doi:10.1002/2475-8876.12120](https://doi.org/10.1002/2475-8876.12120).
  Useful configuration comparison; design charts remain preliminary and
  study-specific.
* Lin, P.-C., & Chen, P.-H. (2024), “Shaking table test of a
  buckling-restrained brace outrigger system,” *Journal of Constructional
  Steel Research*, 213, 108415,
  [doi:10.1016/j.jcsr.2023.108415](https://doi.org/10.1016/j.jcsr.2023.108415).
  Relevant experimental anchor. Consult the full paper before using test
  properties or claiming calibration.
* OpenSees documentation for [Element Recorder](https://opensees.github.io/OpenSeesDocumentation/user/manual/output/ElementRecorder.html),
  [Steel02](https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Steel02.html),
  and [OpenSees source](https://github.com/OpenSees/OpenSees) describes
  software semantics, not building/device validation.

There is no verified published like-for-like benchmark found for a 25-storey
asymmetric RC core/frame with conventional, FVD, and BRB outriggers in the same
OpenSees model. Treat this project's model-to-model comparisons as exploratory
until its project materials, wall geometry/reinforcement, devices, and
representative cyclic response are independently validated.

## Known nonlinear run limitation

The saved full Kobe-X attempt stopped at approximately 2.805 s of a 40.94 s
record after 40 iterations with a displacement-increment norm of
`1.86068e-5` against `1e-7`; the residual norm was approximately 273.3.
This is a numerical nonconvergence, not a completed full-record result and not
enough evidence to identify a specific failing element or material. A
0.005-second smoke test establishes only short-interval execution. Do not
claim a complete Kobe analysis or choose an optimum until the full record
completes and the failure/convergence behavior is reviewed.
