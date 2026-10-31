# Axial shortening: thesis interpretation and literature review

## 1. Meaning of the present result

The supplied gravity run reports applied downward load 286447.790000 kN,
summed upward reactions 286447.788933 kN and minimum global Uz
−0.009579955894636475 m = −9.5799559 mm. Its equilibrium residual is
3.72366×10⁻⁷ percent. This supports the numerical equilibrium of that
assembled load state. It does not establish agreement with ETABS or measured
building movements.

Minimum Uz is the most downward **nodal vertical displacement** anywhere in
the model. It can include floor bending, frame deformation, wall deformation,
compatibility forces from outriggers and the chosen support conditions. It is
not automatically the axial contraction of a named column, nor a prediction of
creep, shrinkage or construction compensation.

The V123 envelope took the minimum over every mesh elevation. The governing
node can change at successive elevations, producing the zigzag in the screenshot.
A zigzag therefore requires inspection of node identity; smoothing that curve
would hide the underlying change of location. V124 retains the explicitly named
displacement envelope and adds separate tracked vertical frame-line profiles
and a CSV with coordinates, node tags, elevation and relative Uz.

The tracked profiles group vertical frame segments at common X/Y coordinates.
They are a geometry-based diagnostic: verify continuous connectivity and member
identity before treating a line as one physical column. Their reference is the
lowest tracked node, which may differ from a foundation node for a transfer column.

## 2. Mechanical definitions and reproducible checks

For a straight, homogeneous, prismatic, purely axial elastic member:

    contraction magnitude δ = N L / (E A)

For several axial segments, sum N_i L_i/(E_i A_i), with a consistent compression
sign convention. In a composite section under strain compatibility, use the
appropriate axial rigidity, e.g. E_c A_c + E_s A_s, with reinforcement area counted
once. Use the actual exported material modulus and section area. A lateral
flexural stiffness modifier is not automatically an axial EA modifier.

For a vertical member with lower node i and upper node j, the first-order
contraction magnitude is Uz_i − Uz_j. With fixed base and downward-negative Uz,
the cumulative contraction of a continuous vertical line is −(Uz_top−Uz_base).
For inclined members, project the displacement difference onto the original
member axis. End axial forces can have opposite signs under local resisting-force
conventions; do not sum their magnitudes as two independent axial loads.

Differential displacement at a common elevation is Uz_column − Uz_core at
specified physical nodes. Report both node IDs, coordinates, load state, sign,
units and reference level. A maximum displacement envelope does not preserve
this pair and cannot substitute for that calculation.

Validation sequence:

1. Check an isolated elastic axial bar against N L/(E A), including units/signs.
2. Check a stack with known segment forces against the segment sum.
3. In the building, identify continuous column/core locations and compare
   relative vertical displacements at identical elevations.
4. Reconcile loads, stiffness, releases, diaphragm assumptions, mesh and support
   conditions against ETABS before interpreting inter-program differences.
5. Check mesh refinement and compare axial-only estimates with the coupled
   model, explaining bending/compatibility contributions.

The numerical equilibrium check is necessary but insufficient for these checks.

## 3. Literature synthesis

**Fintel and Khan (1969)** describe creep/shrinkage prediction with incremental
floor loading, reinforcement restraint and section size effects. Their loading
history treatment explains why applying the final gravity load to the complete
building in one analysis is not equivalent to construction-stage shortening.
Primary abstract: [ACI, DOI 10.14359/7444](https://www.concrete.org/publications/internationalconcreteabstractsportal.aspx?id=7444&m=details).

**Pan, Liu and Bakoss (1993)** separate instantaneous elastic deformation from
creep and shrinkage, and use incremental superposition for long-term prediction.
They discuss secondary actions in floor members caused by unequal column/core
movements and compare predictions with measurements. This motivates reporting
both absolute and differential movements, with an explicit time/loading basis.
Primary abstract: [Journal of Structural Engineering 119(7), 2258–2262](https://ascelibrary.com/doi/10.1061/%28ASCE%290733-9445%281993%29119%3A7%282258%29).

**Matar and Faschan (2017)** connect differential vertical shortening to service
axial stresses, transfers, structural irregularities, serviceability and
communication of compensation to construction teams. For an outrigger/belt
system, the activation sequence of connecting members is therefore a modelling
assumption that should be documented and studied.
Primary paper: [International Journal of High-Rise Buildings 6(1), 73–82, DOI 10.21022/IJHRB.2017.6.1.73](https://global.ctbuh.org/resources/papers/3311-073-082%20%2001.Sami%20S.%20Matar.pdf).

These summaries use the accessible publisher abstracts/paper; they do not claim
a full systematic review or verification of every model proposed in the papers.

## 4. Scope of this thesis implementation

The current assembled elastic gravity case uses source dead/self-weight and
sustained live factors from the exported configuration (currently D + 0.3 Live).
Self-weight follows source pattern multipliers and is counted once in the
assembled load ledger. Check ETABS joint overlap and mass-source conventions.

The run does not implement concrete ageing, creep/shrinkage constitutive laws,
humidity, casting dates, staged floor activation, installation/lock-in dates,
foundation settlement or thermal strains unless these are explicitly added.
Do not title the present 9.58 mm result “long-term column shortening”.

Suggested thesis wording: “The complete elastic model reached static gravity
equilibrium. The maximum downward nodal displacement was approximately
9.58 mm for the stated sustained gravity load. Tracked vertical member-line
displacements were examined separately from the global envelope. Time-dependent
and construction-stage shortening were outside this analysis.”

For a later time-dependent study, obtain project-specific concrete age/modulus,
creep/shrinkage parameters, reinforcement, humidity, construction schedule and
outrigger connection sequence, then validate against independent benchmarks.
