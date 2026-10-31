"""Reusable OpenSees analysis stacks for the V110 gravity / nonlinear workflow.

The helper configures solver objects only. It does not create loads, freeze
gravity, assign masses, or start an analysis automatically. Call it only after
the model, constraints, load patterns, and analysis stage are reviewed.

The supplied tutorial's Linear algorithm is appropriate for an elastic static
solve. This project uses nonlinear forceBeamColumn/fiber sections, so the
gravity preload and NLTHA defaults use Newton iteration.

SparseGeneral is the default general sparse solver. ProfileSPD is an optional
solver for symmetric positive-definite systems only; nonlinear tangent systems
can cease to satisfy that condition. RCM remains the DOF numberer. Transformation
is recommended for rigid diaphragms, but the model must not contain chained or
overlapping multi-point constraints.
"""
from __future__ import annotations

__release__ = '134'
# Command reference: Transformation handler / rigidDiaphragm constraint notes:
# https://openseespydoc.readthedocs.io/en/latest/src/TransformationMethod.html
# https://openseespydoc.readthedocs.io/en/latest/src/rigidDiaphragm.html
# loadConst sequencing: https://openseespydoc.readthedocs.io/en/latest/src/loadConst.html
# See README_V110.md for the limits and meaning of each analysis stage.
import json
import math
import time
from pathlib import Path

ANALYSIS_MODE_CHOICES = (
    "LINEAR_ELASTIC_CHECK",
    "NONLINEAR_STATIC",
    "NONLINEAR_NLTHA",
)
PRIMARY_ANALYSIS_MODE = "NONLINEAR_NLTHA"
NONLINEAR_ALGORITHM_CHOICES = ("Newton", "KrylovNewton", "NewtonLineSearch")
DEFAULT_SYSTEM = "SparseGeneral"
DEFAULT_NUMBERER = "RCM"
DEFAULT_CONSTRAINTS = "Transformation"


def _configure_common(ops, *, system=DEFAULT_SYSTEM, system_options=(),
                      numberer=DEFAULT_NUMBERER,
                      constraints=DEFAULT_CONSTRAINTS):
    """Reset analysis objects and configure the common equation solution stack."""
    ops.wipeAnalysis()
    # Transformation is required for the model's rigid-diaphragm MP constraints.
    ops.constraints(str(constraints))
    ops.numberer(str(numberer))
    ops.system(str(system), *tuple(system_options))


def save_gravity_diagnostics(ops, output_path, *, last_committed_factor,
                             attempted_factor, return_code, system,
                             system_options=(), element_labels=None,
                             max_items=40):
    """Persist a bounded first-failure snapshot; responses may be trial state."""
    report = {
        "status": "FAILED_GRAVITY_SOLVE_DIAGNOSTIC_SNAPSHOT",
        "scope": "Solver failure evidence only; not a stiffness or connectivity diagnosis",
        "last_committed_load_factor": float(last_committed_factor),
        "attempted_load_factor": float(attempted_factor),
        "analysis_time_after_failure": float(ops.getTime()),
        "return_code": int(return_code),
        "linear_system": str(system),
        "linear_system_options": list(system_options),
        "response_state_warning": (
            "A failed analysis may revert to committed state; element responses "
            "are diagnostic samples and may not represent a valid equilibrium state."
        ),
        "nodes_scanned": 0,
        "elements_scanned": 0,
        "nonfinite_nodes": [],
        "node_response_errors": [],
        "largest_displacement_nodes": [],
        "nonfinite_element_responses": [],
        "element_response_errors": [],
    }
    element_labels = element_labels or {}
    node_rows = []
    for tag in ops.getNodeTags():
        try:
            displacement = [float(value) for value in ops.nodeDisp(tag)]
        except Exception as exc:
            report["node_response_errors"].append({
                "tag": int(tag),
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        report["nodes_scanned"] += 1
        if not all(math.isfinite(value) for value in displacement):
            report["nonfinite_nodes"].append({
                "tag": int(tag), "displacement": displacement
            })
        else:
            magnitude = math.sqrt(sum(value * value for value in displacement[:3]))
            node_rows.append((magnitude, int(tag), displacement))
    node_rows.sort(reverse=True)
    report["largest_displacement_nodes"] = [
        {"tag": tag, "translation_norm_model_units": magnitude,
         "displacement": displacement}
        for magnitude, tag, displacement in node_rows[:max_items]
    ]
    for tag in ops.getEleTags():
        report["elements_scanned"] += 1
        for response_name in ("localForce", "basicDeformation"):
            try:
                raw = ops.eleResponse(tag, response_name)
                if raw is None:
                    continue
                values = [float(value) for value in raw]
            except Exception as exc:
                report["element_response_errors"].append({
                    "tag": int(tag), "response": response_name,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                if int(tag) in element_labels:
                    report["element_response_errors"][-1]["model_element"] = element_labels[int(tag)]
                continue
            if not all(math.isfinite(value) for value in values):
                report["nonfinite_element_responses"].append({
                    "tag": int(tag), "response": response_name,
                    "values": values,
                })
                if int(tag) in element_labels:
                    report["nonfinite_element_responses"][-1]["model_element"] = element_labels[int(tag)]
    for key in ("nonfinite_nodes", "node_response_errors", "element_response_errors",
                "nonfinite_element_responses"):
        report[key] = report[key][:max_items]
    report["output_path"] = str(Path(output_path))
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def configure_nonlinear_static(ops, *, tolerance=1.0e-8, max_iterations=50,
                               nsteps=10, algorithm="Newton", system=DEFAULT_SYSTEM,
                               system_options=(),
                               numberer=DEFAULT_NUMBERER,
                               constraints=DEFAULT_CONSTRAINTS):
    """Configure nonlinear, load-controlled static analysis (e.g. gravity)."""
    _configure_common(ops, system=system, system_options=system_options, numberer=numberer,
                     constraints=constraints)
    ops.test("NormDispIncr", float(tolerance), int(max_iterations), 0)
    ops.algorithm(str(algorithm))
    if int(nsteps) < 1:
        raise ValueError("nsteps must be a positive integer")
    ops.integrator("LoadControl", 1.0 / int(nsteps))
    ops.analysis("Static")


def run_static_analysis(ops, nsteps, *, tolerance=1.0e-8,
                        max_iterations=50, algorithm="Newton",
                        system=DEFAULT_SYSTEM, system_options=(), numberer=DEFAULT_NUMBERER,
                        constraints=DEFAULT_CONSTRAINTS, diagnostic_path=None,
                        element_labels=None):
    """Run static steps and raise if OpenSees reports failure.

    For incremental gravity, set nsteps and the LoadControl increment to suit
    the actual pattern factors; review the generated loads before calling.
    """
    nsteps = int(nsteps)
    if nsteps < 1:
        raise ValueError("nsteps must be a positive integer")
    _configure_common(ops, system=system, system_options=system_options, numberer=numberer,
                     constraints=constraints)
    ops.test("NormDispIncr", float(tolerance), int(max_iterations), 0)
    ops.algorithm(str(algorithm))
    ops.integrator("LoadControl", 1.0 / nsteps)
    ops.analysis("Static")
    status = int(ops.analyze(nsteps))
    if status != 0:
        diagnostic_note = ""
        if diagnostic_path is not None:
            committed_factor = float(ops.getTime())
            save_gravity_diagnostics(
                ops, diagnostic_path,
                last_committed_factor=committed_factor,
                attempted_factor=committed_factor + 1.0 / nsteps,
                return_code=status, system=system,
                system_options=system_options,
                element_labels=element_labels,
            )
            diagnostic_note = f" First-failure snapshot: {diagnostic_path}."
        raise RuntimeError(
            f"Static analysis failed: OpenSees returned {status} after "
            f"requesting {nsteps} steps. Check load factors, constraints, "
            "convergence, and model stability." + diagnostic_note
        )
    return status


def freeze_gravity_loads(ops, *, pseudo_time=0.0):
    """Freeze successfully converged gravity patterns before dynamic loading."""
    ops.loadConst("-time", float(pseudo_time))


def run_gravity_stage(ops, support_nodes, total_applied_vertical_load_kN, *,
                     model_nodes=None, nsteps=10, tolerance=1.0e-8, max_iterations=50,
                     algorithm="Newton", equilibrium_tolerance_percent=0.5,
                     freeze=True, system=DEFAULT_SYSTEM, numberer=DEFAULT_NUMBERER,
                     constraints=DEFAULT_CONSTRAINTS, system_options=(),
                     diagnostic_path=None, element_labels=None, adaptive=False):
    """Run incremental gravity, check vertical equilibrium, and freeze loads.

    ``total_applied_vertical_load_kN`` is the verified positive magnitude of
    the downward loads actually applied to the OpenSees model. It must include
    each source exactly once (including any self-weight not already in ETABS DL).
    Supply the support node tags whose vertical reactions are to be summed.
    Gravity preload levels are model inputs: use the project's reviewed
    unfactored dead load plus sustained live load for NLTHA, not a copied
    tutorial's ULS factors.

    Raises on analysis failure or an equilibrium error above the configured
    tolerance. Gravity is frozen with loadConst('-time', 0.0) only after the
    equilibrium check succeeds.
    """
    supports = [int(n) for n in support_nodes]
    applied = float(total_applied_vertical_load_kN)
    if not supports:
        raise ValueError("support_nodes must contain at least one node tag")
    if applied <= 0.0:
        raise ValueError("total_applied_vertical_load_kN must be positive")
    if float(equilibrium_tolerance_percent) < 0.0:
        raise ValueError("equilibrium_tolerance_percent cannot be negative")
    started = time.perf_counter()
    diagnostics = None
    if adaptive:
        _configure_common(ops,system=system,system_options=system_options,
                          numberer=numberer,constraints=constraints)
        ops.test('NormDispIncr',float(tolerance),int(max_iterations),0)
        ops.algorithm('Newton');ops.integrator('LoadControl',1./int(nsteps));ops.analysis('Static')
        increment=1./int(nsteps);minimum=increment/128.;last=started;accepted=0;recoveries=0
        while ops.getTime()<1.-1e-10:
            before=ops.getTime();step=min(increment,1.-before)
            ops.integrator('LoadControl',step);ops.algorithm('Newton')
            code=ops.analyze(1)
            if code:
                recoveries+=1
                if diagnostic_path is not None:
                    if diagnostics is None:
                        diagnostics = save_gravity_diagnostics(
                            ops, diagnostic_path,
                            last_committed_factor=before,
                            attempted_factor=before + step,
                            return_code=code, system=system,
                            system_options=system_options,
                            element_labels=element_labels,
                        )
                        diagnostics["failed_attempts"] = []
                    diagnostics["failed_attempts"].append({
                        "last_committed_factor": float(before),
                        "attempted_increment": float(step),
                        "return_code": int(code),
                    })
                    Path(diagnostic_path).write_text(
                        json.dumps(diagnostics, indent=2), encoding="utf-8"
                    )
                # analyze(1) reverts a failed trial to the last committed state.
                # Never freeze a partial gravity state or relax equilibrium.
                if abs(ops.getTime()-before)>1e-9:raise RuntimeError('Unexpected gravity time after failed step')
                increment=step/2.
                print(f'[GRAVITY RECOVERY] committed factor={before:.6f}; retry increment={increment:g}; code={code}',flush=True)
                if increment<minimum:
                    detail = f"; first-failure snapshot: {diagnostic_path}" if diagnostic_path else ""
                    raise RuntimeError(
                        f"Nonlinear gravity cannot converge at factor {before:g}; "
                        f"minimum increment reached{detail}"
                    )
                continue
            accepted+=1
            if time.perf_counter()-last>5:
                last=time.perf_counter();print(f'[GRAVITY PROGRESS] factor={ops.getTime():.6f}/1; accepted={accepted}; recoveries={recoveries}; wall={last-started:.1f}s',flush=True)
        print(f'[GRAVITY STEPS] accepted={accepted} recovery_attempts={recoveries}',flush=True)
    else:
        run_static_analysis(
            ops,nsteps=nsteps,tolerance=tolerance,max_iterations=max_iterations,
            algorithm=algorithm,system=system,system_options=system_options,
            numberer=numberer,constraints=constraints,
            diagnostic_path=diagnostic_path,element_labels=element_labels)
    ops.reactions()
    reaction = sum(float(ops.nodeReaction(n, 3)) for n in supports)
    error_percent = 100.0 * abs(reaction - applied) / applied
    elapsed = time.perf_counter() - started
    max_downward = None
    if model_nodes is not None:
        vertical_displacements = {
            int(n): float(ops.nodeDisp(int(n), 3)) for n in model_nodes
        }
        max_downward = min(vertical_displacements.values(), default=0.0)
    result = {
        "steps": int(nsteps),
        "applied_vertical_load_kN": applied,
        "support_vertical_reaction_kN": reaction,
        "equilibrium_error_percent": error_percent,
        "equilibrium_tolerance_percent": float(equilibrium_tolerance_percent),
        "max_downward_vertical_displacement_m": max_downward,
        "elapsed_seconds_before_freeze": elapsed,
        "gravity_frozen": False,
    }
    if error_percent > float(equilibrium_tolerance_percent):
        raise RuntimeError(
            "Gravity equilibrium check failed: applied downward load="
            f"{applied:.6g} kN, summed support reaction={reaction:.6g} kN, "
            f"error={error_percent:.6g}% (limit "
            f"{float(equilibrium_tolerance_percent):.6g}%). Gravity was not frozen."
        )
    if freeze:
        freeze_gravity_loads(ops, pseudo_time=0.0)
        result["gravity_frozen"] = True
    result["elapsed_seconds"] = time.perf_counter() - started
    print(
        "[GRAVITY] PASS | "
        f"steps={result['steps']} | applied={applied:.6f} kN | "
        f"support reactions={reaction:.6f} kN | "
        f"equilibrium error={error_percent:.6g}% | "
        f"max downward Uz={max_downward if max_downward is not None else 'not requested'} m | "
        f"frozen={result['gravity_frozen']} | "
        f"elapsed={result['elapsed_seconds']:.3f} s"
    )
    return result


def configure_nonlinear_transient(ops, *, tolerance=1.0e-7,
                                  max_iterations=30, algorithm="Newton",
                                  gamma=0.5, beta=0.25,
                                  system=DEFAULT_SYSTEM,
                                  numberer=DEFAULT_NUMBERER,
                                  constraints=DEFAULT_CONSTRAINTS):
    """Configure implicit Newmark transient analysis for nonlinear NLTHA."""
    _configure_common(ops, system=system, numberer=numberer,
                     constraints=constraints)
    ops.test("NormDispIncr", float(tolerance), int(max_iterations), 0)
    ops.algorithm(str(algorithm))
    ops.integrator("Newmark", float(gamma), float(beta))
    ops.analysis("Transient")


def run_transient_analysis(ops, nsteps, dt, *, tolerance=1.0e-7,
                           max_iterations=30, algorithm="Newton",
                           gamma=0.5, beta=0.25, system=DEFAULT_SYSTEM,
                           numberer=DEFAULT_NUMBERER,
                           constraints=DEFAULT_CONSTRAINTS):
    """Run transient steps and raise if OpenSees reports failure."""
    nsteps = int(nsteps)
    dt = float(dt)
    if nsteps < 1 or dt <= 0.0:
        raise ValueError("nsteps and dt must both be positive")
    configure_nonlinear_transient(
        ops, tolerance=tolerance, max_iterations=max_iterations,
        algorithm=algorithm, gamma=gamma, beta=beta, system=system,
        numberer=numberer, constraints=constraints,
    )
    status = int(ops.analyze(nsteps, dt))
    if status != 0:
        raise RuntimeError(
            f"Transient analysis failed: OpenSees returned {status} after "
            f"requesting {nsteps} steps at dt={dt:g} s. Inspect the last "
            "converged step, time-step sensitivity, convergence test, "
            "material response, damping, and constraint stability."
        )
    return status


def configure_linear_static(ops, *, tolerance=1.0e-10, max_iterations=20,
                            system=DEFAULT_SYSTEM, numberer=DEFAULT_NUMBERER,
                            constraints=DEFAULT_CONSTRAINTS):
    """Configure the tutorial's Linear algorithm for elastic checks only."""
    _configure_common(ops, system=system, numberer=numberer,
                     constraints=constraints)
    ops.test("NormDispIncr", float(tolerance), int(max_iterations), 0)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")


def configure_analysis_mode(ops, mode=PRIMARY_ANALYSIS_MODE, *, stage="transient",
                            nsteps=10, algorithm="Newton", tolerance=None,
                            max_iterations=None, gamma=0.5, beta=0.25,
                            system=DEFAULT_SYSTEM, numberer=DEFAULT_NUMBERER,
                            constraints=DEFAULT_CONSTRAINTS):
    """Choose a solver stack; this does not change the model's material law.

    ``LINEAR_ELASTIC_CHECK`` requires the assembled model itself to use linear
    elastic elements/materials. Setting algorithm='Linear' on a fiber model
    does not turn its constitutive behavior into an elastic model.
    """
    mode = str(mode).upper()
    if mode not in ANALYSIS_MODE_CHOICES:
        raise ValueError(f"mode must be one of {ANALYSIS_MODE_CHOICES}")
    if mode == "LINEAR_ELASTIC_CHECK":
        if stage == "static":
            return configure_linear_static(
                ops, tolerance=1.0e-10 if tolerance is None else tolerance,
                max_iterations=20 if max_iterations is None else max_iterations,
                system=system, numberer=numberer, constraints=constraints)
        if stage == "transient":
            return configure_nonlinear_transient(
                ops, tolerance=1.0e-10 if tolerance is None else tolerance,
                max_iterations=20 if max_iterations is None else max_iterations,
                algorithm="Linear", gamma=gamma, beta=beta, system=system,
                numberer=numberer, constraints=constraints)
        raise ValueError("stage must be 'static' or 'transient'")
    if mode == "NONLINEAR_STATIC":
        if stage != "static":
            raise ValueError("NONLINEAR_STATIC requires stage='static'")
        return configure_nonlinear_static(
            ops, tolerance=1.0e-8 if tolerance is None else tolerance,
            max_iterations=50 if max_iterations is None else max_iterations,
            nsteps=nsteps, algorithm=algorithm, system=system, numberer=numberer,
            constraints=constraints)
    if mode == "NONLINEAR_NLTHA":
        if stage != "transient":
            raise ValueError("NONLINEAR_NLTHA requires stage='transient'")
        return configure_nonlinear_transient(
            ops, tolerance=1.0e-7 if tolerance is None else tolerance,
            max_iterations=30 if max_iterations is None else max_iterations,
            algorithm=algorithm, gamma=gamma, beta=beta, system=system,
            numberer=numberer, constraints=constraints)
