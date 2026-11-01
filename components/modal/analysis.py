"""NBC 105:2025 modal-analysis audit helpers for OpenSeesPy.

This module calculates eigen periods/frequencies and OpenSees modal mass
participation outputs. It audits the NBC 105:2025 §7.3 90% directional
participating-mass criterion and highlights modes above 33 Hz. It does not
perform modal response-spectrum combination, the §7.3 missing-mass correction,
or the §7.5 base-shear scaling; those remain explicitly reported as pending.

Use after the complete model, mass source, diaphragm constraints, and the
reviewed gravity preload have been applied in the same OpenSees process.
References are listed in README_V111.md.
"""
from __future__ import annotations

__release__ = '134'
from OpenSees_Timing_V130 import timed_outputs

import csv
import json
import math
import time
from pathlib import Path


NBC105_MIN_DIRECTIONAL_MASS_PERCENT = 90.0
NBC105_MODAL_COMBINATION_MAX_FREQUENCY_HZ = 33.0


def nbc105_period_estimate(*, height_m, system_type, wall_aw_x_m2=None,
                           wall_aw_y_m2=None, rayleigh_x_s=None,
                           rayleigh_y_s=None):
    """Return NBC 105:2025 §5.1 empirical/amplified/adopted period values.

    For concrete shear-wall buildings, ``wall_aw_*`` is the direction-specific
    effective wall area parameter from §5.1.2:
    Aw = sum(Awi * (0.2 + (min(Lwi/H, 0.9))**2)).
    Supply it separately for X and Y using first-storey walls effective in that
    direction. The routine does not infer net wall areas around openings.

    NBC §5.1.3 amplifies the empirical estimate by 1.25. Where a separately
    calculated Rayleigh period is supplied, the adopted period for design action
    is the lesser of the Rayleigh period and amplified empirical estimate.
    """
    h = float(height_m)
    if not math.isfinite(h) or h <= 0:
        raise ValueError("height_m must be finite and positive")
    def positive_optional(value, name):
        if value in (None, ""):
            return None
        number=float(value)
        if not math.isfinite(number) or number<=0:
            raise ValueError(f"{name} must be finite and positive when supplied")
        return number
    aw_x=positive_optional(wall_aw_x_m2,'wall_aw_x_m2')
    aw_y=positive_optional(wall_aw_y_m2,'wall_aw_y_m2')
    rayleigh_x=positive_optional(rayleigh_x_s,'rayleigh_x_s')
    rayleigh_y=positive_optional(rayleigh_y_s,'rayleigh_y_s')
    system_type = str(system_type).strip().lower()
    fixed_kt = {
        "concrete moment-resisting frame": 0.075,
        "steel moment-resisting frame": 0.085,
        "steel eccentrically braced frame": 0.075,
        "other structural system": 0.05,
    }
    empirical = {}
    for axis, aw in (("X", aw_x), ("Y", aw_y)):
        if "concrete shear-wall" in system_type:
            if aw is None:
                empirical[axis] = None
            else:
                empirical[axis] = 0.075 * h ** 0.75 / math.sqrt(aw)
        else:
            if system_type not in fixed_kt:
                raise ValueError(f"Unsupported NBC empirical period system: {system_type}")
            empirical[axis] = fixed_kt[system_type] * h ** 0.75
    out = {"height_m": h, "system_type": system_type,
           "wall_Aw_X_m2": aw_x,
           "wall_Aw_Y_m2": aw_y,
           "rayleigh_X_s": rayleigh_x,
           "rayleigh_Y_s": rayleigh_y,
           "empirical_X_s": empirical["X"], "empirical_Y_s": empirical["Y"],
           "amplified_empirical_X_s": None if empirical["X"] is None else 1.25 * empirical["X"],
           "amplified_empirical_Y_s": None if empirical["Y"] is None else 1.25 * empirical["Y"]}
    for axis in ("X", "Y"):
        tr = out[f"rayleigh_{axis}_s"]
        te = out[f"amplified_empirical_{axis}_s"]
        out[f"adopted_design_period_{axis}_s"] = None if tr is None or te is None else min(tr, te)
        out[f"adopted_period_status_{axis}"] = (
            "INCOMPLETE: supply direction-specific wall Aw" if te is None else
            "INCOMPLETE: supply NBC Rayleigh period to determine lesser adopted value" if tr is None else
            "READY: adopted period is lesser of Rayleigh and amplified empirical")
    return out


def _series(modal_properties, key, n, fallback=None):
    values = modal_properties.get(key) if isinstance(modal_properties, dict) else None
    if values is None:
        if fallback is None:
            return [None] * n
        values = fallback
    try:
        values = list(values)
    except TypeError:
        return [None] * n
    values = [float(v) for v in values[:n]]
    return values + [None] * (n - len(values))


def modal_response_nodes(model_data):
    """Choose diaphragm masters and actual perimeter-extreme nodes for torsion review."""
    nodes = model_data["nodes"]
    result = []
    seen = set()
    for group in sorted(model_data.get("diaphragms", []),
                        key=lambda item: item["master_xyz"][2]):
        story = "Storey_" + str(group["storey_number"])
        master = int(group["master_tag"])
        candidates = [(master, "master")]
        slaves = [
            (int(tag), nodes.get(str(tag), nodes.get(tag)))
            for tag in group.get("slave_node_tags", [])
            if nodes.get(str(tag), nodes.get(tag)) is not None
        ]
        if slaves:
            for axis, label in ((0, "x_min"), (0, "x_max"),
                                (1, "y_min"), (1, "y_max")):
                extreme = min(slaves, key=lambda item: item[1][axis]) if label.endswith("min") else max(slaves, key=lambda item: item[1][axis])
                candidates.append((extreme[0], label))
        for tag, role in candidates:
            if tag in seen:
                continue
            seen.add(tag)
            xyz = nodes.get(str(tag), nodes.get(tag))
            if xyz is None and tag == master:
                xyz = group["master_xyz"]
            if xyz is None:
                raise ValueError(f"Modal response node {tag} has no coordinates.")
            result.append(dict(
                story_name=story, node_tag=tag, role=role,
                x_m=float(xyz[0]), y_m=float(xyz[1]), z_m=float(xyz[2])))
    return result


def export_story_mode_shapes(ops, eigvals, periods, story_nodes, output_dir):
    """Export raw and per-mode normalized diaphragm/perimeter mode ordinates."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for mode, (eigenvalue, period) in enumerate(zip(eigvals, periods), 1):
        mode_rows = []
        for node in story_nodes:
            vector = [float(ops.nodeEigenvector(
                int(node["node_tag"]), mode, dof)) for dof in range(1, 7)]
            mode_rows.append(dict(
                mode=mode, eigenvalue_s_2=float(eigenvalue),
                period_s=float(period), story_name=node["story_name"],
                node_tag=int(node["node_tag"]), node_role=node["role"],
                x_m=node["x_m"], y_m=node["y_m"], z_m=node["z_m"],
                ux_raw=vector[0], uy_raw=vector[1], uz_raw=vector[2],
                rx_raw=vector[3], ry_raw=vector[4], rz_raw=vector[5]))
        normalization = max(
            (max(abs(row["ux_raw"]), abs(row["uy_raw"]), abs(row["uz_raw"]))
             for row in mode_rows), default=0.0)
        for row in mode_rows:
            row["translation_normalization"] = normalization
            row["ux_normalized"] = row["ux_raw"] / normalization if normalization else 0.0
            row["uy_normalized"] = row["uy_raw"] / normalization if normalization else 0.0
            row["uz_normalized"] = row["uz_raw"] / normalization if normalization else 0.0
        rows.extend(mode_rows)
    path = out / "Modal_Story_Mode_Shapes.csv"
    if rows:
        with path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return path


@timed_outputs('Modal analysis','output_dir')
def run_nbc105_modal_audit(ops, *, nmodes=30, output_dir=".",
                           solver="PythonSparse", target_mass_percent=90.0,
                           max_frequency_hz=33.0, report_prefix="NBC105_Modal_V111",
                           period_inputs=None, fundamental_mode_x=None,
                           fundamental_mode_y=None, story_nodes=()):
    """Run eigenanalysis and write CSV/JSON/text audit files.

    Args:
        ops: imported ``openseespy.opensees`` module with the model already built.
        nmodes: requested eigenpairs. Increase if either X or Y cumulative
            participation is below the NBC threshold.
        output_dir: folder for all modal audit outputs.
        solver: ``PythonSparse`` is recommended for building-scale models.
            Native OpenSees solvers may fail to return promptly on large sparse
            systems; fallback only occurs after a native call returns or raises.
        target_mass_percent: NBC target defaults to 90% in each horizontal axis.
        max_frequency_hz: NBC §7.3 modal-combination limit, 33 Hz.

    Returns a JSON-serializable result dictionary. This is a modal audit only;
    no response-spectrum forces or design actions are generated here.
    """
    nmodes = int(nmodes)
    if nmodes < 1:
        raise ValueError("nmodes must be a positive integer")
    if not (0.0 < float(target_mass_percent) <= 100.0):
        raise ValueError("target_mass_percent must be in (0, 100]")
    started = time.perf_counter()
    from components.shared.eigen_solver import solve_eigen
    eigvals = solve_eigen(ops, nmodes, solver)
    eigvals = [float(x) for x in eigvals]
    if not eigvals:
        raise RuntimeError("OpenSees returned no eigenvalues")
    if any(not math.isfinite(x) or x <= 0 for x in eigvals):
        raise RuntimeError("Eigenvalues must be finite and positive; inspect model stability, restraints, and mass")

    # modalProperties reports participation ratios in percent (not fractions).
    props = ops.modalProperties("-return")
    n = len(eigvals)
    periods = _series(props, "eigenPeriod", n,
                      [2.0 * math.pi / math.sqrt(v) for v in eigvals])
    omegas = _series(props, "eigenOmega", n,
                     [math.sqrt(v) for v in eigvals])
    freqs = _series(props, "eigenFrequency", n,
                    [1.0 / t for t in periods])
    ux_pct = _series(props, "partiMassRatiosMX", n)
    uy_pct = _series(props, "partiMassRatiosMY", n)
    rz_pct = _series(props, "partiMassRatiosRMZ", n)
    ux_cum = _series(props, "partiMassRatiosCumuMX", n)
    uy_cum = _series(props, "partiMassRatiosCumuMY", n)
    rz_cum = _series(props, "partiMassRatiosCumuRMZ", n)

    rows = []
    for i in range(n):
        scores=[ux_pct[i] or 0.,uy_pct[i] or 0.,rz_pct[i] or 0.]
        order=sorted(range(3),key=lambda j:scores[j],reverse=True)
        classification='Other / low horizontal participation' if scores[order[0]]<1. else ['Translation X','Translation Y','Rotation Z'][order[0]]
        if scores[order[1]]>=0.5*scores[order[0]]:classification='Mixed '+classification
        rows.append({
            "classification_candidate":classification,
            "classification_basis":"Heuristic from individual UX/UY/RZ effective mass percentages; inspect eigenvector; not a code acceptance rule",
            "mode": i + 1,
            "eigenvalue_lambda_s-2": eigvals[i],
            "omega_rad_s": omegas[i],
            "frequency_Hz": freqs[i],
            "period_s": periods[i],
            "UX_participation_percent": ux_pct[i],
            "UX_cumulative_percent": ux_cum[i],
            "UY_participation_percent": uy_pct[i],
            "UY_cumulative_percent": uy_cum[i],
            "RZ_participation_percent": rz_pct[i],
            "RZ_cumulative_percent": rz_cum[i],
            "below_33_Hz": bool(freqs[i] < float(max_frequency_hz)),
            "mode_in_lateral_resisting_system": "REVIEW_MODE_SHAPE",
            "modal_combination_included_by_frequency_rule": bool(freqs[i] < float(max_frequency_hz)),
            "above_33_Hz_missing_mass_followup_required": bool(freqs[i] >= float(max_frequency_hz)),
        })

    mode_shape_path = None
    if story_nodes:
        mode_shape_path = export_story_mode_shapes(
            ops, eigvals, periods, story_nodes, output_dir)

    ux_final = ux_cum[-1]
    uy_final = uy_cum[-1]
    ux_ok = ux_final is not None and ux_final >= float(target_mass_percent)
    uy_ok = uy_final is not None and uy_final >= float(target_mass_percent)
    first90 = {}
    for axis, seq in (("X", ux_cum), ("Y", uy_cum)):
        first90[axis] = next((i + 1 for i, val in enumerate(seq)
                              if val is not None and val >= float(target_mass_percent)), None)
    high_modes = [r["mode"] for r in rows if r["above_33_Hz_missing_mass_followup_required"]]
    period_check = None
    if period_inputs:
        period_check = nbc105_period_estimate(**period_inputs)
        for axis, mode in (("X", fundamental_mode_x), ("Y", fundamental_mode_y)):
            if mode is None:
                # Candidate only: mixed translation/torsion requires review of mode shapes.
                ratios = ux_pct if axis == "X" else uy_pct
                mode = max(range(n), key=lambda j: ratios[j] if ratios[j] is not None else -1) + 1
                period_check[f"candidate_modal_mode_{axis}"] = mode
                period_check[f"candidate_modal_period_{axis}_s"] = periods[mode - 1]
                period_check[f"modal_period_candidate_note_{axis}"] = "Mode with largest directional participation; inspect shape and confirm manually."
            else:
                mode = int(mode)
                if mode < 1 or mode > n:
                    raise ValueError(f"fundamental_mode_{axis} must be between 1 and {n}")
                period_check[f"reviewed_modal_mode_{axis}"] = mode
                period_check[f"reviewed_modal_period_{axis}_s"] = periods[mode - 1]
            modal_t = period_check.get(f"reviewed_modal_period_{axis}_s", period_check.get(f"candidate_modal_period_{axis}_s"))
            adopted = period_check.get(f"adopted_design_period_{axis}_s")
            period_check[f"modal_to_adopted_period_ratio_{axis}"] = None if adopted is None or not adopted else modal_t / adopted
    result = {
        "standard": "NBC 105:2025",
        "clauses": ["7.3 Number of Modes to be Considered", "7.4 Combination of Modal Effects", "7.5 Scale Factor for Design Values of the Combined Response"],
        "requested_modes": nmodes,
        "returned_modes": n,
        "eigensolver": str(solver),
        "target_directional_mass_percent": float(target_mass_percent),
        "minimum_modal_combination_frequency_hz": float(max_frequency_hz),
        "cumulative_UX_percent": ux_final,
        "cumulative_UY_percent": uy_final,
        "UX_90_percent_reached": bool(ux_ok),
        "UY_90_percent_reached": bool(uy_ok),
        "first_mode_reaching_target": first90,
        "NBC_5_1_period_check": period_check,
        "increase_requested_modes_if_target_not_reached": not (ux_ok and uy_ok),
        "modes_at_or_above_33_Hz": high_modes,
        "missing_mass_correction": "REQUIRED BUT NOT CALCULATED BY THIS AUDIT" if high_modes else "No returned modes at/above 33 Hz; verify requested mode range is sufficient.",
        "horizontal_resisting_system_mode_review": "REQUIRED: inspect and classify mode shapes; code cannot infer which modes belong to the LFRS.",
        "modal_combination": "NOT PERFORMED: apply an accepted method such as CQC/SRSS per NBC 105:2025 §7.4; for closely spaced modes within 15%, observe §7.4(b).",
        "base_shear_scaling": "NOT PERFORMED: compare combined MRSM base shear with ESM base shear and apply §7.5 when required.",
        "rows": rows,
        "story_mode_shapes_csv": str(mode_shape_path) if mode_shape_path else None,
    }
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{report_prefix}.json"
    csv_path = out / f"{report_prefix}.csv"
    txt_path = out / f"{report_prefix}.txt"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    elapsed = time.perf_counter() - started
    result["elapsed_seconds"] = elapsed
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    lines = [
        "NBC 105:2025 MODAL AUDIT — OpenSeesPy",
        f"Modes returned: {n} (requested {nmodes}); solver: {solver}",
        f"90% seismic mass target: UX={ux_final if ux_final is not None else 'unavailable'}% ({'PASS' if ux_ok else 'NOT MET'}), "
        f"UY={uy_final if uy_final is not None else 'unavailable'}% ({'PASS' if uy_ok else 'NOT MET'})",
        f"First mode reaching target: X={first90['X']}, Y={first90['Y']}",
        f"Modes >= {max_frequency_hz:g} Hz: {high_modes or 'none among returned modes'}",
        "NBC §5.1 period check: " + (json.dumps(period_check, sort_keys=True) if period_check else "NOT RUN: supply height/system and (for adopted period) Rayleigh periods."),
        "Missing-mass correction: " + result["missing_mass_correction"],
        result["horizontal_resisting_system_mode_review"],
        result["modal_combination"],
        result["base_shear_scaling"],
        f"Elapsed: {elapsed:.3f} s",
        "",
        "Mode | T(s) | f(Hz) | UX % / cumulative % | UY % / cumulative % | RZ %",
    ]
    for r in rows:
        def fmt(x): return "NA" if x is None else f"{x:.4f}"
        lines.append(f"{r['mode']:>4} | {fmt(r['period_s'])} | {fmt(r['frequency_Hz'])} | "
                     f"{fmt(r['UX_participation_percent'])} / {fmt(r['UX_cumulative_percent'])} | "
                     f"{fmt(r['UY_participation_percent'])} / {fmt(r['UY_cumulative_percent'])} | "
                     f"{fmt(r['RZ_participation_percent'])}")
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[NBC105 MODAL] {'PASS' if ux_ok and uy_ok else 'REVIEW'} | "
          f"UX={ux_final if ux_final is not None else 'NA'}% | "
          f"UY={uy_final if uy_final is not None else 'NA'}% | "
          f">=33Hz modes={len(high_modes)} | elapsed={elapsed:.3f}s")
    return result
