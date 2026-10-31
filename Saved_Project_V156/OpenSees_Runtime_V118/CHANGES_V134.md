# V134 changes

- Added unscaled node six-DOF readouts and deformed-node markers; new gravity and MRSM outputs include rotations, and MRSM includes masters. Missing legacy/history DOFs remain N/A.
- Standardized 3D cameras and view presets; added response-envelope illustration controls and panel fitting.
- Replaced the crowded ESM tab strip with SLS/ULS rows, force/eccentricity labels and case explanation.
- Added modal-table horizontal scrolling and legacy classification candidates without requiring a rerun merely for labels.
- Embedded Ch(T) and SLS/ULS design spectra in Tk; soil dropdowns and explicit usage text.
- Explicit MRSM eccentric-case log labels, SLS/ULS/Both operation, saved-result graphics, and automatic Excel/PNG/PDF reports.
- Added native centered CM reference solves for stiffness/torsion screens, polygon-based re-entrant checks and plan inspection. Directional strength inputs remain evidence-dependent; missing levels are not skipped.
- Added completed-history result access and automatic graph display after success. Fixed timing sidecar JSON being mistaken for summaries. Recovered charts from the user's completed run without rerunning it.
- Centralized acceleration conversion and separated motion factor, conversion factor and total Path factor in the unit audit. Numerical g-to-m/s2 conversion retained.
- Replaced ambiguous readiness path errors with template diagnostics, manifest-relative resolution and an evidence-aware model-bound draft editor. No physical calibration/readiness gate was removed.

The source model, workbooks and live D: result folders were read only. Historical aliases and V132 numerical-result filenames remain supported.
