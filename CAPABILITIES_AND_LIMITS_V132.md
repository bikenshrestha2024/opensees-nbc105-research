# V132 capability boundaries

Implemented and exercised: assembled gravity; ineligible ULS ESM comparison calculation and solver path; separate SLS/ULS modal audits; model MRSM with CQC, force-only base-shear scaling and signed floor eccentric-influence cases; shared drift reporting; available-input autofill; UTF-8 interface/process I/O.

Still requiring project evidence or work:

- Nonlinear wall/frame/device calibration and completed readiness evidence. No full-building nonlinear earthquake run was performed for this release.
- Weak-storey strength capacities and reviewed plan/vertical discontinuity evidence. Incomplete checks are not marked regular.
- Member design, concurrent interaction actions and orthogonal/gravity design combinations. MRSM global component envelopes are analysis outputs, not a complete member design.
- Missing-mass correction if known high-frequency modes are present. The MRSM engine stops in that situation.
- Independent ETABS reconciliation of load, seismic mass, geometric overlap conventions, cracked-wall stiffness, mesh sensitivity and foundation assumptions.
- Roof-live source assignments were absent from the supplied export; no roof-live load is invented.

The eccentric MRSM implementation is a signed floor-torque influence model on the existing eigenbasis. It does not claim a separate re-eigensolution with a physically shifted mass matrix. History 3D views are rigid-floor lateral reconstructions, not full finite-element animation. CQC deformation views are envelopes, not simultaneous nodal states.

Calibration/readiness confirmations remain manual. Values without a defensible source stay incomplete even when surrounding GUI fields are populated.
