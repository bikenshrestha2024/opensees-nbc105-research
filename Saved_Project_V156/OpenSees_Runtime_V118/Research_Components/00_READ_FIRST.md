# OR158: component results GUI

1. Extract the complete OR158 folder.
2. Run `00_OPEN_RESULTS_GUI.py` in your OpenSees Python environment to view completed results without rerunning analyses.
3. Choose Load/Browse and select your existing OR157/results/Components_20261028_061714 folder (the folder containing Run_Summary.json). The included completed results can also be viewed immediately.
4. Run `01_RUN_COMPONENT_BASELINES.py` for a new baseline run; it opens the GUI automatically when finished. `--no-gui` keeps command-line operation.

The viewer has separate Concrete01, Concrete02, ConcreteCM, Steel02, SteelMPF, FVD, BRB and wall tabs. Each displays response graphs, parameter/source reports and logs, with Excel/CSV/PNG opening and recorded response-path animation/GIF export. Animation illustrates the component protocol, not a building earthquake response.

Requires OpenSeesPy, numpy, scipy, matplotlib, openpyxl and Tk; GIF export requires Pillow. Use the same environment as the main program.

Read 02_MODELLING_BASIS.md for formulation selection, citations and assumptions. Cards are research baselines, not independently experimentally validated project materials. M30 is nominal cube grade; the 24 MPa cylinder baseline is an assumption. Fe500 yield is nominal; cyclic coefficients are not established for project reinforcement. The wall card runs E_SFI_MVLEM_3D as explicitly recorded in its report.

This is a research add-on, not a replacement full ETABS GUI. Building assignments and readiness approvals are unchanged. study/Case_Matrix.csv is a plan, not completed building analyses. 03_RANK_COMPLETED_CASES.py excludes incomplete cases.
