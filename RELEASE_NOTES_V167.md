# V167 release notes

V167 is a repository/handoff refresh, not a new structural model calibration.

## Updated

- Replaced the obsolete V134 root README with a current V167 entry point.
- Added a V167 start guide naming the current scripts, preserved baseline export, validation status, and required run order.
- Updated the literature basis with separate evidence and reproducibility gates for RC beams, RC columns, RC walls, conventional steel outriggers, BRBs, and FVDs.
- Corrected the validation inventory: the recorded configured gravity preload converged, while the Kobe nonlinear transient failed at its first step with return code `-3`.
- Added repository ignores for Python bytecode/cache directories, temporary files, and PDFs. PDFs are omitted from this GitHub upload to avoid redistributing papers/reports without confirmed rights; bibliographic metadata and source links remain in the project.

## Verification state

- `python -m compileall -q components`: passed.
- `python tests\verify_v133.py`: passed, 10 tests; native OpenSeesPy test skipped because the package is unavailable.
- `python tests\verify_v150.py`: passed, 6 tests.
- No OpenSeesPy building transient or experimental specimen reproduction was run for V167.

## Limitations

The first-step earthquake transient failure remains unresolved. Component-specific literature benchmarks have not yet been reproduced. Project material calibration, complete earthquake records, device demand/energy output, and a validated best outrigger combination remain outstanding.
