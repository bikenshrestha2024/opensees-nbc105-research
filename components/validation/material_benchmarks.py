"""Literature benchmark response comparison for OpenSees RC wall models.

This is a screening/traceability tool, not a code acceptance test. It compares
paired experimental/reference and reproduced OpenSees histories, reports
response errors, and lists project-similarity gaps that block extrapolation.

CSV columns (same sampling/order for each row):
    experimental_displacement, experimental_force,
    model_displacement, model_force
Use consistent displacement and force units. Do not mix specimen tests, axes,
or loading protocols within one file.

Example:
  python OpenSees_Literature_Validation_V117.py compare wall_test.csv \
      --report wall_test_validation.json --tolerance 0.15

References:
  Kolozvari, K., López, C.N., & Massone, L.M. (2023), Engineering Structures,
  294, 116700. https://doi.org/10.1016/j.engstruct.2023.116700
  López, C.N., Massone, L.M., & Kolozvari, K. (2022), Engineering Structures,
  252, 113590. https://doi.org/10.1016/j.engstruct.2021.113590
  Kolozvari, K., Orakcal, K., & Wallace, J. (2015), PEER Report 2015/12,
  Appendix B.3 (RW-A15-P10-S78). https://peer.berkeley.edu/publications/2015-12

A response match is necessary but insufficient for transferring parameters:
confirm geometry/aspect ratio, axial-load ratio, openings/coupling beams,
reinforcement layout/ratios, concrete and steel grades, boundary detailing,
loading protocol, and model formulation. Use at least one independent test for
validation after any parameter fitting. Never tune and validate on the same
specimen history and call that independent validation.
"""
from __future__ import annotations

__release__ = '134'

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


REQUIRED = ("experimental_displacement", "experimental_force",
            "model_displacement", "model_force")
SIMILARITY_FIELDS = (
    "wall_length_to_height_ratio", "axial_load_ratio", "wall_thickness_m",
    "opening_configuration", "coupling_beam_detail", "boundary_elements",
    "vertical_reinforcement_ratio", "horizontal_reinforcement_ratio",
    "concrete_strength_MPa", "steel_yield_strength_MPa", "loading_protocol",
    "element_formulation",
)


def _finite_column(rows: list[dict[str, str]], name: str) -> list[float]:
    out = []
    for line, row in enumerate(rows, 2):
        try:
            v = float(row[name])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"CSV line {line}: {name!r} must be numeric.") from exc
        if not math.isfinite(v):
            raise ValueError(f"CSV line {line}: {name!r} must be finite.")
        out.append(v)
    return out


def _relative_error(pred: float, ref: float, scale: float) -> float | None:
    denom = abs(ref) if abs(ref) > 1.0e-12 else scale
    return abs(pred - ref) / denom if denom > 1.0e-12 else None


def compare_histories(csv_path: str | Path, *, tolerance: float = 0.15,
                      metadata_path: str | Path | None = None) -> dict[str, Any]:
    """Compare paired cyclic force-displacement histories and make a cautious report."""
    if not 0 < tolerance < 1:
        raise ValueError("tolerance must be a fraction strictly between zero and one")
    with Path(csv_path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED) - set(reader.fieldnames or [])
        if missing:
            raise ValueError("CSV missing required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    if len(rows) < 3:
        raise ValueError("Provide at least three paired history rows.")
    ed = _finite_column(rows, "experimental_displacement")
    ef = _finite_column(rows, "experimental_force")
    md = _finite_column(rows, "model_displacement")
    mf = _finite_column(rows, "model_force")
    fscale = max(ef) - min(ef)
    dscale = max(ed) - min(ed)
    if fscale <= 0 or dscale <= 0:
        raise ValueError("Reference force and displacement histories must each have nonzero range.")
    rmse_f = math.sqrt(sum((a-b)**2 for a, b in zip(mf, ef)) / len(ef))
    nrmse_f = rmse_f / fscale
    peak_force_err = max(_relative_error(max(mf), max(ef), fscale) or 0.0,
                         _relative_error(min(mf), min(ef), fscale) or 0.0)
    peak_disp_err = max(_relative_error(max(md), max(ed), dscale) or 0.0,
                        _relative_error(min(md), min(ed), dscale) or 0.0)
    # Absolute line integral is cumulative path work (not loop-only dissipation).
    # Report it transparently so users do not mistake it for a calibrated energy metric.
    def path_work(d: list[float], f: list[float]) -> float:
        return sum(abs(0.5*(f[i]+f[i+1])*(d[i+1]-d[i])) for i in range(len(d)-1))
    exp_work, model_work = path_work(ed, ef), path_work(md, mf)
    work_err = _relative_error(model_work, exp_work, max(exp_work, 1.0e-12))
    metrics = {"force_NRMSE_over_reference_range": nrmse_f,
               "peak_force_max_relative_error": peak_force_err,
               "peak_displacement_max_relative_error": peak_disp_err,
               "cumulative_absolute_force_displacement_work_relative_error": work_err,
               "reference_force_range": fscale, "reference_displacement_range": dscale,
               "reference_path_work": exp_work, "model_path_work": model_work,
               "row_count": len(rows), "user_screening_tolerance": tolerance}
    scored = [nrmse_f, peak_force_err, peak_disp_err]
    if work_err is not None:
        scored.append(work_err)
    fit = all(v <= tolerance for v in scored)
    metadata: dict[str, Any] = {}
    if metadata_path:
        metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8-sig"))
    benchmark = metadata.get("benchmark", {})
    project = metadata.get("project", {})
    compared = {}
    unresolved = []
    for key in SIMILARITY_FIELDS:
        b, p = benchmark.get(key), project.get(key)
        if b is None or p is None:
            unresolved.append(key)
            compared[key] = {"benchmark": b, "project": p, "status": "NOT PROVIDED"}
        else:
            same = str(b).strip().casefold() == str(p).strip().casefold()
            compared[key] = {"benchmark": b, "project": p,
                             "status": "MATCHED LABEL" if same else "DIFFERENT / REVIEW"}
            if not same:
                unresolved.append(key)
    return {
        "tool": "OpenSees_Literature_Validation_V117",
        "reference": metadata.get("reference", {
            "citation": "Kolozvari et al. (2023), Engineering Structures 294, 116700; compare with the selected specimen's published response data.",
            "doi": "https://doi.org/10.1016/j.engstruct.2023.116700"}),
        "input_csv": str(Path(csv_path).resolve()),
        "metrics": metrics,
        "literature_reproduction_screen": "WITHIN_USER_TOLERANCE" if fit else "OUTSIDE_USER_TOLERANCE",
        "fit_interpretation": ("This only screens reproduction of the supplied benchmark history. It is not independent validation or permission to transfer parameters."),
        "benchmark_to_project_similarity": compared,
        "unresolved_or_different_similarity_fields": unresolved,
        "parameter_transfer_status": "CANDIDATE_FOR_PROJECT_STUDY_ONLY" if fit and not unresolved else "DO_NOT_EXTRAPOLATE_YET",
        "required_next_steps": [
            "Record exact specimen and data provenance, units, protocol, and any digitization uncertainty.",
            "Separate calibration specimens from independent validation specimens.",
            "Compare project and specimen geometry, axial load, reinforcement, materials, boundary/jamb detailing, and openings.",
            "For the perforated core, validate pier/spandrel/coupling-beam behavior against opening-wall tests or a justified subassembly benchmark.",
            "Run parameter sensitivity and uncertainty studies before using transferred candidates in building NLTHA.",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", help="paired experimental/reference and model force-displacement CSV")
    p.add_argument("--metadata", help="optional JSON with benchmark/project similarity fields")
    p.add_argument("--report", default="OpenSees_Literature_Validation_Report_V117.json")
    p.add_argument("--tolerance", type=float, default=0.15,
                   help="user screening tolerance as fraction (default 0.15; not a code criterion)")
    a = p.parse_args()
    report = compare_histories(a.csv, tolerance=a.tolerance, metadata_path=a.metadata)
    Path(a.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"screen": report["literature_reproduction_screen"],
                      "parameter_transfer_status": report["parameter_transfer_status"],
                      "metrics": report["metrics"], "report": str(Path(a.report).resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
