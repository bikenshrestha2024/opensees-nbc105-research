# Building response recorders

The analysis runners write CSV/JSON response outputs beside the case results.
`Response_Recorder_Index*.json` identifies the channels and clarifies whether
the data are a synchronized history or a component-wise envelope.

| Analysis | Main response outputs |
| --- | --- |
| Gravity preload | `Gravity_Load_Settlement.csv` at every converged load increment; `Gravity_Node_Displacements.csv`; six-component `Gravity_Support_Reactions.csv`; the existing gravity report and beam-end-action tables |
| Equivalent static | Existing story displacement, drift, story shear, secant stiffness, nodal deformation and irregularity outputs; new accepted-load-step `NBC105_ESM_BaseShear_RoofDisplacement_*.csv` and incremental support-reaction table |
| Modal | Period, frequency and directional/rotational mass participation; new `Modal_Story_Mode_Shapes.csv` with raw and per-mode normalized diaphragm-master and plan-extreme node ordinates |
| Modal response spectrum | Existing CQC story displacement/drift/shear profiles, support reaction and element force envelopes, deformation output; explicit response profile and recorder index per case |
| Linear time history | Per-step story displacement, rotation, drift, relative floor acceleration, six summed support reactions and signed base shear; synchronized base-shear/roof-displacement path |
| Nonlinear time history | Per-accepted-substep story response, relative acceleration, drift, support reactions/base shear, base-shear/roof-displacement path, tracked frame moment-curvature and tracked E-SFI panel stress-strain histories; final frame actions |

## Outrigger-position comparison

Compare candidate outrigger levels using the same model assumptions, gravity
profile, record suite and scaling, damping, time-step limits, and convergence
criteria. Useful response measures include peak roof translation in X/Y,
maximum floor-edge interstorey drift (not only diaphragm-center drift), peak
base shear and overturning reactions, floor torsional rotation, floor
acceleration, and force-deformation histories for the outrigger members and
devices. Compare both peak response and residual displacement after the record.
If FVD/BRB devices are present, retain their element force and deformation
histories and check device energy/demand against their calibrated properties.

The position with the lowest roof displacement is not automatically optimal:
also check drift concentration, torsional response, member/device force demand,
residual drift, and the project's governing design constraints. These recorders
do not themselves implement a multi-objective optimization, design acceptance,
or experimental calibration.

## Interpretation limits

Support-reaction base shear is reported with the sign convention
`base_shear = - incremental summed horizontal support reaction`; the
gravity-frozen reaction is the baseline. Relative floor acceleration under
`UniformExcitation` is not absolute floor acceleration; add the ground
acceleration consistently if absolute acceleration is needed for nonstructural
component demand.

The equivalent-static base-shear/displacement series is a linear load-control
path, not a nonlinear pushover curve. Modal response-spectrum CQC displacement,
force, and reaction results are component-wise envelopes and are not
synchronized physical states; do not use them to construct hysteresis loops.
Nonlinear force-deformation curves are only recorded for the explicitly
tracked frame and wall tags; select representative outrigger/device tags for
each configuration before interpreting local device performance.

The exploratory NLTHA recovery policy keeps the `NormDispIncr` tolerance at
`1e-7` with 40 iterations. It first retries a failed interval with Newton and
subdivides the time step before using alternate algorithms at the configured
subdivision limit (default depth 5). This reduces repeated full-model recovery
work without relaxing convergence criteria; it does not establish that a run
which stops before the record end is complete.
