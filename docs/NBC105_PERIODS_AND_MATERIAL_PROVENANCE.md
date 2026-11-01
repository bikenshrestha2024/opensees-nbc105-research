# NBC 105:2025 periods and nonlinear material provenance

This note records the equations implemented by the modal/Rayleigh workflow and
the evidence limits of its nonlinear research material profiles. It is not a
design certification or a substitute for checking the complete project model.

## Fundamental periods

The governing reference is the official [NBC 105:2025, Seismic Design of
Buildings in Nepal](https://giwmscdnone.gov.np/media/files/NBC_105_2025_Seismic%20Design%20of%20Buildings%20in%20Nepal_lqqvx6a.pdf):

* **§5.1.1, Eq. 5.1(1), printed p. 28:** `T1 = 2π √[Σ(Wi di²) / (g Σ(Fi di))]`. `di` is the elastic horizontal
  displacement of the center of mass at level `i`, ignoring torsion; `Fi` is
  the lateral force at that level; `Wi` is its seismic weight.
* **§5.1.2, Eq. 5.1(2), printed pp. 28–29:** `Temp = kt H^0.75`. For concrete shear-wall buildings,
  `kt = 0.075 / √Aw`, with
  `Aw = Σ[Awi (0.2 + (Lwi/H)²)]`; `Lwi/H` is limited to 0.9. The other
  listed coefficients are 0.075 for concrete moment frames, 0.085 for steel
  moment frames, 0.075 for steel eccentrically braced frames, and 0.05 for
  other systems.
* **§5.1.3, printed p. 30:** `Temp` is amplified by 1.25. The lesser of that
  value and the independently computed Rayleigh period is adopted for design
  action.
* **§5.2, printed p. 30:** seismic weight includes dead load and factored
  seismic live load; Table 5-1 factors are 0.60 for storage, 0.30 for other
  occupancy, and zero for roof live load.
* **§6.3, printed p. 39:** the equivalent-static vertical force shape is
  proportional to `Wi hi^k`, with `k=1` for `T≤0.5 s`, `k=2` for `T≥2.5 s`,
  and linear interpolation between them.

The code keeps these distinct quantities separate: OpenSees eigenperiods are
modal diagnostics; the force/displacement Rayleigh period and the empirical
period are §5.1 estimates; the adopted design period is their prescribed
minimum after empirical amplification. An ETABS period is a comparison
reference only. For asymmetric buildings, identify translational modes from
mode shapes and directional mass participation; do not assume the first mode
is a pure X or Y translation.

The preliminary Rayleigh runner uses the assembled floor seismic-weight ledger,
the NBC gravity constant `g=9.81 m/s²`, and floor forces distributed by
`Wi hi^k`; its initial `k` is selected from the unamplified empirical period
as a provisional equivalent-static force shape. It equilibrates gravity before applying the small lateral
perturbation, then uses incremental diaphragm-master translations with diaphragm
rotation restrained to implement the §5.1.1 torsion-ignored displacement
definition. Its story-ledger height is the exported base-to-roof extent;
verify the seismic base and exclude basement height only when it meets the
specific §5.1.2 exclusion condition. The result remains diagnostic until the
weights, force shape, center-of-mass representation, wall geometry, and
basement treatment are reviewed.

For wall `Aw`, the independent geometry estimate merges contiguous shell mesh
intervals on each wall line, separates physical gaps/openings, and applies the
NBC factor to each resulting segment using that segment's own `Lwi`. This is a
geometry-derived audit/fallback, not a definitive rule for grouping a
perforated wall in the NBC summation: the standard does not explicitly explain
whether an opening-bearing wall should be represented as one wall with net
`Awi` and an overall `Lwi`, or as multiple effective piers. A reviewed
workbook value—such as one computed from the full wall area less opening area
and an overall wall length—is therefore preserved as the period input rather
than silently replaced by the segment estimate. Both values and any
difference are reported for engineering reconciliation. Confirm the export
captures openings, wall intersections, first-storey limits, and directional
wall lengths. If automatic reconstruction fails, the workbook value is
retained only as an explicitly noted review input.

Rayleigh **damping coefficients** are another, separate calculation:
`ζ(ω)=αM/(2ω)+βKω/2`. The nonlinear runner currently fits its selected modes
to 5% at the endpoints of its inspected modal-frequency range; intermediate
modal ratios follow the equation and are exported for review. This is not the
NBC §5.1 period calculation. NBC §8.1.1.5 explicitly caps *linear*
time-history viscous damping at 5%; nonlinear §9.3 additionally requires
hysteretic dissipation.
Do not treat the damping calibration as evidence that materials or the
nonlinear model are calibrated.

## Material provenance and transfer limits

The following are literature-informed benchmark inputs, not verified
properties or detailing for the 25-storey building:

| Component | Current source and use | Transfer limit |
|---|---|---|
| RC wall web | PEER Report 2015/12, Appendix B.3 web-material card used by `PEER_Web_ESFI_Patch.json` (ConcreteCM/SteelMPF; reported concrete strength about 55.8 MPa, steel yield about 402.7 MPa, and reinforcement ratios 0.0074). | This is a published web-material benchmark. The E-SFI-MVLEM-3D paper by Kolozvari, Lopez & Massone (2023), [Engineering Structures 294, 116700](https://doi.org/10.1016/j.engstruct.2023.116700), supports the element formulation, not a claim that the building core reproduces the paper's SD-06 specimen. The patch geometry, axial load, wall openings/corners, and project reinforcement remain unvalidated assumptions. |
| RC beams/columns | The unconfined Concrete01 curve is drawn from the OpenSees [Example 3.1 RC frame](https://opensees.berkeley.edu/OpenSees/OpenSeesExamples1.1.pdf), not a building-specific material test. The research profile uses nominal Fe500, 200 GPa modulus, Steel02 `b=0.01`, and existing section/bar-layout templates. | These are illustrative analysis inputs, not a peer-reviewed calibration of the project beams/columns. Confirm grades, bar schedules, ties, confinement, concrete strengths, expected strengths, and hinge behavior against the ETABS/issued structural details and tests. Do not assign confined-core enhancement without actual transverse reinforcement. |
| Steel braces | Exploratory model uses source section area and elastic modulus with assumed `Fy=345 MPa` and `b=0.01`; the standard fiber-section SHS example separately uses an explicitly labeled expected-strength assumption. | No matched brace coupon/cyclic test or project material certificate is represented. A conventional Steel01/Steel02 truss does not model brace flexural buckling, local buckling, fracture, or fatigue. Do not use it as a BRB qualification model. |
| BRB / FVD | Device helpers expose material/geometry parameters and cite the PEER BRB and OpenSees ViscousDamper sources; FVD stiffness and device properties require explicit inputs. | No device-specific test or manufacturer qualification was supplied. Generic paper/device parameters are not transferable without matching core/brace geometry, connection details, and cyclic protocol. |

Source URLs and parameter-level locators are also recorded in
`Material_Catalog/PEER_Web_ESFI_Patch.json`,
`Material_Catalog/Official_Concrete01.json`, and the generated
`Research_Material_Assignment_V161.json`. These profiles are suitable for
exploratory comparison and sensitivity studies only. For design-level
predictions, use project material tests/certificates and reinforcement/device
details, then calibrate and independently validate the model against
representative cyclic data. A parameter taken verbatim from a paper is not
automatically applicable to a different geometry, axial-load ratio, scale,
boundary condition, or construction detail.

## Solver selection for the modal audit

`PythonSparse` is the recommended solver for building-scale models. The
OpenSees native eigensolver call is synchronous; its fallback can only run
after the native call returns or raises, so it cannot automatically recover
from a native call that remains blocked. Use the GUI batch stop control and
rerun with `PythonSparse` if a native solve stalls. `-fullGenLapack` is dense
and is deliberately skipped for models above the existing node-count limit.
