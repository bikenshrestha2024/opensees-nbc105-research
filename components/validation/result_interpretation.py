"""Part IV helpers: force-output interpretation and modal-shape snapshots.

These functions run against an already-built and analyzed OpenSeesPy model.
The 12-component mapping applies to 3D beam-column elements returning the
standard localForce response. Other element formulations may return different
vectors; their responses are preserved as indexed values rather than guessed.
"""
from __future__ import annotations

__release__ = '134'

import csv
import json
import math
from pathlib import Path


LOCAL_FORCE_3D_BEAM_COLUMN = (
    "N_i", "Vy_i", "Vz_i", "T_i", "My_i", "Mz_i",
    "N_j", "Vy_j", "Vz_j", "T_j", "My_j", "Mz_j",
)


def _float_list(values):
    return [float(value) for value in values]


def get_element_force_record(ops, element_tag, node_i=None, node_j=None):
    """Return separate global/local force records for one element.

    ``ops.eleForce`` is the element resisting-force vector in global axes;
    ``ops.eleResponse(tag, 'localForce')`` is the local resisting-force vector.
    Both are element resisting forces and exclude inertial forces. The result
    is not a code design envelope; call it after the desired load case/step.
    """
    tag = int(element_tag)
    global_force = _float_list(ops.eleForce(tag))
    try:
        local_force = _float_list(ops.eleResponse(tag, "localForce"))
    except Exception as exc:
        local_force = []
        local_error = str(exc)
    else:
        local_error = ""

    record = {
        "element_tag": tag,
        "node_i": node_i,
        "node_j": node_j,
        "global_resisting_force": global_force,
        "local_resisting_force": local_force,
        "local_response_error": local_error,
        "local_response_interpretation": "standard 3D beam-column end forces"
        if len(local_force) == 12 else "raw indexed response; component mapping not assumed",
    }
    if len(local_force) == 12:
        record["local_force_components"] = dict(zip(LOCAL_FORCE_3D_BEAM_COLUMN, local_force))
    else:
        record["local_force_components"] = {f"response_{i}": v for i, v in enumerate(local_force)}
    return record


def write_element_force_snapshot(ops, element_rows, output_dir, case_name="analysis_case"):
    """Write JSON plus a flat CSV from ``[(tag, node_i, node_j), ...]``.

    Capture immediately after each case/step of interest. ``element_rows``
    can contain tuples of length one, two, or three: tag[, i-node[, j-node]].
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for row in element_rows:
        values = tuple(row) if isinstance(row, (list, tuple)) else (row,)
        if not 1 <= len(values) <= 3:
            raise ValueError("Each element row must be (tag,), (tag, node_i), or (tag, node_i, node_j)")
        values += (None,) * (3 - len(values))
        records.append(get_element_force_record(ops, *values))

    stem = f"{case_name}_element_forces"
    json_path = out / f"{stem}.json"
    csv_path = out / f"{stem}.csv"
    with json_path.open("w", encoding="utf-8") as stream:
        json.dump({"case": case_name, "force_convention_note":
                   "Global and local resisting forces are separate outputs; inertial forces are excluded.",
                   "elements": records}, stream, indent=2)
    columns = ["case", "element_tag", "node_i", "node_j", "global_resisting_force",
               "local_response_interpretation", "local_response_error", *LOCAL_FORCE_3D_BEAM_COLUMN]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            row = {**rec, "case": case_name,
                   "global_resisting_force": json.dumps(rec["global_resisting_force"])}
            for key in LOCAL_FORCE_3D_BEAM_COLUMN:
                row[key] = rec["local_force_components"].get(key, "")
            writer.writerow(row)
    return {"json": str(json_path), "csv": str(csv_path), "element_count": len(records)}


def normalized_mode_shape(ops, node_ids, mode, dof=1):
    """Read one DOF at supplied nodes and normalize by maximum absolute value.

    The returned normalization is for plotting/comparison only; eigenvectors
    are arbitrarily scaled and this does not change physical response.
    Supply nodes ordered by floor/position for a meaningful profile.
    """
    mode, dof = int(mode), int(dof)
    raw = [float(ops.nodeEigenvector(int(node), mode, dof)) for node in node_ids]
    peak = max((abs(value) for value in raw), default=0.0)
    normalized = [value / peak for value in raw] if peak else raw[:]
    return [{"node": int(node), "mode": mode, "dof": dof,
             "eigenvector_component": value, "normalized_component": norm}
            for node, value, norm in zip(node_ids, raw, normalized)]


def write_modal_shape_snapshot(ops, mode_specs, output_dir, periods_s=None,
                               report_prefix="NBC105_V115_modal_shapes"):
    """Export normalized mode vectors for explicitly supplied node/DOF sets.

    ``mode_specs`` is an iterable of dicts with ``mode``, ``dof``, ``axis``
    and floor-ordered ``node_ids``. Modal character labels remain user-reviewed.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in mode_specs:
        shape = normalized_mode_shape(ops, spec["node_ids"], spec["mode"], spec["dof"])
        for item in shape:
            rows.append({**item, "axis_or_component": spec.get("axis", "unspecified"),
                         "period_s": (periods_s[int(spec["mode"]) - 1]
                                      if periods_s and int(spec["mode"]) <= len(periods_s) else ""),
                         "mode_character_review": spec.get("character", "REVIEW actual mode shape")})
    path = out / f"{report_prefix}.csv"
    fields = ["axis_or_component", "mode", "period_s", "mode_character_review", "node", "dof",
              "eigenvector_component", "normalized_component"]
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def period_from_eigenvalue(eigenvalue):
    """Convert a positive eigenvalue lambda=omega**2 to period in seconds."""
    value = float(eigenvalue)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Eigenvalue must be finite and positive")
    return 2.0 * math.pi / math.sqrt(value)

