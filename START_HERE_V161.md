# V161 — literature-informed nonlinear building research

Run **01_START_ETABS_TO_OPENSEES.py** for the main program. Open the building research nonlinear history window, or run **18_BUILDING_FULL_NONLINEAR.py** directly. Select the assembled export folder and an earthquake pair. Both states run ULS then SLS; each selected orientation rebuilds its own model. Duration 0 requests the complete record. A positive duration is a truncated numerical trial.

## What is now assigned

The new route uses the selected building geometry, source loads/mass, nonlinear Concrete01/Steel02 frame sections, and nonlinear E_SFI_MVLEM_3D walls using ConcreteCM + SteelMPF + FSAM. It runs in an isolated copy. It does not silently approve the production calibration checklist.

**PUBLISHED_REFERENCE** uses the PEER 2015/12 Appendix B.3 wall constitutive card: concrete compression magnitude 55.7785865 MPa, peak strain -0.002371, E 37253.8712 MPa; steel yield 402.72484 MPa, E 199947.9612 MPa, hardening 0.02. These are specimen reference values, not M30/Fe500 test results. SteelMPF transition constants are 20, 18.5, 0.0015. Frame concrete uses the OpenSees primer example (34.473786 MPa); frame steel is nominal Fe500 with E 200000 MPa and assumed b=0.01. No confinement strength gain is assigned.

**M30_FE500_SENSITIVITY** assumes cylinder compression strength 0.8*30=24 MPa, peak strain -0.002, and nominal 500 MPa reinforcement. The cube-to-cylinder conversion, concrete curve shape and steel hardening are explicit research assumptions. This is not an experimentally calibrated M30/Fe500 card.

The existing wall layout is two curtains of 20 mm bars at 200 mm spacing in each direction. For 600 mm thickness, rho = 2*pi*20^2/(4*200*600) = 0.00523599. This available historical layout still needs confirmation against drawings. It replaces the specimen reinforcement ratio; no special boundary elements are introduced. Existing beam/column bar-layout templates remain assumptions. The report records their actual dimensions, cover, bar count and diameter.

## Traceability and inspection

Each run writes Research_Material_Assignment_V161.json, ASSUMPTIONS_NOT_DESIGN.json, RunConfig.json, initial eigenperiod/damping data, and accepted response rows. The parameter button displays the actual assignment. MPa is multiplied by 1000 once for kN/m². Input acceleration in g is multiplied by 9.80665 once; motion scale is separate. Plot/playback and existing component calibration tools are retained.

Source implementation: components/nonlinear_time_history/research_building_materials.py. The ordinary reviewed production route is unchanged. Full-wall native transient testing is reported in V161_TEST_STATUS.md; a failed or short run is never reported as a completed earthquake history.

## References and applicability

- Kolozvari, Lopez & Massone (2023), Engineering Structures 294, 116700, https://doi.org/10.1016/j.engstruct.2023.116700 ; author command documentation: https://kkolozvari.github.io/E-SFI-MVLEM-3D/ . This supplies the E-SFI element formulation; it does not supply this building's reinforcement or validate its unconfined perforated core.
- Kolozvari, Orakcal & Wallace, PEER 2015/12, Appendix B.3: https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf . The reference web card is separate from the 2023 SD-06 specimens.
- OpenSees examples primer: https://opensees.berkeley.edu/OpenSees/OpenSeesExamples1.1.pdf . Example Concrete01 parameters are a reproducible baseline, not measured project concrete.
- Steel02 documentation: https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Steel02.html . R0=20, cR1=0.925, cR2=0.15 follow documented recommendations; yield strength and hardening require their own basis.
- ConcreteCM: https://openseespydoc.readthedocs.io/en/latest/src/ConcreteCM.html ; FSAM: https://openseespydoc.readthedocs.io/en/latest/src/FSAM.html . Native command formulations and units are retained.

NBC design acceptance, experimental wall validation, IO/LS/CP acceptance, and a final optimum outrigger location are not established by component convergence. Use the existing performance-objective module with justified component criteria and compare converged full-record suites before drawing the thesis conclusion.
