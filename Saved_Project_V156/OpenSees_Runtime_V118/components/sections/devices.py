"""Project-parameterized OpenSeesPy link/brace devices (V115).

This library supplies mechanics and validation only. It does not infer a
device's properties from an ETABS section name, convert an ETABS brace object,
or claim that example parameters represent a tested device. All inputs must be
derived from a manufacturer datasheet, a published test/model, or a documented
calibration. Keep this file beside the model-builder that imports it.

Verified command forms: OpenSees Wiki, ViscousDamper Material and Two Node Link
Element; Steel02 and corotTruss command forms are documented by OpenSees.
"""
from __future__ import annotations

__release__ = '134'

import math

DEVICE_ANALYSIS_ENABLED = False  # Explicit opt-in in the user's nonlinear model.


def define_fvd_material(ops, *, material_tag, K, Cd, alpha,
                        gap_length=0.0, unit_note="user-verified consistent units"):
    """Define Maxwell ViscousDamper material: spring K + dashpot Cd*v**alpha.

    K is force/length; Cd is force*(time/length)**alpha. OpenSees' ViscousDamper
    models these in series. K is not simply the damper coefficient divided by
    an arbitrary time; derive it from brace/device axial stiffness.
    """
    tag, K, Cd, alpha, gap_length = int(material_tag), float(K), float(Cd), float(alpha), float(gap_length)
    if tag <= 0 or K <= 0 or Cd <= 0 or not 0 < alpha <= 1 or gap_length < 0:
        raise ValueError("FVD needs positive tag/K/Cd, 0 < alpha <= 1 and gap_length >= 0.")
    ops.uniaxialMaterial("ViscousDamper", tag, K, Cd, alpha, gap_length)
    return {"material_tag": tag, "model": "ViscousDamper", "K": K, "Cd": Cd,
            "alpha": alpha, "LGap": gap_length, "units": unit_note,
            "calibration_status": "USER MUST RECORD SOURCE; NOT AUTO-CALIBRATED"}


def add_fvd_link(ops, *, element_tag, i_node, j_node, material_tag,
                 do_rayleigh=False):
    """Add a 3D twoNodeLink along the nonzero i-j geometry's local x axis.

    The element axis must coincide with the damper line of action. The element
    does not receive Rayleigh damping by default; enable it only after checking
    the intended combination with explicit device damping to avoid double count.
    Use separate nodes at the device ends and connect them to the surrounding
    frame/brace geometry with an explicitly modeled and reviewed detail.
    """
    ele, ni, nj, mat = map(int, (element_tag, i_node, j_node, material_tag))
    if min(ele, ni, nj, mat) <= 0 or ni == nj:
        raise ValueError("FVD link needs positive tags and distinct end nodes.")
    args = ["twoNodeLink", ele, ni, nj, "-mat", mat, "-dir", 1]
    if do_rayleigh:
        args.append("-doRayleigh")
    ops.element(*args)
    return {"element_tag": ele, "type": "twoNodeLink", "i_node": ni,
            "j_node": nj, "material_tag": mat, "local_axis": "x along i-j",
            "rayleigh_included": bool(do_rayleigh)}


def define_brb_core_material(ops, *, material_tag, Fy, E0, b,
                             R0, cR1, cR2, a1, a2, a3, a4,
                             initial_stress=0.0, unit_note="user-verified consistent units"):
    """Define a calibrated Steel02 idealization for a BRB yielding core.

    Fy and E0 use the model's force/area units; b and Steel02 transition and
    isotropic-hardening constants are dimensionless. Supply all parameters
    from the selected experimental calibration; this function has no defaults.
    """
    vals = [float(x) for x in (Fy, E0, b, R0, cR1, cR2, a1, a2, a3, a4, initial_stress)]
    Fy, E0, b, R0, cR1, cR2, a1, a2, a3, a4, initial_stress = vals
    tag = int(material_tag)
    if tag <= 0 or Fy <= 0 or E0 <= 0 or not 0 <= b < 1 or min(R0, cR1, cR2) <= 0:
        raise ValueError("Invalid BRB Steel02 tag, strengths, hardening ratio, or transition constants.")
    if any(not math.isfinite(x) for x in vals):
        raise ValueError("All BRB Steel02 inputs must be finite.")
    ops.uniaxialMaterial("Steel02", tag, Fy, E0, b, R0, cR1, cR2,
                         a1, a2, a3, a4, initial_stress)
    return {"material_tag": tag, "model": "Steel02", "Fy": Fy, "E0": E0,
            "b": b, "R0": R0, "cR1": cR1, "cR2": cR2,
            "a1": a1, "a2": a2, "a3": a3, "a4": a4,
            "initial_stress": initial_stress, "units": unit_note,
            "calibration_status": "USER MUST RECORD TEST/PUBLICATION AND CALIBRATION"}


def add_brb_corot_truss(ops, *, element_tag, i_node, j_node,
                        core_area, material_tag):
    """Add an axial corotTruss BRB idealization using core area (not casing area)."""
    ele, ni, nj, mat = map(int, (element_tag, i_node, j_node, material_tag))
    area = float(core_area)
    if min(ele, ni, nj, mat) <= 0 or ni == nj or area <= 0:
        raise ValueError("BRB needs positive tags/area and distinct end nodes.")
    ops.element("corotTruss", ele, ni, nj, area, mat)
    return {"element_tag": ele, "type": "corotTruss", "i_node": ni,
            "j_node": nj, "core_area": area, "material_tag": mat}


def assert_nonlinear_execution_enabled():
    """Fail closed until the model author deliberately enables device NLTHA."""
    if not DEVICE_ANALYSIS_ENABLED:
        raise RuntimeError("FVD/BRB nonlinear execution is OFF. After model, parameters, calibration, damping and analysis controls are verified, deliberately set DEVICE_ANALYSIS_ENABLED=True in the model-builder.")


MODEL_BUILDER_EXAMPLE = r'''# Example pattern only. Replace all tags and parameters with verified project inputs.
from OpenSees_FVD_BRB_Devices_V115 import (
    define_fvd_material, add_fvd_link,
    define_brb_core_material, add_brb_corot_truss,
)

# FVD parameters K (force/length), Cd (force*(time/length)**alpha), alpha:
define_fvd_material(ops, material_tag=801, K=K_FVD, Cd=CD_FVD,
                    alpha=ALPHA_FVD, unit_note="kN-m-s; cite datasheet/test")
add_fvd_link(ops, element_tag=8801, i_node=901, j_node=902,
             material_tag=801, do_rayleigh=False)

# Steel02 parameters and BRB yielding core area must come from calibration:
define_brb_core_material(ops, material_tag=802, Fy=FY_CORE, E0=E_STEEL,
    b=B_HARDENING, R0=R0, cR1=CR1, cR2=CR2, a1=A1, a2=A2, a3=A3, a4=A4,
    unit_note="kN-m-s; cite brace test/calibration")
add_brb_corot_truss(ops, element_tag=8802, i_node=903, j_node=904,
                    core_area=A_CORE, material_tag=802)
'''
