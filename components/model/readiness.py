"""Project workflow controls for stability checks and damped-outrigger studies.

NBC 105:2025 is the governing Nepal seismic basis. NBC clauses require P-Delta
effects in analysis but do not prescribe a numerical theta stability limit in
the retrieved 2025 text. IS 16700:2023 clause 7.3.10 gives theta <= 0.20 for
its tall-building scope; this module labels that check supplementary and does
not claim that IS 16700 governs a Nepal project.
"""
from __future__ import annotations

__release__ = '134'

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Source registry used by the project workflow; the full annotated bibliography
# and learning-resource notes are in REFERENCES_AND_LEARNING_RESOURCES_V116.md.
# NBC 105 governs the Nepal seismic basis. IS 16700 P-Delta load case selection
# is a project-required supplemental initial-analysis basis; its stability
# coefficient remains supplemental unless adopted by the approving authority.
PROJECT_REFERENCES = {
    "NBC105_2025": "https://www.dudbc.gov.np/pages/24231978/",
    "IS16700_2023": "https://www.services.bis.gov.in/tmp/CED20920094_14092023_1.pdf",
    "OPENSEES_DOCS": "https://opensees.github.io/OpenSeesDocumentation/",
    "OPENSEES_GITHUB": "https://github.com/OpenSees/OpenSees",
    "OPENSEESPY_GITHUB": "https://github.com/zhuminjie/OpenSeesPy",
    "ESFI_MVLEM_3D_PAPER": "https://doi.org/10.1016/j.engstruct.2023.116700",
    "ESFI_MVLEM_3D_DOCS": "https://kkolozvari.github.io/E-SFI-MVLEM-3D/",
    "OPENSEES_FVD_EXAMPLE": "https://opensees.berkeley.edu/wiki/index.php/Dynamic_Analyses_of_1-Story_Moment_Frame_with_Viscous_Dampers",
    "OPENSEES_FVD_MATERIAL": "https://opensees.berkeley.edu/wiki/index.php/ViscousDamper_Material",
    "YOUTUBE_NLTHA": "https://www.youtube.com/watch?v=s-AneO9KjgA",
}

IS16700_THETA_LIMIT = 0.20

STUDY_CASES = (
    ("C0_BASELINE_SHS", "Reference model: all mapped outrigger/belt/cap-truss braces remain SHS."),
    ("C1_PARTIAL_FVD", "Replace only the explicitly listed SHS objects with calibrated FVD devices."),
    ("C2_ALL_FVD", "Replace all eligible listed SHS brace objects with FVD devices."),
    ("C3_PARTIAL_BRB", "Replace only the explicitly listed SHS objects with calibrated BRB elements."),
    ("C4_ALL_BRB", "Replace all eligible listed SHS brace objects with BRBs."),
    ("C5_MIXED_FVD_BRB_SHS", "Use explicit object lists for FVD, BRB, and retained SHS in one model."),
)

REQUIRED_MODEL_COVERAGE = {
    "rc_beams_columns": "Review section/material mapping, offsets, releases, local axes and connection assumptions.",
    "core_walls_with_openings": "Model wall piers, spandrels/coupling beams and opening geometry; audit wall-shell or validated macro-element formulation.",
    "floor_slab_and_openings": "Create area/shell elements or another justified diaphragm/floor representation; account for openings, mass, stiffness and load transfer.",
    "rigid_diaphragm": "Use only where in-plane rigidity is justified; retain distinct ETABS diaphragm groups and all connected structural nodes.",
    "shs_braces_outrigger_belt_cap": "Map brace section properties, orientation, end connectivity, gussets/rigid arms, and tension/compression behavior.",
    "mass_and_gravity": "Close story mass and gravity ledgers including slab, wall, frame, cladding/equipment and device self-weight as applicable.",
    "fvd_brb_devices": "Use cited/certified device or test parameters; define location, axial direction, connection/series stiffness, stroke and force limits.",
    "nonlinear_model_validation": "Validate component laws and 3D model response before record runs; keep baseline and each replacement case comparable.",
}


def stability_coefficient_is16700(P_i: float, delta_i: float, V_i: float, h_i: float, R: float) -> float:
    """IS 16700:2023 §7.3.10 diagnostic: theta=P*Delta/(V*h*R).

    Use consistent force and length units; delta_i is the design inter-storey
    drift quantity entered for that clause. Positive magnitudes are required.
    This routine does not compute Delta from nodal displacements or determine
    code load factors; those quantities must come from a reviewed analysis.
    """
    vals = [float(P_i), float(delta_i), float(V_i), float(h_i), float(R)]
    if not all(math.isfinite(v) for v in vals):
        raise ValueError("P_i, delta_i, V_i, h_i and R must be finite")
    P_i, delta_i, V_i, h_i, R = vals
    if P_i < 0 or delta_i < 0 or V_i <= 0 or h_i <= 0 or R <= 0:
        raise ValueError("Use P_i >= 0, delta_i >= 0, and positive V_i, h_i, R")
    return P_i * delta_i / (V_i * h_i * R)


def evaluate_stability_rows(rows: List[Dict[str, Any]], theta_limit: float = IS16700_THETA_LIMIT) -> List[Dict[str, Any]]:
    """Evaluate dict rows with storey, axis, case, P_i, delta_i, V_i, h_i, R."""
    limit = float(theta_limit)
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("theta_limit must be positive and finite")
    result = []
    for row in rows:
        theta = stability_coefficient_is16700(row["P_i"], row["delta_i"], row["V_i"], row["h_i"], row["R"])
        result.append({**row, "theta_is16700": theta, "supplemental_limit": limit,
                       "status": "WITHIN SUPPLEMENTAL LIMIT" if theta <= limit else "EXCEEDS SUPPLEMENTAL LIMIT - REVIEW"})
    return result


def read_stability_csv(path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Read required columns from a user-reviewed per-storey force/drift CSV."""
    required = {"storey", "axis", "case", "P_i", "delta_i", "V_i", "h_i", "R"}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("Stability CSV missing columns: " + ", ".join(sorted(missing)))
        parsed_rows: List[Dict[str, Any]] = []
        numeric_columns = ("P_i", "delta_i", "V_i", "h_i", "R")
        for line_num, row in enumerate(reader, start=2):
            for column in numeric_columns:
                try:
                    row[column] = float(row[column])
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid value in CSV row {line_num}, column '{column}': {row.get(column)!r}; "
                        "enter a numeric value."
                    ) from exc
            parsed_rows.append(row)
        return parsed_rows


def write_stability_report(input_csv: Union[str, Path], output_csv: Union[str, Path], building_height_m: Optional[float] = None) -> Dict[str, Any]:
    """Write the supplemental IS theta results and applicability statement."""
    rows = evaluate_stability_rows(read_stability_csv(input_csv))
    height = None if building_height_m in (None, "") else float(building_height_m)
    is_scope_note = ("IS 16700 tall-building scope (50 m < H <= 250 m): applicability appears met; confirm building/system scope."
                    if height is not None and 50.0 < height <= 250.0 else
                    "IS 16700 tall-building scope not established (scope states RC buildings >50 m and <=250 m); treat theta as diagnostic only.")
    p = Path(output_csv)
    p.parent.mkdir(parents=True, exist_ok=True)
    fields = ["storey", "axis", "case", "P_i", "delta_i", "V_i", "h_i", "R", "theta_is16700", "supplemental_limit", "status"]
    with p.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return {"report_csv": str(p), "rows": len(rows), "scope_note": is_scope_note,
            "governing_basis_note": "NBC 105:2025 requires P-Delta effects in analysis; this IS 16700 theta check is supplementary, not an NBC pass/fail criterion."}


def write_stability_input_template(path: Union[str, Path]) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["storey", "axis", "case", "P_i", "delta_i", "V_i", "h_i", "R"])
        writer.writerow(["REPLACE_WITH_STOREY", "X", "REPLACE_WITH_LOAD_CASE", "", "", "", "", ""])
    return str(p)


def write_case_matrix(path: Union[str, Path], base_model_path: Union[str, Path, None] = None,
                      results_root: Union[str, Path, None] = None) -> str:
    """Create a case register; each variant should branch from frozen baseline files."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    base = "" if base_model_path is None else str(base_model_path)
    root = "" if results_root is None else Path(results_root)
    with p.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["case_id", "study_description", "base_model_path", "results_dir",
                         "etabs_brace_object_ids", "device_or_shs_parameters_source", "run_status"])
        for case_id, description in STUDY_CASES:
            case_dir = "" if not root else str(root / case_id)
            writer.writerow([case_id, description, base, case_dir, "", "",
                             "NOT CONFIGURED - enter reviewed object IDs and source parameters"])
    return str(p)


def write_readiness_checklist(path: Union[str, Path], format: str = "json") -> str:
    """Export REQUIRED_MODEL_COVERAGE as JSON or Markdown for review/sign-off."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fmt = format.lower()
    if fmt not in {"json", "md", "markdown"}:
        raise ValueError("format must be 'json' or 'markdown'")
    if fmt == "json":
        checklist = {
            "project_status": "NOT READY UNTIL REVIEWED AND SIGNED OFF",
            "instructions": "Record evidence and reviewer/date for each item. Do not infer readiness from successful execution.",
            "governing_basis": "NBC 105:2025; IS 16700:2023 initial P-Delta case basis as project-required supplemental input.",
            "requirements": {key: {"description": description, "evidence": "", "reviewer": "", "date": "", "status": "PENDING"}
                             for key, description in REQUIRED_MODEL_COVERAGE.items()},
        }
        with p.open("w", encoding="utf-8") as stream:
            json.dump(checklist, stream, indent=2)
    else:
        lines = ["# OpenSees model readiness checklist (V116)", "",
                 "> Status: **NOT READY UNTIL REVIEWED AND SIGNED OFF**. A run completing is not model validation.", "",
                 "Basis: NBC 105:2025 governs seismic design. The project-required IS 16700:2023 P-Delta initial load cases are tracked separately; the IS stability check is supplemental.", "",
                 "| Coverage item | Required review | Evidence / file / ETABS check | Reviewer / date | Status |",
                 "|---|---|---|---|---|"]
        for key, description in REQUIRED_MODEL_COVERAGE.items():
            lines.append(f"| `{key}` | {description} |  |  | PENDING |")
        lines += ["", "See [annotated references and learning resources](REFERENCES_AND_LEARNING_RESOURCES_V116.md)."]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)

