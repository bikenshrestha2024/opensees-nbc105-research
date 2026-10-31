# Parameter provenance and citations

The numerical RC template inputs (35 MPa cover strength, 44.1 MPa confined strength, residual 8.8 MPa, core strains −0.0046/−0.015, steel 550 MPa and hardening 0.01) are inherited illustrative choices. No specimen or building calibration is established for these values. Imported source properties identify M45; do not substitute the M35 template without a justified mapping.

[Concrete01 documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Concrete01.html) defines the constitutive inputs and sign convention. It does not establish this project's confinement strengths or strains. Confinement requires the actual transverse reinforcement geometry and a justified constitutive calibration.

[Steel02 documentation](https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Steel02.html) gives recommended transition constants R0 in the range 10–20, cR1=0.925 and cR2=0.15. Those recommendations support the transition defaults, not the assumed grade, hardening or BRB cyclic performance. The documentation references Filippou, Popov and Bertero (1983), EERC 83-19. BRB yielding length, core area and cyclic calibration remain project inputs.

[ViscousDamper documentation](https://opensees.berkeley.edu/wiki/index.php/ViscousDamper_Material) describes a Maxwell spring and nonlinear dashpot in series. K has force/length units; Cd has force×(time/length)^alpha units. Supply physical K explicitly.

[OpenSees one-storey damper example](https://opensees.ist.berkeley.edu/wiki/index.php?title=Dynamic_Analyses_of_1-Story_Moment_Frame_with_Viscous_Dampers) uses K=25 kN/mm, Cd=20.74 kN(s/mm)^0.35 and alpha=0.35. In kN–m–s these become K=25,000 kN/m and Cd=20.74×1000^0.35 kN(s/m)^0.35. The GUI exposes this as a reference-only profile. It is not evidence of a suitable damper for the 95 m building.

See AXIAL_SHORTENING_LITERATURE_V124.md for the retained elastic, creep, shrinkage and staged-construction discussion. The reported gravity displacement is an instantaneous model result and does not include all long-term differential-shortening mechanisms.
