# V159 full application: literature profiles and component research

Run 01_START_ETABS_TO_OPENSEES.py. In the section/material column use:
- Literature profiles - exact values / formulation / run
- Saved component graphs - all 8 materials / devices
- Individual material / device setup and tuning

Direct shortcuts: 15_LITERATURE_MATERIAL_PROFILES.py and 16_COMPONENT_RESULTS.py.

## What is integrated
17 selectable profiles cover Concrete01, Concrete02, ConcreteCM, Steel02, SteelMPF, FVD, idealized BRB and E-SFI wall patches. For each profile the GUI displays parameter values, units, evidence class, exact source locator, source-unit inputs, formulation and executable native kN-m commands. Run selected profile uses a child process. Export writes Selected_Card.json, Parameter_Provenance.csv, Basis.md and Native_Materials_kN_m.py. Successful runs add graphs, response CSV, Excel, command trace, report and log. The existing tuning panel and animation can be opened directly with the selected card. Saved OR157/158 run folders can be viewed without rerunning.

## Which numbers really come from a source
Concrete01: OpenSees primer unconfined cover example, -5 ksi, epsc0=-.002, zero residual, epsU=-.006.
Concrete02: official MEFI material-4 example, fpc=-47.09 MPa, epsc0=-.00232, fpcu=0, epsU=-.037, lambda=.1, ft=2.13 MPa, Ets=1738.33 MPa. These example values are not an M30 strain-capacity prescription.
ConcreteCM: author example (-6.2 ksi, -.0021, 4500 ksi, 7, 1.035, .30 ksi, .00008, 1.2, 10000) and separate PEER 2015 Appendix B.3 web-concrete card.
SteelMPF: separate official command example and PEER web-rebar card. The latter retains the source legacy curvature values 18.5/.0015, rather than silently substituting .925/.15.
Steel02: the existing fit to published SimCenter qfem-0019 coupon data. This is a fit produced here, not a paper's reported parameter table; same-coupon temporal holdout remains limited.
FVD: author example K=300 kN/mm, Cd=280.3 kN(s/mm)^.3, alpha=.3. Convert K by 1000 and Cd by 1000^.3.
BRB: the available simplified Steel02 uniform-core card remains an explicitly assumed idealization. Black, Makris and Aiken 2002 supports the testing/characterization route; it does not make these selected core dimensions or cyclic coefficients a reproduced brace test. A complete tested device card has not been invented.
Wall: PEER web material/ratios with an E-SFI numerical patch is a mixed-source diagnostic. Its geometry/loading are not the SD-06-00/45 or RW experiment. M30/Fe500 remains a separate nominal research baseline.

## Relation to the thesis building
The integrated workbench exports runnable material definitions. It does not overwrite building assignments, change actual reinforcement, fabricate experimental capacities or approve nonlinear readiness. Project frame sections still require reinforcement geometry and confinement; FSAM mappings require the actual wall regions/openings. Existing main-program mapping/configuration is retained. M30 cube strength, cylinder strength, expected strength and a literature specimen strength are not interchangeable.

For comparing outrigger elevations use the same material set, mass, gravity/preload, damping, records/scales, device sizing rule and acceptance criteria across configurations; retain ULS then SLS and XY/YX identities. The included Research_Components/study matrix is a plan, not completed building NLTHA. Record peak/residual edge drift, roof displacement, floor acceleration, member strains/rotations, device demand, convergence, energy and timing. IO/LS/CP assignment requires applicable component acceptance data; a material hysteresis plot alone does not establish performance.

## Verification and limitations
Main fresh-process startup passed. GUI loads all 17 profiles and eight saved result panels; exported definitions preserve an existing OpenSees node domain. Eight of nine added reference profile runs completed; the PEER-material E-SFI patch failed at cyclic reversal step31. Failure and partial results are retained in Verification_V159. No source parameters were changed to manufacture a pass. The supplied eight nominal baselines completed previously. Project material validation and full building NLTHA are not claimed.

References and exact URLs are included in each catalog card and in Research_Components/References.json and 02_MODELLING_BASIS.md. Primary-source locators were checked on 2026-10-28.
