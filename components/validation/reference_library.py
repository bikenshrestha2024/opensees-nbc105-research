"""Annotated source registry for the NBC 105:2025 OpenSees project.

Use the references as traceable sources for equations, element formulations,
and published validation. They do not validate this project's ETABS export,
member properties, wall openings, or damper calibration by themselves.
The matching human-readable bibliography is REFERENCES_AND_LEARNING_RESOURCES_V116.md.
"""
from __future__ import annotations

__release__ = '135'

from typing import Dict, List

REFERENCE_CATEGORIES: Dict[str, List[dict[str, str]]] = {
    "governing_and_project_design_basis": [
        {
            "id": "NBC105-2025",
            "title": "NBC 105:2025 — Seismic Design of Buildings in Nepal",
            "url": "https://www.dudbc.gov.np/pages/24231978/",
            "use": "Governing seismic design basis for this Nepal study; obtain the official document from the DUDBC code listing.",
            "limit": "Verify the adopted edition, errata, project jurisdiction, and clause text before design decisions.",
        },
        {
            "id": "IS16700-2023",
            "title": "IS 16700:2023 — Criteria for Structural Safety of Tall Concrete Buildings",
            "url": "https://www.services.bis.gov.in/tmp/CED20920094_14092023_1.pdf",
            "use": "Project-required supplementary source for initial P-Delta load case (7.2(d)) and tall-building stability checks where applicable.",
            "limit": "It does not replace NBC 105. Check the official BIS publication and applicability to the project; stability provisions are not to be represented as NBC pass/fail criteria.",
        },
    ],
    "opensees_software_and_examples": [
        {
            "id": "OpenSees-docs",
            "title": "OpenSees Documentation",
            "url": "https://opensees.github.io/OpenSeesDocumentation/",
            "use": "Command semantics and model/analysis documentation, including damping and element behavior.",
            "limit": "Documentation describes software behavior; engineering input selection remains project-specific.",
        },
        {
            "id": "OpenSees-source",
            "title": "OpenSees source repository",
            "url": "https://github.com/OpenSees/OpenSees",
            "use": "Implementation source and release history for OpenSees.",
            "limit": "Pin and record the actual OpenSees/OpenSeesPy version used for reproducibility.",
        },
        {
            "id": "OpenSees-examples",
            "title": "OpenSees examples",
            "url": "https://github.com/OpenSees/OpenSeesExamples",
            "use": "Example models and analysis scripts to understand command patterns.",
            "limit": "Examples are not project designs or proof that a model is validated.",
        },
        {
            "id": "OpenSeesPy",
            "title": "OpenSeesPy repository and user documentation",
            "url": "https://github.com/zhuminjie/OpenSeesPy",
            "use": "Python interface and package information.",
            "limit": "Confirm command syntax against the installed OpenSeesPy release.",
        },
        {
            "id": "OpenSeesPy-docs",
            "title": "OpenSeesPy documentation repository",
            "url": "https://github.com/zhuminjie/OpenSeesPyDoc",
            "use": "OpenSeesPy documentation sources and examples.",
            "limit": "Examples are instructional; check for version-specific differences.",
        },
        {
            "id": "OpenSees-twoNodeLink",
            "title": "Two Node Link Element — OpenSees Wiki",
            "url": "https://opensees.berkeley.edu/wiki/index.php/Two_Node_Link_Element",
            "use": "Link DOFs, directions, local axes, recordable responses, and Rayleigh damping option.",
            "limit": "Check that link orientation and DOFs correspond to the actual damper/brace geometry.",
        },
        {
            "id": "OpenSees-ViscousDamper",
            "title": "ViscousDamper Material — OpenSees Wiki",
            "url": "https://opensees.berkeley.edu/wiki/index.php/ViscousDamper_Material",
            "use": "Maxwell spring-dashpot material command and parameter definitions (K, Cd, alpha).",
            "limit": "Do not copy the wiki example parameter values as project device properties; use manufacturer/test-calibrated inputs and compatible units.",
        },
        {
            "id": "OpenSees-FVD-example",
            "title": "Dynamic Analyses of 1-Story Moment Frame with Viscous Dampers",
            "url": "https://opensees.berkeley.edu/wiki/index.php/Dynamic_Analyses_of_1-Story_Moment_Frame_with_Viscous_Dampers",
            "use": "Worked example for twoNodeLink and ViscousDamper usage and response recording.",
            "limit": "Single-storey demonstration; not a validated high-rise outrigger design or parameter source.",
        },
        {
            "id": "Kolozvari-E-SFI-MVLEM-3D-code",
            "title": "E-SFI-MVLEM-3D documentation and implementation resources",
            "url": "https://kkolozvari.github.io/E-SFI-MVLEM-3D/",
            "use": "Published three-dimensional RC wall macro-element formulation, implementation guidance, and example resources.",
            "limit": "Confirm wall geometry, opening/coupling-beam applicability, and model assumptions; an element formulation is not itself a full core model.",
        },
        {
            "id": "Kolozvari-SFI-MVLEM-3D",
            "title": "SFI-MVLEM-3D original wall formulation (2021), distinct from E-SFI (2023)",
            "url": "https://kkolozvari.github.io/SFI-MVLEM-3D/",
            "use": "Research implementation/reference for three-dimensional shear-flexure interaction wall modeling.",
            "limit": "Review repository status, dependencies, element availability in the chosen OpenSees build, and licensing before use.",
        },
        {
            "id": "Community-OpenSeesPy-Tutorials",
            "title": "OpenSeesPy Tutorials (community repository)",
            "url": "https://github.com/Ashim-Paudel/OpenSeesPy-Tutorials",
            "use": "Supplementary learning examples for OpenSeesPy workflows.",
            "limit": "Community material; not authoritative documentation or a structural design reference.",
        },
    ],
    "research_papers": [
        {
            "id": "Kolozvari-et-al-2023-E-SFI-MVLEM-3D",
            "title": "Kolozvari, K., López, C. N., & Massone, L. M. (2023). Efficient three-dimensional shear-flexure interaction model for reinforced concrete walls. Engineering Structures, 294, 116700.",
            "url": "https://doi.org/10.1016/j.engstruct.2023.116700",
            "use": "Formulation and experimental comparison of a computationally efficient nonlinear 3D RC wall model; relevant to solid and non-planar walls.",
            "limit": "An opening wall requires explicit piers/spandrels/coupling behavior and demonstrated mesh/element suitability; do not assume a solid-wall calibration transfers unchanged.",
        },
        {
            "id": "Kolozvari-et-al-2021-SFI-MVLEM-3D",
            "title": "Kolozvari, K., Kalbasi, K., Orakcal, K., & Wallace, J. W. (2021). Three-dimensional shear-flexure interaction model for analysis of non-planar reinforced concrete walls. Journal of Building Engineering, 44, 102946.",
            "url": "https://doi.org/10.1016/j.jobe.2021.102946",
            "use": "SFI-MVLEM-3D formulation and validation for non-planar/flanged wall response under multidirectional loading.",
            "limit": "Check model assumptions and its treatment of openings and coupling elements for the actual core layout.",
        },
        {
            "id": "Lopez-et-al-2022-E-SFI-planar-validation",
            "title": "López, C. N., Massone, L. M., & Kolozvari, K. (2022). Validation of an efficient shear-flexure interaction model for planar reinforced concrete walls. Engineering Structures, 252, 113590.",
            "url": "https://doi.org/10.1016/j.engstruct.2021.113590",
            "use": "Validation against ten planar wall tests spanning shear-span/depth ratios and loading conditions.",
            "limit": "Validation domain and specimen details must be compared with the thesis wall reinforcement, axial load, aspect ratio, and openings.",
        },
        {
            "id": "PEER-2015-12-Kolozvari-Orakcal-Wallace",
            "title": "Kolozvari, K., Orakcal, K., & Wallace, J. W. (2015). Analytical Model for Nonlinear Response of RC Walls. PEER Report 2015/12.",
            "url": "https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf",
            "use": "Model formulation and validation background for SFI-MVLEM and RC wall nonlinear response.",
            "limit": "Use specimen-level calibration data and report applicability limitations; the report predates newer 3D formulations.",
        },
        {
            "id": "Chopra-McKenna-2016-Rayleigh",
            "title": "Chopra, A. K., & McKenna, F. (2016). Modeling viscous damping in nonlinear response history analysis of buildings for earthquake excitation. Earthquake Engineering & Structural Dynamics, 45(2), 193–211.",
            "url": "https://doi.org/10.1002/eqe.2622",
            "use": "Discusses Rayleigh damping choices and their implications for nonlinear response-history analysis.",
            "limit": "Damping coefficients and formulation should be sensitivity-checked for this model; avoid double-counting explicit FVD energy dissipation.",
        },
    ],
    "damped_outriggers_and_device_research": [
        {
            "id": "Smith-Willford-2007-damped-outrigger",
            "title": "Smith, R. J., & Willford, M. R. (2007). The damped outrigger concept for tall buildings. The Structural Design of Tall and Special Buildings, 16(4), 501–517.",
            "url": "https://doi.org/10.1002/tal.413",
            "use": "Conceptual and analytical basis for coupling a perimeter outrigger to supplemental damping.",
            "limit": "Study-specific results; its reported damping improvement is not a transferable damping multiplier for this building.",
        },
        {
            "id": "Chen-et-al-2010-damped-outriggers",
            "title": "Chen, Y., McFarland, D. M., Wang, Z., Spencer, B. F., & Bergman, L. A. (2010). Analysis of Tall Buildings with Damped Outriggers. Journal of Structural Engineering, 136(11), 1435–1443.",
            "url": "https://doi.org/10.1061/(ASCE)ST.1943-541X.0000247",
            "use": "Analytical screening method for damper-outrigger location, size, and modal response.",
            "limit": "Simplified analytical model; not experimental validation of this 3D asymmetric RC building.",
        },
        {
            "id": "Huang-Takeuchi-2017-damped-outrigger-height",
            "title": "Huang, B., & Takeuchi, T. (2017). Dynamic Response Evaluation of Damped-Outrigger Systems with Various Heights. Earthquake Spectra, 33(2), 665–685.",
            "url": "https://doi.org/10.1193/051816EQS082M",
            "use": "Method for screening damper-outrigger elevation and damper size using analytical and member models.",
            "limit": "The simplified cantilever/SDOF results are not floor prescriptions for a different building.",
        },
        {
            "id": "Lin-Takeuchi-Matsui-2018-BRB-outrigger",
            "title": "Lin, P.-C., Takeuchi, T., & Matsui, R. (2018). Seismic performance evaluation of single damped-outrigger system incorporating buckling-restrained braces. Earthquake Engineering & Structural Dynamics, 47(12), 2343–2365.",
            "url": "https://doi.org/10.1002/eqe.3072",
            "use": "BRB-outrigger elevation and stiffness relationships evaluated with nonlinear response-history analysis.",
            "limit": "The modeled heights and idealized system differ from this 25-storey asymmetric RC building; do not copy its optimum elevation or BRB properties.",
        },
        {
            "id": "Lin-Takeuchi-Matsui-2019-multiple-BRB-outrigger",
            "title": "Lin, P.-C., Takeuchi, T., & Matsui, R. (2019). Optimal design of multiple damped-outrigger system incorporating buckling-restrained braces. Engineering Structures, 194, 441–457.",
            "url": "https://doi.org/10.1016/j.engstruct.2019.05.078",
            "use": "Supports treating multiple outrigger elevations and relative core, perimeter-column, and BRB stiffness as coupled design variables.",
            "limit": "Study-specific idealized buildings; use as a search methodology, not a direct project design.",
        },
        {
            "id": "Lin-Takeuchi-2019-BRB-configurations",
            "title": "Lin, P.-C., & Takeuchi, T. (2019). Seismic performance of buckling-restrained brace outrigger system in various configurations. Japan Architectural Review, 2(4), 392–408.",
            "url": "https://doi.org/10.1002/2475-8876.12120",
            "use": "Compares BRB-outrigger configurations and elevation-selection methods for preliminary design.",
            "limit": "Charts and numerical recommendations depend on the studied building/system assumptions.",
        },
        {
            "id": "Lin-Chen-2024-BRB-outrigger-test",
            "title": "Lin, P.-C., & Chen, P.-H. (2024). Shaking table test of a buckling-restrained brace outrigger system. Journal of Constructional Steel Research, 213, 108415.",
            "url": "https://doi.org/10.1016/j.jcsr.2023.108415",
            "use": "Relevant experimental reference for BRB-outrigger behavior and model-validation planning.",
            "limit": "Use detailed test values only after reviewing the full paper and matching specimen, scale, setup, and loading; this is not validation of the present model.",
        },
    ],
    "video_learning_only": [
        {
            "id": "ASDEA-OpenSees-W16-NLTHA",
            "title": "Get Started with OpenSees with STKO: W16 Nonlinear Dynamic (Time History) Analysis",
            "url": "https://www.youtube.com/watch?v=s-AneO9KjgA",
            "use": "Walk-through of time-series, damping, uniform excitation, and transient-analysis workflow concepts.",
            "limit": "Educational software demonstration only; it is not a code interpretation, design authority, or validation of this project's analysis.",
        },
        {
            "id": "ASDEA-OpenSees-NLTHA",
            "title": "Nonlinear Time History Analysis (STKO/OpenSees demonstration)",
            "url": "https://www.youtube.com/watch?v=rp4N2icP1y4",
            "use": "Supplementary visual explanation of nonlinear time-history workflow.",
            "limit": "Educational only. Verify all commands, scaling, acceptance criteria, and units against authoritative sources and the installed version.",
        },
    ],
}


def iter_references() -> List[dict[str, str]]:
    """Return a flat copy suitable for GUI display, citation reports, or export."""
    return [dict(category=category, **item)
            for category, items in REFERENCE_CATEGORIES.items()
            for item in items]
