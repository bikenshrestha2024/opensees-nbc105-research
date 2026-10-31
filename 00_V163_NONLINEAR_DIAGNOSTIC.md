# V163 nonlinear research diagnostic

This snapshot is based on V162 and adds a non-finite displacement guard after a
failed nonlinear step. It stops instead of continuing to retry a contaminated
domain. It does not cure the underlying failure or assert design validation.

Three tests used the isolated saved building geometry in work/test160_model,
ULS, the published-reference wall research profile and the user's Kobe RSN1120
pair. All first ran the same nonlinear gravity preload (286447.788933 kN).

| First transient step, 0.005 s | Eigenanalysis | Damping | Input | Return |
|---|---|---|---|---|
| Control | no | zero | no motion | 0 |
| Control | 20 modes | zero | no motion | 0 |
| Excitation | 20 modes | zero | XY, 4095 points each, dt 0.01 s | -3 |

The excitation uses g-to-m/s2 factor 9.80665 once. The failure also occurred
in prior trials using mass-only damping, UMFPACK and SuperLU. It is associated
with applying the record in this model, but the underlying matrix, forcing,
constraint or material cause has not yet been identified. Zero-motion success
is not proof of correctness or an earthquake validation. See Diagnostic_Evidence
for complete logs and the reproducible diagnostic script.

Do not approve the production readiness manifest on this basis. The user's
actual reinforcement and FSAM assignment still need evidence. None of these
tests establishes an optimum outrigger position or completes a full earthquake.

Newmark effective tangent formulation:
https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/integrator/Newmark.html
Wall formulation and benchmark scope:
https://kkolozvari.github.io/E-SFI-MVLEM-3D/
