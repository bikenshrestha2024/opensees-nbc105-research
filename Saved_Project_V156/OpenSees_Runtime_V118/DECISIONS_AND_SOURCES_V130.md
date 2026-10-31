Historical V130 record. V132 documentation supersedes the current capability and validation status.

# V130 decisions and sources

## Code basis and scope

[NBC 105:2025, official municipal-hosted code](https://ebps.kathmandu.gov.np/UploadFiles/NBC_105_2025_Sesmic_Design.pdf) is the earthquake-method reference. Review the exact project classification, site investigation and approved design basis. Sections 3.2, 3.4, 5.1, 7, 8 and 9 govern method eligibility, stiffness, periods and dynamic analysis. A successful eigenanalysis is not permission to use an otherwise ineligible equivalent static method. ULS ESM exclusions remain visible; no substitute ULS plot is fabricated.

The empirical equation family describes the period-estimation expression, not a second structural-system assignment. Directional wall indices, empirical estimates, Rayleigh estimates and adopted design periods remain distinct. X/Y force coefficients are calculated separately. Opposite signs and eccentricity signs may share base-shear magnitude while changing load direction/torsion. The supplied SLS results were X=20,354.039 kN and Y=21,588.744 kN; they were not equal.

## Slabs and floor loads

[IS 16700:2023, BIS-hosted text, Table 5](https://www.services.bis.gov.in/tmp/CED20920094_14092023_1.pdf) gives slab bending factors 0.35 for SLS and 0.25 for ULS, with gross cross-sectional area. These factors are implemented without reducing membrane EA or physical self-weight. The implementation algebra and load-path checks are in LOAD_PATH_AND_DIAPHRAGM.md. Applicability of amendments and the project's adopted edition still requires confirmation.

[CSI Analysis Reference](https://docs.csiamerica.com/manuals/etabs/Analysis%20Reference.pdf) describes shell surface loading. The assembled model uses a compatible shell mesh and equivalent nodal loading. It does not add a second 45-degree tributary load to beams. Beam, wall and column stiffness/connectivity determine load sharing. This is an FE representation, not proof of identical ETABS member forces.

[Official ShellMITC4 implementation](https://github.com/OpenSees/OpenSees/blob/master/SRC/element/shell/ShellMITC4.cpp) and [official Python shell example](https://github.com/OpenSees/OpenSees/blob/master/EXAMPLES/ExamplePython/Example7.1.py) support the selected element and nodal-load representation. An independent small shell/perimeter-beam check is included.

## Rigid diaphragms

[OpenSees rigidDiaphragm](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/mp_constraint/rigidDiaphragm.html) assumes small rotations. For a horizontal diaphragm, DOFs 1, 2 and 6 are constrained with geometric translation/rotation coupling; vertical displacement remains free. Raw ETABS assignments now include the 25 physical centre points omitted by the earlier preview grouping. Generated mesh nodes are extended only where the story has an unambiguous diaphragm assignment. A rigid diaphragm remains a modeling assumption requiring review for openings, transfer floors and irregular geometry.

## Numerical and material values

[OpenSees Steel02](https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Steel02.html) documents the transition parameters and Filippou, Popov and Bertero (1983). Recommended numerical transition values do not establish project yield strength or confinement properties. Inherited M35/Fe550 section-builder presets and confined-concrete strengths/strains are illustrative until supported by the project's material tests/design data; source M45 does not automatically calibrate them.

[OpenSees Newmark](https://openseespydoc.readthedocs.io/en/latest/src/newmark.html): gamma=0.5, beta=0.25 is the average-acceleration numerical choice, not an NBC-prescribed material parameter. [UniformExcitation](https://openseespydoc.readthedocs.io/en/latest/src/uniformExcitation.html) returns relative nodal responses. [NIST standard gravity](https://physics.nist.gov/cgi-bin/cuu/Value?gn) supports g=9.80665 m/s2 for unit conversion, separate from motion scaling.

[ViscousDamper](https://opensees.berkeley.edu/wiki/index.php/ViscousDamper_Material) and [E-SFI-MVLEM-3D research implementation](https://github.com/kkolozvari/E-SFI-MVLEM-3D) support available constitutive formulations. Device K, Cd, alpha, BRB core properties, wall constitutive inputs and failure limits require device tests, manufacturer data or a matching published experiment. A reference formulation is not calibration evidence. Keep devices inactive until calibrated.

## Record processing and timing

The runners preserve record sampling metadata and require explicit units. Pair selection supports preliminary single-event runs and XY/YX orientation cases. A single-event trial is not the complete design ensemble. The implementation documents clause references and unresolved editorial/statistical interpretation in its method panel; confirm scaling and ensemble decisions against the approved procedure.

Processing time is an implementation measurement, not a code requirement. Sidecars report the whole named stage, start/end/time zone/status, preserving existing CSV schemas. A failed or incomplete stage is not a successful analysis. See PARAMETER_SOURCES_V125.md and METHOD_AND_PARAMETER_EVIDENCE_V129.md for the inherited detailed parameter register; this file records V130 changes and current limits.
