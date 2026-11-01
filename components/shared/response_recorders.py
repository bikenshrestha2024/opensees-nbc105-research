"""Shared response recorder exports for gravity and seismic analysis cases."""
from __future__ import annotations

import csv
import json
from pathlib import Path


REACTION_COMPONENTS = (
    "support_reaction_Fx_kN",
    "support_reaction_Fy_kN",
    "support_reaction_Fz_kN",
    "support_reaction_Mx_kNm",
    "support_reaction_My_kNm",
    "support_reaction_Mz_kNm",
)


def support_resultants(ops, support_nodes):
    """Return signed summed support reactions; call after each converged state."""
    supports = [int(node) for node in support_nodes]
    if not supports:
        raise ValueError("At least one support node is required for reaction recording.")
    ops.reactions()
    values = [sum(float(ops.nodeReaction(node, dof)) for node in supports)
              for dof in range(1, 7)]
    return dict(zip(REACTION_COMPONENTS, values))


def write_rows(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f"Cannot write an empty response recorder: {path}")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(dict.fromkeys(
            key for row in rows for key in row)))
        writer.writeheader()
        writer.writerows(rows)
    return target


def write_recorder_index(output_dir, analysis, files, notes=(),
                         filename="Response_Recorder_Index.json"):
    target = Path(output_dir) / str(filename)
    payload = {
        "analysis": str(analysis),
        "files": [dict(name=str(name), channels=list(channels))
                  for name, channels in files],
        "notes": list(notes),
        "units": {"displacement": "m", "rotation": "rad", "force": "kN",
                  "moment": "kN m", "time": "s", "drift": "dimensionless"},
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def append_base_shear(row, ops, support_nodes, baseline=None):
    """Add signed incremental base shears and six support resultants to a sample."""
    current = support_resultants(ops, support_nodes)
    reference = baseline or {}
    for key, value in current.items():
        row[key] = value - float(reference.get(key, 0.0))
    row["base_shear_X_kN"] = -row["support_reaction_Fx_kN"]
    row["base_shear_Y_kN"] = -row["support_reaction_Fy_kN"]
    return row


def write_base_shear_roof_curve(path, rows, roof_story_name):
    """Write synchronized base-shear/roof-displacement samples, not envelopes."""
    roof = str(roof_story_name)
    selected = [
        {
            "time_s": row["time_s"],
            "roof_UX_m": row[roof + "_UX_m"],
            "roof_UY_m": row[roof + "_UY_m"],
            "base_shear_X_kN": row["base_shear_X_kN"],
            "base_shear_Y_kN": row["base_shear_Y_kN"],
        }
        for row in rows
        if "base_shear_X_kN" in row and "base_shear_Y_kN" in row
    ]
    if not selected:
        raise ValueError("No synchronized base-shear and roof-displacement samples.")
    return write_rows(path, selected)
