# Nonlinear Time History

Implementation modules: runner_and_gui.

Load through the matching root compatibility file in MODULE_INDEX_V134.json. See START_HERE.md and VALIDATION_V134.md for data flow and verification scope.

The nonlinear runner keeps UmfPack as its default and allows SparseGeneral or BandGeneral for model-specific timing comparisons. Mumps is not present in the OpenSeesPy 3.8.0 environment checked for this release; no solver is treated as universally fastest. The exploratory building GUI exposes separate gravity and transient choices; SparseGeneral uses pivoting. A full-wall gravity diagnostic with this build terminated the native process when SparseGeneral was selected after the first 0.05 load increment, so treat that path as diagnostic-only and retain UmfPack for normal runs. A failed adaptive gravity solve writes a bounded node/element-response snapshot to `Gravity_Failure_Diagnostics_<limit_state>.json`; this is solver evidence, not an automatic stiffness or connectivity diagnosis. The main program's material sensitivity planner exports a one-factor-at-a-time grade/bar case matrix only; separate model variants, readiness review, and equivalent NLTHA runs are still required.
