# V129 method and parameter evidence record

This record distinguishes requirements, source data, numerical choices and uncalibrated examples. It is not a complete code-compliance certificate.

## Analysis-method applicability
[NBC 105:2025 official PDF](https://ebps.kathmandu.gov.np/UploadFiles/NBC_105_2025_Sesmic_Design.pdf)

Section 3.2.1 governs ESM eligibility. The supplied 95 m model and periods above 0.5 s do not qualify for ULS ESM. Modal eigenanalysis and elastic time history are separate methods; their ULS outputs do not populate an ESM force tab. Sections 9.3.2.3–9.3.2.4 support orthogonal component application, direction swapping and the implemented digitization/T1/Tn/0.01 s bounds. These bounds are not a time-step convergence study. Sections 8 and 9 must be applied to their respective methods; the record-matching procedure still needs independent project review.

## Values in the completed Kobe trial

| Item | Value / source | Interpretation |
|---|---|---|
| Limit-state context | ULS, selected RunConfig | Names the stiffness/analysis context; does not certify member design |
| Input records | RSN1120_KOBE_TAK000 pair, original source paths in audit | User-supplied matched records; spectral adequacy was not independently re-established |
| Orientations | XY and YX | Saved .dat arrays were checked against their intended source components |
| Scale | Recorded in input audit; Path acceleration factor includes scale and units | No second scaling is applied to stored .dat values |
| Integration step | 0.01 s | Meets the implemented upper-bound calculation for this trial |
| Duration | 40.94 s | Original selected record duration; 4094 accepted steps per orientation |
| Newmark | gamma=0.5; beta=0.25 | Average-acceleration numerical method; not an NBC-mandated parameter pair |
| Inherent damping | 5% selected target | A project modelling choice, not proof that 5% is optimal; no FVD was represented in this linear baseline |
| Damping calibration periods | 1.5573775010 s; 0.07356591167 s | Imported modal range for the selected case; not empirical period substitutes |
| Adopted X/Y periods | 2.0385674 s / 1.92197978 s | Saved project values; provenance workflow retained from earlier versions |
| Tn X/Y | 0.14612924237 s / 0.16714542143 s | Saved directional modal participation cutoffs |
| Rayleigh formulation | alphaM*M + betaKcommitted*Kcommitted | Existing numerical modelling choice; not a claim that committed stiffness avoids all artificial damping |
| Linear algorithm | One linear solution per step | Solver completion is not an iterative nonlinear equilibrium validation |
| Trial scope | One earthquake pair | Preliminary setup check; no final suite or design adequacy conclusion |

### Numerical-method sources

[OpenSees Newmark documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/integrator/Newmark.html) identifies the average-acceleration parameter pair. Stability properties do not establish time-step accuracy for this building; a step-size sensitivity study remains separate.

[OpenSees UniformExcitation documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/pattern/uniformExcitationPattern.html) specifies relative nodal responses. The reported roof motions are relative to the excitation reference, not absolute ground-plus-relative displacements.

[OpenSees Rayleigh documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/damping/rayleigh.html) defines the mass and stiffness terms. The current choice is documented, not universally endorsed for nonlinear yielding. [Chopra's PEER damping report](https://peer.berkeley.edu/sites/default/files/publications/2020_01_chopra_final_report.pdf) discusses limitations of viscous damping in nonlinear response-history analysis. A nonlinear damping sensitivity/calibration study is still required.

[OpenSees Linear algorithm documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/algorithm/LinearAlgorithm.html) describes the single-step linear algorithm and conditional matrix reuse. No factorOnce performance change was made in V129 because the P-Delta and damping matrix assumptions require separate verification.

## Imported properties versus illustrative library values

The elastic source uses imported ETABS properties (including M45 source material labels), rather than treating all fibre-library presets as calibrated properties. See the generated Properties audit for actual E, geometry and source provenance.

PARAMETER_SOURCES_V125.md and the Library parameters Excel sheet distinguish inherited illustrative M35/Fe550 and confinement presets from documented transition constants and published examples. The 44.1 MPa confined strength, residual 8.8 MPa, core strains and 0.01 hardening are not established project calibration values. Concrete01/Steel02 model citations do not validate those numbers. Device parameters and nonlinear wall FSAM calibration remain mandatory project evidence. No missing project value was replaced with a literature number in this update.

## Remaining engineering checks

The supplied CSVs support numerical consistency checks, not physical model validation. ETABS/OpenSees equivalence, rational wall/slab effective stiffness, connection and opening representations, floor-edge torsional drift, foundation/basement input location, spectrum matching and member actions remain independent checks. The outputs currently record floor-master translations and drift, not every member action or complete floor-edge demands. A modal mass PASS or preliminary drift screen cannot establish completion of these items.

## Software recovery choices

Long-running analysis windows are now nonmodal: they release the Tk input grab and have independent window-manager ownership. This fixes an application interaction problem and does not change structural parameters. Windows > Restore all windows and Ctrl+Shift+R provide recovery within the running application. These are software choices, not code provisions.
