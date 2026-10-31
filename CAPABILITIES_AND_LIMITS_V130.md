Historical V130 record. V132 documentation supersedes the current capability and validation status.

# V130 capabilities and limits

- Section mapping, material/section library and brace assignment are separate entry points. Constitutive templates need project calibration.
- Gravity uses assembled source loads, a single physical self-weight ledger and a reaction-equilibrium check.
- Equivalent static calculations retain separate X/Y and SLS/ULS cases and method-eligibility blocks.
- Modal eigenanalysis has separate SLS/ULS stiffness cases and output locations. Cumulative modal mass is a participation check, not a complete design audit.
- The response_spectrum component provides site and record spectrum/scaling diagnostics. A complete MRSM member-force workflow with modal combination, missing-mass treatment and base-shear scaling is not implemented in this release.
- Linear time history supports selected record pairs, both orientations, histories and GUI inspection. No new full-building V130 time-history ensemble was run for this release.
- Nonlinear time history has its own runner, input/readiness gate and solver recovery. Full-building nonlinear constitutive validation, acceptance criteria and calibrated wall/device behavior remain project work. No full-building V130 NLTHA result is supplied.
- Slab bending modifiers are implemented; rational cracked-wall stiffness equivalence has not been established by this change.
- Load transfer checks establish force/moment balance and connectivity. Mesh convergence and independent member-force comparison with ETABS remain necessary.
- No roof-live assignments were present in the supplied source ledger. No roof live was invented. Confirm whether the source model must be corrected and re-exported.
- Rigid diaphragm checks establish the implemented constraints. They do not establish that the rigid assumption is appropriate for every floor.

This release is a reviewed computational workflow, not an unconditional certificate of NBC compliance or a completed structural design.
