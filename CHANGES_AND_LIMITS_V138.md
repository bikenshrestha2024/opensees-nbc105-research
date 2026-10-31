# V138 - compact gravity view, ULS/SLS comparison and staged building trial

Launch RUN_ETABS_TO_OPENSEES.py. Rebuild the saved export to refresh its runtime. Older releases remain intact. No live D: files were changed by this work.

## Gravity view
Plot controls now occupy two compact rows above the chart, with a narrow navigation row below. Camera presets and zoom remain available. The 3D model is enlarged with its physical aspect ratio retained. A native 1200x850 window check measured a 1196x705 plot canvas. Its size still depends on the available window height and screen scaling; no model geometry is stretched to fill the horizontal space.

## Force profiles
Use Plots, then Side-by-side ULS / SLS force profiles (also available in the individual case-profile window). ULS is left, SLS right; floor forces and storey shear form separate rows. X/Y curves share horizontal scales within each row. Select matching force polarity and eccentricity (E0, E+, E-). Missing cases are stated explicitly. ULS-ineligible ESM remains a comparison-only reference, not permitted ULS design analysis merely because it is plotted.

## Working current-building exploratory route
In the main analysis column or nonlinear history window, choose Current building: exploratory nonlinear frames / elastic walls. Select the assembled export folder, earthquake pair, XY/YX/both, integration step and trial duration. Duration 0 requests the full record; the default 1-second trial is deliberately shorter. A timestamped scenario receives copies of the model inputs and a complete ASSUMPTIONS_NOT_DESIGN.json. The source model/config/readiness files are not changed.

THIS IS A STAGED MODEL: nonlinear RC fiber frames and idealized axial braces with ELASTIC WALLS. It is not a fully nonlinear wall-frame assessment. It uses the building's 3627 nodes, 4912 elements, source loads, masses, supports and rigid diaphragms. RC properties are existing illustrative M35/Fe550 templates, not project-calibrated M45 properties. The full template data are recorded. Hinged SHS braces use corotTruss with source area/E, assumed fy345MPa and hardening0.01; this axial idealization does not model flexural buckling, fatigue or fracture. No frame-release behavior is silently represented as calibrated.

Walls use source geometry/E/thickness and elastic effective flexural factors ULS0.5/SLS0.7; floor slab factors remain ULS0.25/SLS0.35. The membrane stiffness and physical gravity/mass accounting remain preserved. This staging is an explicit research idealization, not a substitute for calibrating FSAM wall behavior.

Twenty positive initial modes are inspected; a two-term Rayleigh law is set to 5% at the lowest/highest inspected frequencies. The report retains all inspected periods/damping ratios. This checks the initial inspected band, not all modes throughout nonlinear softening or full NBC modal-mass coverage. dt is bounded by record dt, 0.01 s, inspected T1/100 and inspected shortest period. Spectrum matching must be separately verified; source record metadata do not certify it. Ground motion in g is converted once by 9.80665; scale1 is independent of unit conversion. Gravity is equilibrated and frozen before Newmark 0.5/0.25 with iterative Newton-family recovery and bounded subdivision. Accepted substeps are retained.

## Actual verification
The selected source geometry completed gravity at 286447.788933 kN with the staged model. Independent Kobe XY and YX trials each completed 10 requested steps of 0.005 s, covering only 0.05 s of the 40.94 s paired record. Both used at most two Newton iterations per accepted step and no recovery. Transient-stage/report processing took about 15 s XY and 17 s YX after construction/gravity/modal work. These short, low-amplitude startup trials do not establish response at the strong-motion peak, yielding, mesh convergence, full-record convergence, safety or code acceptance. No full earthquake record was run for the building in this release.

Worked_Example_V138 contains both startup histories, coherent deformation snapshots, drift screens, copied geometry and logs. Inspect saved histories / playback opens the existing history viewer. Playback based on floor masters is a rigid-floor reconstruction, not exact local wall curvature. The new runner additionally exports concurrent final frame actions when the element supplies a standard 12-component local-force vector; no reinforcement design or component acceptance is inferred from those actions.

## Fully nonlinear wall route: unresolved and documented
The original one-centered-macro-fiber panel representation was deficient for in-plane bending. The builders now require multiple separated axial macro-fibers, with five equal-width fibers as the starting numerical discretization. Five is a modeling choice requiring convergence checks, not an NBC-prescribed count. Both assembly and standalone area export use the corrected E_SFI_MVLEM_3D command spelling.

Diagnostic results: a single E-SFI cell with one centered fiber became unstable during the small transient diagnostic; a five-fiber E-SFI cell completed that diagnostic. However, applying the five-fiber PEER web material to all source building wall cells failed at 25% gravity. The earlier one-fiber full-building model passed gravity but failed at the second transient step; a mass-only damping diagnostic also failed. These observations do not establish that damping alone caused the problem, and no solver failure was converted into a success. Full FSAM-wall behavior remains unresolved; it needs mesh/constraint/material-region review and project calibration. The calibrated production route still requires its readiness evidence and actual material definitions/maps. That gate is not auto-approved by the exploratory route.

## Sources and existing limitations
NBC 105:2025 remains the governing seismic basis; Table3-1 effective elastic wall stiffness and Section5.5 drift checks remain separate from nonlinear material acceptance:
https://ebps.kathmandu.gov.np/UploadFiles/NBC_105_2025_Sesmic_Design.pdf
E-SFI formulation and commands:
https://openseesdocumentation.readthedocs.io/en/latest/user/manual/model/elements/E_SFI_MVLEM_3D.html
https://kkolozvari.github.io/E-SFI-MVLEM-3D/
PEER specimen material card (research reference only):
https://peer.berkeley.edu/publications/2015-12
Newmark integration:
https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/integrator/Newmark.html
The inherited V137 literature review distinguishes teaching parameters from project calibration. The V135 design-check limitations remain: no automatic complete RC reinforcement-demand/interaction-surface engine or nonlinear performance acceptance certificate.
