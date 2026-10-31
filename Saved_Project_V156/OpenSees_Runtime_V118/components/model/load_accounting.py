"""NBC 105:2025 load bookkeeping helpers for ETABS-to-OpenSees workflows.

This module keeps physical loads unfactored and calculates NBC combinations
separately. It does not infer tributary supports or instantiate shell, wall,
brace, damper, or BRB elements; those require verified ETABS mapping.

Code hierarchy: applicable Nepal NBC clauses first. Use the relevant Indian
Standard only where the applicable Nepal standard is silent, and record the
fallback citation and project assumption in the input/audit.
"""
from __future__ import annotations

__release__ = '134'
# Citation rule: confirm clause/table and edition against the controlled Nepal
# standard copy. Nepal standards take precedence; an Indian Standard is a
# documented fallback only where the applicable Nepal code is silent.
# Official DUDBC code index: https://www.dudbc.gov.np/pages/24231978/
# See CODE_GUIDE_V108.md for interpretation and limits of these expressions.
import math

MODULE_VERSION = "V108"
SOURCES = {
    "seismic_design": "NBC 105:2025 §§3.4, 3.6, 5.2; Tables 3-1 and 5-1",
    "occupancy_loads": "NBC 103 where applicable; otherwise IS 875 (Part 2):1987",
    "dead_load_unit_weights": "Nepal applicable provisions / ETABS material data; otherwise IS 875 (Part 1):2026",
    "rc_properties": "NBC 110; use IS 456 only for matters not specified/adopted by Nepal standards",
    "official_nepal_codes": "https://www.dudbc.gov.np/pages/24231978/",
}

# NBC 105:2025 §3.6.1/§3.6.2. LL is classified by occupancy.
NBC105_COMBINATIONS = {
    "gravity_strength": {"expression": "1.2 DL + 1.5 LL", "DL": 1.2, "LL": 1.5},
    "gravity_plus_snow_liquid_earth": {"expression": "1.2 DL + 0.5 LL + S", "DL": 1.2, "LL": 0.5, "S": 1.0},
    "seismic_plus": {"expression": "DL + lambda LL + E", "DL": 1.0, "LL": None, "E": 1.0},
    "seismic_minus": {"expression": "DL + lambda LL - E", "DL": 1.0, "LL": None, "E": -1.0},
    "seismic_overturning_plus": {"expression": "0.9 DL + E", "DL": 0.9, "E": 1.0},
    "seismic_overturning_minus": {"expression": "0.9 DL - E", "DL": 0.9, "E": -1.0},
    "nonparallel": "DL + lambda LL ± (Ex ± 0.3 Ey), and DL + lambda LL ± (Ey ± 0.3 Ex)",
}
LIVE_LOAD_COMBINATION_FACTOR = {"storage": 0.60, "other": 0.30}
SEISMIC_MASS_FACTOR = {"dead": 1.00, "storage_live": 0.60,
                       "other_live": 0.30, "roof_live": 0.00}


def perimeter_equivalent_line_load_kN_m(pressure_kN_m2, area_m2, perimeter_m):
    """Uniform perimeter line load preserving total force for symmetric plan.

    It does not reproduce actual two-way slab tributary distribution/local
    beam moments. Do not use for an irregular plan, openings, or core-supported
    panels without an explicit tributary/support model.
    """
    q, area, perimeter = map(float, (pressure_kN_m2, area_m2, perimeter_m))
    if not all(math.isfinite(v) for v in (q, area, perimeter)) or area < 0 or perimeter <= 0:
        raise ValueError("Require finite pressure, nonnegative floor area, and positive perimeter")
    return q * area / perimeter


def line_self_weight_kN_m(area_m2, unit_weight_kN_m3):
    """Return unfactored member self-weight per length; apply once only."""
    area, gamma = map(float, (area_m2, unit_weight_kN_m3))
    if not all(math.isfinite(v) for v in (area, gamma)) or area <= 0 or gamma <= 0:
        raise ValueError("Section area and unit weight must be finite and positive")
    return area * gamma


def surface_self_weight_kN_m2(thickness_m, unit_weight_kN_m3):
    """Return unfactored slab/wall self-weight per area; apply once only."""
    t, gamma = map(float, (thickness_m, unit_weight_kN_m3))
    if not all(math.isfinite(v) for v in (t, gamma)) or t <= 0 or gamma <= 0:
        raise ValueError("Thickness and unit weight must be finite and positive")
    return t * gamma


def gravity_udl_local_components_kN_m(weight_kN_m, member_role):
    """OpenSees 3D ``beamUniform`` args (Wy, Wz, Wx) for downward gravity.

    Assumes the exporter convention: horizontal beam local z is global +Z;
    vertical column local x points upward from i to j. A diagonal brace needs
    a full local-axis projection and must not use this shortcut.
    """
    w = float(weight_kN_m)
    if not math.isfinite(w) or w < 0:
        raise ValueError("weight_kN_m must be finite and nonnegative")
    role = str(member_role).strip().upper()
    if role in {"BEAM", "HORIZONTAL_BEAM"}:
        return (0.0, -w, 0.0)  # gravity acts in local -z
    if role in {"COLUMN", "VERTICAL_COLUMN"}:
        return (0.0, 0.0, -w)  # axial gravity acts in local -x
    raise ValueError("Only verified horizontal beams or upward-oriented vertical columns are supported")


def self_weight_policy(component, etabs_dead_includes_self_weight):
    """Fail-closed decision: whether exporter may add member/surface SW."""
    component = str(component).strip().upper()
    allowed = {"BEAM", "COLUMN", "SHEAR_WALL", "SLAB", "BRACE", "FVD", "BRB"}
    if component not in allowed:
        raise ValueError(f"Unsupported component category: {component}")
    if etabs_dead_includes_self_weight is None:
        return {"status": "BLOCKED", "reason": "Confirm ETABS dead-load self-weight inclusion before adding weight; duplicate SW is prohibited."}
    if bool(etabs_dead_includes_self_weight):
        return {"status": "ETABS_SOURCE_ONLY", "reason": "ETABS dead pattern includes self-weight; do not add a second OpenSees self-weight."}
    if component in {"FVD", "BRB"}:
        return {"status": "REQUIRES_EXPLICIT_DEVICE_DATA", "reason": "Use manufacturer/ETABS device weight and mass; damping coefficient or BRB material strength is not a weight."}
    return {"status": "OPENSees_SELF_WEIGHT_ALLOWED", "reason": "Use verified section geometry and applicable unit weight; add once to DL."}


def factored_component_loads(dead, live, *, occupancy="other", earthquake=0.0):
    """Return NBC combinations for scalar load effects; inputs remain raw."""
    d, l, e = map(float, (dead, live, earthquake))
    lam = LIVE_LOAD_COMBINATION_FACTOR["storage" if str(occupancy).lower().startswith("stor") else "other"]
    return {
        "NBC105_strength_gravity": 1.2*d + 1.5*l,
        "NBC105_seismic_plus": d + lam*l + e,
        "NBC105_seismic_minus": d + lam*l - e,
        "NBC105_seismic_overturning_plus": 0.9*d + e,
        "NBC105_seismic_overturning_minus": 0.9*d - e,
        "live_load_factor_lambda": lam,
        "note": "Report combinations separately; never scale imported reference loads in-place.",
    }



