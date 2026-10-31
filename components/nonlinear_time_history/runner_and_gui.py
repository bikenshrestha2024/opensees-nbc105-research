# -*- coding: utf-8 -*-
"""NBC 105:2025 nonlinear paired-component time-history analysis GUI and runner.

The GUI writes a transparent run configuration and launches this file in the
selected OpenSeesPy interpreter. The selected model-builder must create a
complete, genuinely nonlinear 3D model and complete gravity preload. This
runner does not create/calibrate an incomplete ETABS model or perform design.
Execution is OFF by default and requires a reviewed readiness manifest.
"""
from __future__ import annotations

__release__ = '134'
from OpenSees_Timing_V130 import timed_outputs
from OpenSees_Transient_Runtime_V133 import CaseProfiler,save_workload,history_metadata,HistoryStream,acceleration_conversion

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from OpenSees_Runtime_Utilities_V117 import add_path_excitation, excel_cell
from OpenSees_Step13_Analysis_Basis_V115 import rayleigh_coefficients, NBC105_MAX_LINEAR_DAMPING_RATIO

# ---------------------------------------------------------------------------
# SECTION 18 — NONLINEAR TIME-HISTORY USER SETTINGS (execution is OFF by default)
# Set this flag to True in the GUI only after checking the model and records.
# The supplied matched near-field and far-field X/Y components are configured
# as eight orthogonal pairs. The default runs both XY and YX orientations.
# X-only screening remains available separately. Preserve records at scale 1.0.
# ---------------------------------------------------------------------------
RUN_NONLINEAR_TIME_HISTORY = False
from OpenSees_Input_Records_V130 import (
    LTH_DEFAULT_MODE,LTH_X_ONLY_MODE,LTH_MATCHING_METADATA,
    LTH_DEFAULT_X_RECORDS,LTH_DEFAULT_Y_RECORDS,LTH_DEFAULT_PEER_PAIRS,
    _read_peer_text_record,_read_csv,_numeric_record,_read_manifest_component,_read_inputs)





# SECTION 18.1 — CSV / motion input validation (PEER text and paired records)








# SECTION 18.2 — Readiness gate + nonlinear transient solver
def _require_nonlinear_readiness(config):
    """Require an explicit, model-specific checklist before nonlinear NLTHA."""
    model = Path(config["model_script"]).expanduser().resolve()
    path = Path(config.get("model_readiness_json") or
                model.with_name("OpenSees_Model_Readiness_V116.json")).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing NLTHA readiness manifest: {path}. Complete OpenSees_Model_Readiness_Template_V116.json beside the model script.")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    recorded=str(data.get("model_script", "")).strip()
    if not recorded or 'absolute path to' in recorded.lower():
        raise RuntimeError("The selected file is an uncompleted readiness TEMPLATE. Open Prepare / inspect readiness checklist, complete evidenced items and save its model-bound draft. The V136 editor fixes the previously blank checklist. Your nonlinear configuration also needs a reviewed material file and wall FSAM mappings; changing the checklist alone does not create them.")
    bound=Path(recorded).expanduser()
    if not bound.is_absolute():bound=path.parent/bound
    if bound.resolve() != model:
        raise RuntimeError("Readiness file is bound to "+str(bound.resolve())+" but selected model is "+str(model)+". Select the matching file or prepare a new unapproved draft; existing approval cannot be transferred silently.")
    if data.get('model_script_sha256'):
        import hashlib
        if data['model_script_sha256']!=hashlib.sha256(model.read_bytes()).hexdigest():raise RuntimeError('Model script changed after readiness review. Review and save a new model-specific checklist.')
    if data.get("approved_for_nltha") is not True:
        missing=[k.replace('_',' ') for k,v in data.get('checks',{}).items() if v is not True]
        raise RuntimeError("Nonlinear readiness is not approved. Missing prerequisites: "+'; '.join(missing)+". Open the readiness checklist; this cannot be resolved by changing the model path alone.")
    keys = (
        "etabs_topology_and_story_mapping_reviewed", "wall_opening_and_coupling_beam_mesh_reviewed",
        "wall_nonlinear_materials_and_reinforcement_cited_calibrated", "frame_concrete_and_rebar_materials_reviewed",
        "slab_and_diaphragm_idealization_compatible", "area_and_frame_gravity_loads_reconciled_to_etabs",
        "seismic_mass_reconciled_to_etabs_by_storey", "support_conditions_and_foundation_assumptions_reviewed",
        "is16700_initial_pdelta_plus_minus_cases_completed", "p_delta_and_gravity_preload_completed", "modal_periods_modes_and_mass_participation_reviewed",
        "brace_fvd_brb_case_matches_selected_scenario", "device_properties_cited_calibrated_or_devices_disabled",
        "rayleigh_damping_and_device_damping_not_double_counted", "single_element_and_wall_benchmark_checks_passed",
        "record_pair_units_scales_and_nbc_limits_reviewed",
    )
    checks = data.get("checks", {})
    missing = [key for key in keys if checks.get(key) is not True]
    if missing:
        raise RuntimeError("NLTHA readiness checks are incomplete: " + ", ".join(missing))
    return {"path": str(path), "model_script": str(model), "check_count": len(keys)}


def _configure_nonlinear_transient(ops, algorithm="Newton", tolerance=1.0e-7, max_iterations=40):
    ops.wipeAnalysis()
    ops.constraints("Transformation")
    ops.numberer("RCM")
    ops.system("UmfPack")
    ops.test("NormDispIncr", float(tolerance), int(max_iterations), 0)
    ops.algorithm(str(algorithm))
    ops.integrator("Newmark", 0.5, 0.25)
    ops.analysis("Transient")


def _advance_nonlinear_interval(ops, dt, depth=0, max_depth=5, on_accept=None, diagnostics=None):
    """Use Newton-family fallbacks, then bisect a failed time step recursively."""
    failures = []
    diagnostics={} if diagnostics is None else diagnostics
    for algorithm in ("Newton", "NewtonLineSearch", "KrylovNewton", "ModifiedNewton"):
        diagnostics['attempts']=diagnostics.get('attempts',0)+1
        diagnostics['algorithm_'+algorithm]=diagnostics.get('algorithm_'+algorithm,0)+1
        try:
            ops.test("NormDispIncr", 1.0e-7, 40, 0)
            ops.algorithm(algorithm)
            rc = int(ops.analyze(1, float(dt)))
        except Exception as exc:
            rc = -999
            failures.append(f"{algorithm}: {exc}")
        else:
            if rc == 0:
                diagnostics['minimum_accepted_dt_s']=min(float(dt),diagnostics.get('minimum_accepted_dt_s',float(dt)))
                try:diagnostics['max_convergence_iterations']=max(ops.testIter(),diagnostics.get('max_convergence_iterations',0))
                except (AttributeError,TypeError):pass
                if on_accept is not None:on_accept()
                return 1
            failures.append(f"{algorithm}: return code {rc}")
        # Do not retry a domain whose trial state already contains NaN/Inf.
        # Such a retry can propagate a failed linear solve into every element;
        # it does not constitute a convergence recovery.
        for node in ops.getNodeTags():
            displacement = ops.nodeDisp(node)
            if any(not math.isfinite(float(value)) for value in displacement):
                raise RuntimeError(
                    f"Non-finite nodal displacement after {algorithm} failure "
                    f"at node {node}, t={ops.getTime():.6g}s. "
                    "Stopping rather than retrying a contaminated model state.")
    if depth >= max_depth:
        raise RuntimeError(f"Nonlinear step failed at t={ops.getTime():.6g}s, dt={dt:.6g}s after {depth} subdivision levels: " + "; ".join(failures))
    diagnostics['bisections']=diagnostics.get('bisections',0)+1
    half = float(dt) / 2.0
    return (_advance_nonlinear_interval(ops, half, depth + 1, max_depth,on_accept,diagnostics) +
            _advance_nonlinear_interval(ops, half, depth + 1, max_depth,on_accept,diagnostics))


# SECTION 18.3 — Build one fresh model, freeze gravity, and configure damping
@timed_outputs('Nonlinear time history','config')
def _run_analysis(config):
    if not config.get("execute_nonlinear_time_history", False):
        raise RuntimeError("Execution is OFF by default. Enable nonlinear time history only after completing the model-readiness manifest.")
    readiness = _require_nonlinear_readiness(config)
    start = time.perf_counter()
    out = Path(config["output_dir"]); out.mkdir(parents=True, exist_ok=True)
    motions, stories = _read_inputs(config)
    save_workload(motions,config)
    model_length_unit = config.get("model_length_unit", "m")
    if model_length_unit not in ("m", "mm"):
        raise ValueError("model_length_unit must be 'm' or 'mm'.")
    model_length_to_m = 1.0 if model_length_unit == "m" else 0.001
    model_acceleration_unit = "m/s2" if model_length_unit == "m" else "mm/s2"
    g_in_model_units = 9.80665 / model_length_to_m
    audit_rows = []
    for motion in motions:
        for component in (("X", motion["x"], motion["dt_x"]),) if motion.get("mode") == "X_ONLY" else (("X", motion["x"], motion["dt_x"]), ("Y", motion["y"], motion["dt_y"])):
            axis, values, sample_dt = component
            audit_rows.append({"record_or_pair_id": motion["pair_id"], "component": axis,
                "source_path": motion.get(f"{axis.lower()}_path", ""), "samples": len(values), "digitization_dt_s": sample_dt,
                "duration_s": (len(values) - 1) * sample_dt, "minimum_acceleration_input": min(values),
                "maximum_acceleration_input": max(values), "peak_abs_acceleration_input": max(abs(v) for v in values),
                "source_units": motion["units"], "model_acceleration_units": model_acceleration_unit,
                "path_acceleration_factor_to_model_units": acceleration_conversion(motion["units"],model_length_unit,motion["scale"])["total_path_factor"],
                "scale_factor": motion["scale"], "field_type": motion.get("field_type", "Near-field" if motion.get("mode") == "X_ONLY" else "Custom")})
    with (out / "NBC105_Nonlinear_Time_History_Input_Record_Audit_V116.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(audit_rows[0])); writer.writeheader(); writer.writerows(audit_rows)
    print('[UNITS] Source accelerations are converted once to '+model_acceleration_unit+'; g=9.80665 m/s2. Motion scale is separate. See Input_Record_Audit total Path factors.',flush=True)
    print('[SCOPE] '+('PRELIMINARY setup check' if config.get('preliminary_selection') else 'Selected suite')+' | pairs: '+', '.join(m['pair_id'] for m in motions)+' | each pair runs XY and YX',flush=True)
    records = []
    for pair_index, motion in enumerate(motions, 1):
        orientations = ("X_ONLY",) if motion.get("mode") == "X_ONLY" else ("XY", "YX")
        for orientation in orientations:
            case = f"{motion['pair_id']}_{orientation}"
            print(f"[START] {case}: rebuilding nonlinear model and preparing transient analysis", flush=True)
            profiler=CaseProfiler(out,case,"nonlinear")
            phase_clock=time.perf_counter();stream=None
            # Each record/orientation starts with an independently rebuilt model.
            import runpy
            model = Path(config["model_script"]).resolve()
            if not model.is_file(): raise FileNotFoundError(model)
            sys.path.insert(0, str(model.parent))
            if "openseespy.opensees" in sys.modules:
                del sys.modules["openseespy.opensees"]
            os.environ['OPENSEES_LIMIT_STATE']=config['limit_state']
            try:runpy.run_path(str(model), run_name="opensees_ltha_model")
            except BaseException as exc:
                profiler.add('model_and_gravity',phase_clock);profiler.finish('failed',str(exc));raise
            profiler.add('model_and_gravity',phase_clock)
            import openseespy.opensees as ops
            try:
                if not ops.getNodeTags(): raise RuntimeError("The selected model script did not leave an OpenSees model in the domain.")
                node_tags = set(int(x) for x in ops.getNodeTags())
                missing = [s["node"] for s in stories if s["node"] not in node_tags]
                if missing: raise RuntimeError(f"Story master nodes missing from model: {missing}")
                # Freeze the completed gravity state and reset transient time.
                ops.loadConst("-time", 0.0)
                periods = (float(config["damping_period_1_s"]), float(config["damping_period_2_s"]))
                if min(periods) <= 0: raise ValueError("Both Rayleigh calibration periods must be positive.")
                zeta = float(config["damping_ratio_percent"]) / 100.0
                if not 0 < zeta <= NBC105_MAX_LINEAR_DAMPING_RATIO: raise ValueError("NBC 105:2025 §8.1.1 limits linear viscous damping to 5%.")
                alpha_m, beta_kc = rayleigh_coefficients(periods[0], periods[1], zeta)
                ncheck = int(config["modes_to_check"])
                # NBC linear viscous damping model; calibrate at the two
                # user-selected circular frequencies (both mass and stiffness terms).
                phase_clock=time.perf_counter()
                from components.shared.eigen_solver import solve_eigen
                eigenvalues = solve_eigen(ops,ncheck)
                profiler.add('damping_eigenanalysis',phase_clock)
                frequencies = [math.sqrt(float(v)) for v in eigenvalues if float(v) > 0]
                if not frequencies: raise RuntimeError("Eigen analysis returned no positive frequencies for Rayleigh damping check.")
                damping_model=config.get("damping_model","Rayleigh committed")
                if damping_model not in ("Rayleigh committed","Modal (initial eigenbasis)"):raise ValueError("Unknown nonlinear damping model")
                modal_damping = [{"mode": i + 1, "omega_rad_s": w, "period_s": 2 * math.pi / w,
                    "damping_ratio_percent": 100 * (zeta if damping_model=="Modal (initial eigenbasis)" else alpha_m / (2 * w) + beta_kc * w / 2)} for i, w in enumerate(frequencies)]
                exceeded = [r for r in modal_damping if r["damping_ratio_percent"] > 5.0 + 1e-8]
                if exceeded:
                    raise RuntimeError("Rayleigh damping exceeds NBC's 5% limit in the checked modes: " + ", ".join(f"mode {r['mode']}={r['damping_ratio_percent']:.3f}%" for r in exceeded) + ". Change calibration periods and review the full modal range.")
                if damping_model=='Modal (initial eigenbasis)':
                    ops.rayleigh(0.,0.,0.,0.)
                    ops.modalDamping(*([zeta]*len(frequencies)))
                    alpha_m=beta_kc=0.
                else:ops.rayleigh(alpha_m, 0.0, 0.0, beta_kc)
                print('[DAMPING] '+damping_model+' | checked initial modes='+str(len(frequencies))+' | target='+str(100*zeta)+'%; Rayleigh committed ratios may evolve during yielding',flush=True)
                # The record scale factor is already verified to satisfy NBC's
                # 0.33–3 bound; g-valued records are converted to m/s².
                # Convert source acceleration into the model's length/time unit.
                # g is 9.80665 m/s²: use 9.80665 for m-s and 9806.65 for mm-s.
                accel_factor = acceleration_conversion(motion["units"],model_length_unit,motion["scale"])["total_path_factor"]
                record_dir = out / "record_inputs"; record_dir.mkdir(exist_ok=True)
                # SECTION 18.3 — Apply either the X-only screening record or
                # both components of a 3D pair. The paired branch also runs YX.
                if orientation == "X_ONLY":
                    x_acc, dx = motion["x"], motion["dt_x"]
                    y_acc, dy = [], dx
                    series = ((1, 1, 1, x_acc, dx, "X"),)
                else:
                    x_acc, y_acc = (motion["x"], motion["y"]) if orientation == "XY" else (motion["y"], motion["x"])
                    dx, dy = (motion["dt_x"], motion["dt_y"]) if orientation == "XY" else (motion["dt_y"], motion["dt_x"])
                    series = ((1, 1, 1, x_acc, dx, "X"), (2, 2, 2, y_acc, dy, "Y"))
                for ts, pat, direction, values, dt_rec, comp in series:
                    values_path = record_dir / f"{motion['pair_id']}_{orientation}_{comp}.dat"
                    values_path.write_text("\n".join(f"{v:.12g}" for v in values) + "\n", encoding="ascii")
                    ts, pat = add_path_excitation(ops, direction=direction, dt=dt_rec, file_path=values_path, factor=accel_factor)
                dt_record = dx if orientation == "X_ONLY" else min(dx, dy)
                if orientation == "X_ONLY":
                    t1, tn = float(config["T1_x_s"]), float(config["Tn_x_s"])
                else:
                    t1 = min(float(config["T1_x_s"]), float(config["T1_y_s"]))
                    tn = min(float(config["Tn_x_s"]), float(config["Tn_y_s"]))
                if min(t1, tn) <= 0: raise ValueError("Enter positive NBC directional T1 and Tn values.")
                # NBC §9.3.2.4 lists T1/100, Tn, and 0.01 s as independent
                # upper bounds; the Tn term is not divided by 100.
                dt = min(dt_record, t1 / 100.0, tn, 0.01)
                duration = (len(motion["x"]) - 1) * motion["dt_x"] if orientation == "X_ONLY" else max((len(motion["x"]) - 1) * motion["dt_x"], (len(motion["y"]) - 1) * motion["dt_y"])
                nsteps = int(math.ceil(duration / dt))
                # SECTION 18.4 — Nonlinear Newmark. NBC §9.3.2.4 keeps Tn as
                # an independent step bound; it is not Tn/100.
                _configure_nonlinear_transient(ops)
                # Record every accepted adaptive substep, including intermediate peaks.
                gravity_offsets={s["node"]:list(ops.nodeDisp(s["node"])) for s in stories}
                csv_path=out / f"NBC105_NLTHA_{case}_history.csv"
                stream=HistoryStream(csv_path)
                history_metadata(csv_path,config['model_script'],stories,config['limit_state'],status='running')
                next_progress_at=time.perf_counter()+10.
                lines = []
                def record_accepted():
                    sample_clock=time.perf_counter()
                    row = {"time_s": float(ops.getTime())}
                    for story in stories:
                        disp = ops.nodeDisp(story["node"])
                        row[f"{story['story_name']}_UX_m"] = (float(disp[0])-gravity_offsets[story["node"]][0]) * model_length_to_m
                        row[f"{story['story_name']}_UY_m"] = (float(disp[1])-gravity_offsets[story["node"]][1]) * model_length_to_m
                        row[f"{story['story_name']}_RZ_rad"] = float(disp[5])-gravity_offsets[story["node"]][5] if len(disp)>5 else 0.
                    for i, story in enumerate(stories):
                        for axis, col in (("X", "UX"), ("Y", "UY")):
                            current = row[f"{story['story_name']}_{col}_m"]
                            below = row[f"{stories[i-1]['story_name']}_{col}_m"] if i else 0.0
                            row[f"{story['story_name']}_drift_{axis}"] = (current - below) / story["height"]
                    row["accepted_internal_substeps"] = 1
                    lines.append(row)
                    stream.append(row)
                    profiler.internal_steps+=1
                    profiler.sample_seconds+=time.perf_counter()-sample_clock
                profiler.solve_clock=time.perf_counter()
                for step in range(nsteps):
                    dt_this = min(dt, max(0.0, duration - float(ops.getTime())))
                    if dt_this <= 1.0e-12: break
                    substeps = _advance_nonlinear_interval(ops, dt_this, on_accept=record_accepted,diagnostics=profiler.solver_diagnostics)
                    if (step + 1) % max(1, nsteps // 20) == 0 or time.perf_counter()>=next_progress_at:
                        print(f"[PROGRESS] {case}: {step + 1}/{nsteps} steps, t={ops.getTime():.3f}s", flush=True)
                        profiler.progress(step+1,nsteps);stream.flush();next_progress_at=time.perf_counter()+10.
                profiler.add('transient_with_recording',profiler.solve_clock)
                phase_clock=time.perf_counter()
                # SECTION 18.6 — Save case history and response/drift summary.
                csv_path = out / f"NBC105_NLTHA_{case}_history.csv"
                stream.close()
                history_metadata(csv_path,config['model_script'],stories,config['limit_state'])
                from OpenSees_Response_Checks_V132 import export_history_checks
                edge_peaks=export_history_checks(lines,stories,out,case,config['limit_state'],config['model_script'])
                drift_limit = 0.025 if config["limit_state"] == "ULS" else 0.006
                peak = {"case": case, "pair_id": motion["pair_id"], "field_type": motion.get("field_type", "Custom"), "orientation": orientation,
                    "scale_factor": motion["scale"], "acceleration_units": motion["units"], "record_dt_min_s": dt_record,
                    "analysis_dt_max_s": dt, "duration_s": duration, "requested_steps": nsteps,
                    "peak_roof_UX_m": max(abs(r[f"{stories[-1]['story_name']}_UX_m"]) for r in lines),
                    "peak_roof_UY_m": max(abs(r[f"{stories[-1]['story_name']}_UY_m"]) for r in lines),
                    "minimum_roof_UX_m": min(r[f"{stories[-1]['story_name']}_UX_m"] for r in lines),
                    "maximum_roof_UX_m": max(r[f"{stories[-1]['story_name']}_UX_m"] for r in lines),
                    "minimum_roof_UY_m": min(r[f"{stories[-1]['story_name']}_UY_m"] for r in lines),
                    "maximum_roof_UY_m": max(r[f"{stories[-1]['story_name']}_UY_m"] for r in lines),
                    "peak_story_drift_X": max(abs(r[f"{s['story_name']}_drift_X"]) for r in lines for s in stories),
                    "peak_story_drift_Y": max(abs(r[f"{s['story_name']}_drift_Y"]) for r in lines for s in stories),
                    "minimum_story_drift_X": min(r[f"{s['story_name']}_drift_X"] for r in lines for s in stories),
                    "maximum_story_drift_X": max(r[f"{s['story_name']}_drift_X"] for r in lines for s in stories),
                    "minimum_story_drift_Y": min(r[f"{s['story_name']}_drift_Y"] for r in lines for s in stories),
                    "maximum_story_drift_Y": max(r[f"{s['story_name']}_drift_Y"] for r in lines for s in stories),
                    "drift_limit_ratio": drift_limit,
                    "drift_screen_X": "PASS" if max(abs(r[f"{s['story_name']}_drift_X"]) for r in lines for s in stories) <= drift_limit else "REVIEW",
                    "drift_screen_Y": "PASS" if max(abs(r[f"{s['story_name']}_drift_Y"]) for r in lines for s in stories) <= drift_limit else "REVIEW",
                    "damping_model":damping_model,"damping_check_scope":"Initial eigenmodes; committed-stiffness Rayleigh ratios can change during yielding",
                    "rayleigh_alphaM_s-1": alpha_m, "rayleigh_betaKcommitted_s": beta_kc,
                    "rayleigh_calibration_periods_s": periods, "checked_modal_damping": modal_damping,
                    "history_csv": str(csv_path), "model_readiness_manifest": readiness["path"]}
                for axis,value in edge_peaks.items():
                    peak['master_peak_story_drift_'+axis]=peak['peak_story_drift_'+axis]
                    peak['floor_edge_peak_story_drift_'+axis]=value
                    peak['peak_story_drift_'+axis]=max(peak['peak_story_drift_'+axis],value)
                    peak['drift_screen_'+axis]='PASS' if peak['peak_story_drift_'+axis]<=drift_limit else 'REVIEW'
                profiler.add('case_exports_and_drift',phase_clock)
                peak['performance']=profiler.finish()
                records.append(peak)
                print(f"[OK] {case}: steps={nsteps}, dt={dt:.6g}s, peak drifts X/Y={peak['peak_story_drift_X']:.6g}/{peak['peak_story_drift_Y']:.6g}", flush=True)
            finally:
                if stream is not None:stream.close()
                if not profiler.complete:
                    if stream is not None:history_metadata(stream.path,config['model_script'],stories,config['limit_state'],status='incomplete / inspect failure log')
                    profiler.finish('failed',str(sys.exc_info()[1]))
                try: ops.wipe()
                except Exception: pass
    # NBC §8.1.3 statistic is applied to pair-level response demands. The two
    # required direction-swapped runs are enveloped within each orthogonal pair;
    # the response statistic is then selected by the number of record pairs.
    pair_peak_keys = ("peak_roof_UX_m", "peak_roof_UY_m", "peak_story_drift_X", "peak_story_drift_Y")
    pair_demands = []
    for pair_id in dict.fromkeys(r["pair_id"] for r in records):
        pair_cases = [r for r in records if r["pair_id"] == pair_id]
        demand = {"pair_id": pair_id, "field_type": pair_cases[0].get("field_type", "Custom"),
                  "orientations_included": [r["orientation"] for r in pair_cases]}
        for key in pair_peak_keys:
            demand[key] = max(r[key] for r in pair_cases)
        pair_demands.append(demand)

    def _aggregate_pair_set(selected, label):
        n_pairs = len(selected)
        if n_pairs == 7:
            method = "REVIEW_REQUIRED: NBC §8.1.3 wording does not specify exactly seven"
            aggregate = {key: None for key in pair_peak_keys}
        elif n_pairs < 7:
            method = "maximum of pair-level orientation envelopes (fewer than 7 pairs)"
            aggregate = {key: max(d[key] for d in selected) for key in pair_peak_keys} if selected else {}
        else:
            method = "arithmetic mean of pair-level orientation envelopes (more than 7 pairs)"
            aggregate = {key: sum(d[key] for d in selected) / n_pairs for key in pair_peak_keys} if selected else {}
        for axis in ("X", "Y"):
            key = f"peak_story_drift_{axis}"
            if aggregate.get(key) is not None:
                limit = 0.025 if config["limit_state"] == "ULS" else 0.006
                aggregate[f"drift_screen_{axis}"] = "PASS" if aggregate[key] <= limit else "REVIEW"
        return {"set": label, "pair_count": n_pairs, "statistic": method, "response_demands": aggregate}

    aggregation = {"all_selected_pairs": _aggregate_pair_set(pair_demands, "all selected records")}
    for field_type in dict.fromkeys(d["field_type"] for d in pair_demands):
        subset = [d for d in pair_demands if d["field_type"] == field_type]
        aggregation[f"{field_type.lower().replace('-', '_')}_subset"] = _aggregate_pair_set(subset, field_type)

    x_envelope = None
    if config.get("motion_mode") == "X_ONLY_SCREENING":
        x_envelope = {"basis": "maximum across six individual X records per NBC §8.1.3 (<7 records)",
            "peak_roof_UX_m": max(r["peak_roof_UX_m"] for r in records),
            "peak_story_drift_X": max(r["peak_story_drift_X"] for r in records),
            "drift_screen_X": "PASS" if max(r["peak_story_drift_X"] for r in records) <= (0.025 if config["limit_state"] == "ULS" else 0.006) else "REVIEW"}
    summary = {"standard": "NBC 105:2025", "analysis": "Nonlinear paired-component time history", "input_mode": config.get("motion_mode", "PAIRED_3D"),
        "directional_scope": "X-only screening; not a full NBC paired-component 3D verification" if config.get("motion_mode") == "X_ONLY_SCREENING" else f"{len(motions)} selected orthogonal 3D pairs; XY and YX orientations",
        "record_metadata": {"site_soil": "C", "period_range_s": [0.05, 6.0], "record_set": "User-selected X-only SeismoMatch/PEER screening records"} if config.get("motion_mode") == "X_ONLY_SCREENING" else LTH_MATCHING_METADATA,
        "model_length_unit": model_length_unit, "model_acceleration_unit": model_acceleration_unit,
        "clauses": ["3.2.3", "8.1.1", "8.1.2", "8.1.3", "9.3.2", "9.3.3"],
        "model_script": config["model_script"], "model_readiness_manifest": readiness, "limit_state_context": config["limit_state"], "torsion_sensitive": config["torsion_sensitive"],
        "record_pairs": len(motions) if config.get("motion_mode") != "X_ONLY_SCREENING" else 0,
        "individual_record_count": len(motions), "motion_case_count": len(records),
        "pair_aggregation_guidance": "For each orthogonal pair, the two required swapped-orientation analyses are enveloped by taking the larger peak demand for each response quantity. NBC §8.1.3 then selects maximum for fewer than 7 pairs or arithmetic mean for more than 7 pairs. The supplied combined suite has 8 pairs; near-field (6) and far-field (2) subgroup statistics are reported separately for comparison. Exactly 7 is left flagged because the clause wording does not specify it.",
        "response_aggregation_by_record_set": aggregation, "pair_level_orientation_envelopes": pair_demands,
        "X_only_screening_envelope": x_envelope,
        "T1_x_s": config["T1_x_s"], "T1_y_s": config["T1_y_s"], "Tn_x_s": config["Tn_x_s"], "Tn_y_s": config["Tn_y_s"],
        "damping_target_percent": config["damping_ratio_percent"], "time_step_rule": "min(record digitization interval, T1/100, Tn, 0.01 s)",
        "member_action_rule": "Nonlinear inelastic deformation demands require material-standard limits under NBC 9.3.3.2. Do not divide nonlinear response actions by Rmu using the elastic-history rule. Component capacities and acceptance remain separately reviewed.",
        "records": records, "elapsed_seconds": time.perf_counter() - start}
    (out / "NBC105_Nonlinear_Time_History_Summary_V116.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # Optional overview plot and workbook; raw histories remain in CSV regardless.
    warnings = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        labels = [r["case"] for r in records]
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
        for i,axis in enumerate(('X','Y')):
            axes[i,0].bar(labels,[r['peak_roof_U'+axis+'_m']*1000 for r in records],color='#315b8a')
            axes[i,0].set(title='Peak relative roof displacement '+axis,ylabel='mm')
            axes[i,1].bar(labels,[r['peak_story_drift_'+axis] for r in records],color='#bb4a55')
            axes[i,1].set(title='Peak interstorey drift '+axis,ylabel='drift ratio')
            for ax in axes[i]:ax.tick_params(axis='x',rotation=25,labelsize=7);ax.grid(axis='y',alpha=.25)
        scope='PRELIMINARY' if config.get('preliminary_selection') else 'Selected suite'
        fig.suptitle(f"{config['limit_state']} | Nonlinear time history | {scope} | XY / YX")
        fig.savefig(out / "NBC105_Nonlinear_Time_History_V116.png", dpi=170); plt.close(fig)
        if config.get("motion_mode") == "X_ONLY_SCREENING":
            fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
            for record in records:
                hist = _read_csv(record["history_csv"])
                roof_key = f"{stories[-1]['story_name']}_UX_m"
                ax.plot([float(r["time_s"]) for r in hist], [1000 * float(r[roof_key]) for r in hist], linewidth=.7, label=record["pair_id"])
            ax.set(title="X-direction screening: relative roof displacement histories", xlabel="Time (s)", ylabel="Relative roof Ux (mm)")
            ax.grid(True, alpha=.25); ax.legend(fontsize=7, ncol=2)
            fig.savefig(out / "NBC105_Nonlinear_Time_History_Roof_UX_Histories_V116.png", dpi=160); plt.close(fig)
    except Exception as exc: warnings.append(f"Matplotlib overview unavailable: {exc}")
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        wb = Workbook(); ws = wb.active; ws.title = "Case Summary"
        headers = list(records[0]) if records else []
        ws.append(headers)
        for r in records: ws.append([excel_cell(r.get(h)) for h in headers])
        for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="244062")
        ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
        agg_sheet = wb.create_sheet("NBC Aggregation")
        agg_sheet.append(["Record set", "Pair count", "NBC statistic", *pair_peak_keys, "Drift screen X", "Drift screen Y"])
        for group in aggregation.values():
            response = group["response_demands"]
            agg_sheet.append([group["set"], group["pair_count"], group["statistic"],
                *[response.get(k) for k in pair_peak_keys], response.get("drift_screen_X"), response.get("drift_screen_Y")])
        agg_sheet.freeze_panes = "A2"
        for c in agg_sheet[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="244062")
        info = wb.create_sheet("Method and checks")
        for row in [("Standard", "NBC 105:2025"), ("Analysis", "Nonlinear inelastic time history"), ("References", "§§3.2.3, 8.1.1–8.1.3, 9.3.2–9.3.3"),
                    ("Rayleigh formulation", "C = alphaM*M + betaKcommitted*Kcommitted"),
                    ("Rayleigh coefficients", "alphaM=2*zeta*w1*w2/(w1+w2); betaKcommitted=2*zeta/(w1+w2)"),
                    ("Damping cap", "Rayleigh damping checked at selected modes; <=5% per NBC §8.1.1; FVD device damping is explicit and must not be double-counted"),
                    ("Time step", "min(record digitization interval, T1/100, Tn, 0.01 s)"),
                    ("Ground motion scaling", "User-supplied; target matching is not performed by this utility"),
                    ("Gravity state", "Model-builder must complete gravity first; runner then calls ops.loadConst('-time',0.0)"),
                    ("Relative response", "UniformExcitation node response is relative to ground motion"),
                    ("Aggregation", summary["pair_aggregation_guidance"]),
                    ("Drift screening", "ULS 0.025; SLS 0.006 per numerical values in NBC §5.5.3. §8.1.3.1 cross-references §5.6, which is accidental eccentricity in the 2025 edition; this discrepancy is flagged for engineer review."),
                    ("Design boundary", "Nonlinear component acceptance uses material-standard deformation limits (NBC 9.3.3.2); no elastic-history Rmu reduction is applied.")]: info.append(row)
        info.column_dimensions["A"].width = 28; info.column_dimensions["B"].width = 110
        for i, record in enumerate(records, 1):
            # Preserve every time-history result as a separate worksheet too.
            rows = _read_csv(record["history_csv"])
            sh = wb.create_sheet(f"Hist{i}_{record['orientation']}"[:31])
            if rows:
                sh.append(list(rows[0]))
                for r in rows: sh.append([r.get(h) for h in rows[0]])
                for c in sh[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="244062")
                sh.freeze_panes = "A2"; sh.auto_filter.ref = sh.dimensions
        wb.save(out / "NBC105_Nonlinear_Time_History_V116.xlsx")
    except Exception as exc: warnings.append(f"Excel workbook unavailable: {exc}")
    summary['selected_pair_ids']=config.get('selected_pair_ids')
    summary['preliminary_selection']=bool(config.get('preliminary_selection',False))
    summary['assessment_scope']='PRELIMINARY SETUP CHECK — not a completed suite assessment' if config.get('preliminary_selection') else 'Selected suite; review record-set adequacy independently'
    if warnings: summary["output_warnings"] = warnings
    (out / "NBC105_Nonlinear_Time_History_Summary_V116.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[COMPLETE] {len(records)} motion/orientation cases; elapsed={summary['elapsed_seconds']:.2f}s; output={out}", flush=True)
    for warning in warnings: print(f"[WARNING] {warning}", flush=True)


class NonlinearTimeHistoryGUI:
    def __init__(self, parent=None):
        self.win = tk.Toplevel(parent) if parent else tk.Tk()
        self.win.title("OpenSeesPy — Nonlinear Time History | NBC 105:2025")
        self.win.geometry("1120x880"); self.win.minsize(900, 700)
        self.model = tk.StringVar(); self.python = tk.StringVar(value=sys.executable)
        self.model_length_unit = tk.StringVar(value="m")
        self.manifest = tk.StringVar(); self.stories = tk.StringVar(); self.output = tk.StringVar(); self.readiness = tk.StringVar()
        self.damping_model=tk.StringVar(value="Rayleigh committed")
        self.damping = tk.StringVar(value="5.0"); self.p1 = tk.StringVar(); self.p2 = tk.StringVar()
        self.t1x = tk.StringVar(); self.t1y = tk.StringVar(); self.tnx = tk.StringVar(); self.tny = tk.StringVar()
        self.nmodes = tk.StringVar(value="20"); self.ls = tk.StringVar(value="ULS")
        self.torsion = tk.BooleanVar(value=True); self.running = False
        self.motion_mode = tk.StringVar(value=LTH_DEFAULT_MODE)
        self.x_scale = tk.StringVar(value="1.0")
        self.pair_scale = tk.StringVar(value="1.0")
        self.x_record_paths = list(LTH_DEFAULT_X_RECORDS)
        self.y_record_paths = list(LTH_DEFAULT_Y_RECORDS)
        self.execute = tk.BooleanVar(value=RUN_NONLINEAR_TIME_HISTORY)
        self._build()
        from OpenSees_Linear_Autofill_V124 import populate_available
        ttk.Button(self.win,text='Refresh available project inputs',command=lambda:populate_available(self,role='nonlinear_model_script')).pack(anchor='w')
        self.win.after_idle(lambda:populate_available(self,role='nonlinear_model_script'))
        self.model.trace_add('write',lambda *unused:self.win.after_idle(lambda:__import__('OpenSees_Linear_Autofill_V124').populate_linear(self,Path(self.model.get()).parent)) if self.model.get() else None)
        self.ls.trace_add('write',lambda *unused:populate_available(self,role='nonlinear_model_script'))

    def _browse(self, variable, kind, title):
        if kind == "file": value = filedialog.askopenfilename(title=title, parent=self.win, filetypes=[("CSV files", "*.csv"), ("Python files", "*.py"), ("All files", "*.*")])
        elif kind == "python": value = filedialog.askopenfilename(title=title, parent=self.win, filetypes=[("Python executable", "python.exe"), ("All files", "*.*")])
        else: value = filedialog.askdirectory(title=title, parent=self.win)
        if value: variable.set(value)

    def _entry(self, parent, label, variable, browse=None):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=30).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True)
        if browse: ttk.Button(row, text="Browse…", command=browse).pack(side="left", padx=(5, 0))

    def _build(self):
        from OpenSees_Research_UI_V123 import scrollable_form
        root = scrollable_form(self.win)
        ttk.Label(root, text="NBC 105:2025 NONLINEAR TIME HISTORY", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(root, text="Nonlinear Newmark 3D transient analysis • orthogonal record pairs • solver fallbacks and bounded step subdivision • drift histories + audit outputs", wraplength=1060).pack(anchor="w", pady=(3, 8))
        inputs = ttk.LabelFrame(root, text="1. Reviewed nonlinear OpenSees model and project inputs", padding=8); inputs.pack(fill="x")
        self._entry(inputs, "Nonlinear model-builder script", self.model, lambda: self._browse(self.model, "file", "Select complete nonlinear OpenSeesPy model script"))
        self._entry(inputs, "Python interpreter with OpenSeesPy", self.python, lambda: self._browse(self.python, "python", "Select OpenSeesPy Python interpreter"))
        unit_row = ttk.Frame(inputs); unit_row.pack(fill="x", pady=3)
        ttk.Label(unit_row, text="Model length unit", width=30).pack(side="left")
        ttk.Combobox(unit_row, textvariable=self.model_length_unit, values=("m", "mm"), state="readonly", width=10).pack(side="left")
        ttk.Label(unit_row, text="Choose the length unit used by the model script (kN–m–s or kN–mm–s). g records are converted to m/s² or mm/s²; response displacements are exported in metres.", wraplength=780).pack(side="left", padx=8)
        mode_row = ttk.Frame(inputs); mode_row.pack(fill="x", pady=3)
        ttk.Label(mode_row, text="Ground-motion input mode", width=30).pack(side="left")
        mode_box = ttk.Combobox(mode_row, textvariable=self.motion_mode, state="readonly", values=(LTH_DEFAULT_MODE, LTH_X_ONLY_MODE))
        mode_box.pack(side="left", fill="x", expand=True)
        self._entry(inputs, "Optional custom pair manifest CSV", self.manifest, lambda: self._browse(self.manifest, "file", "Select custom ground motion pair manifest"))
        self._entry(inputs, "Common X/Y pair scale factor", self.pair_scale)
        from OpenSees_Pair_Selection_V128 import PairSelector
        self.pair_selector=PairSelector(inputs,self.manifest,LTH_DEFAULT_PEER_PAIRS)
        ttk.Label(inputs, text=f"Default: {len(LTH_DEFAULT_PEER_PAIRS)} preloaded X/Y pairs: 6 near-field + 2 far-field, matched in SeismoMatch for Soil C over 0.05–6 s. Both components use the same factor (1.0 preserves your verified records); XY and YX orientations run. A custom manifest replaces this default set.", wraplength=1040, foreground="#45556b").pack(anchor="w", pady=(2, 5))
        xrow = ttk.Frame(inputs); xrow.pack(fill="x", pady=3)
        ttk.Label(xrow, text="X-only screening records", width=30).pack(side="left")
        self.x_count = ttk.Label(xrow, text=f"{len(self.x_record_paths)} files selected (SeismoMatch PEER text)")
        self.x_count.pack(side="left", fill="x", expand=True)
        ttk.Button(xrow, text="Select X records…", command=self._select_x_records).pack(side="left", padx=(5, 0))
        self._entry(inputs, "Common X record scale factor", self.x_scale)
        ttk.Label(inputs, text="X-only screening remains available separately; those records are not substituted for missing Y components. Pair defaults preserve the user-supplied PEER/SeismoMatch time histories and parse each component's own time step and units.", wraplength=1040, foreground="#45556b").pack(anchor="w", pady=(2, 5))
        self._entry(inputs, "Story master-node CSV", self.stories, lambda: self._browse(self.stories, "file", "Select story master-node mapping"))
        self._entry(inputs, "NLTHA readiness manifest", self.readiness, lambda: self._browse(self.readiness, "file", "Select completed OpenSees_Model_Readiness_V116.json"))
        ttk.Button(inputs,text="Prepare / inspect model-bound readiness checklist",command=lambda:__import__("OpenSees_Readiness_GUI_V134").launch(self.win,self.model.get(),self.readiness)).pack(anchor="w")
        ttk.Button(inputs,text="Run separate literature nonlinear demo (no building approval)",command=lambda:__import__("OpenSees_Literature_Demo_GUI_V137").launch(self.win)).pack(anchor="w")
        ttk.Button(inputs,text="Current building: exploratory nonlinear frames / elastic walls",command=lambda:__import__("OpenSees_Building_Exploratory_GUI_V138").launch(self.win,Path(self.model.get()).parent,self.output.get())).pack(anchor="w")
        self._entry(inputs, "One-folder output directory", self.output, lambda: self._browse(self.output, "dir", "Select output folder"))
        ttk.Button(inputs, text="Write CSV templates", command=self._templates).pack(anchor="e", pady=(5, 0))
        params = ttk.LabelFrame(root, text="2. NBC period, damping and time-step checks", padding=8); params.pack(fill="x", pady=8)
        damping_row=ttk.Frame(params);damping_row.pack(fill='x')
        ttk.Label(damping_row,text='Nonlinear viscous damping model').pack(side='left')
        ttk.Combobox(damping_row,textvariable=self.damping_model,values=['Rayleigh committed','Modal (initial eigenbasis)'],state='readonly',width=30).pack(side='left')
        ttk.Label(params,text='Damping is a project assumption: 5% is a limit, not a measured value. Modal damping uses converged Newton iterations; explicit FVD damping remains separate. See Chopra & McKenna (2016), doi:10.1002/eqe.2622.',wraplength=1060).pack(anchor='w')
        grid = ttk.Frame(params); grid.pack(fill="x")
        fields = [("ULS/SLS context", self.ls), ("Damping target (%) — max 5", self.damping), ("Rayleigh period 1 (s)", self.p1), ("Rayleigh period 2 (s)", self.p2),
                  ("T1 X (s)", self.t1x), ("T1 Y (s)", self.t1y), ("Tn X (s), ≥90% mass", self.tnx), ("Tn Y (s), ≥90% mass", self.tny), ("Modes to check for ζ≤5%", self.nmodes)]
        for i, (label, var) in enumerate(fields):
            ttk.Label(grid, text=label).grid(row=i // 3, column=(i % 3) * 2, sticky="w", padx=(0, 4), pady=3)
            if var is self.ls: ttk.Combobox(grid, textvariable=var, values=("ULS", "SLS"), state="readonly", width=11).grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="ew", padx=(0, 12))
            else: ttk.Entry(grid, textvariable=var, width=12).grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="ew", padx=(0, 12))
        for c in range(6): grid.columnconfigure(c, weight=1 if c % 2 else 0)
        ttk.Checkbutton(params, text="Torsionally sensitive 3D structure (requires at least 3 orthogonal motion pairs)", variable=self.torsion).pack(anchor="w", pady=(5, 0))
        ttk.Label(params, text="T1 is from NBC §5.1 (lesser adopted period); Tn is the highest mode needed for 90% mass participation in each axis. Obtain/verify these in the Modal Analysis GUI. The chosen Rayleigh calibration periods and checked modal damping must keep all inspected modes ≤5%.", wraplength=1060, foreground="#8a3412").pack(anchor="w", pady=(5, 0))
        ttk.Label(root, text="Readiness is intentionally strict: the nonlinear model must already contain the reviewed ETABS geometry, wall opening mesh and coupling beams, calibrated wall/frame materials, compatible slab/diaphragm representation, reconciled area/frame loads and seismic mass, completed gravity/P-Delta, modal checks, and the selected SHS/FVD/BRB scenario. This tool freezes that completed gravity state with loadConst(time=0) and runs nonlinear Newmark. It cannot make a missing ETABS-to-OpenSees subsystem complete. The manifest is an explicit user checklist, not an automatic certification.", wraplength=1060, foreground="#8a3412").pack(anchor="w", pady=(0, 8))
        ttk.Button(root, text="NBC site spectrum + optional X/Y scale diagnostic (A–D)", command=self._open_spectrum_tool).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(root, text="RUN_NONLINEAR_TIME_HISTORY = True  —  enable execution (default False)", variable=self.execute).pack(anchor="w", pady=(0, 4))
        ttk.Button(root, text="Run NBC Nonlinear Time-History Cases", command=self._run).pack(anchor="w", pady=(0, 8))
        ttk.Button(root,text='Performance objectives / component acceptance',command=lambda:__import__('components.validation.nonlinear_performance',fromlist=['launch']).launch(self.win,self.output.get())).pack(anchor='w',pady=4)
        ttk.Button(root,text='Completed run graphs / Excel / unit audit',command=lambda:__import__('OpenSees_History_Results_V134').launch(self.win,self.output.get())).pack(anchor='w',pady=4)
        tabs = ttk.Notebook(root); tabs.pack(fill="both", expand=True)
        self.log = tk.Text(tabs, bg="#0b1220", fg="#dbeafe", insertbackground="white", font=("Cascadia Mono", 9), wrap="word")
        tabs.add(self.log, text="Run log")
        notes = tk.Text(tabs, wrap="word", font=("Segoe UI", 10)); notes.insert("1.0", "NBC 105:2025 nonlinear time-history guide\n\n• §9.3: nonlinear response-history analysis needs a 3D nonlinear model, gravity/P-Delta state, damping, compatible wall/brace material laws, and documented ground-motion scaling.\n• §9.3.2.2: use the ULS target C(T)/Ωu over Tn through √Rμ × T1; each scale factor is 0.33–3.0; a 3D pair uses the lower of X/Y factors for both components. Pre-matched SeismoMatch records are passed unchanged at factor 1.0 unless the verified project workflow says otherwise.\n• §9.3.2.4: Δt ≤ record digitization interval, T1/100, Tn and 0.01 s. Tn is its own upper bound (not Tn/100).\n• §9.3.2.3 / 9.3.3: run both horizontal component orientations within each record pair and apply the code response statistic to pair-level envelopes.\n• Soil spectra: §4.1.2, Eq. 4.1(2), Table 4-1. Select site class from geotechnical evidence under §4.1.3.3; Kirtipur Ward 10 is listed as D in Table 4-3, subject to site investigation.\n• Damping: two-term Rayleigh coefficients are calculated at user-entered periods; the five-percent limit is checked on selected modes. Explicit FVD dissipation must not be counted again as Rayleigh damping. Nonlinear model material damping is separate from record scaling.\n• Drift screen: NBC §5.5.3 states 0.025 ULS and 0.006 SLS; review the NBC §9.3.3.1 cross-reference discrepancy before treating the screen as design acceptance. This runner reports drift and histories only; no member design is performed.\n• Solver recovery: Newton, NewtonLineSearch, KrylovNewton and ModifiedNewton are attempted; only then is the requested step recursively divided, within a bounded subdivision depth. A failed case remains a failure; convergence recovery does not establish model validity.\n\nReadiness gate: the JSON sign-off manifest must be complete for wall openings/coupling beams, frame and wall material calibration, area loads, total floor seismic mass, slab/diaphragm representation, gravity/P-Delta, modal checks, brace/device scenario, and independent benchmark checks. This is a user review record, not automated verification.\n\nReferences\n• NBC 105:2025 §§4.1.1–4.1.3, 5.1, 5.2, 5.5.3, 8.1.1–8.1.3, 9.3.2–9.3.3. DUDBC: https://www.dudbc.gov.np/pages/building-code/\n• OpenSeesPy Path TimeSeries: https://openseespydoc.readthedocs.io/en/latest/src/pathTs.html\n• OpenSeesPy UniformExcitation: https://openseespydoc.readthedocs.io/en/latest/src/uniformExcitation.html\n• OpenSeesPy Newmark: https://openseespydoc.readthedocs.io/en/latest/src/newmark.html\n• E-SFI-MVLEM-3D: Kolozvari, Lopez & Massone (2023), Eng. Struct. 294, 116700, doi:10.1016/j.engstruct.2023.116700; https://github.com/kkolozvari/E-SFI-MVLEM-3D\n\nMatched SeismoMatch/PEER input values, sampling intervals and units are read from the records and preserved. g-to-model-unit conversion is separate from spectrum scaling.")
        notes.configure(state="disabled"); tabs.add(notes, text="NBC clauses + citations")

    def _templates(self):
        folder = filedialog.askdirectory(title="Choose where to write CSV templates", parent=self.win)
        if not folder: return
        p = Path(folder)
        (p / "NBC105_LTH_Motion_Pairs_Template.csv").write_text("pair_id,component_x_path,component_y_path,dt_x_s,dt_y_s,units,scale_factor\nPair01,record_X.dat,record_Y.dat,0.005,0.005,g,1.0\n", encoding="utf-8-sig")
        (p / "NBC105_LTH_Story_Master_Nodes_Template.csv").write_text("story_number,story_name,master_node_tag,elevation_m\n1,Storey 1,101,3.0\n2,Storey 2,201,6.0\n", encoding="utf-8-sig")
        messagebox.showinfo("Templates written", f"Edit the verified templates in:\n{p}", parent=self.win)

    def _open_spectrum_tool(self):
        try:
            from NBC105_Spectrum_Scaling_V115 import launch_spectrum_gui
            app=launch_spectrum_gui(self.win)
            from OpenSees_Linear_Autofill_V124 import populate_spectrum
            populate_spectrum(app,self)
        except Exception as exc:
            messagebox.showerror("NBC spectrum tool", f"Could not open the V115 site-spectrum module:\n{exc}", parent=self.win)

    def _select_x_records(self):
        paths = filedialog.askopenfilenames(title="Select matched X-direction SeismoMatch / PEER text records", parent=self.win, filetypes=[("Earthquake text records", "*.txt *.AT2 *.at2"), ("All files", "*.*")])
        if paths:
            self.x_record_paths = list(paths)
            self.x_count.configure(text=f"{len(paths)} files selected")

    def _run(self):
        if self.running: return
        try:
            if not self.execute.get():
                self.log.delete("1.0", "end")
                self.log.insert("end", "[OFF] RUN_NONLINEAR_TIME_HISTORY is False. Review the nonlinear model, readiness manifest, matched records, scale, periods and damping first.\n")
                return
            x_only = self.motion_mode.get() == LTH_X_ONLY_MODE
            use_preloaded_pairs = (not x_only) and (not self.manifest.get().strip())
            required=[('Rayleigh period 1 (s)',self.p1),('Rayleigh period 2 (s)',self.p2),('NBC T1 X (s)',self.t1x),('Tn X at 90% mass (s)',self.tnx)]
            if not x_only:required += [('NBC T1 Y (s)',self.t1y),('Tn Y at 90% mass (s)',self.tny)]
            missing=[label for label,var in required if not var.get().strip()]
            if missing:raise ValueError('Missing inputs: '+', '.join(missing)+'. Refresh project inputs or rerun Modal audit for the selected export and stiffness state.')
            values = {"modal_input_reference_status": getattr(self,"modal_reference_status",{}), "model_script": self.model.get().strip(), "python": self.python.get().strip(), "model_length_unit": self.model_length_unit.get(), "motion_manifest": self.manifest.get().strip(),
                "story_nodes_csv": self.stories.get().strip(), "model_readiness_json": self.readiness.get().strip(), "output_dir": self.output.get().strip(), "limit_state": self.ls.get(),
                "damping_ratio_percent": float(self.damping.get()), "damping_period_1_s": float(self.p1.get()), "damping_period_2_s": float(self.p2.get()),
                "T1_x_s": float(self.t1x.get()), "T1_y_s": float(self.t1y.get()) if self.t1y.get().strip() else None,
                "Tn_x_s": float(self.tnx.get()), "Tn_y_s": float(self.tny.get()) if self.tny.get().strip() else None,
                "modes_to_check": int(self.nmodes.get()), "torsion_sensitive": bool(self.torsion.get()),
                "motion_mode": "X_ONLY_SCREENING" if x_only else "PAIRED_3D", "peer_x_paths": self.x_record_paths,
                "x_scale_factor": float(self.x_scale.get()), "pair_scale_factor": float(self.pair_scale.get()),
                "use_preloaded_peer_pairs": use_preloaded_pairs, "peer_pairs": LTH_DEFAULT_PEER_PAIRS,
                "execute_nonlinear_time_history": True, "record_matching_metadata": LTH_MATCHING_METADATA}
            if not x_only:values.update(self.pair_selector.config())
            values["damping_model"]=self.damping_model.get()
            required = ["model_script", "python", "story_nodes_csv", "output_dir", "model_readiness_json"]
            if not x_only and not use_preloaded_pairs: required.append("motion_manifest")
            for k in required:
                if not values[k]: raise ValueError(f"Select or enter {k.replace('_', ' ')}.")
            if not x_only and (values["T1_y_s"] is None or values["Tn_y_s"] is None):
                raise ValueError("The full paired 3D procedure needs T1 and Tn for both X and Y directions.")
            if values["damping_ratio_percent"] > 5.0: raise ValueError("NBC 105:2025 §8.1.1: viscous damping cannot exceed 5%; avoid double-counting explicit FVD damping.")
            if values["modes_to_check"] < 1: raise ValueError("Check at least one eigenmode.")
            # Validate CSV and motion metadata before starting a long analysis.
            _read_inputs(values)
            _require_nonlinear_readiness(values)
            out = Path(values["output_dir"]); out.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            scope='Trial' if values.get('preliminary_selection') else 'Suite'
            kind='NLTH' if 'Nonlinear' in type(self).__name__ else 'LTH'
            out=out/f"{kind}_{values['limit_state']}_{scope}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            out.mkdir(parents=True,exist_ok=True);values['output_dir']=str(out)
            cfg = out / "NBC105_Nonlinear_Time_History_RunConfig_V116.json"
            from OpenSees_Timing_V130 import StageTimer
            timer=StageTimer(cfg.parent,"Time-history configuration export")
            cfg.write_text(json.dumps(values, indent=2), encoding="utf-8");timer.finish("completed")
            self.log.delete("1.0", "end"); self.log.insert("end", f"[INFO] Configuration saved: {cfg}\n[INFO] Input mode: {values['motion_mode']}\n[INFO] Starting OpenSeesPy process…\n")
            self.running = True
            threading.Thread(target=self._worker, args=(values["python"], cfg), daemon=True).start()
        except Exception as exc: messagebox.showerror("Input needs review", str(exc), parent=self.win)

    def _worker(self, python, cfg):
        try:
            proc = subprocess.Popen([python, str(Path(__file__).resolve()), "--run", str(cfg)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, env={**dict(__import__('os').environ),'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
            log_path = Path(json.loads(cfg.read_text(encoding="utf-8"))["output_dir"]) / "NBC105_Nonlinear_Time_History_Run_V116.log"
            with log_path.open("w", encoding="utf-8") as logfile:
                for line in proc.stdout:
                    logfile.write(line); logfile.flush()
                    self.win.after(0, self._append_log, line)
                code = proc.wait()
                end_line = f"\n{'[SUCCESS]' if code == 0 else '[FAILED]'} Process exit code {code}. Persistent log: {log_path}\n"
                logfile.write(end_line); logfile.flush()
            self.win.after(0, self._append_log, end_line)
            if code==0:self.win.after(0,lambda:__import__("OpenSees_History_Results_V134").launch(self.win,log_path.parent))
        except Exception as exc: self.win.after(0, self._append_log, f"[FAILED] {exc}\n")
        finally: self.running = False

    def _append_log(self, line):
        try: self.log.insert("end", line); self.log.see("end")
        except tk.TclError: pass

    def run(self):
        from OpenSees_Window_Manager_V129 import analysis_window
        analysis_window(self.win)


def launch_nonlinear_time_history_gui(parent=None):
    """Open the NBC 105:2025 readiness-gated nonlinear time-history GUI."""
    gui = NonlinearTimeHistoryGUI(parent)
    gui.run()
    if parent is None:
        gui.win.mainloop()
    return gui


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--run", help="Run an analysis config JSON"); args = parser.parse_args()
    if args.run:
        run_started = time.perf_counter()
        try: _run_analysis(json.loads(Path(args.run).read_text(encoding="utf-8")))
        except Exception as exc:
            elapsed = time.perf_counter() - run_started
            print(f"[FAILED after {elapsed:.2f}s] {exc}\n{traceback.format_exc()}", flush=True)
            try: Path(args.run).with_name("NBC105_Nonlinear_Time_History_Error_V116.txt").write_text(f"Elapsed seconds: {elapsed:.3f}\n{exc}\n{traceback.format_exc()}", encoding="utf-8")
            except Exception: pass
            sys.exit(1)
    else:
        launch_nonlinear_time_history_gui()


if __name__ == "__main__": main()



