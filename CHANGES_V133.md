# V133 implementation changes

This release continues feature work after V132; it retains V132 and previous ZIPs.

- Fixed nonlinear GUI pair selection: selected_pair_ids and preliminary_selection now reach run configuration, as already intended in the linear GUI.
- Retained nonlinear analysis objects between intervals. Recovery switches the Newton-family algorithm/test without repeatedly rebuilding the numberer/system/integrator. Cyclic yielding equivalence and adaptive-substep recording are covered by tests.
- Recorded every accepted nonlinear substep rather than only the end of a subdivided requested interval.
- Added measured workload/case profiles, per-stage timing, live rate/ETA and convergence diagnostics. Report/flush occurs on percentage milestones or at least every ten wall seconds while steps complete.
- Streamed accepted history samples to disk. New sidecar metadata includes source payload hash, stiffness case, displacement reference and running/completed/incomplete state.
- Bound the final linear interval by remaining record duration, and removed its redundant convergence-test command. No factorOnce assumption or relaxed integration bound was introduced.
- Propagated SLS/ULS context into the nonlinear builder before model construction.
- Added explicit modal damping option for nonlinear iterative analysis; retained the committed-Rayleigh default for backward compatibility and documented limitations of both.
- Replaced the old history inspector's 2000-row-only table with full-row pagination/filter/export, grouped plotting, extrema-preserving display decimation, input response spectra, logs and measured performance.
- Added coherent history playback/scrubbing, scale/speed controls, storey/type filters, source-ID highlight and zoom/fit. It remains a rigid-floor lateral reconstruction. Floor-center interpolation was corrected.
- Added gravity dead/live/component stacked charts, exact source filters and load-path/diaphragm evidence display.
- Added full selected citation/parameter text below library rows.
- Added fingerprint-checked centered static results to the irregularity review and positive/evidence checks for manually reviewed stiffness/capacity rows. Other-direction coverage remains explicit.
- Replaced duplicate V108 solver implementation with a compatibility forwarding surface to the identical V110 solver functions.
- Corrected stale MRSM button wording and added the request coverage documentation menu.

Numerical site spectra, ESM force equations, MRSM CQC/scaling, source gravity classification and section parameters were not changed. Header release identifiers are not physical changes. Historical aliases and V132 response filenames are retained so previously generated scripts and readers remain compatible.
