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
FRAME_SOLVER_TAG_BASE = 100001


def frame_solver_tag_catalog(frames):
    """Map the stable assembled frame solver tags back to ETABS frame objects."""
    return [
        {
            "solver_tag": FRAME_SOLVER_TAG_BASE + index,
            "source_object": str(element.get("object", "")),
            "category": str(element.get("category", "")),
            "section_property": str(element.get("properties", {}).get("section", "")),
            "node_i": int(element["nodes"][0]),
            "node_j": int(element["nodes"][1]),
            "release_i": bool(element.get("release_i", False)),
            "release_j": bool(element.get("release_j", False)),
        }
        for index, element in enumerate(frames)
    ]


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


def selected_member_response(ops, element_tag, node_tags, node_coordinates,
                            baseline_displacements):
    """Capture a selected member's local end forces and gravity-relative axial extension."""
    i_node, j_node = (int(node) for node in node_tags)
    start = [float(value) for value in node_coordinates.get(str(i_node), node_coordinates.get(i_node))]
    end = [float(value) for value in node_coordinates.get(str(j_node), node_coordinates.get(j_node))]
    axis = [b - a for a, b in zip(start, end)]
    length = sum(value * value for value in axis) ** .5
    if not length > 0:
        raise ValueError(f"Element {element_tag} has zero initial length.")
    axis = [value / length for value in axis]

    def translation(node):
        values = list(ops.nodeDisp(node))
        if len(values) < 3:
            raise ValueError(f"Node {node} displacement has fewer than three translational DOFs.")
        return [float(value) for value in values[:3]]

    current_i, current_j = translation(i_node), translation(j_node)
    initial_i = baseline_displacements[i_node][:3]
    initial_j = baseline_displacements[j_node][:3]
    extension = sum(
        ((current_j[k] - current_i[k]) - (initial_j[k] - initial_i[k])) * axis[k]
        for k in range(3)
    )
    def response_vector(response):
        if response is None:
            return []
        try:
            return [float(value) for value in response]
        except TypeError:
            return [float(response)]

    forces = response_vector(ops.eleResponse(int(element_tag), "localForce"))
    if not forces:
        axial = response_vector(ops.eleResponse(int(element_tag), "axialForce"))
        if axial:
            forces = [float(axial[0]), -float(axial[0])]
    if not forces:
        raise ValueError(f"Element {element_tag} returned neither localForce nor axialForce.")
    return {
        "element_tag": int(element_tag),
        "axial_extension_m": extension,
        "local_end_forces_kN_kNm": forces,
    }
