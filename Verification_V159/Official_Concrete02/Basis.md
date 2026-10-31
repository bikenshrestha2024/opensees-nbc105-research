# OpenSees MEFI example: unconfined material 4

DIRECT PUBLISHED NUMERICAL EXAMPLE | These are that example material values; epsU=-0.037 must not be treated as an unconfined project strain capacity.

Same parabolic/linear compressive backbone; initial tangent=2*fpc/epsc0. Tensile cracking strain=ft/E0; after cracking sigma=max(0,ft-Ets*(eps-ft/E0)). lambda controls cyclic unloading. Native Yassin implementation governs reversals.

Source: https://openseesdocumentation.readthedocs.io/en/latest/user/manual/model/elements/MEFI.html
Locator: Pushover example: uniaxialMaterial Concrete02 tag 4

No experimental equivalence or project approval is inferred. This export does not set nonlinear_parameters_reviewed or change the building configuration.
