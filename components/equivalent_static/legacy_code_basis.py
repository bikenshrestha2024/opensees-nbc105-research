import math
"""NBC 105:2025 analysis settings V108 used by the ETABS/OpenSeesPy workflow.

Values below are transcribed from NBC 105:2025 §§3.4, 3.6.1 and 3.6.2
(including Table 3-1) and the user's specified earthquake mass source.
Official DUDBC index: https://www.dudbc.gov.np/pages/24231978/
NBC 105:2025 PDF:
https://giwmscdnone.gov.np/media/files/NBC_105_2025_Seismic%20Design%20of%20Buildings%20in%20Nepal_lqqvx6a.pdf

The mass-source coefficients are stored here, but a complete nodal mass model
must also include verified member/slab self-weight and correctly classified
ETABS load patterns. Do not treat load-only audit masses as final analysis mass.
"""

__release__ = '134'

MODULE_VERSION = "V108"
DESIGN_METHOD = "Limit State Method (LSM) only"

# OpenSees solver presets, separate from NBC load factors. Nonlinear defaults
# are chosen for the forceBeamColumn/fiber model; do not use algorithm Linear
# for nonlinear fiber gravity or transient analyses.
OPENSEES_ANALYSIS_STACK = {
    "constraints": "Transformation (rigid-diaphragm multi-point constraints)",
    "numberer": "RCM",
    "system": "SparseGeneral (general sparse direct solver)",
    "optional_systems": {
        "ProfileSPD": "Only for symmetric positive-definite systems; not the nonlinear NLTHA default.",
        "BandGeneral": "Useful baseline for small/moderate bandwidth models; may be inefficient for a large building.",
    },
    "primary_mode": "NONLINEAR_NLTHA",
    "mode_choices": ["LINEAR_ELASTIC_CHECK", "NONLINEAR_STATIC", "NONLINEAR_NLTHA"],
    "nonlinear_algorithm_choices": ["Newton", "KrylovNewton", "NewtonLineSearch"],
    "algorithm_policy": "Start with Newton; test KrylovNewton or NewtonLineSearch as documented convergence alternatives, not as automatic substitutes for model/load review.",
    "nonlinear_static": {
        "test": "NormDispIncr", "tolerance": 1.0e-8, "max_iterations": 50,
        "algorithm": "Newton", "integrator": "LoadControl", "analysis": "Static",
    },
    "nonlinear_transient": {
        "test": "NormDispIncr", "tolerance": 1.0e-7, "max_iterations": 30,
        "algorithm": "Newton (KrylovNewton / NewtonLineSearch are selectable alternatives)", "integrator": "Newmark", "gamma": 0.5,
        "beta": 0.25, "analysis": "Transient",
    },
    "elastic_check_only": {
        "algorithm": "Linear", "integrator": "LoadControl", "analysis": "Static",
    },
    "check_analyze_return_code": True,
    "freeze_gravity_after_convergence": 'ops.loadConst("-time", 0.0)',
}

# Section 3.4/Table 3-1 gives effective *elastic* stiffness where rational
# cracked-section analysis has not been performed. These factors are reference
# settings for elastic stiffness checks/models. Do not multiply forceBeamColumn
# Fiber material stiffness by them: that would also modify material yielding and
# can double-count cracking when nonlinear fiber response is being modeled.
NBC105_NLTHA_STIFFNESS_POLICY = {
    "fiber_model": "Use calibrated nonlinear material response; do not apply Table 3-1 multipliers directly to fiber materials.",
    "elastic_check": "Use Table 3-1 effective stiffness factors where rational cracked-section analysis is absent.",
    "beam_compatibility_torsion_only": 0.10,
    "steel_uses_gross_stiffness": True,
}

NBC105_CLAUSE_REFERENCES = {
    "cracked_stiffness": "NBC 105:2025 §3.4, Table 3-1",
    "load_combinations": "NBC 105:2025 §3.6.1 and §3.6.2",
    "earthquake_live_load_fraction": "NBC 105:2025 §3.6.1, definition of lambda",
}

# NBC 105:2025 §3.6 load-combination forms. Shared formulas are displayed for both ULS and SLS;
# use the state-appropriate seismic action (ULS or SLS coefficient) when evaluating E terms.
# S = 1.2*S0 (snow), 1.2*Slp (static liquid pressure), or 1.5*Sep (earth pressure).
# lambda = 0.6 for storage occupancy and 0.3 for other occupancy.
# This project uses the NBC Limit State Method only. §3.7 Working Stress Method
# combinations are deliberately excluded. SLS checks remain part of the LSM
# workflow; Table 3-1 serviceability stiffness values are retained below.
# Keep source load patterns unfactored and apply factors to response combinations.
PARALLEL_SYSTEM_COMBINATIONS = [
    {"name": "LSM-01", "expression": "1.2 DL + 1.5 LL"},
    {"name": "LSM-02", "expression": "1.2 DL + 0.5 LL + S"},
    {"name": "LSM-03X+", "expression": "DL + λ LL + Ex"},
    {"name": "LSM-03X-", "expression": "DL + λ LL - Ex"},
    {"name": "LSM-03Y+", "expression": "DL + λ LL + Ey"},
    {"name": "LSM-03Y-", "expression": "DL + λ LL - Ey"},
    {"name": "LSM-04X+", "expression": "0.9 DL + Ex"},
    {"name": "LSM-04X-", "expression": "0.9 DL - Ex"},
    {"name": "LSM-04Y+", "expression": "0.9 DL + Ey"},
    {"name": "LSM-04Y-", "expression": "0.9 DL - Ey"},
]

NONPARALLEL_SYSTEM_COMBINATIONS = [
    {"name": "LSM-NP-01X", "expression": "DL + λ LL ± (Ex ± 0.3 Ey)"},
    {"name": "LSM-NP-01Y", "expression": "DL + λ LL ± (Ey ± 0.3 Ex)"},
    {"name": "LSM-NP-02X", "expression": "0.9 DL ± (Ex ± 0.3 Ey)"},
    {"name": "LSM-NP-02Y", "expression": "0.9 DL ± (Ey ± 0.3 Ex)"},
]

NBC105_LOAD_FACTORS = {
    "strength_gravity": {"DL": 1.2, "LL": 1.5},
    "displayed_for_uls_and_sls": True,
    "strength_with_S": {"DL": 1.2, "LL": 0.5},
    "seismic": {"DL": 1.0, "LL": "lambda", "E": 1.0},
    "seismic_overturning": {"DL": 0.9, "E": 1.0},
    "nonparallel_orthogonal_factor": 0.3,
    "lambda_storage": 0.6,
    "lambda_other": 0.3,
    "S_snow_or_static_liquid": 1.2,
    "S_earth_pressure": 1.5,
}

UNFACTORED_LOAD_POLICY = {
    "patterns": "Import reference DL, LL, and other load patterns without design factors.",
    "gravity_preload": "Use reviewed service-level DL plus sustained LL; converge before loadConst.",
    "strength_combinations": "Apply NBC §3.6 factors to response combinations, not source pattern values.",
    "NLTHA": "Do not scale ground-motion acceleration by gravity ULS factors.",
    "self_weight": "Count each component once; never add it again when included in imported ETABS DL.",
}

LOAD_ACCOUNTING_COVERAGE = {
    "beam_column_brace_frame_load_assignments": "Reviewed ETABS distributed assignments are currently imported only for exported horizontal beams.",
    "beam_column_self_weight": "Not auto-added; requires verified unit weight/section area and confirmation ETABS DL excludes self-weight.",
    "slab_wall_area_loads": "Audited but not transferred into the forceBeamColumn model; requires validated shell/wall elements or explicit supporting-member tributaries.",
    "slab_wall_self_weight": "Not applied; requires verified thickness, unit weight, mesh/tributary transfer, and duplicate-load check.",
    "FVD_BRB_weight": "Not inferred from damping coefficient or steel strength; require explicit device weight/mass and load path.",
    "earthquake_mass": "Mass factors are defined here; the forceBeamColumn exporter does not assign complete nodal masses.",
}

LIVE_LOAD_FACTORS = {"storage_facilities": 0.60, "other_occupancy": 0.30}

# Factors are for flexural stiffness EI. All other section components remain
# gross unless a separate documented analysis says otherwise. Steel stays gross.
CRACKED_STIFFNESS_MODIFIERS = {
    "beam": {"ultimate": 0.35, "serviceability": 0.70},
    "column": {"ultimate": 0.70, "serviceability": 0.90},
    "wall_cracked": {"ultimate": 0.50, "serviceability": 0.70},
    "wall_uncracked": {"ultimate": 0.80, "serviceability": 0.90},
    "masonry_wall": {"ultimate": 0.45, "serviceability": 0.60},
    "flat_slab": {"ultimate": 0.25, "serviceability": 0.50},
    "steel": {"ultimate": 1.00, "serviceability": 1.00},
    "beam_compatibility_torsion": 0.10,
}

# User-specified earthquake mass source. Pattern names are configurable because
# ETABS load-pattern labels vary by model. Roof live has factor zero by design.
EARTHQUAKE_MASS_SOURCE = {
    "dead_load_factor": 1.00,
    "storage_live_factor": 0.60,
    "other_live_factor": 0.30,
    "roof_live_factor": 0.00,
    "include_roof_live": False,
    "dead_pattern_names": ["DL", "Dead", "Floor Finish", "Partition"],
    "storage_pattern_names": ["Storage", "Storage Facility", "Storage Live"],
    "other_live_pattern_names": ["Live", "LL", "Live Load"],
    "roof_live_pattern_names": ["Roof Live", "Roof Live Load", "Roof LL"],
}


def live_load_factor(occupancy):
    key = str(occupancy).strip().lower()
    if key in {"storage", "storage facility", "storage facilities"}:
        return LIVE_LOAD_FACTORS["storage_facilities"]
    return LIVE_LOAD_FACTORS["other_occupancy"]


def flexural_stiffness_modifier(component, stage="ultimate"):
    """Return Table 3-1 factor for the selected component and design stage."""
    key = str(component).strip().lower().replace(" ", "_")
    stage_key = str(stage).strip().lower()
    if stage_key not in {"ultimate", "serviceability"}:
        raise ValueError("stage must be 'ultimate' or 'serviceability'")
    if key in {"beam", "rc_beam"}:
        return CRACKED_STIFFNESS_MODIFIERS["beam"][stage_key]
    if key in {"column", "rc_column"}:
        return CRACKED_STIFFNESS_MODIFIERS["column"][stage_key]
    if key in {"wall", "wall_cracked", "cracked_wall"}:
        return CRACKED_STIFFNESS_MODIFIERS["wall_cracked"][stage_key]
    if key in {"wall_uncracked", "uncracked_wall"}:
        return CRACKED_STIFFNESS_MODIFIERS["wall_uncracked"][stage_key]
    if key in {"masonry", "masonry_wall"}:
        return CRACKED_STIFFNESS_MODIFIERS["masonry_wall"][stage_key]
    if key == "flat_slab":
        return CRACKED_STIFFNESS_MODIFIERS["flat_slab"][stage_key]
    if key in {"slab", "conventional_slab", "floor_slab"}:
        raise ValueError("NBC 105:2025 Table 3-1 has a tabulated stiffness factor only for flat slabs. For a conventional slab, provide documented rational cracked stiffness or verified ETABS effective stiffness.")
    return 1.0  # Unknown/steel component: do not invent a reduction.


def mass_source_factor(pattern_name, is_roof_live=False):
    """Return seismic mass factor; roof-live assignments always receive zero.

    Where roof and floor live loads share one ETABS pattern, the caller must
    identify individual roof assignments with ``is_roof_live=True`` or split
    the patterns before applying mass. Pattern-name matching alone cannot
    distinguish roof from floor assignments in a shared pattern.
    """
    name = str(pattern_name).strip().casefold()
    spec = EARTHQUAKE_MASS_SOURCE
    if is_roof_live or any(name == x.casefold() for x in spec["roof_live_pattern_names"]):
        return 0.0
    if any(name == x.casefold() for x in spec["dead_pattern_names"]):
        return spec["dead_load_factor"]
    if any(name == x.casefold() for x in spec["storage_pattern_names"]):
        return spec["storage_live_factor"]
    if any(name == x.casefold() for x in spec["other_live_pattern_names"]):
        return spec["other_live_factor"]
    return 0.0


# =============================================================================
# NBC 105:2025 EQUIVALENT STATIC METHOD (ESM) — calculation helpers
# Source clauses: §§3.2.1, 4.1.1-4.1.5, 4.2, 5.1-5.2, 6.1-6.4.
# This module computes seismic weights and equivalent-static floor forces from
# user-verified ETABS story totals. It does not infer missing dead load or certify
# model completeness. See NBC105_Equivalent_Static_Gui_V108.py for the workflow.
# =============================================================================
NBC105_DOCUMENTATION_URL = (
    "https://giwmscdnone.gov.np/media/files/"
    "NBC_105_2025_Seismic%20Design%20of%20Buildings%20in%20Nepal_lqqvx6a.pdf"
)
NBC105_ESM_SOIL_PARAMETERS = {
    # NBC 105:2025 Table 4-1. For ESM, Ta = 0 (Table 4-1 footnote).
    # Stored Tc, Td and alpha define the Figure 4-1(a) ESM spectrum.
    "A": {"Ta_s": 0.0, "Tc_s": 0.5, "Td_s": 4.0, "alpha": 2.50},
    "B": {"Ta_s": 0.0, "Tc_s": 0.7, "Td_s": 4.0, "alpha": 2.50},
    "C": {"Ta_s": 0.0, "Tc_s": 1.0, "Td_s": 4.0, "alpha": 2.50},
    "D": {"Ta_s": 0.0, "Tc_s": 2.0, "Td_s": 5.0, "alpha": 2.25},
}
NBC105_ESM_TABLE5_1_FACTORS = {
    "dead": 1.00,
    "storage_live": 0.60,
    "other_live": 0.30,
    "roof_live": 0.00,
}
NBC105_ESM_SYSTEM_FACTORS = {
    # NBC 105:2025 Table 5-2: (R_mu, Omega_u, Omega_s)
    "RC moment resisting frame": (4.0, 1.5, 1.25),
    "Steel moment resisting frame": (4.0, 1.5, 1.25),
    "RC shear wall": (3.0, 1.3, 1.15),
    "RC dual system with shear wall": (3.5, 1.4, 1.20),
    "Steel buckling restrained braces": (4.0, 1.5, 1.25),
}


def esm_spectral_shape_factor(period_s, soil_type):
    """NBC 105 Figure 4-1(a) / Table 4-1 ESM shape factor Ch(T).

    With Ta=0 for ESM: Ch=alpha through Tc; alpha*Tc/T through Td;
    alpha*Tc*Td/T**2 at and beyond Td.
    """
    T = float(period_s)
    soil = str(soil_type).strip().upper()
    if T < 0.0:
        raise ValueError("Period T1 must be nonnegative.")
    if soil not in NBC105_ESM_SOIL_PARAMETERS:
        raise ValueError("soil_type must be A, B, C, or D.")
    p = NBC105_ESM_SOIL_PARAMETERS[soil]
    alpha, Tc, Td = p["alpha"], p["Tc_s"], p["Td_s"]
    if T <= Tc:
        return alpha
    if T <= Td:
        return alpha * Tc / T
    return alpha * Tc * Td / (T * T)


def esm_period_exponent(period_s):
    """NBC 105 §6.3 k: 1 for T<=0.5, 2 for T>=2.5, linear between."""
    T = float(period_s)
    if T <= 0.5:
        return 1.0
    if T >= 2.5:
        return 2.0
    return 1.0 + (T - 0.5) / 2.0


def esm_eligibility(height_m, period_s, limit_state, irregular=None):
    """Return (permitted, explanation) under NBC 105:2025 §3.2.1.

    ESM is permitted for all SLS. For ULS at least one test is required:
    H<=15m; T1<0.5s; or regular structure with H<40m. ``irregular`` must
    be explicitly True/False to evaluate the third criterion.
    """
    H, T = float(height_m), float(period_s)
    state = str(limit_state).strip().upper()
    if state == "SLS":
        return True, "NBC 105:2025 §3.2.1 permits ESM for all SLS calculations."
    if state != "ULS":
        raise ValueError("limit_state must be ULS or SLS")
    checks=[]
    if H <= 15.0:
        checks.append("height <= 15 m")
    if T < 0.5:
        checks.append("fundamental period < 0.5 s")
    if H < 40.0 and irregular is False:
        checks.append("regular configuration and height < 40 m")
    if checks:
        return True, "ULS ESM criterion satisfied: " + "; ".join(checks) + "."
    if irregular is None and H < 40.0:
        return False, "ULS ESM eligibility needs explicit regularity confirmation under §5.4; otherwise use MRSM."
    return False, (
        "ULS ESM is not permitted by the supplied data under §3.2.1: requires "
        "H<=15 m, or T1<0.5 s, or a regular structure with H<40 m. "
        "Use MRSM or nonlinear analysis as applicable."
    )


def calculate_esm(stories, *, period_s, soil_type, zoning_factor_z,
                  importance_factor_i, limit_state="ULS", r_mu=4.0,
                  omega_u=1.5, omega_s=1.25, irregular=None):
    """Calculate NBC 105 story seismic weights, base shear and floor forces.

    Each story record requires ``height_m``, ``dead_load_kN``,
    ``storage_live_load_kN`` and ``other_live_load_kN``. Roof live is forced
    to zero by Table 5-1. The returned records contain Wi and Fi in kN.
    """
    if not stories:
        raise ValueError("At least one story row is required.")
    T = float(period_s); Z = float(zoning_factor_z); I = float(importance_factor_i)
    state = str(limit_state).strip().upper()
    if T < 0 or Z <= 0 or I <= 0:
        raise ValueError("T1 must be >=0; Z and I must be positive.")
    if not all(math.isfinite(float(v)) and float(v)>0 for v in (r_mu,omega_u,omega_s)):raise ValueError('System factors must be finite and positive')
    normalized=[]
    for row in stories:
        h=float(row["height_m"])
        if not math.isfinite(h) or h <= 0: raise ValueError(f"Invalid story height: {row}")
        dl=float(row["dead_load_kN"])
        storage=float(row.get("storage_live_load_kN",0.0) or 0.0)
        other=float(row.get("other_live_load_kN",0.0) or 0.0)
        if not all(math.isfinite(v) for v in (dl,storage,other)) or min(dl,storage,other) < 0:
            raise ValueError("Story load inputs must be nonnegative magnitudes in kN.")
        wi=dl + 0.60*storage + 0.30*other
        if wi <= 0: raise ValueError(f"Story seismic weight must be positive: {row}")
        normalized.append({**row,"height_m":h,"dead_load_kN":dl,
            "storage_live_load_kN":storage,"other_live_load_kN":other,
            "roof_live_factor":0.0,"seismic_weight_kN":wi})
    normalized.sort(key=lambda r: float(r["height_m"]))
    heights=[r["height_m"] for r in normalized]
    if any(b<=a for a,b in zip(heights,heights[1:])):
        raise ValueError("Story heights must be unique and strictly increasing.")
    H=max(heights)
    permitted,eligibility_note=esm_eligibility(H,T,state,irregular)
    if not permitted:
        raise ValueError(eligibility_note)
    Ch=esm_spectral_shape_factor(T,soil_type)
    elastic_spectrum=Ch*Z*I
    if state == "ULS":
        if float(r_mu)<=0 or float(omega_u)<=0: raise ValueError("Rmu and Omega_u must be positive.")
        Cd=elastic_spectrum/(float(r_mu)*float(omega_u))
        divisor=f"R_mu*Omega_u={float(r_mu):g}*{float(omega_u):g}"
    else:
        if float(omega_s)<=0: raise ValueError("Omega_s must be positive.")
        # NBC §4.2: Cs(T)=0.20*C(T); §6.1.2: Cd=Cs/Omega_s.
        Cd=0.20*elastic_spectrum/float(omega_s)
        divisor=f"Omega_s={float(omega_s):g}; SLS spectrum=0.20*C(T)"
    W=sum(r["seismic_weight_kN"] for r in normalized)
    V=Cd*W
    k=esm_period_exponent(T)
    denom=sum(r["seismic_weight_kN"]*(r["height_m"]**k) for r in normalized)
    for row in normalized:
        row["distribution_exponent_k"]=k
        row["lateral_force_kN"]=(row["seismic_weight_kN"]*row["height_m"]**k/denom)*V
    return {
        "standard":"NBC 105:2025", "clauses":"§§3.2.1, 4.1.1-4.1.5, 4.2, 5.1-5.2, 6.1-6.4",
        "limit_state":state,"soil_type":str(soil_type).upper(),"period_s":T,
        "zoning_factor_Z":Z,"importance_factor_I":I,"spectral_shape_Ch":Ch,
        "elastic_spectrum_C_k":elastic_spectrum,"design_coefficient_Cd":Cd,
        "coefficient_divisor":divisor,"period_exponent_k":k,
        "ductility_factor_R_mu":float(r_mu),"overstrength_factor_Omega_u":float(omega_u),
        "overstrength_factor_Omega_s":float(omega_s),
        "deflection_scale_factor_kd":({1:1.0,2:0.97,3:0.94,4:0.91,5:0.88}.get(len(normalized),0.85)),
        "drift_limit_ratio":(0.025 if state=="ULS" else 0.006),
        "total_seismic_weight_kN":W,"base_shear_kN":V,
        "total_floor_force_kN":sum(r["lateral_force_kN"] for r in normalized),
        "height_m":H,"esm_eligibility":eligibility_note,
        "live_load_factors":dict(NBC105_ESM_TABLE5_1_FACTORS),"stories":normalized,
        "source_pdf":NBC105_DOCUMENTATION_URL,
    }




