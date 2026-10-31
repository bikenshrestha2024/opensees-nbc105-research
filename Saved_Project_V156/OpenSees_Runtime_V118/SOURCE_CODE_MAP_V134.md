# Source code map - V134

Root historical filenames are compatibility loaders. The complete source is under components/; use the main-window source-folder button or open these files directly for inspection. Launch RUN_ETABS_TO_OPENSEES.py from the package root so resource and helper imports resolve correctly.

| Feature | Implementation |
|---|---|
| Main UI | components/ui/application.py |
| RC config and section definitions | components/sections/definitions.py |
| Material/property audit and citations | components/sections/mapping_audit.py |
| Complete model/load/mass/diaphragm builder | components/model/assembly.py |
| Gravity storey components | components/gravity/storey_loads.py |
| Gravity solver/GUI | components/gravity/solver_stack.py; components/gravity/gui_and_reports.py |
| ESM formulas | components/equivalent_static/code_basis.py |
| ESM calculation/GUI/generated runners | components/equivalent_static/calculation_and_gui.py |
| Modal analysis and classification candidates | components/modal/analysis.py |
| Modal GUI/export | components/modal/gui_and_reports.py |
| Site spectrum and record scaling diagnostic | components/response_spectrum/site_spectrum_and_scaling.py |
| Model MRSM/CQC and force scaling | components/response_spectrum/model_analysis.py |
| Linear histories | components/linear_time_history/runner_and_gui.py |
| Nonlinear histories | components/nonlinear_time_history/runner_and_gui.py |
| Shared motion input | components/inputs/records.py |
| Workbook sources and current-field autofill | components/inputs/project_workbooks.py; components/inputs/analysis_autofill.py |
| Drift/deformation/irregularity outputs | components/validation/response_checks.py |
| Stage timing | components/shared/timing.py |

MODULE_INDEX_V134.json maps all 51 loaders. CODE_REVIEW_INVENTORY_V134.csv lists function names, source lines and AST hashes. Edit implementations rather than replacing compatibility entries with duplicate application bodies.

| New V134 feature | Implementation |
|---|---|
| Case workload, timing, progressive recording | components/shared/transient_runtime.py |
| Complete history inspector and playback | components/ui/history_inspection.py |
| Classified gravity charts and source filters | components/gravity/load_review.py |

| V134 addition | Implementation |
|---|---|
| Shared cameras / DOF formatting | components/ui/view_controls.py |
| Deformation/node result viewer | components/ui/response_viewer.py |
| ESM case rows | components/ui/case_selection.py |
| Saved MRSM charts / Excel | components/response_spectrum/reports.py |
| Calculated irregularity review | components/validation/irregularity_review.py |
| Completed history result access | components/ui/history_results.py |
| Nonlinear readiness draft editor | components/model/readiness_gui.py |
