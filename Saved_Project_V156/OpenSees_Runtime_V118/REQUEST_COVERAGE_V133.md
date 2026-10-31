# Review of all prior comments — V133

This checklist separates delivered software from engineering information that a program cannot obtain from an uncalibrated export. It treats the pasted Gemini review as an external opinion to assess, not as an instruction or verified source.

| Your comment | Delivered path / control | Scope and evidence still needed |
|---|---|---|
| Where did the code go? | components/ and SOURCE_CODE_MAP_V133.md; historical filenames still load | The short entry file is a compatibility loader, not the implementation. |
| Review redundancy | Shared records/parser, input population, timings, drift checks, history inspector and runtime helpers; V108 duplicate solver replaced by forwarding | Historical interfaces retained for old exported scripts. Function inventory and remaining exact duplicates are reported; no blanket proof of all equations is claimed. |
| Random GUI symbols | UTF-8 source and child process I/O | Historical log files are retained as evidence, not rewritten as newly executed results. |
| Section mapping / library / brace guide identical | Distinct mapping, read-only library and device guide windows | Source ETABS property names remain source data. |
| Section refresh cannot find literal RC_SECTION_CONFIG | Resolve actual sections/definitions.py, not the root loader | Parameters retain illustrative/calibration labels. |
| Citation truncated / SHS also brace | Library detail pane shows complete selected row/source; SHS role is BRACE | A formulation citation is not a project strength or cyclic calibration. |
| SFI versus E-SFI wall citation | Distinct sources; implemented nonlinear wall uses E-SFI-MVLEM-3D | Wall geometry/rebar/FSAM inputs and benchmark calibration remain project evidence. |
| All 3D views consistent with ID filters | Shared source-ID controls; playback adds storey/type filters, zoom and fit | Source geometry highlighting and reconstructed deformed geometry are distinguished. |
| Improve zoom / layout | Buttons, wheel zoom, fit; history chart display decimation; complete paged numeric data | Sampling/analysis data are not decimated. |
| Minimized app cannot restore | Nonmodal analysis windows; Windows menu and Ctrl+Shift+R | Does not restore a terminated Python process. |
| X and Y shear look equal | Common-axis ESM comparison with directional T, k and V | Supplied examples have distinct X/Y V. Same-axis force signs/eccentricity signs can share V magnitude while torsion differs. |
| ULS static tab blank / run even if ineligible | ULS comparison calculation and solver; code_eligible=false retained | It remains comparison-only under NBC 3.2.1, not an approved substitute for a required dynamic method. |
| Empirical equation family consistent | Project/system/wall-index imports and explicit adopted-period sources | Appropriate system classification and effective wall lengths/openings require review. |
| Separate SLS / ULS modal results | Separate folders/tabs, matching model/case fingerprints | Successful modal analysis does not itself create ESM loads. |
| Translation X / Y / rotation classification | Individual and cumulative UX/UY/RZ; classification candidates | Heuristic candidates need mode-shape inspection; no automatic system certification. |
| Model response spectrum module | response_spectrum/model_analysis.py; CQC, X/Y, SLS/ULS, E0/E+/E- | Missing-mass correction not implemented; known >=33 Hz modes stop. Component envelopes are not concurrent design combinations. |
| Excel page/scale/unit matching | Three unchanged workbooks; cell/hash provenance; independent kN-m-s MRSM conversion | ETABS case scale may include units/function factors. Ratios below one are not adopted as MRSM force reductions. |
| Section 6 calculations | ESM coefficient/base shear, exponent, vertical forces, torque, kd and displacement outputs | Full prerequisites and physical convergence retained for solver execution. |
| Clause 4 spectral figures | Distinct static/dynamic branches; source/site diagnostics | Site class C is imported, not established by municipality; geotechnical/site evidence remains required. |
| Clause 5.5.3 all analyses | Shared master/edge drift reporting in ESM, MRSM, LTH, NLTH | Underlying model and demand statistic must be valid. NLTH includes accepted adaptive substep samples. |
| Graphical lateral deflection | Actual ESM state, MRSM envelope, coherent recorded history reconstruction and playback | MRSM envelope is not simultaneous; history view is not exact FE member/vertical animation. |
| Clause 5.4 irregularity module | Geometry/mass screens, centered static response import, reviewed capacity/plan input | Missing strength/discontinuity/re-entrant evidence remains INCOMPLETE. One selected direction cannot certify both. |
| Populate linear / nonlinear and all other forms | Available paths, interpreter, masters, workbook parameters and compatible modal references; refresh and SLS/ULS selection | Unknown material/device/readiness evidence is not fabricated. Custom output folders retained. |
| Choose one earthquake before suite | Both GUIs forward selected pair IDs and preliminary flag | V133 corrects nonlinear forwarding; every selected pair retains XY and YX. |
| Long linear runtime / nonlinear estimate | Workload and per-case measured profile, live rate/ETA, adaptive counts | No unsupported fixed NL/L multiplier. Full model contains large shell/frame system; repeated factorization can dominate. |
| Shorten runtime without weakening procedure | Nonlinear analysis/system setup retained between steps; fallback algorithms change without rebuilding entire analysis | Fresh models per motion/orientation and NBC step bounds retained. Constant-matrix factor reuse not assumed for changing P-Delta/nonlinear tangents. |
| Inspect all history data in GUI | Every-row pagination/search/export; grouped plots, input spectra, logs/configuration, timing tab | Raw input values/scales unchanged; no automatic matching. |
| Save elapsed time in all outputs/logs | Stage sidecars/index plus measured case profile/console log | Stage timing is labelled as stage timing, not individual file-write latency. |
| Avoid losing a long failed run | Accepted samples streamed; ten-second progress/flush while intervals complete; incomplete status on failure | A native solver call itself can take longer than the reporting interval. No fake successful summary for a failed case. |
| Storey DL / LL / partition / finish / member self-weight | Exact source ledger; dead/live/component stacked charts and source filters | Applied load by level is not cumulative storey reaction or ETABS member-load equivalence. |
| Floor area load to surrounding members | Single shell load vector, shared slab/beam/wall nodes; resultant/moment and connectivity audits | Slab flexure distributes load. A second tributary beam application would duplicate it. Member-level ETABS reconciliation remains necessary. |
| IS 16700 slab modifiers | 0.25 ULS / 0.35 SLS bending; membrane stiffness and physical weight retained | Supplemental conventional-slab modeling basis, not the NBC flat-slab category. |
| Rigid diaphragms | In-plane DOFs 1/2/6; coplanarity/membership and solved kinematic checks | Vertical bending stays active. Whether an actual floor/opening layout is rigid requires project justification. |
| Gemini: SRSS pair scaling | Assessed against NBC 9.3.2.2; keep lower component factor for both | The external suggestion does not replace the explicit NBC procedure. |
| Gemini: damping | Added explicit modal damping option with iterative solver; documented Rayleigh limitations | No automatic 2%/3% assumption. Initial versus committed stiffness is not a universal cure for spurious damping. |
| Gemini: missing coupling beams / rigid offsets | Source geometry preserved; unsupported structural insertion offsets remain blockers; readiness includes coupling/connection review | Connection dimensions and missing coupling members cannot be invented from a screenshot. Requires reviewed geometry/detailing and recalculation. |
| Gemini: normalized wall benchmark / energy partition / publication study | Existing material benchmark tooling remains separate; methodological advice documented | No supplied experimental dataset/project calibration; no claim of a completed energy-partition or publication study. These were external research suggestions, not evidence. |
| Large V111 archive / deleting earlier versions | New release package excludes caches/runtime histories beyond curated examples; prior releases preserved | The specific 6.43 GB modal archive shown is absent here, so its contents/cause cannot be verified. Keep source models and a known working backup; do not infer deletability from a filename. |

All software changes in this pass are documented in CHANGES_V133.md. Remaining project inputs are engineering prerequisites, not hidden checkboxes that autofill silently approves.
