"""Bounded post-failure diagnostic evidence, not a structural validation.

Use only on a failed trial. The solver may have rolled back the domain;
responses returned here may be invalid/contaminated. Unsupported recorder
responses are deliberately not treated as a failure or as zeros.
"""
from __future__ import annotations
import json
import math
from pathlib import Path


def _numbers(raw):
    if raw is None:
        return []
    if isinstance(raw, (float, int)):
        return [float(raw)]
    return [float(v) for v in raw]


def snapshot_failed_step(ops, output_path, *, algorithm, dt, return_code,
                         element_map_path=None, maximum_findings=150):
    """Collect all observed non-finite responses (bounded output).

    Do not reuse or continue a model when a non-finite quantity is detected.
    An absence of NaN in available recorders does NOT prove nonsingularity.
    """
    out=Path(output_path)
    out.parent.mkdir(parents=True,exist_ok=True)
    inverse={}
    if element_map_path and Path(element_map_path).is_file():
        for source, tags in json.loads(Path(element_map_path).read_text(encoding="utf-8-sig")).items():
            if isinstance(tags, list):
                for tag in tags:
                    inverse[int(tag)]=source
    summary={"status":"FAILED_STEP_DIAGNOSTIC","analysis_time_s":float(ops.getTime()),
             "attempt_dt_s":float(dt),"return_code":int(return_code),
             "algorithm":str(algorithm),"element_map":str(element_map_path) if element_map_path else None,
             "warning":"Post-failure responses may be rollback/contaminated states; first observed non-finite element is not necessarily the cause.",
             "nodes_scanned":0,"elements_scanned":0,"nonfinite_nodes":[],"nonfinite_elements":[],
             "unsupported_responses":{},"query_errors":[]}
    for tag in ops.getNodeTags():
        summary["nodes_scanned"]+=1
        try:
            vals=_numbers(ops.nodeDisp(tag))
            if any(not math.isfinite(v) for v in vals):
                summary["nonfinite_nodes"].append({"tag":int(tag),"displacement":list(map(str,vals))})
        except Exception as exc:
            if len(summary["query_errors"])<maximum_findings:
                summary["query_errors"].append({"node":int(tag),"error":str(exc)})
    for tag in ops.getEleTags():
        summary["elements_scanned"]+=1
        source=inverse.get(int(tag))
        # Broad queries work for frames/shells; wall panel queries only
        # attempted on source AREA objects. Unsupported responses are omitted.
        queries=[("localForce",("localForce",)),
                 ("basicDeformation",("basicDeformation",)),
                 ("globalForce",("globalForce",))]
        if source and source.startswith("AREA:"):
            queries += [("ShearDef",("ShearDef",)),("Curvature",("Curvature",)),
                        ("RCPanel1_panel_stress",("RCPanel",1,"panel_stress")),
                        ("RCPanel1_panel_strain",("RCPanel",1,"panel_strain"))]
        for label,args in queries:
            try:
                vals=_numbers(ops.eleResponse(int(tag),*args))
                if not vals:
                    summary["unsupported_responses"][label]=summary["unsupported_responses"].get(label,0)+1
                    continue
                if any(not math.isfinite(v) for v in vals):
                    if len(summary["nonfinite_elements"])<maximum_findings:
                        summary["nonfinite_elements"].append({
                            "tag":int(tag),"source":source,"response":label,
                            "values":[str(v) for v in vals[:30]]})
            except Exception as exc:
                if len(summary["query_errors"])<maximum_findings:
                    summary["query_errors"].append({"element":int(tag),"response":label,"error":str(exc)})
    out.write_text(json.dumps(summary,indent=2,allow_nan=False),encoding="utf-8")
    return summary
