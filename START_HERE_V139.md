# V139 - new-source load preview and modal batch

Run RUN_ETABS_TO_OPENSEES.py from this complete extracted folder. Re-run ETABS export for the newly selected EDB to refresh its saved load data and runtime. Rebuilding an old saved export cannot recover assignments that were never extracted. No live D: files were modified.

Changes:
- Area uniform loads are read from AreaObj.GetLoadUniform (object assignments), rather than AreaElm (analysis elements). Nonzero return codes and malformed array responses are reported as failed queries, never interpreted as verified zero loads. Exact object mapping, allowed patterns, direction/sign checks and single-count assembly remain in place.
- Floor plan with no extracted loads defaults to diaphragm membership and explains the missing data. This display is not proof of complete load transfer.
- Shared ID/camera controls wait for page load, avoiding a concurrent relayout during Plotly initialization. Two-dimensional plans use 2-D zoom/reset and do not receive a 3-D camera.
- Modal stiffness dropdown includes Both. Each state runs in a separate process with its own Modal_ULS or Modal_SLS folder, result state and log. One process returning nonzero does not silently turn the batch into a success.

New source diagnosis:
D:/Thesis Opensees/Etabs Nodes Export 1 contains 805 source BEAM objects. The assembled frame segments have no exact coincident beam geometry (coordinate precision 1e-6 m). No near-parallel same-span beams within 1 m were found in the source topology screen. The oblique whole-building projection alone does not establish duplicate members; opposing frame lines can appear close in projection. No structural members were removed. Inspect a single storey in Top view and select exact ETABS IDs to distinguish objects.
All 725 saved AreaElm queries returned status 1, with zero extracted/applied area assignments. The empty area CSV is therefore an extraction failure, not confirmation that this model has no floor loads. Gravity equilibrium only verifies the loads actually assembled; it cannot establish completeness of omitted assignments. The new source gravity total 236047.788933 kN differs from the old source 286447.788933 kN and must be reconciled by load component after re-export.

The included New_Export_Viewer_Diagnostic floor plan displays only saved diaphragm data with an explicit warning. It does not invent missing floor loads.

Validation: all Python sources parsed; mocked AreaObj success and error responses checked; modal Both orchestration tested with mocked solver (separate ULS/SLS runner, folder and result metadata). No new real ETABS API export or numerical modal analysis was executed in this release. Existing exploratory nonlinear limitations remain: staged frame-nonlinear building route has elastic walls and is not calibrated building acceptance; full FSAM-wall route remains unresolved.

CSI reference: https://docs.csiamerica.com/help-files/etabs-api-2016/html/05fbb8d2-47d5-a3fa-aa92-5a58e3db964b.htm (AreaObj.GetLoadUniform object assignments, return code zero on success). Element API: https://docs.csiamerica.com/help-files/etabs-api-2016/html/a4fc6808-535b-adaf-27d9-49a9c29f289e.htm .
