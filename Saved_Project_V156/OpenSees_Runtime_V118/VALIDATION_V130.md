Historical V130 record. V132 documentation supersedes the current capability and validation status.

# V130 validation record

## Executed checks

28 automated regression checks passed with D:/condaenvs/etabs_env312/python.exe. They include input handling, readiness, record selection, source regressions, floor shell/perimeter-beam equilibrium, slab membrane/bending scaling, rigid-diaphragm kinematics, CSV-safe timing metadata and failed-stage timing.

All 38 compatibility modules imported. Main application, modal, linear time-history and nonlinear time-history GUI constructors completed. Child analysis windows held no Tk modal grab. This constructor check does not simulate every minimize/restore interaction or every user action.

The 421-function inventory records source locations and AST hashes. It is not a claim that every branch was numerically validated.

## Supplied-model workspace rebuild

The supplied export data were copied to work/V130_Project_Check; the live D: export was not overwritten.

- 1,612 frame segments and 3,300 shell elements assembled without reported assembly errors.
- 25 diaphragms: 1,275 floor nodes covered, zero omitted floor nodes.
- Unfactored area-load totals: floor finish 18,000 kN; live 48,000 kN; partition 18,000 kN. No roof-live source assignments.
- Applied gravity and total support reaction: 286,447.788933 kN each; equilibrium error 4.8566e-12 percent.
- ULS maximum downward displacement: -0.009579955894637476 m.
- SLS maximum downward displacement: -0.009527805465681124 m.
- Maximum gravity diaphragm in-plane compatibility residual: 6.625199008692091e-32 (mixed translation/rotation diagnostic).
- 40-mode ULS audit: UX=98.12586455266445%, UY=97.92530534468594%; modal stage 34.972 s.
- 40-mode SLS audit: UX=98.1296834228814%, UY=97.91169863746394%; modal stage 33.322 s.

Worked example files accompany this release. Their processing durations are measured stages, not runtime promises. They were produced before the final cache-fingerprint metadata refinement; rerun modal audits from the delivered GUI before using results as automatic time-history inputs. Cached results lacking current implementation fingerprints are intentionally rejected.

No full-building V130 static-case suite, MRSM or time-history ensemble was rerun. Earlier release results are historical evidence only. See CAPABILITIES_AND_LIMITS_V130.md for remaining engineering checks.
