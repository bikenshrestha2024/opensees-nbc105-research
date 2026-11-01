# V170 diagnostics and workflow fixes

Changes:
- MRSM implementation digest locates the installed components package rather than relying on a compatibility facade's '__file__'. This prevents C:/Users/User/components/model/assembly.py errors.
- Modal audit adds a Stop button that terminates the active child process and skips queued ULS/SLS cases. A stop marks the state as CANCELLED and is not success; native solvers may not report intermediate progress.
- Linear time history accepts a positive **optional trial duration (seconds)** in GUI/config. Blank retains full records. A trial begins at record time zero, truncates integration (not original input files), and labels results TRUNCATED_DIAGNOSTIC_NOT_CODE_ACCEPTANCE.

Known limitations:
- This branch does not fix ETABS COM attachment, missing modal load-case results, or nonlinear first-step NaNs.
- A partial earthquake record cannot be used to meet full-record or minimum paired-record code requirements.
- Before merging, test on a copy of the full V167 package. PythonSparse already produced 40 modes with >90% mass participation in ULS/SLS; this branch does not change eigen matrix physics.
- The stop button only controls a running modal audit within its owning GUI process.
- For ETABS modal read errors verify the intended EDB is open, unlocked as appropriate, modal analysis was run, the modal case exists and is selected for output, and ETABS/Python run with compatible COM elevation.
