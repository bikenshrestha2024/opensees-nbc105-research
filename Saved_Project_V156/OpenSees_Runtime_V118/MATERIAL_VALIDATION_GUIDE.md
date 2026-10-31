# Material selection and literature-validation procedure

## Purpose

Use this guide when choosing OpenSees material parameters without project
physical tests. This is **literature-based model validation**, not experimental
validation of this building. The project's ETABS/design material schedule is
the source for project grades; published specimens validate the selected
formulation and calibration method.

## 1. Keep grade, material curve, and model validation separate

1. Read the project's concrete and steel grades from verified ETABS material
   records, design drawings, or specifications. Confirm whether concrete
   strength is a cube or cylinder value before interpreting it as (f'_c).
2. Obtain full material inputs from a cited test or source: peak strength and
   strain, post-peak response, tension response, cyclic rules, and confinement
   details. A grade alone does not define these values.
3. Reproduce the source specimen with its reported geometry, axial load,
   reinforcement, loading protocol, and material properties.
4. Compare simulated and measured curves and report peak strength, initial
   stiffness, cyclic degradation/pinching, residual response, and energy
   dissipation when the source provides those data.
5. Only then transfer the modeling approach to the building, substituting the
   project's verified grades and reinforcement. Run sensitivity cases for
   uncertain post-peak, tension, confinement, and device properties.

Do not tune material strengths merely to match the building period or drift;
that can hide errors in geometry, mass, boundary conditions, or load transfer.

## 2. Concrete and reinforcement

### RC beam/column fiber sections

`Define_Section_V109.py` currently creates the beam/column concrete fibers with
`Concrete01`. If the thesis adopts `Concrete02`, change the section helper only
after specifying and citing all seven inputs: `fpc`, `epsc0`, `fpcu`, `epsU`,
`lambda`, `ft`, and `Ets`. OpenSees defines Concrete02 as a compression
envelope with linear tension softening; these inputs are not all determined by
the concrete grade. [OpenSees Concrete02 manual](https://opensees.berkeley.edu/OpenSees/OpenSeesCommands.pdf)

Use separate cover and confined-core curves only where the member's transverse
reinforcement and detailing justify confinement. The user's statement that
the walls have no special boundary elements is not a reason to remove column
core confinement where column ties provide it; it is a reason not to invent a
confined wall-boundary zone.

### RC wall benchmark profile

The optional profile in `Define_Section_V109.py` reproduces the solid planar
specimen RW-A15-P10-S78 reported in Kolozvari, Orakcal, and Wallace (PEER
2015/12, Appendix B.3). Its ConcreteCM/SteelMPF/FSAM parameters are benchmark
inputs, not calibrated properties for the user's M45 (or other) core walls.
The report and OpenSeesPy docs define the model and parameters:

- [PEER Report 2015/12](https://apps.peer.berkeley.edu/publications/peer_reports/reports_2015/webPEER-2015-12-kolozvari.pdf)
- [OpenSeesPy ConcreteCM command](https://openseespydoc.readthedocs.io/en/latest/src/ConcreteCM.html)
- [OpenSees ConcreteCM source](https://github.com/OpenSees/OpenSees/blob/master/SRC/material/uniaxial/ConcreteCM.cpp)

Do not use its confined boundary material unless the project wall has
corresponding boundary confinement. The optional helper creates material
objects only; it does not create wall elements, openings, reinforcement layout,
or wall loads/mass.

For opening-wall comparison, start with published cyclic opening-wall tests,
then select an individual specimen whose opening arrangement and aspect ratio
are reasonably close to the project. For example, Yu et al. tested a control
wall and four walls with small openings; their specimens were flexure-designed,
so they are not automatically representative of every perforated core wall.
[Yu et al. (2019), open-access cyclic tests](https://link.springer.com/article/10.1186/s40069-019-0352-1)
The [PUC Shear Wall Database](https://centrohormigon.uc.cl/recursos/ensayos-de-muros)
provides public force-displacement data and specimen references for additional
benchmark selection.

The project-specified web layout (Ø20 vertical/horizontal, 200 mm each face,
two curtains, 25 mm clear cover) gives web ratios only when wall thickness is
known. It excludes opening jamb, pier-end, and lintel/spandrel bars. Use the
actual detailing for each opening; do not spread a single uniform web ratio
over the opening region.

### Rebar steel

The user-specified rebar yield strength is 550 MPa. Confirm that grade and
whether it is specified or measured yield strength from the project's source
documents. For `Steel02`, document (E_0), hardening ratio, and transition and
isotropic-hardening parameters; the OpenSees recommended transition defaults
are not a substitute for a grade-specific cyclic backbone.
[OpenSees Steel02 documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Steel02.html)

## 3. FVD and BRB devices

Treat device properties as **device-specific**, not as steel/concrete grades.

- **FVD:** source (K), (C_d), velocity exponent \(\alpha\), units,
  temperature/frequency/amplitude range, and force response from the actual
  device specification or a comparable published test. The OpenSees
  `ViscousDamper` is a Maxwell spring-dashpot model. Reproduce the reported
  loading protocol and force-displacement loop before building-level analysis.
  [OpenSees Maxwell calibration example](https://opensees.berkeley.edu/wiki/index.php?title=Calibration_of_Maxwell_Material)
- **BRB:** source core area, yield strength, yielding length, elastic modulus,
  tension/compression strength adjustment, hardening, and cyclic qualification
  data. Validate brace force-deformation loops against a published brace test;
  a `Steel02` coupon curve alone does not capture all brace-level behavior.
  [BRB modeling approaches compared with experiments](https://www.sciencedirect.com/science/article/pii/S221450951730253X)

If the project has no device specification, record the assumed published
device, clearly mark it as a proxy, and run a parameter sensitivity study.
Do not present proxy damper/BRB properties as ETABS-extracted project values.

## 4. Evidence register to complete for the thesis

Complete this table for every material/device definition and keep it with the
run outputs:

| Item | Project value/source | Benchmark specimen/source | OpenSees inputs/source | Validation comparison | Status |
|---|---|---|---|---|---|
| Wall concrete, unconfined | ETABS/design schedule; confirm cube/cylinder | Opening-wall test selected by geometry | ConcreteCM/FSAM inputs and units | Wall base shear vs drift; stiffness/energy | Pending |
| Wall boundary concrete | Only if confinement is detailed | Match confinement details | Separate curve only if justified | Local strain/strength response | Pending / N/A |
| Beam/column concrete | ETABS/design schedule | Frame/member test | Concrete02 or chosen model inputs | Member moment-rotation or force-drift | Pending |
| Rebar | User input fy=550 MPa; verify drawings | Coupon/member test source | SteelMPF/Steel02 inputs | Steel cyclic curve | Pending |
| FVD | Manufacturer/model/test | Device test | (K,C_d,\alpha), units | Device hysteresis under same protocol | Pending |
| BRB | Manufacturer/model/test | Qualification test | Core/backbone/device inputs | Brace hysteresis/strength adjustment | Pending |

Mark a row **validated** only after a documented comparison. Where the source
does not report needed parameters, state the adopted assumption and uncertainty
rather than implying the value was measured.

## 5. Package limitations

The current V109 package is a documented extraction, section-review, and
analysis-helper package. It does not yet instantiate the user's complete
three-dimensional opening-wall system or fully assemble all FVD/BRB devices,
connections, and loads. The wall benchmark helper is deliberately opt-in. A
whole-building nonlinear result should not be reported as validated until the
wall formulation/mesh, opening load path, diaphragm connectivity, mass, gravity
preload, device models, and analysis stages are assembled and checked.
