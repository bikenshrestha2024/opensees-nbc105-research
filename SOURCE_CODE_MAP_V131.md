# Where the code is

Open these full source files in Spyder:

| Feature | Implementation |
|---|---|
| Main GUI and RC builder | components/ui/application.py |
| RC and steel section definitions/configuration | components/sections/definitions.py |
| Material library, parameter sources and classifications | components/sections/mapping_audit.py |
| Complete model, loads, self-weight and diaphragms | components/model/assembly.py |
| Storey dead/live gravity ledger | components/gravity/storey_loads.py |
| Gravity GUI and Excel report | components/gravity/gui_and_reports.py |
| Equivalent static | components/equivalent_static/calculation_and_gui.py |
| Modal calculations | components/modal/analysis.py |
| Modal GUI | components/modal/gui_and_reports.py |
| Spectrum diagnostics | components/response_spectrum/site_spectrum_and_scaling.py |
| Linear time history | components/linear_time_history/runner_and_gui.py |
| Nonlinear time history | components/nonlinear_time_history/runner_and_gui.py |

Run RUN_ETABS_TO_OPENSEES.py from the package root. Open implementation files for reading/editing; keep root loaders and components together when moving the application. The old named files execute the matching component source so existing scripts retain compatible imports. A component run directly may not find root helper modules/resources; launch from the root entry.

MODULE_INDEX_V130.json plus OpenSees_Storey_Gravity_V131.py identify the complete loader map. Compatibility filenames are not release numbers of the implementation. CODE_REVIEW_INVENTORY_V131.csv lists function locations and source hashes.
