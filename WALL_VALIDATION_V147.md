# Wall validation workbench - V147

Run **10_WALL_VALIDATION.py**, or use the **Wall validation - Kolozvari 2023 / Lu 2015** button in Section / Material Review. A separate process protects the active OpenSees domain. JSON, CSV, PNG and elapsed times are saved in Wall_Validation_Results. Full Lu cyclic execution is optional; it can fail, and that is reported rather than ignored. The complete numbered bundle retains prior application functionality.

## What is implemented and verified

1. Kolozvari route: native E_SFI_MVLEM_3D creation, five separated FSAM macro-fibers, gravity reaction balance, and 10 Newmark transient steps (0.05 s synthetic low acceleration). Uses the existing **PEER 2015 RW-A15-P10-S78 web material card**, not the 2023 SD-06 material card. Gravity relative equilibrium error was about 3.8e-16. This verifies executable commands and a small numerical case only.
2. Lu route: imports only model-definition calls from the official OpenSeesPy conversion, retaining ShellNLDKGQ, LayeredShell, PlaneStressUserMaterial, PlateFromPlaneStress, PlateRebar and specimen reinforcement/trusses. Solver return codes are now checked. The small +/-0.1 mm reversal completed; gravity relative imbalance was about 2.9e-5. Native model units are N/m; exported forces are kN and displacements m.
3. Full Lu cyclic protocol was attempted and **failed convergence**. It is not marked experimentally validated. The original example's unchecked analyze calls must not be treated as evidence of convergence. Partial converged rows are retained. Original protocol is prescribed-displacement data despite the source comment calling it load-controlled. Our displacement-control stepping differs from its Path/SP driver and must be reviewed before experimental comparison.
4. Explicit section adapters check FSAM arrays and LayeredShell thickness sums. No-boundary project cards reject assumed confined concrete and missing reinforcement/material/local-axis/regularization evidence. These adapters are foundations, **not automatic building assembly integration**.
5. A validation matrix lists numerical and physical stages; unexecuted stages remain NOT_EVALUATED. No overall PASS, no automatic readiness approval.

## Kolozvari 2023 first: remaining reproduction steps

Use SD-06-00 and SD-06-45 geometry, actual axial loading, reinforcement, concrete/steel and experimental records from the authors/test report. Author public repository/documentation currently supplies figures and descriptions; a complete numerical specimen dataset was not recovered here. Do not relabel the PEER-2015 card as SD-06. Reproduce 0 and 45 degree hysteresis and shear-deformation partition; then independently validate another suitable specimen. The reported errors in the paper are observations for those specimens, not universal acceptance limits.

Rigid end sections in a macro-element formulation are kinematic assumptions, not physical beams inserted into your core. Check that the assumption is appropriate for panel height, openings and local strain distribution. The project has no special boundary elements: use actual distributed reinforcement and unconfined concrete unless real detailing supports confinement. Adjacent faces must share physical corner nodes; do not rigid-link away warping or add nonexistent beams.

## Lu route: next development stages

Use the official boundary specimen only as a software benchmark. For your core, construct local layers from actual web bars and cover, without copying special boundary reinforcement/trusses. Verify local PlateRebar angles separately on each wall face; the example's global orientation is different from your vertical XZ/YZ faces. Verify layer thickness and steel volume without double counting. Establish tension/compression softening regularization and mesh sensitivity before extrapolating from a planar specimen to a nonplanar core.

Required stages in validation_matrix.csv: material monotonic/cyclic response; elastic axial/bending/shear patch tests; rigid-body/objectivity/local-axis tests; signed cyclic envelopes, unloading, pinching, residual drift and closed-cycle energy; mesh/macro-fiber refinement; axial-load sensitivity; biaxial/torsion/corner connectivity; openings/coupling; out-of-plane/buckling applicability; geometric nonlinearity; transient time-step and damping sensitivity; independent validation; actual building gravity/mass/modal reconciliation. **These stages are listed, not falsely claimed implemented or passed.**

The CSV comparison function accepts displacement_m/base_shear_kN. It reports signed peaks and whole-path work. Cyclic paths must not be compared by sorting displacement or interpolating across different branches. Whole-path work is not closed-cycle dissipated energy. No arbitrary universal error tolerance is installed.

## Sources and parameter provenance

- Kolozvari, Lopez and Massone (2023), Efficient Three-dimensional Shear-flexure Interaction Model for Reinforced Concrete Walls, Engineering Structures 294, 116700. https://doi.org/10.1016/j.engstruct.2023.116700 ; https://kkolozvari.github.io/E-SFI-MVLEM-3D/
- Habasaki et al. (1999), Multi-axial loading test for RC wall of reactor building, SMiRT-15 H03/3: SD-06 experimental basis cited by the authors.
- Lu et al. (2015), A shear wall element for nonlinear seismic analysis of super-tall buildings using OpenSees, Finite Elements in Analysis and Design 98, 14-25. https://doi.org/10.1016/j.finel.2015.01.006
- Official Python conversion by Anurag Upadhyay: https://openseespydoc.readthedocs.io/en/latest/src/RCshearwall.html ; source/data copied with attribution and SHA256 provenance in wall_validation_sources/SOURCE_MANIFEST.json. Included source remains unchanged apart from text encoding/newline storage. Its suggested steel/concrete numbers belong to the specimen only.
- Stokley and Lowes, PEER 2024/11, Evaluation and Calibration of an OpenSees Layered Shell Element Model for Simulating the Earthquake Response of Flexure-Controlled Reinforced Concrete Walls. https://peer.berkeley.edu/sites/default/files/publications/peer_2024_11_final.pdf
- PEER 2015/12, Kolozvari, Orakcal and Wallace: existing FSAM reference card source. Separate from 2023 example.

OpenSees element capability is not an NBC 105:2025 compliance certificate. Existing building nonlinear readiness remains unchanged. No live D: model or project material was overwritten. Missing project inputs remain explicit in Unconfined_Core_Input_Template.json.
