# V137 literature review and recommended nonlinear route

Review date: 2026-10-24. Connected GitHub account: bikenshrestha2024. The inventory returned 20 accessible repositories. All were screened for relevance; 14 structural repositories had root contents and metadata inspected, followed by focused source inspection. This is not a line-by-line audit of every repository or a search of all GitHub. No GitHub repository was modified.

## Decision and runnable result
Start with the published RC portal example, already completed locally, before expanding the project building. It gives genuine nonlinear direct integration with a small, inspectable model. Use the verified PEER wall material card to understand FSAM, then reproduce and calibrate a wall component before adopting a building wall-property mapping. E-SFI-MVLEM-3D is the selected wall formulation for future project integration because it is the efficient shear-flexure-interaction formulation already intended by this exporter.

Launch `17_LITERATURE_COMPONENT_DEMO.py` (the legacy `RUN_LITERATURE_DEMO.py` alias is retained), or use Literature nonlinear demo in the main analysis column / nonlinear history window. Run elastic + nonlinear comparison, then View saved graphs / animation. Select an AT2 earthquake or keep bundled El Centro. The output folder is independent of the building export. This route deliberately does not read, alter or approve the building readiness manifest.

The source teaching frame has 360 in span, 144 in height, 15 x 24 in columns, 1.5 in cover and eight 0.60 in2 reinforcing fibers. All dimensions, forces and stresses are converted into kN-m-s. Concrete01 core is (-6 ksi, -0.004, -5 ksi, -0.014), cover (-5 ksi, -0.002, 0, -0.006), and Steel01 is (60 ksi, 30000 ksi, b=0.01). Source tags are retained within the isolated model. These are teaching values, not approved properties of the source M45 building.

Source: OpenSees Example 3.1, Andreas Schellenberg (2017):
https://github.com/OpenSees/OpenSees/blob/master/EXAMPLES/ExamplePython/Example3.1.py
Transient reference: Minjie, OpenSeesPy RCFrameEarthquake:
https://openseespydoc.readthedocs.io/en/latest/src/RCFrameEarthquake.html
The user fork's notebook was checked against those sources:
https://github.com/bikenshrestha2024/OpenSeesPy-Official-Structural-Examples/tree/main/Reinforced%20Concrete%20Frame%20Earthquake%20Analysis
Its name does not establish official provenance; the actual OpenSees sources above provide that reference. Its notebook comment says feet although the dimensions and stress data are inch-kip quantities. The new demonstration makes the conversion explicit and uses five integration points from the OpenSees source, rather than eight in the fork. It uses standard g=9.80665 m/s2 consistently for weight-derived mass and acceleration rather than the tutorial's rounded 386.4 in/s2. Other additions are response recording, an elastic initial-section-tangent baseline, plots and playback; this is not claimed as bit-identical reproduction of the old tutorial.

## Numerical implementation and observation
Newmark gamma=0.5, beta=0.25 is implicit average acceleration with Newton iteration. This is direct integration of the finite-element equations, not modal response-spectrum superposition. Gravity is converged and frozen first. P-Delta is retained. Reference committed-stiffness damping betaKcomm=0.000625 seconds is preserved; it is a benchmark setting, not a universal damping prescription. Initial damping ratios for the two inspected nonlinear modes are about 0.51% and 4.13%. No claim is made for every higher mode or NBC site compliance.
https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/integrator/Newmark.html

El Centro has 1559 samples at 0.02 s, in g. Run length is (1559-1)*0.02 = 31.16 s. The selected integration step is 0.0025 s. One g is converted once by 9.80665; the GUI motion scale multiplies independently. This record has not been matched to the Nepal project spectrum. Absolute acceleration is relative node acceleration plus contemporaneous ground acceleration. Restoring base shear is assembled from GLOBAL column-end force components; local column axial force is not mislabelled as lateral shear.

Observed peak roof response: elastic baseline 50.467 mm; nonlinear fiber model 62.984 mm. Nonlinear steel strain exceeds the model yield strain 0.002, and material loops show inelastic response. The selected bar reaches about 0.0351 strain; Steel01 has no fracture/degradation cutoff here, so this is not a safe-capacity or collapse prediction. Halving dt to 0.00125 s changes peak roof displacement by 0.0046% elastic and 0.0283% nonlinear. This establishes small time-step sensitivity for this run, not experimental validation. Execution took about two seconds including charts in this environment; it cannot predict a 25-storey building runtime.

Graphs, histories, JSON parameters, timing and an actual recorded-node playback are supplied in Worked_Example_V137/RC_Portal_Direct_Integration. Playback uses recorded translations for both roof nodes with straight member chords, not exact distributed fiber curvature.

## Wall material data verified in the primary report
The existing literature profile was verified against Kolozvari, Orakcal and Wallace, PEER 2015/12, Appendix B.3, printed pages 90-92 (PDF pages 102-104). The separate JSON card preserves source units and specimen identity RW-A15-P10-S78. ConcreteCM, SteelMPF and FSAM definitions use converted stresses and dimensionless reinforcement ratios. Web FSAM tag is 906 and boundary tag is 907; the five-panel specimen partition uses [907,906,906,906,907]. Boundary properties must not be assigned to all project wall cells. The card and Literature_Wall_Materials.py are examples, not a project mapping.
https://peer.berkeley.edu/publications/2015-12
https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf

The published planar specimen has neither the source building's openings nor its actual reinforcement/confinement. The separate E-SFI check is one small four-node cell using the material/width partition; its geometry adapter, 1-kN probe load and element defaults are numerical choices. It successfully created SteelMPF, ConcreteCM, FSAM and E_SFI_MVLEM_3D in OpenSees 3.8.0 and converged. It is a command/material availability check, not an experimental validation or wall response-history test. Full experimental reproduction remains a later step.

### Actual builder bug corrected
The previous code called E-SFI_MVLEM_3D with a hyphen. The native command requires E_SFI_MVLEM_3D with underscores. Both the complete assembly and separate area exporter now use the correct command, verified by the standalone cell check. The author GitHub documentation uses the hyphenated model name; the command spelling is confirmed by the OpenSees command manual:
https://openseesdocumentation.readthedocs.io/en/latest/user/manual/model/elements/E_SFI_MVLEM_3D.html
Author formulation/paper links:
https://kkolozvari.github.io/E-SFI-MVLEM-3D/
https://doi.org/10.1016/j.engstruct.2023.116700
Earlier formulation:
https://kkolozvari.github.io/SFI-MVLEM-3D/

## GitHub repository findings
| Repository | Use and decision |
|---|---|
| OpenSeesPy-Official-Structural-Examples | Selected RC portal notebook + El Centro record; verified against true OpenSees sources. |
| OpenSees_course | 2_RC_Frame has separate gravity, modal, pushover X/Y and history X/Y Tcl scripts. Good organization reference, not project calibration. |
| OpenSeesPy-Tutorials | Fiber, curvature, nonlinear cantilever and reverse-cyclic examples; useful learning sequence. |
| OpenSeesPyTutorials | cslotboom tutorials: fiber section and cyclic pushover; component workflow reference. |
| OpenSees-Examples | Anurag Upadhyay dynamics: reviewed GMAnalysis.tcl, bridge-specific recorders and recovery stack. Not adopted wholesale for the building. |
| OPENSEES_SALAR | Broad examples and verification folders. Useful secondary examples; each case needs its own evidence. No blanket adoption of constants. |
| SALAR_PYTHON-CODE | Newton, moment-curvature, spectra and other analytical examples; not a calibrated wall material library. |
| SEISMOSTRUCT_SALAR | The named Vecchio frame folder contained only a one-byte placeholder. No calibration evidence can be recovered from that folder. |
| SALAR_EXCEL-CODE | Project/finance and hinge methods; not selected for nonlinear FE constitutive parameters. |
| FM-2D | MATLAB/OpenSees steel-frame platform; useful later for steel frame validation, not the selected RC wall benchmark. No bundled executable run. |
| vfo | Visualization candidate; no constitutive parameters inferred from visualization software. |
| opstool | Pre/postprocessing and section tools; not a replacement for material calibration. |
| GPR_SDoF_Maxwell_FVD | README describes Maxwell-damper SDOF surrogate predictions; not a general RC wall or full-building nonlinear calibration. Large archives not downloaded. |
| limitstates | README says public beta, currently Canadian design libraries with RC checks still on the roadmap. It does not supply an NBC/IS RC reinforcement-design engine. |

The remaining six repositories (web-page-dumper, sketchup-mcp, GFPLAIN, pyRevit, photocraft, rea) were screened from the inventory and excluded from constitutive-model selection. See GitHub_Repository_Screening_20261024.json for all 20 repository URLs, upstreams and exact review scope. No exhaustive line audit or all-GitHub search is claimed.

## Building course of action
1. Inspect the completed portal histories and yielding loops. Rerun a selected AT2 in the isolated GUI.
2. Use PEER material cards and the successful E_SFI cell check; reproduce the full specimen cyclic protocol before claiming experimental validation.
3. For the building, reconcile actual M45 cylinder/cube interpretation, steel curves, cover, tie confinement, wall web/boundary/jamb reinforcement and opening/coupling-beam geometry. The source-wall layout helper is not evidence for every boundary region. One FSAM material per exported quad cannot automatically represent a distinct confined boundary inside that quad.
4. Review nonlinear end releases and all frame section mappings. The existing builder explicitly rejects unsupported hinged-brace nonlinear releases; adding wall tags alone will not complete it.
5. Complete nonlinear gravity/P-Delta, initial modal comparison, element/mesh checks and recorded component-response acceptance before the full bidirectional XY/YX suite. Retain NBC 105:2025 record/scaling, integration-step and acceptance requirements; a 2D El Centro demo is not a substitute for that building assessment.

No project readiness check is auto-ticked, no calibrated-property claim is manufactured, and no live D: model/configuration was edited. Rebuild the export to use the corrected wall command. Existing numeric-cache checks may require fresh results after a runtime/source change; old approval is not transferred silently.
