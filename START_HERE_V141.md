# V141 - slab load path, source layers, material evidence and Excel formulas

Extract the complete release and launch RUN_ETABS_TO_OPENSEES.py. Rebuild the assembled model, then rerun gravity and seismic analyses. V141 changes the connected slab/beam mesh; old member demands, periods and responses must not be reused as if calculated on the refined model. No live D: files were changed by this work.

## Double lines
The actual export contains 1,050 source slab-outline edges exactly coincident with beam edges. The shared 3D viewer now has a Slab outline overlay (display only) checkbox, initially off. Source floors and solver shell elements remain intact; only the outline drawing layer is hidden. It applies to both structural-by-storey and connectivity views and persists through ordinary filtering. Viewer_Preview_V141 contains copies of your saved views with this display fix. Enable slab outlines to inspect boundaries. Actual independent structural members are not deleted.

## Vertical load path and model correction
rigidDiaphragm(3) constrains UX/UY/RZ in a horizontal plane; it does not impose UZ, RX or RY constraints or transfer vertical pressure. Floor pressures use q*A per ShellMITC4 mesh cell, represented by four equivalent vertical nodal loads q*A/4 for a uniform parallelogram cell. Connected shell bending/shear and beam/wall/column stiffness distribute the response. These are FE nodal loads, not a guessed tributary beam UDL. A second q*tributary-width load on the beams is NOT added, avoiding double counting.

A panel with only column/wall-supported corner nodes cannot resolve beam-span bending under uniform floor pressure. Global equilibrium does not detect this limitation. V141 seeds a conforming refined slab grid before area meshing; shared nodes also split the connected beams and align wall/slab boundaries. Default floor_subdivisions=4 per source-panel direction is a starting numerical discretization, not an NBC-prescribed or project-converged mesh. Main GUI: Slab load path / mesh + Excel formulas lets you select 2/4/8/16, then rebuild. Compare moments, deflections and reactions for convergence. More cells increase runtime, especially nonlinear histories.

Mesh demonstration: a 6 m square slab on four edge beams, rigid in-plane constraint and corner vertical supports, q=4 kN/m2. All meshes give 144 kN support reaction. One cell gives zero beam bending and zero slab deflection; 2/4/8/16 subdivisions give maximum beam end bending 7.869/19.588/22.611/23.122 kNm. The 8-to-16 change is about 2.3% in this benchmark. This confirms a discretization issue and illustrates convergence; it is not independent experimental validation or project mesh acceptance.

## Where to see the loads and beam response
Gravity GUI: Slab load path + formulas; main GUI: Slab load path / mesh + Excel formulas. Slab_Load_Path_Formulas_V141.xlsx provides Surface load formulas, Loaded node path and Member weight formulas. Node-path rows identify the loaded node and connected beam/wall solver tags. Interior nodes transfer through shell stiffness.

Complete-model gravity preload now exports Gravity_Beam_End_Actions_ULS_V141.csv (or SLS), with source object, solver tag, end/node and concurrent local N/Vy/Vz/T/My/Mz. These are actions from the FULL applied preload, not unique attribution to one slab panel or design combination. The existing gravity action tabs and Export all action pages remain available. When those CSVs exist, formula workbooks include corresponding raw Beam end actions sheets. The new CSV exporter was regression-tested with a controlled response vector; the full-building gravity solve preceded adding this reporting-only function, so no new real-building beam CSV is claimed in the included example.

## Formulas instead of copied derived totals
Both the source-ledger workbook and the Gravity Results workbook now compute applied_kN=unfactored_kN*gravity_factor. Floor source totals use SUMIFS from the cell calculations, and storey totals use SUMIFS from source detail. Surface sheets show q*A, preload factor, mass factor/g, and q*A/4 per node. Slab self-weight pressure is physical thickness*source unit weight*self-weight multiplier. Member weights show A*L*unit weight. Material conversions show MPa/ksi/kN-m and mm-m formulas. Recorded solver displacements, reactions and member forces remain raw numerical results: Excel is not a finite-element solver. Existing files do not change until regenerated. Excel is instructed to recalculate on opening; formula structure and independent arithmetic were verified, not cached recalculation by Excel.

## Material library
143 parameter/evidence rows now cover RC templates, Steel02, SteelMPF, ConcreteCM, FSAM, E-SFI wall benchmark inputs, elastic shell/beam/torsion properties and exploratory Steel01 SHS, FVD and BRB requirements. Current source parameters and Validation and limits have separate tabs, with source-opening buttons. Source formulation, published specimen input, numerical capability checks and actual project calibration are distinguished. Missing device data or reinforcement calibration remain missing. Published PEER wall cards do not automatically calibrate this building. The full FSAM building route remains unresolved; the exploratory route still has elastic walls.

## Actual checks on your source export
New source now contains 1,050 applied area-load components. Floor Finish 18,000 + Partition 18,000 + Live preload 14,400 = 50,400 kN, independently reconciled from q*A and assembled provenance. The isolated refined rebuild contains 11,072 structural/mesh nodes, 3,862 frame segments, 7,000 FLOOR cells and 3,400 wall cells. Gravity applied/reactions both 286447.788933 kN; equilibrium error 5.79135e-12%; max downward Uz -0.0170950462 m. This gravity run took about 105 s including construction. Total-load equilibrium is not section strength, slab design, convergence or NBC certification.

Python syntax, JavaScript syntax, native library/mesh GUI, formula row references, independent floor-load arithmetic, node/beam connectivity, mesh benchmark and full refined gravity were checked. No full refined nonlinear earthquake record or project mesh-convergence study was run.

## Primary sources
Rigid diaphragm implementation and constrained DOFs: https://opensees.berkeley.edu/OpenSees/api/doxygen2/html/RigidDiaphragm_8cpp-source.html
ShellMITC4 formulation and node convention: https://openseespydoc.readthedocs.io/en/latest/src/ShellMITC4.html ; source https://opensees.berkeley.edu/OpenSees/api/doxygen2/html/ShellMITC4_8cpp-source.html
Elastic shell section: https://opensees.berkeley.edu/wiki/index.php/Elastic_Membrane_Plate_Section
ConcreteCM: https://openseespydoc.readthedocs.io/en/latest/src/ConcreteCM.html
SteelMPF: https://openseespydoc.readthedocs.io/en/stable/src/SteelMPF.html
Steel01: https://opensees.github.io/OpenSeesDocumentation/user/manual/material/uniaxialMaterials/Steel01.html
PEER 2015/12 wall material/validation study: https://peer.berkeley.edu/sites/default/files/webpeer-2015-12-kristijan_kolozvari_kutay_orakcal_john_wallace.pdf (Appendix B.3 card values; specimen scope)
E-SFI-MVLEM-3D: https://kkolozvari.github.io/E-SFI-MVLEM-3D/ ; https://doi.org/10.1016/j.engstruct.2023.116700
Existing NBC/IS sources and applicability qualifications remain in prior method documents. The mesh choice is a numerical modeling decision, not a newly asserted code rule.
