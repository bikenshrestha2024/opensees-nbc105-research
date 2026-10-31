# V140 - shell uniform load sets, logs, evidence and trial reporting

Extract this complete folder and run RUN_ETABS_TO_OPENSEES.py. Re-run the ETABS export on the selected EDB, then rebuild and rerun the analyses. No live D: export, EDB, or original trial files were modified in preparing this release.

## Missing slab loads: actual cause
The screenshot uses a Shell Uniform Load Set named Load Set, with Floor Finish 1.5, Live 4 and Partition 1.5 kN/m2. These are set definitions, distinct from direct uniform assignments. V139 queried direct AreaObj loads but did not expand the load-set assignment/definition tables. The old AreaElm error was also real, but changing that query alone was insufficient. Outrigger elevation does not itself explain missing loads.

V140 reads Area Load Assignments - Uniform Load Sets and Shell Uniform Load Sets, joins exact area UniqueName to the assigned set and expands each pattern separately in gravity direction. It retains set/component provenance, preserves direct loads as separate additive assignments, and does not mutate or explode assignments in ETABS. The existing area-to-shell equivalent load assembly and gravity/mass factors consume those expanded assignments once. Definitions alone are not assumed assigned to every slab. Nonzero/malformed direct/table reads remain UNVERIFIED and now block new complete assembly rather than silently treating missing data as zero. Table numeric values use the exporter's kN-m unit setting.

Live ETABS attachment could not be established in this agent session (WinError -2147221021). The table parser was tested with the screenshot's values and documented table schema, not with a successful live re-export. Confirm a nonzero expanded component count and assigned area count in the export log and inspect the resulting CSV/HTML. Reconcile per-storey components with ETABS before trusting analysis results. Old gravity 236047.788933 kN and old mass/modal/MRSM/time histories may omit the set loads and must be recomputed after a successful import.

## Nonlinear reporting error and recovered run
A loop over final frame ends reused the name end for I/J, replacing the floating duration. Summary generation then compared a string with the record duration. The end-label variable is now independent. An actual fresh two-step 0.01-second OpenSees trial on the selected saved geometry passed construction/gravity/transient/end-action export and both case/global summaries. This is a regression check, not a full-record study.

Your existing one-second XY history was recovered without rerunning integration: 201 accepted rows, roof peaks X=4.12636847 mm and Y=2.22520634 mm. Recovered_1s_Trial_V140 contains the history, summary and plot. Recovery does not invent missing iteration diagnostics or claim that the failed original process exited normally. A Recover report from saved trial button is included. The original run remains unchanged.

Both trials remain explicitly exploratory: assumed illustrative frame materials, elastic walls, no calibrated full-building FSAM behavior, no design acceptance. Recovered data also retain the previous incomplete load inventory.

## Interface / readiness / irregularity
Selectable modal logs now have vertical and horizontal scrollbars. MRSM has Copy entire log with both scrollbars. Irregularity logs have the same controls and the header identifies pending checks and the action needed.

Readiness now fills empty evidence fields with existing source geometry, configuration, mass/load audit, restraint, gravity and SLS/ULS modal file references where available. Existing entries are preserved. File presence does not prove reconciliation, calibration or review; no approval checkbox is automatically selected. Missing wall FSAM definitions and actual project reinforcement calibration remain missing.

Soft-storey and torsion require Calculate selected state(s), which runs centered lateral reference responses; modal eigenanalysis alone cannot calculate those checks. Weak-storey requires reviewed lateral-strength capacities, not elastic stiffness. Load-path discontinuities require continuity/detail evidence. The program retains NOT EVALUATED rather than inventing strengths. Re-entrant geometry screening remains available, with plan inspection. Recalculate response checks after corrected load/mass extraction.

## Checks
All Python sources parsed. Tests cover load-set expansion (1.5/4/1.5), exact assignment join, independent direct/set contributions, gravity direction, failed database return; native Tk log scrollbars and MRSM Copy button; readiness evidence fill without approval; saved-history recovery; actual short OpenSees trial through summary export. No full earthquake run or successful live ETABS export is claimed.

## Sources
CSI Shell Uniform Load Sets (defines constituent dead/live patterns and gravity direction): https://docs.csiamerica.com/help-files/etabs/Menus/Define/Shell_Uniform_Load_Sets.htm
CSI assignment procedure (set assignment to selected shell objects): https://docs.csiamerica.com/help-files/etabs/Menus/Assign/Shell_Loads/Shell_Load_Uniform_Load_Sets.htm
Read-only database-table schema corroboration, upstream implementation reviewed; no ETABS mutation procedure adopted: https://github.com/ebrahimraeyat/etabs_api/blob/master/area.py (get_expanded_shell_uniform_load_sets), https://github.com/ebrahimraeyat/etabs_api/blob/master/database.py (read_table).
Existing NBC references and analysis limitations are retained in the earlier method documentation. This release adds extraction/UI/reporting fixes, not new component capacity or performance acceptance criteria.
