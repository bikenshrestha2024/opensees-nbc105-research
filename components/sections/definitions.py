"""Define Section module V109 for SHS, RC fiber sections, FVD, and BRB.

Section inputs are mm and MPa. OpenSees values default to kN-m; use
unit_system="N-mm" for models in N-mm-s. Importing does not create objects;
call define_all_sections(ops) after ops.model(...).

Code basis and limits:
- Nepal seismic design: NBC 105:2025; RC detailing/design: NBC 110.
- Supplemental Indian concrete-property equation: IS 456:2000, 6.2.3.1.
- Dead-load material unit weights: project/ETABS material data first; consult the
  currently listed IS 875 (Part 1):2026 where the Indian standard is applicable.
These citations identify calculation sources; they do not validate this example's
member design, material grades, or ETABS/OpenSees equivalence.
"""

from __future__ import annotations

__release__ = '134'
import math

MODULE_VERSION = "V109"

# SOURCE NOTES (checked 2026-10-20):
# Nepal DUDBC lists NBC 105:2025 (seismic design), NBC 110 (plain/reinforced
# concrete), and NBC 103 (occupancy/imposed loads):
#   https://www.dudbc.gov.np/pages/24231978/
# IS 456:2000 status/title (BIS) and clause 6.2.3.1 formula reference:
#   https://standards.bis.gov.in/website/standard-details
#   Ecm = 5000*sqrt(fck) MPa, fck in MPa. This is a code estimate, not an
#   automatic replacement for tested/project-specified modulus.
# BIS currently lists IS 875 (Part 1):2026 for dead loads/unit weights; its
# actual tables and local project material specifications must be checked:
#   https://standards.bis.gov.in/website/standard-details
# OpenSees Concrete01 source initializes tangent as 2*fpc/epsc0:
#   https://opensees.berkeley.edu/OpenSees/html/Concrete01_8cpp-source.html


def concrete_elastic_properties(fck_mpa, poisson_ratio=0.20,
                                unit_weight_kN_m3=None):
    """Return Ec and Gc using IS 456's Ec estimate and G=Ec/[2(1+nu)].

    ``poisson_ratio=0.20`` is an explicit modeling assumption, not asserted
    here as a mandatory IS 456 value. Supply a project/test value when known.
    Unit weight is returned only when explicitly supplied; obtain it from ETABS
    material data/specifications or the applicable dead-load standard.
    """
    fck_mpa = float(fck_mpa)
    poisson_ratio = float(poisson_ratio)
    if fck_mpa <= 0:
        raise ValueError("fck_mpa must be positive")
    if not (-1.0 < poisson_ratio < 0.5):
        raise ValueError("poisson_ratio must be between -1 and 0.5")
    ec_mpa = 5000.0 * math.sqrt(fck_mpa)
    result = {"fck_MPa": fck_mpa, "Ec_MPa": ec_mpa,
              "poisson_ratio_assumed_or_supplied": poisson_ratio,
              "Gc_MPa": ec_mpa / (2.0 * (1.0 + poisson_ratio))}
    if unit_weight_kN_m3 is not None:
        if float(unit_weight_kN_m3) <= 0:
            raise ValueError("unit_weight_kN_m3 must be positive")
        result["unit_weight_kN_m3_supplied"] = float(unit_weight_kN_m3)
    return result

SECTION_TAGS = {
    "SHS_350x350x16_STEEL_FIBER": 701,
    "RC_BEAM_600x800_FIBER": 611,
    "RC_COLUMN_1100x1100_FIBER": 621,
    "RC_COLUMN_1250x1250_FIBER": 631,
}
MATERIAL_TAGS = {
    "SHS_STEEL": 702,
    "RC_BEAM_COVER": 612, "RC_BEAM_CORE": 613, "RC_BEAM_REBAR": 614,
    "RC_1100_COVER": 622, "RC_1100_CORE": 623, "RC_1100_REBAR": 624,
    "RC_1250_COVER": 632, "RC_1250_CORE": 633, "RC_1250_REBAR": 634,
    "FVD": 801, "BRB": 802,
}

# BEGIN GUI-COMMITTED RC SECTION CONFIG
RC_SECTION_CONFIG = {
    "RC_BEAM_600x800_FIBER": {"width_mm": 600.0, "depth_mm": 800.0, "cover_mm": 25.0, "tie_diameter_mm": 12.0, "bar_diameter_mm": 16.0, "bars_per_side": 4, "section_tag": 611, "cover_tag": 612, "core_tag": 613, "rebar_tag": 614, "cover_fc_mpa": 35.0, "cover_epsc0": -0.002, "cover_fcu_mpa": 0.0, "cover_epsU": -0.005, "core_fcc_mpa": 44.1, "core_epsc0": -0.0046, "core_fpcu_mpa": 8.8, "core_epsU": -0.015, "fy_rebar_mpa": 550.0, "E0_mpa": 200000.0, "unit_weight_kN_m3": 25.0},
    "RC_COLUMN_1100x1100_FIBER": {"width_mm": 1100.0, "depth_mm": 1100.0, "cover_mm": 40.0, "tie_diameter_mm": 12.0, "bar_diameter_mm": 25.0, "bars_per_side": 5, "section_tag": 621, "cover_tag": 622, "core_tag": 623, "rebar_tag": 624, "cover_fc_mpa": 35.0, "cover_epsc0": -0.002, "cover_fcu_mpa": 0.0, "cover_epsU": -0.005, "core_fcc_mpa": 44.1, "core_epsc0": -0.0046, "core_fpcu_mpa": 8.8, "core_epsU": -0.015, "fy_rebar_mpa": 550.0, "E0_mpa": 200000.0, "unit_weight_kN_m3": 25.0},
    "RC_COLUMN_1250x1250_FIBER": {"width_mm": 1250.0, "depth_mm": 1250.0, "cover_mm": 40.0, "tie_diameter_mm": 12.0, "bar_diameter_mm": 25.0, "bars_per_side": 5, "section_tag": 631, "cover_tag": 632, "core_tag": 633, "rebar_tag": 634, "cover_fc_mpa": 35.0, "cover_epsc0": -0.002, "cover_fcu_mpa": 0.0, "cover_epsU": -0.005, "core_fcc_mpa": 44.1, "core_epsc0": -0.0046, "core_fpcu_mpa": 8.8, "core_epsU": -0.015, "fy_rebar_mpa": 550.0, "E0_mpa": 200000.0, "unit_weight_kN_m3": 25.0},
}
for _section_config in RC_SECTION_CONFIG.values():
    _section_config.setdefault("cover_fibers", 8)
    _section_config.setdefault("core_fibers", 16)
    _section_config.setdefault("steel_b", 0.01)
    _section_config.setdefault("steel_R0", 20.0)
    _section_config.setdefault("steel_cR1", 0.925)
    _section_config.setdefault("steel_cR2", 0.15)
# END GUI-COMMITTED RC SECTION CONFIG


def _unit_scales(unit_system):
    if unit_system == "kN-m": return 1.0e-3, 1.0e3
    if unit_system == "N-mm": return 1.0, 1.0
    raise ValueError("unit_system must be 'kN-m' or 'N-mm'")


def rectangular_torsion_J(width, depth):
    """Saint-Venant J for a solid rectangle, using the long-side convention.

    Inputs and output use the same length unit. This is used only for RC
    section torsional rigidity; it is not the polar moment Iy + Iz.
    """
    a, b = max(float(width), float(depth)), min(float(width), float(depth))
    if b <= 0:
        raise ValueError("Rectangle dimensions must be positive")
    ratios = (1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0, 1.0e6)
    betas = (0.1406, 0.1661, 0.1958, 0.2287, 0.2494, 0.2633,
             0.2808, 0.2913, 0.3123, 1.0 / 3.0)
    ratio = a / b
    beta = betas[-1] if ratio >= ratios[-1] else (
        betas[0] if ratio <= ratios[0] else
        next((betas[i] + (betas[i + 1] - betas[i]) *
              (ratio - ratios[i]) / (ratios[i + 1] - ratios[i])
              for i in range(len(ratios) - 1) if ratios[i] <= ratio <= ratios[i + 1]), betas[-1]))
    return beta * a * b**3


def shs_closed_section_torsion_J(width, depth, wall):
    """Thin-walled closed-cell Saint-Venant J for a uniform rectangular tube."""
    b, h, t = float(width), float(depth), float(wall)
    if t <= 0 or 2*t >= min(b, h):
        raise ValueError("SHS dimensions/wall thickness are invalid")
    bm, hm = b - t, h - t  # median-line dimensions
    area_m = bm * hm
    median_perimeter_over_t = 2.0 * (bm + hm) / t
    return 4.0 * area_m**2 / median_perimeter_over_t


def define_shs_350x350x16(ops, section_tag=701, material_tag=702,
                          fy_expected_mpa=379.5, E0_mpa=200000.0,
                          b=0.01, R0=18.0, cR1=0.925, cR2=0.15,
                          unit_system="kN-m", poisson_ratio=0.30):
    """Define SHS 350x350x16 Steel02 material and fiber section (4 wall fibers).

    fy_expected_mpa=379.5 (1.1 x Fe345) is the user's expected-strength
    assumption, not a general code-prescribed yield value. Confirm steel grade,
    design strength, and expected-strength factor against ETABS/certificates and
    the governing Nepal steel/seismic provisions before analysis.
    """
    if int(section_tag) == int(material_tag): raise ValueError("Use distinct section and material tags")
    ls, ss = _unit_scales(unit_system)
    H = B = 350.0*ls; t = 16.0*ls
    ops.uniaxialMaterial("Steel02", int(material_tag), fy_expected_mpa*ss,
                         E0_mpa*ss, b, R0, cR1, cR2)
    # Elastic Saint-Venant torsion for a uniform thin-walled closed SHS.
    # Steel Poisson ratio 0.30 is a stated default assumption; replace with
    # project/test data when available. MPa -> model stress units via ss.
    G_mpa = E0_mpa / (2.0 * (1.0 + float(poisson_ratio)))
    J_mm4 = shs_closed_section_torsion_J(350.0, 350.0, 16.0)
    GJ_model = G_mpa * J_mm4 * (ss * ls**4)
    ops.section("Fiber", int(section_tag), "-GJ", GJ_model)
    nf_t, nf_w, nf_f = 4, 15, 15
    ops.patch("rect", int(material_tag), nf_t, nf_f, H/2-t, -B/2, H/2, B/2)
    ops.patch("rect", int(material_tag), nf_t, nf_f, -H/2, -B/2, -H/2+t, B/2)
    ops.patch("rect", int(material_tag), nf_w, nf_t, -H/2+t, -B/2, H/2-t, -B/2+t)
    ops.patch("rect", int(material_tag), nf_w, nf_t, -H/2+t, B/2-t, H/2-t, B/2)
    return {"section_tag": int(section_tag), "material_tag": int(material_tag),
            "shape": "SHS", "width_mm": 350.0, "depth_mm": 350.0,
            "wall_mm": 16.0, "fy_expected_mpa": fy_expected_mpa,
            "G_MPa": G_mpa, "J_mm4": J_mm4, "GJ_model_units": GJ_model,
            "poisson_ratio_assumed": float(poisson_ratio),
            "unit_system": unit_system}


def define_shs_350x350x16_section(ops, **kwargs):
    return define_shs_350x350x16(ops, **kwargs)


def _define_rc_materials(ops, q, unit_system):
    _, ss = _unit_scales(unit_system)
    # Concrete01 does not accept Ec separately. OpenSees sets initial tangent
    # = 2*fpc/epsc0; the GUI's fc/epsc0 choices therefore define the tangent.
    # Compare it with concrete_elastic_properties(fck_mpa) and calibrate the
    # nonlinear cover/core curves to test/design data. Do not treat confinement
    # strength (fcc) as characteristic fck for the IS 456 Ec equation.
    ops.uniaxialMaterial("Concrete01", int(q["cover_tag"]),
                         -q["cover_fc_mpa"]*ss, q["cover_epsc0"],
                         -q["cover_fcu_mpa"]*ss, q["cover_epsU"])
    ops.uniaxialMaterial("Concrete01", int(q["core_tag"]),
                         -q["core_fcc_mpa"]*ss, q["core_epsc0"],
                         -q["core_fpcu_mpa"]*ss, q["core_epsU"])
    ops.uniaxialMaterial("Steel02", int(q["rebar_tag"]),
                         q["fy_rebar_mpa"]*ss, q["E0_mpa"]*ss,
                         q["steel_b"], q["steel_R0"], q["steel_cR1"], q["steel_cR2"])


def _define_rc(ops, key, unit_system="kN-m"):
    q = dict(RC_SECTION_CONFIG[key])
    ls, _ = _unit_scales(unit_system)
    _define_rc_materials(ops, q, unit_system)
    H=q["width_mm"]*ls; B=q["depth_mm"]*ls; cover=q["cover_mm"]*ls
    tie=q["tie_diameter_mm"]*ls; db=q["bar_diameter_mm"]*ls
    n=int(q["bars_per_side"]); cy=H/2-cover; cz=B/2-cover
    if min(cy,cz)<=0 or n<2: raise ValueError(f"Invalid RC section configuration: {key}")
    # Add elastic Saint-Venant torsion so the 3-D forceBeamColumn section is
    # stable in torsion. Flexure/axial response remains nonlinear fiber-based.
    # Ec is the IS 456:2000 estimate from cover f'c; nu=0.20 is an explicit
    # assumption unless the project provides another value.
    nu = float(q.get("poisson_ratio", 0.20))
    Ec_mpa = 5000.0 * math.sqrt(float(q["cover_fc_mpa"]))
    G_mpa = Ec_mpa / (2.0 * (1.0 + nu))
    J_mm4 = rectangular_torsion_J(float(q["width_mm"]), float(q["depth_mm"]))
    ls, ss = _unit_scales(unit_system)
    GJ_model = G_mpa * J_mm4 * (ss * ls**4)
    ops.section("Fiber", int(q["section_tag"]), "-GJ", GJ_model)
    ops.patch("rect", int(q["core_tag"]), int(q["core_fibers"]), int(q["core_fibers"]), -cy, -cz, cy, cz)
    ops.patch("rect", int(q["cover_tag"]), int(q["cover_fibers"]), int(q["core_fibers"])*2, -H/2, -B/2, -cy, B/2)
    ops.patch("rect", int(q["cover_tag"]), int(q["cover_fibers"]), int(q["core_fibers"])*2, cy, -B/2, H/2, B/2)
    ops.patch("rect", int(q["cover_tag"]), int(q["core_fibers"]), int(q["cover_fibers"]), -cy, -B/2, cy, -cz)
    ops.patch("rect", int(q["cover_tag"]), int(q["core_fibers"]), int(q["cover_fibers"]), -cy, cz, cy, B/2)
    area=math.pi*db**2/4; offset=q["cover_mm"]+q["tie_diameter_mm"]+q["bar_diameter_mm"]/2
    y=q["width_mm"]/2-offset; z=q["depth_mm"]/2-offset
    y*=ls; z*=ls
    for j in range(n):
        zz=-z+2*z*j/(n-1)
        ops.fiber(y, zz, area, int(q["rebar_tag"]))
        ops.fiber(-y, zz, area, int(q["rebar_tag"]))
    for j in range(1,n-1):
        yy=-y+2*y*j/(n-1)
        ops.fiber(yy, z, area, int(q["rebar_tag"]))
        ops.fiber(yy, -z, area, int(q["rebar_tag"]))
    return {"section_tag": int(q["section_tag"]), "width_mm": q["width_mm"],
            "depth_mm": q["depth_mm"], "bars": 4*n-4,
            "G_MPa_for_torsion": G_mpa, "J_mm4_for_torsion": J_mm4,
            "GJ_model_units": GJ_model, "poisson_ratio_assumed": nu,
            "configuration": q, "unit_system": unit_system}


def define_rc_beam_600x800(ops, unit_system="kN-m"):
    return _define_rc(ops, "RC_BEAM_600x800_FIBER", unit_system)


def define_rc_column_1100x1100(ops, unit_system="kN-m"):
    return _define_rc(ops, "RC_COLUMN_1100x1100_FIBER", unit_system)


def define_rc_column_1250x1250(ops, unit_system="kN-m"):
    return _define_rc(ops, "RC_COLUMN_1250x1250_FIBER", unit_system)


def define_all_fiber_sections(ops, unit_system="kN-m"):
    return {
        "SHS_350x350x16_STEEL_FIBER": define_shs_350x350x16(ops, unit_system=unit_system),
        "RC_BEAM_600x800_FIBER": define_rc_beam_600x800(ops, unit_system),
        "RC_COLUMN_1100x1100_FIBER": define_rc_column_1100x1100(ops, unit_system),
        "RC_COLUMN_1250x1250_FIBER": define_rc_column_1250x1250(ops, unit_system),
    }


# ============================================================================
# FVD — FLUID VISCOUS DAMPER MATERIAL
# ============================================================================
def define_fvd_material(ops, material_tag=801, alpha=0.5, tau=0.02,
                        damping_coefficient=30000.0, K=None):
    """Legacy entry: supply physical K explicitly; old example values are uncalibrated.

    https://opensees.berkeley.edu/wiki/index.php/ViscousDamper_Material
    For nonlinear alpha, Cd/tau does not have units of axial stiffness.
    """
    if K is None:raise ValueError('Supply a sourced physical FVD K (force/length); Cd/tau is not a valid general stiffness conversion. Use OpenSees_FVD_BRB_Devices_V115 with explicit K, Cd and alpha.')
    if tau<=0 or damping_coefficient<=0 or not (0<alpha<=1):
        raise ValueError("FVD tau/C must be positive and alpha must be in (0,1]")
    kel=float(K)
    if not math.isfinite(kel) or kel<=0:raise ValueError('FVD K must be finite and positive')
    ops.uniaxialMaterial("ViscousDamper", int(material_tag), kel,
                         damping_coefficient, alpha)
    return {"material_tag": int(material_tag), "alpha": alpha, "tau_s": tau,
            "C": damping_coefficient, "Kel": kel}


# ============================================================================
# BRB — BUCKLING-RESTRAINED BRACE CORE MATERIAL
# ============================================================================
def define_brb_core_material(ops, material_tag=802, fy_core_mpa=290.0,
                             E0_mpa=200000.0, unit_system="kN-m"):
    """Create Steel02 BRB core material with supplied isotropic hardening."""
    _, ss=_unit_scales(unit_system)
    ops.uniaxialMaterial("Steel02", int(material_tag), fy_core_mpa*ss,
                         E0_mpa*ss, 0.01, 18.0, 0.925, 0.15,
                         0.03, 1.0, 0.03, 1.0)
    return {"material_tag": int(material_tag), "fy_MPa": fy_core_mpa,
            "E_MPa": E0_mpa, "unit_system": unit_system}


def _define_frame_and_device_sections(ops, unit_system="kN-m", include_fvd=False, include_brb=False):
    """Define every fiber section and optional FVD/BRB materials in the domain."""
    result={"fiber_sections": define_all_fiber_sections(ops, unit_system),
           "auxiliary_materials": {}}
    if include_fvd: result["auxiliary_materials"]["FVD"]=define_fvd_material(ops)
    if include_brb: result["auxiliary_materials"]["BRB"]=define_brb_core_material(ops, unit_system=unit_system)
    return result


ETABS_TO_OPENSEES_SECTION = {
    "Col 1100*1100": "RC_COLUMN_1100x1100_FIBER",
    "Col 1250*1250": "RC_COLUMN_1250x1250_FIBER",
    "Beam 600*800": "RC_BEAM_600x800_FIBER",
    "350*350*16 SHS": "SHS_350x350x16_STEEL_FIBER",
}






# Preserve the base library entry points before adding the optional wall profile.
_base_unit_scales = _unit_scales
_define_all_sections_base = _define_frame_and_device_sections

# Parameter source: Kolozvari, Orakcal & Wallace (2015), PEER Report 2015-12,
# Appendix B.3, specimen RW-A15-P10-S78, units kip-in-sec / ksi in source.
# This is a tested/calibrated moderately slender planar wall specimen, not a
# code-prescribed generic parameter set and not the user's perforated core.
# Report: https://peer.berkeley.edu/publications/2015-12
# Exact source input listing: report Appendix B.3, pp. 90-92 (PDF pp. 101-103).
# Model definitions: OpenSees SFI-MVLEM wiki and OpenSeesPy ConcreteCM docs.
WALL_REFERENCE_PROFILE = {
    "profile_id": "PEER2015_RW-A15-P10-S78",
    "status": "LITERATURE_BENCHMARK_ONLY_NOT_PROJECT_CALIBRATED",
    "source_citation": (
        "Kolozvari, K., Orakcal, K., and Wallace, J. (2015). Shear-Flexure "
        "Interaction Modeling for Reinforced Concrete Structural Walls and "
        "Columns under Reversed Cyclic Loading. PEER Report 2015-12, Appendix B.3."
    ),
    "source_url": "https://peer.berkeley.edu/publications/2015-12",
    "specimen": "RW-A15-P10-S78 (Tran and Wallace, 2012)",
    "source_units": "kip, in, sec, ksi",
    "specimen_geometry_in": {"thickness": 6.0, "length": 48.0, "height": 72.0},
    # ksi values are preserved in the source-unit profile and converted to MPa
    # for this module's kN-m convention (1 ksi = 6.894757293 MPa).
    "ksi_to_mpa": 6.894757293,
    "concrete_unconfined": {
        "fc_ksi": 8.09, "epsc0": -0.002371, "Ec_ksi": 5403.2172,
        "rc": 15.0, "xcrn": 1.022, "ft_ksi": 0.335798,
        "et": 0.00008, "rt": 1.2, "xcrp": 10000.0,
        "gap_close": 0,
    },
    "concrete_confined": {
        "fc_ksi": 10.479723, "epsc0": -0.005873, "Ec_ksi": 5953.9187,
        "rc": 12.072964, "xcrn": 1.023, "ft_ksi": 0.335798,
        "et": 0.00008, "rt": 1.2, "xcrp": 10000.0,
        "gap_close": 0,
    },
    "steel": {
        "fy_web_x_ksi": 58.4103, "fy_web_y_ksi": 58.4103,
        "fy_boundary_y_ksi": 69.0, "E0_ksi": 29000.0,
        "b_web_x": 0.02, "b_web_y": 0.02, "b_boundary_y": 0.005,
        "R0": 20.0, "a1": 18.5, "a2": 0.0015,
    },
    # FSAM X is horizontal reinforcement; Y is vertical reinforcement in the
    # source model. These are reinforcement ratios, not guessed bar layouts.
    "reinforcement_ratio": {
        "rouX_web": 0.0074, "rouY_web": 0.0074,
        "rouX_boundary": 0.0082, "rouY_boundary": 0.0587,
    },
    "fsam": {"rho": 0.0, "nu": 0.8, "alfadow": 0.01},
    "tags": {
        "steel_x": 901, "steel_y_web": 902, "steel_y_boundary": 903,
        "concrete_web": 904, "concrete_boundary": 905,
        "fsam_web": 906, "fsam_boundary": 907,
    },
    "limitations": [
        "Benchmark wall is planar, solid, moderately slender, and has no opening.",
        "Do not transfer specimen reinforcement ratios to the project core without checking drawings/ETABS.",
        "This creates SteelMPF, ConcreteCM, and FSAM material objects only; no wall elements, geometry, openings, or mesh are created.",
        "Verify the OpenSees build includes SteelMPF, ConcreteCM, and FSAM before use.",
        "Calibrate and validate against project material tests/details and an opening-wall benchmark before thesis NLTHA.",
    ],
}

# PROJECT-SUPPLIED WALL REINFORCEMENT LAYOUT (geometry only; material strengths
# remain sourced from ETABS/drawings). Two curtains means one reinforcement
# mat near each wall face. Cover is clear cover to the outermost bar surface.
WALL_REINFORCEMENT_LAYOUT = {
    "source": "User-provided project detail, 2026-10-21",
    "vertical_bar_diameter_mm": 20.0,
    "horizontal_bar_diameter_mm": 20.0,
    "vertical_spacing_mm": 200.0,
    "horizontal_spacing_mm": 200.0,
    "curtains": 2,
    "clear_cover_each_face_mm": 25.0,
    "cover_definition": "clear distance from concrete face to outermost bar surface",
    # User supplied 550 MPa as the concrete-member rebar grade. Treat this as
    # a project input pending confirmation from ETABS design assignments/drawings;
    # it is not the yield strength of the PEER benchmark specimen below.
    "steel_grade": "fy=550 MPa (user-supplied; verify against ETABS/drawings)",
    "steel_fy_MPa": 550.0,
}


def wall_reinforcement_ratios(thickness_mm, layout=None):
    """Return gross-section web reinforcement ratios for a two-curtain wall.

    FSAM uses rouX for horizontal bars and rouY for vertical bars. For equally
    spaced bars on both faces, rho = 2*Ab/(s*t). The calculation assumes the
    stated spacing applies on each face and excludes any extra jamb/boundary
    reinforcement. It does not define steel/concrete constitutive parameters.
    """
    cfg = dict(WALL_REINFORCEMENT_LAYOUT if layout is None else layout)
    t = float(thickness_mm)
    if t <= 0:
        raise ValueError("wall thickness must be positive")
    curtains = int(cfg["curtains"])
    if curtains != 2:
        raise ValueError("this helper expects two reinforcement curtains")
    result = {"thickness_mm": t, "curtains": curtains,
              "clear_cover_each_face_mm": float(cfg["clear_cover_each_face_mm"])}
    for direction in ("vertical", "horizontal"):
        dia = float(cfg[f"{direction}_bar_diameter_mm"])
        spacing = float(cfg[f"{direction}_spacing_mm"])
        if dia <= 0 or spacing <= 0:
            raise ValueError(f"{direction} bar diameter and spacing must be positive")
        area = math.pi * dia**2 / 4.0
        rho = curtains * area / (spacing * t)
        result[f"{direction}_bar_area_mm2"] = area
        result[f"rho_{direction}"] = rho
    result["fsam_rouX_horizontal"] = result["rho_horizontal"]
    result["fsam_rouY_vertical"] = result["rho_vertical"]
    result["bar_centerline_from_face_mm_approx"] = (
        result["clear_cover_each_face_mm"]
        + float(cfg["vertical_bar_diameter_mm"]) / 2.0
    )
    result["steel_grade"] = cfg.get("steel_grade")
    result["note"] = (
        "Web ratios only; confirm steel grade and any additional opening-jamb, "
        "pier-edge, or spandrel reinforcement from ETABS/drawings."
    )
    return result


def define_wall_reference_materials(ops, unit_system="kN-m", tags=None):
    """Define optional PEER 2015 SFI-MVLEM specimen materials.

    Creates SteelMPF X/web-Y/boundary-Y, ConcreteCM unconfined/confined, and
    FSAM web/boundary materials. Stress inputs are converted from the source
    ksi values to the requested OpenSees stress units. No element is created.

    This is only a benchmark starting point. It must not be treated as the
    user's project wall material calibration, especially for a perforated core.
    """
    _, stress_scale = _base_unit_scales(unit_system)
    cfg = WALL_REFERENCE_PROFILE
    tags = dict(cfg["tags"] if tags is None else tags)
    required = set(cfg["tags"])
    if set(tags) != required:
        raise ValueError(f"tags must contain exactly: {', '.join(sorted(required))}")
    if len(set(map(int, tags.values()))) != len(tags):
        raise ValueError("Wall benchmark material tags must be unique")
    k = float(cfg["ksi_to_mpa"])
    steel = cfg["steel"]
    def stress(value_ksi):
        return float(value_ksi) * k * stress_scale

    ops.uniaxialMaterial("SteelMPF", int(tags["steel_x"]),
                         stress(steel["fy_web_x_ksi"]), stress(steel["fy_web_x_ksi"]),
                         stress(steel["E0_ksi"]), steel["b_web_x"], steel["b_web_x"],
                         steel["R0"], steel["a1"], steel["a2"])
    ops.uniaxialMaterial("SteelMPF", int(tags["steel_y_web"]),
                         stress(steel["fy_web_y_ksi"]), stress(steel["fy_web_y_ksi"]),
                         stress(steel["E0_ksi"]), steel["b_web_y"], steel["b_web_y"],
                         steel["R0"], steel["a1"], steel["a2"])
    ops.uniaxialMaterial("SteelMPF", int(tags["steel_y_boundary"]),
                         stress(steel["fy_boundary_y_ksi"]), stress(steel["fy_boundary_y_ksi"]),
                         stress(steel["E0_ksi"]), steel["b_boundary_y"], steel["b_boundary_y"],
                         steel["R0"], steel["a1"], steel["a2"])

    for key, tag_key in (("concrete_unconfined", "concrete_web"),
                         ("concrete_confined", "concrete_boundary")):
        c = cfg[key]
        args = [int(tags[tag_key]), -stress(c["fc_ksi"]), c["epsc0"],
                stress(c["Ec_ksi"]), c["rc"], c["xcrn"], stress(c["ft_ksi"]),
                c["et"], c["rt"], c["xcrp"], "-GapClose", c["gap_close"]]
        ops.uniaxialMaterial("ConcreteCM", *args)

    ratios, fsam = cfg["reinforcement_ratio"], cfg["fsam"]
    ops.nDMaterial("FSAM", int(tags["fsam_web"]), fsam["rho"],
                   int(tags["steel_x"]), int(tags["steel_y_web"]),
                   int(tags["concrete_web"]), ratios["rouX_web"],
                   ratios["rouY_web"], fsam["nu"], fsam["alfadow"])
    ops.nDMaterial("FSAM", int(tags["fsam_boundary"]), fsam["rho"],
                   int(tags["steel_x"]), int(tags["steel_y_boundary"]),
                   int(tags["concrete_boundary"]), ratios["rouX_boundary"],
                   ratios["rouY_boundary"], fsam["nu"], fsam["alfadow"])
    return {
        "profile_id": cfg["profile_id"], "status": cfg["status"],
        "source_citation": cfg["source_citation"], "unit_system": unit_system,
        "tags": tags, "specimen_geometry_in": dict(cfg["specimen_geometry_in"]),
        "reinforcement_ratio": dict(ratios), "limitations": list(cfg["limitations"]),
    }


def define_all_sections(ops, unit_system="kN-m", include_fvd=False,
                        include_brb=False, include_wall_reference=False):
    """Define frame library; optional wall profile is explicitly benchmark-only."""
    result = _define_all_sections_base(ops, unit_system, include_fvd, include_brb)
    if include_wall_reference:
        result["wall_reference_materials"] = define_wall_reference_materials(ops, unit_system)
    return result

