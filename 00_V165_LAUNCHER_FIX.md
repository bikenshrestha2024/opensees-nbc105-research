# V165 nonlinear research launcher fix

The exploratory GUI now locates `OpenSees_Building_Exploratory_V138.py` in the active Python package rather than deriving its location from `__file__`. The GUI may be imported directly or executed through its compatibility facade; in the latter case `__file__` identifies the facade, so the previous parent-directory calculation pointed outside the package. The process log now includes the resolved runner path and the child is started in the package directory.

Launch `01_START_ETABS_TO_OPENSEES.py` from the extracted V165 folder, open the building exploratory research history and use a short trial first. If using an existing export runtime instead, refresh it from this package; do not mix GUI modules and runners from different releases.

This repairs the missing-file startup error only. The earlier first-step singular solve under earthquake motion remains unresolved. The research model uses assumed material and reinforcement values and is not calibrated or design-approved. The separate reviewed nonlinear analysis retains its readiness and evidence checks; missing project material/FSAM inputs are not marked approved.
