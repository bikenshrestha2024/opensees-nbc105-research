# V155 - integrated experimental Steel02 calibration
Run 01_START_ETABS_TO_OPENSEES.py. Under ETABS / OpenSees section and material review, select Experimental Steel02 calibration - run / graphs / Excel. The visual validation workbench has the same shortcut. 13_STEEL02_CALIBRATION.py opens it directly.

Show bundled fit displays the supplied MC154 results immediately. Run experimental calibration fits the ordered SimCenter qfem-0019 coupon in a separate process and creates a timestamped output folder. Tabs display measured/predicted curves, ordered stress history, residuals, parameters and fit metrics. Outputs include the complete source provenance, CSV, JSON, PNG, formula-based unit conversion Excel, and persistent run log. Animate fitted curve opens recorded material-path playback with GIF export.

256 training samples and 86 withheld temporal samples belong to the SAME coupon. This is not independent specimen validation, Fe415/Fe500/Fe550 grade equivalence, or approval to transfer parameters to project reinforcement. No project material assignments or readiness approvals are changed automatically. Stress MPa converts to kN/m2 by multiplication by 1000, once.

Verification: native GUI subprocess reproduced full-history RMSE 27.884886189406316 MPa; exported Excel/CSV/JSON/PNG/log; parent OpenSees node domain remained intact. Main startup and package integrity checks are recorded separately. Existing numerical validation limitations remain in the supplied documentation.
