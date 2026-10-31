# Floor loads and rigid diaphragms

## Supported finite-element procedure

For a uniform global vertical load q on a four-node parallelogram cell, the assembled translational load is f_i=integral(N_i q dA)=qA/4 at each corner. The four forces reproduce both total force and first moments. This result is restricted to the supported affine geometry. Non-parallelograms and unsupported directions are rejected; openings remain absent source panels.

The mesh shares coordinates/tags across adjoining panels. Frame lines are split at coincident mesh nodes. Slab bending therefore transfers forces into connected beam segments and other supports through compatibility and equilibrium. A rigid diaphragm does not perform this vertical load distribution. The source patterns are not also applied as a second set of tributary beam loads.

This is the shell finite-element path, not a claim that every floor force passes exclusively through a beam. Walls/columns can receive load directly at shared nodes. Equal source nodal forces do not imply equal beam reactions. Member-level load sharing still needs ETABS comparison and mesh convergence. Physical overlap or double-counted partition assignments in the original ETABS model cannot be resolved from pattern names alone.

The official [CSI analysis reference](https://docs.csiamerica.com/manuals/etabs/Analysis%20Reference.pdf) describes surface loading of shell elements. OpenSees [ShellMITC4 source](https://github.com/OpenSees/OpenSees/blob/master/SRC/element/shell/ShellMITC4.cpp) supplies the element interpolation and equilibrium formulation; the [official Python shell example](https://github.com/OpenSees/OpenSees/blob/master/EXAMPLES/ExamplePython/Example7.1.py) demonstrates nodal loading on a shell mesh. These sources support the FE formulation. The qA/4 specialization and equilibrium/moment checks are explicit derivations in this implementation, not a copied NBC beam-distribution rule.

## Patterns and gravity versus seismic mass

The fresh source audit contains 350 floor-finish, 350 live and 350 partition records. Their unfactored downward area-load totals are 18000, 48000 and 18000 kN respectively. No roof-live area assignments were supplied. The program reports their absence and does not invent an occupancy intensity.

Unfactored patterns are retained separately from gravity and mass multipliers. Default sustained earthquake preload uses the reviewed gravity factors; it is not a full DL+LL strength combination. In this source, live 48000 kN becomes 14400 kN in the 0.3 preload contribution. Roof-live exclusion from seismic weight is not a justification for deleting an existing unfactored roof-load pattern. Review mass/gravity factors explicitly for occupancy and each intended load combination.

## Slab stiffness without changing weight

With bending factor f, E*=E/sqrt(f), t*=t sqrt(f). Therefore E*t*=Et and E*(t*)^3=fEt^3. Poisson ratio is unchanged. These are computational section parameters; gravity and seismic weight continue to use physical source thickness and unit weight. Density in the shell section is zero because the audited mass is assigned separately at nodes.

The transformation applies to the slab section only. It does not supply an independently calibrated in-plane cracked-wall bending model.

## Rigid-plane constraints

Each source diaphragm group retains a separate master. Explicit raw ETABS point assignments are reconciled with the older preview grouping, including physical centre points omitted by that preview. Generated floor mesh nodes extend only an unambiguous single group at a level. Multiple groups at the same level are rejected until explicit generated-node membership is supplied.

OpenSees [rigidDiaphragm](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/mp_constraint/rigidDiaphragm.html) constrains ux, uy and rz for a horizontal rigid plane under a small-rotation assumption. Uz and slab bending rotations are not rigidified. The checked relations are ux=Ux-dy*Rz, uy=Uy+dx*Rz, rz=Rz. Transformation constraints are used by the analysis stack.

The audit checks tag uniqueness, membership overlap, coplanarity and floor coverage. A lateral/torsional small-model test checks the displacement relations under load. The fresh gravity run also records a constraint residual. These tests demonstrate the implemented MPC kinematics; rigid-floor appropriateness for openings, geometry and actual diaphragm flexibility remains a structural modelling decision.
