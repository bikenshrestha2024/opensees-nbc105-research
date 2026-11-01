"""Bounded post-failure evidence capture; responses may be contaminated."""
from __future__ import annotations

import json
import math
from pathlib import Path


def _numbers(raw):
    if raw is None:
        return []
    if isinstance(raw, (int, float)):
        return [float(raw)]
    try:
        return [float(value) for value in raw]
    except TypeError:
        return [float(raw)]


def snapshot_failed_step(
    ops, output_path, *, algorithm, dt, return_code,
    element_map_path=None, maximum_findings=150,
):
    """Write observed non-finite responses without treating missing responses as zero."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    inverse = {}
    if element_map_path and Path(element_map_path).is_file():
        mapping = json.loads(
            Path(element_map_path).read_text(encoding="utf-8-sig")
        )
        for source, tags in mapping.items():
            if isinstance(tags, list):
                for tag in tags:
                    inverse[int(tag)] = source

    report = {
        "status": "FAILED_STEP_DIAGNOSTIC",
        "analysis_time_s": float(ops.getTime()),
        "attempt_dt_s": float(dt),
        "return_code": int(return_code),
        "algorithm": str(algorithm),
        "element_map": str(element_map_path) if element_map_path else None,
        "warning": (
            "Post-failure responses may be rollback/contaminated states; "
            "the first observed non-finite element is not necessarily the cause."
        ),
        "nodes_scanned": 0,
        "elements_scanned": 0,
        "nonfinite_nodes": [],
        "nonfinite_elements": [],
        "unsupported_responses": {},
        "query_errors": [],
    }

    for tag in ops.getNodeTags():
        report["nodes_scanned"] += 1
        try:
            values = _numbers(ops.nodeDisp(tag))
            if any(not math.isfinite(value) for value in values):
                report["nonfinite_nodes"].append(
                    {"tag": int(tag), "displacement": [str(v) for v in values]}
                )
        except Exception as exc:
            if len(report["query_errors"]) < maximum_findings:
                report["query_errors"].append({"node": int(tag), "error": str(exc)})

    for tag in ops.getEleTags():
        report["elements_scanned"] += 1
        source = inverse.get(int(tag))
        queries = [
            ("localForce", ("localForce",)),
            ("basicDeformation", ("basicDeformation",)),
            ("globalForce", ("globalForce",)),
        ]
        if source and source.startswith("AREA:"):
            queries.extend([
                ("ShearDef", ("ShearDef",)),
                ("Curvature", ("Curvature",)),
                ("RCPanel1_panel_stress", ("RCPanel", 1, "panel_stress")),
                ("RCPanel1_panel_strain", ("RCPanel", 1, "panel_strain")),
            ])
        for label, args in queries:
            try:
                values = _numbers(ops.eleResponse(int(tag), *args))
                if not values:
                    unsupported = report["unsupported_responses"]
                    unsupported[label] = unsupported.get(label, 0) + 1
                elif any(not math.isfinite(value) for value in values):
                    if len(report["nonfinite_elements"]) < maximum_findings:
                        report["nonfinite_elements"].append({
                            "tag": int(tag),
                            "source": source,
                            "response": label,
                            "values": [str(value) for value in values[:30]],
                        })
            except Exception as exc:
                if len(report["query_errors"]) < maximum_findings:
                    report["query_errors"].append({
                        "element": int(tag),
                        "response": label,
                        "error": str(exc),
                    })

    out.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
