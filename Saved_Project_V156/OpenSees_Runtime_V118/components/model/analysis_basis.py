"""Step 13 reference settings: NBC 105:2025 + required project IS 16700 case.

NBC 105:2025 governs seismic analysis inputs and RC effective stiffness.
For this project, the user requires completion of the IS 16700:2023 §7.2(d)
initial P-Delta cases before NBC equivalent-static earthquake analysis. This
project workflow requirement does not relabel the IS combination as an NBC
combination. The IS §7.3.10 theta check remains a separate reported screen.
"""
from __future__ import annotations

__release__ = '134'

import math

# NBC 105:2025 Table 3-1 flexural EI multipliers in absence of rational cracked
# section analysis. Area remains gross (1.0 Ag); steel stays gross.
NBC105_FLEXURAL_MODIFIERS = {
    "beam": {"ULS": 0.35, "SLS": 0.70},
    "column": {"ULS": 0.70, "SLS": 0.90},
    "wall_cracked": {"ULS": 0.50, "SLS": 0.70},
    "wall_uncracked": {"ULS": 0.80, "SLS": 0.90},
    "masonry_wall": {"ULS": 0.45, "SLS": 0.60},
    "flat_slab": {"ULS": 0.25, "SLS": 0.50},
    "steel": {"ULS": 1.00, "SLS": 1.00},
}

# IS 16700 Table 5 comparison values. Not applicable to this project's
# conventional slab unless the user explicitly adopts that basis.
IS16700_SLAB_MODIFIERS = {
    "area_Ag": {"serviceability": 1.00, "strength": 1.00},
    "inertia_Ig": {"serviceability": 0.35, "strength": 0.25},
}

# IS 16700:2023 Clause 7.2(d): initial analysis considering P-Delta.
# EL/WL denotes the applicable signed lateral action case, run separately.
IS16700_INITIAL_PDELTA_FACTORS = {"DL": 1.20, "IL": 0.50, "EL_or_WL": 1.50}
IS16700_INITIAL_PDELTA_CASES = ("+EL/WL", "-EL/WL")

# NBC 105:2025 §8.1.1 linear viscous damping limit.
NBC105_MAX_LINEAR_DAMPING_RATIO = 0.05
LINEAR_TIME_HISTORY_EXECUTION_DEFAULT = False


def effective_flexural_modifier(component: str, limit_state: str) -> float:
    """Return NBC 105:2025 Table 3-1 flexural EI factor.

    This returns an EI multiplier only; it does not edit nonlinear fiber
    material or shell sections automatically. IS 16700 slab values are kept
    separately for comparative reporting and are not selected here.
    """
    comp = str(component).strip().lower().replace(" ", "_")
    state = str(limit_state).strip().upper()
    if state not in ("ULS", "SLS"):
        raise ValueError("limit_state must be ULS or SLS")
    if comp == "flat_slab":
        return NBC105_FLEXURAL_MODIFIERS["flat_slab"][state]
    if comp in ("slab", "floor_slab", "conventional_slab"):
        raise ValueError("NBC 105:2025 Table 3-1 gives a tabulated modifier only for flat slabs. For a conventional slab, provide a documented rational cracked-section stiffness or verified ETABS effective stiffness; no factor is inferred.")
    aliases = {"rc_beam": "beam", "rc_column": "column", "wall": "wall_cracked", "cracked_wall": "wall_cracked", "uncracked_wall": "wall_uncracked", "steel_brace": "steel"}
    comp = aliases.get(comp, comp)
    try:
        return NBC105_FLEXURAL_MODIFIERS[comp][state]
    except KeyError as exc:
        raise ValueError(f"Unknown component {component!r}; no stiffness reduction inferred.") from exc


def initial_pdelta_combinations(lateral_action="EL", directions=("X", "Y")):
    """Return factor maps for signed IS 16700 cases in each requested direction."""
    action = str(lateral_action).strip().upper()
    if action not in ("EL", "WL"):
        raise ValueError("lateral_action must be EL or WL")
    result = {}
    for direction in directions:
        direction = str(direction).strip().upper()
        if direction not in ("X", "Y"):
            raise ValueError("directions must contain only X or Y")
        result[f"PD_INIT_{action}_{direction}_PLUS"] = {"DL": 1.20, "IL": 0.50, action: 1.50, "direction": direction}
        result[f"PD_INIT_{action}_{direction}_MINUS"] = {"DL": 1.20, "IL": 0.50, action: -1.50, "direction": direction}
    return result


def validate_initial_pdelta_results(results, lateral_actions=("EL",), directions=("X", "Y")):
    """Fail unless each required +/- IS 16700 initial P-Delta case converged.

    ``results`` is a mapping keyed by e.g. ``PD_INIT_EL_X_PLUS``. Each value
    must contain ``converged: True`` and a nonempty ``result_file`` or
    ``result_note`` audit trail. This validates recorded evidence only; the
    project model builder is responsible for constructing/running the actual
    load combinations and restoring the intended analysis state afterwards.
    """
    if not isinstance(results, dict):
        raise ValueError("Provide IS16700_INITIAL_PDELTA_RESULTS as an audited mapping.")
    required = []
    for action in lateral_actions:
        action = str(action).strip().upper()
        if action not in ("EL", "WL"):
            raise ValueError("Required lateral actions must be EL or WL.")
        for direction in directions:
            direction = str(direction).strip().upper()
            if direction not in ("X", "Y"):
                raise ValueError("Required directions must be X or Y.")
            required.extend((f"PD_INIT_{action}_{direction}_PLUS", f"PD_INIT_{action}_{direction}_MINUS"))
    missing = []
    for name in required:
        item = results.get(name)
        if not isinstance(item, dict) or item.get("converged") is not True:
            missing.append(name + " (missing or not converged)")
        elif not str(item.get("result_file") or item.get("result_note") or "").strip():
            missing.append(name + " (no audit trail)")
    if missing:
        raise ValueError("Required IS 16700:2023 §7.2(d) cases incomplete: " + "; ".join(missing))
    return {"required_cases": required, "completed_cases": len(required)}


def rayleigh_coefficients(T1_s: float, T2_s: float, zeta: float = 0.05):
    """Two-term Rayleigh coefficients at T1/T2; return alphaM and betaKcommitted.

    C = alphaM*M + betaKcommitted*Kcommitted. Both terms are retained.
    """
    T1, T2, z = float(T1_s), float(T2_s), float(zeta)
    if not all(math.isfinite(x) for x in (T1, T2, z)) or min(T1, T2) <= 0 or not 0 < z <= NBC105_MAX_LINEAR_DAMPING_RATIO:
        raise ValueError("Periods must be positive; damping ratio must be >0 and <= NBC's 5% cap.")
    w1, w2 = 2.0 * math.pi / T1, 2.0 * math.pi / T2
    alpha_m = 2.0 * z * w1 * w2 / (w1 + w2)
    beta_kc = 2.0 * z / (w1 + w2)
    return alpha_m, beta_kc


def modal_damping_ratio(alpha_m: float, beta_k: float, omega: float) -> float:
    """Return ζ(ω)=αM/(2ω)+βKω/2 for the coefficients used by OpenSees."""
    a, b, w = float(alpha_m), float(beta_k), float(omega)
    if w <= 0:
        raise ValueError("omega must be positive")
    return a / (2.0 * w) + b * w / 2.0


def apply_two_term_rayleigh(ops, T1_s: float, T2_s: float, zeta: float = 0.05):
    """Apply alphaM + betaKcommitted to OpenSees, after the intended preload."""
    alpha_m, beta_kc = rayleigh_coefficients(T1_s, T2_s, zeta)
    ops.rayleigh(alpha_m, 0.0, 0.0, beta_kc)
    return alpha_m, beta_kc


def open_step13_gui(parent=None):
    """Show the concise, cited basis used by the model workflow."""
    import tkinter as tk
    from tkinter import ttk
    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("Step 13 — IS 16700 initial P-Delta gate + NBC stiffness / damping")
    win.geometry("1000x720"); win.minsize(850, 600)
    root = ttk.Frame(win, padding=12); root.pack(fill="both", expand=True)
    ttk.Label(root, text="STEP 13 — LINEAR TIME HISTORY, P-DELTA BASIS + STIFFNESS", font=("Segoe UI", 14, "bold")).pack(anchor="w")
    ttk.Label(root, text="NBC 105:2025 remains the seismic-design basis. Per the selected project basis, complete and converge both IS 16700:2023 §7.2(d) initial P-Delta cases before running NBC equivalent-static earthquake analysis. The cases are an explicit project prerequisite, while retaining their correct IS source label.", wraplength=950).pack(anchor="w", pady=6)
    ttk.Label(root, text="REQUIRED PROJECT GATE — IS 16700:2023 §7.2(d) initial P-Delta cases", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 3))
    ttk.Label(root, text="For X and Y, run + and − earthquake signs: 1.2 DL + 0.5 IL ± 1.5 EL. Record convergence and audit files in the model-builder variable IS16700_INITIAL_PDELTA_RESULTS with keys PD_INIT_EL_X_PLUS / MINUS and PD_INIT_EL_Y_PLUS / MINUS. The ESM runner validates all four before running. Add WL cases where required. This initial check is distinct from the sustained gravity preload for NLTHA; before transient analysis, establish the reviewed gravity state and preserve it with loadConst(time=0).", wraplength=950).pack(anchor="w")
    ttk.Label(root, text="Flexural stiffness modifiers", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 3))
    cols=("component", "NBC ULS", "NBC SLS", "IS strength", "IS serviceability", "source")
    tree=ttk.Treeview(root, columns=cols, show="headings", height=8)
    for c,h in zip(cols,("Component","NBC ULS / strength","NBC SLS / serviceability","IS 16700 strength*","IS 16700 serviceability*","Source")): tree.heading(c,text=h)
    rows=[("Conventional RC slab","Not tabulated","Not tabulated","0.25 Ig","0.35 Ig","IS 16700:2023 Table 5 (supplemental; verify applicability)"),("Flat slab","0.25 Ig","0.50 Ig","0.25 Ig","0.35 Ig","NBC Table 3-1 / IS Table 5"),("Beam","0.35 Ig","0.70 Ig","—","—","NBC 105:2025 Table 3-1"),("Column","0.70 Ig","0.90 Ig","—","—","NBC 105:2025 Table 3-1"),("Cracked wall","0.50 Ig","0.70 Ig","—","—","NBC 105:2025 Table 3-1"),("Uncracked wall","0.80 Ig","0.90 Ig","—","—","NBC 105:2025 Table 3-1"),("Masonry wall","0.45 Ig","0.60 Ig","—","—","NBC 105:2025 Table 3-1"),("Steel","1.00 Ig","1.00 Ig","—","—","Gross stiffness")]
    for row in rows: tree.insert("","end",values=row)
    for c,w in zip(cols,(180,130,150,130,160,390)): tree.column(c,width=w,anchor="w")
    tree.pack(fill="x")
    ttk.Label(root, text="* IS 16700:2023 Table 5 gives slab modifiers of 1.00 Ag and 0.25 Ig for strength design, and 1.00 Ag and 0.35 Ig for serviceability design. These are shown as a supplemental comparison for this conventional slab; they are not automatically applied. Confirm code applicability and the project's adopted analysis basis before selecting them. NBC Table 3-1's 0.25/0.50 row is for flat slabs only and does not apply to this conventional slab. For NBC analysis use a documented rational cracked stiffness or verified ETABS effective stiffness. Do not multiply elastic modifiers into nonlinear fiber/FSAM constitutive behavior.", wraplength=950, foreground="#9a3e1d").pack(anchor="w", pady=8)
    ttk.Label(root, text="Rayleigh damping — NBC 105:2025 §8.1.1", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(8,3))
    ttk.Label(root, text="C = αM M + βKcommitted Kcommitted; ζ(ω)=αM/(2ω)+βKcommitted·ω/2. Choose the two calibration periods/modes from the analyzed model; the runner computes αM and βKcommitted, uses both terms, and stops if checked modal damping exceeds 5%. Linear time-history execution remains OFF by default.", wraplength=950).pack(anchor="w")
    ttk.Button(root,text="Close",command=win.destroy).pack(anchor="e",pady=(10,0))
    return win
