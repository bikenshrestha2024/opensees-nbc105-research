# V169 first-step evidence (diagnostic branch)

The exploratory runner writes `XY/First_Step_Failure_Evidence.json` (or `YX/`) after an unsuccessful transient solve, before attempting another algorithm. It reads `isolated_model/OpenSees_Complete_Element_Map_V118.json` to label suspect elements with their ETABS source object.

The collector scans nodal displacements and element responses (localForce, basicDeformation, globalForce). For AREA objects it also queries ShearDef, Curvature, and first-panel RCPanel stress/strain. Unsupported responses are tallied separately; the first recorded nonfinite response may be a downstream symptom.

**Safety:** Do not run another algorithm or reduce time step when any nonfinite state is observed. The snapshot is post-failure diagnostic evidence, not a reliable committed element state, stiffness rank test, or successful NLTHA. No material values, gravity loads, or convergence tolerances were changed.

To try this branch:

```bat
git fetch origin
git switch diagnostics/v169-first-step-evidence
python 18_BUILDING_FULL_NONLINEAR.py
```

Use a distinct output folder for each ZERO/X/Y/XY test. Review `First_Step_Failure_Evidence.json`, `Initial_Modal_Damping.json`, material-assignment JSON and the element map together. Full building analyses and experimental validation have NOT been executed in this change.
