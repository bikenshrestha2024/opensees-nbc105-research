# Source code map - V132

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

MODULE_INDEX_V132.json maps all 41 loaders. CODE_REVIEW_INVENTORY_V132.csv lists function names, source lines and AST hashes. Edit implementations rather than replacing compatibility entries with duplicate application bodies.
