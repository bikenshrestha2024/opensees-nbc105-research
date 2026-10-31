# -*- coding: utf-8 -*-
"""ETABS area-object integration for OpenSeesPy (V116).

Creates floor ShellMITC4 elements and 3D E-SFI-MVLEM wall panels from the
existing ETABS topology export. The export is used as-is: a missing wall quad
stays an opening; this module never fills holes or creates guessed panels.

This is an area-element stage, not a ready-made building analysis. Wall FSAM
materials, floor section parameters, total mass, gravity combination, diaphragm
strategy, and panel direction/material calibration must be reviewed first.
See the companion JSON template and README for the required input provenance.

References:
* Kolozvari, Lopez & Massone (2023), Engineering Structures 294, 116700,
  E-SFI-MVLEM-3D; https://doi.org/10.1016/j.engstruct.2023.116700
* E-SFI-MVLEM-3D command and benchmark documentation:
  https://github.com/kkolozvari/E-SFI-MVLEM-3D
* NBC 105:2025 §7.3.12 requires the response of wall segments and coupling
  beams to be represented for walls with openings.
* IS 16700:2023 §7.3.12 asks for wall models to represent solid/coupled/
  perforated/punched wall segment and coupling-beam behavior (supplementary).
* OpenSees ShellMITC4 is an elastic shell formulation when paired with an
  ElasticMembranePlateSection; it is not a nonlinear RC slab constitutive law.
"""
from __future__ import annotations

__release__ = '134'

import ast
import csv
import json
import math
from pathlib import Path
from typing import Any

AREA_BUILDER_EXECUTION_DEFAULT = False
E_SFI_REFERENCE = "Kolozvari, Lopez & Massone (2023), Eng. Struct. 294, 116700, doi:10.1016/j.engstruct.2023.116700"


def _load_topology(path: str | Path) -> tuple[dict[int, tuple[float, float, float]], list[dict[str, Any]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    node_map = {int(n["opensees_node_tag"]): tuple(float(x) for x in n["coordinates_m"])
                for n in data.get("node_map", [])}
    elements = list(data.get("elements", []))
    if not node_map or not elements:
        raise ValueError("Topology JSON must contain node_map and elements from OpenSees_Element_Connectivity.json.")
    return node_map, elements


def _area_assignments(path: str | Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            result[str(row["etabs_area_object"]).strip()] = row
    return result


def _quad_geometry(node_tags: list[int], xyz: dict[int, tuple[float, float, float]], *,
                   horizontal: bool = False, tolerance: float = 1.0e-6) -> dict[str, float]:
    if len(node_tags) != 4 or len(set(node_tags)) != 4:
        raise ValueError("Area element must be a four-node quad with four distinct nodes.")
    try:
        p = [xyz[n] for n in node_tags]
    except KeyError as exc:
        raise ValueError(f"Area mesh references unknown OpenSees node tag {exc.args[0]}.") from exc
    distances = [math.dist(p[i], p[(i + 1) % 4]) for i in range(4)]
    if min(distances) <= tolerance:
        raise ValueError("Area quad has a zero-length edge.")
    # Parallelogram-like opposing edge check and Newell normal for a robust
    # planarity/degeneracy check. ETABS mesh remains the source of geometry.
    n = [0.0, 0.0, 0.0]
    for i in range(4):
        a, b = p[i], p[(i + 1) % 4]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    area2 = math.sqrt(sum(v * v for v in n))
    if area2 <= tolerance:
        raise ValueError("Area quad has zero area or invalid node winding.")
    unit = [v / area2 for v in n]
    scale = max(distances)
    plane_error = max(abs(sum((p[i][k] - p[0][k]) * unit[k] for k in range(3))) for i in range(1, 4))
    if plane_error > max(tolerance, 1.0e-5 * scale):
        raise ValueError(f"Non-planar area quad (warpage {plane_error:g} m); repair the ETABS mesh before conversion.")
    if horizontal and max(q[2] for q in p) - min(q[2] for q in p) > max(tolerance, 1.0e-6 * scale):
        raise ValueError("Floor ShellMITC4 input is not horizontal; this helper handles horizontal floor quads only.")
    return {"edge_ij_m": distances[0], "edge_jk_m": distances[1], "area_m2": 0.5 * area2,
            "normal_z": unit[2], "warpage_m": plane_error}


def instantiate_area_elements(ops, *, topology_json: str | Path,
                              area_assignment_csv: str | Path,
                              config_json: str | Path,
                              floor_shells: bool = True,
                              nonlinear_wall_panels: bool = True) -> dict[str, Any]:
    """Add audited floor and wall area elements to an existing 3D 6-DOF domain.

    Required config schema is documented in ``OpenSees_Area_Model_Config_TEMPLATE_V116.json``.
    Floor sections are linear shell sections. Wall panels use E-SFI-MVLEM_3D
    with one macro-fiber per ETABS quad, and require pre-defined FSAM tags.
    """
    xyz, records = _load_topology(topology_json)
    assignment = _area_assignments(area_assignment_csv)
    cfg = json.loads(Path(config_json).read_text(encoding="utf-8-sig"))
    if cfg.get("coordinate_units") != "m" or cfg.get("force_units") != "kN":
        raise ValueError("Area integration expects coordinates in metres and forces in kN; convert/confirm ETABS units first.")
    if not cfg.get("source_reviewed_by_user", False):
        raise ValueError("Set source_reviewed_by_user=true only after reviewing the ETABS units, assignments, section/material values and modeling choice.")
    if not (floor_shells or nonlinear_wall_panels):
        return {"floor_shells": 0, "wall_panels": 0, "analysis_ready": False}

    floor_sections = cfg.get("floor_sections", {})
    wall_properties = cfg.get("wall_properties", {})
    # The source ETABS area property is mapped to a named OpenSees wall-panel
    # definition. Keep this separate from line-member section mappings.
    etabs_wall_map = cfg.get("etabs_to_opensees_wall_mapping", {})
    wall_library = cfg.get("opensees_wall_sections", {})
    mapping_file = cfg.get("section_mapping_json")
    if mapping_file:
        map_path = Path(mapping_file)
        if not map_path.is_absolute():
            map_path = Path(config_json).resolve().parent / map_path
        if not map_path.is_file():
            raise FileNotFoundError(f"Configured ETABS-to-OpenSees section mapping JSON was not found: {map_path}")
        map_data = json.loads(map_path.read_text(encoding="utf-8-sig"))
        # GUI export is authoritative for the ETABS area-property -> named
        # OpenSees wall definition link when a mapping file is configured.
        etabs_wall_map = map_data.get("etabs_to_openseespy_wall_area_mapping", etabs_wall_map)
    used_tags = set(int(t) for t in ops.getEleTags())
    section_defs: dict[str, int] = {}
    floor_count = wall_count = 0
    warnings: list[str] = []
    element_audit: list[dict[str, Any]] = []

    for rec in records:
        category = str(rec.get("category", "")).upper()
        if rec.get("dimension") != "area_polygon":
            continue
        obj = str(rec.get("etabs_object", ""))
        nodes = [int(n) for n in rec.get("node_tags", [])]
        prop = str(assignment.get(obj, {}).get("assigned_property", "")).strip()
        tag = int(rec.get("opensees_element_tag") or rec.get("element_tag"))
        if tag in used_tags:
            raise ValueError(f"Reserved area element tag {tag} for ETABS area {obj} is already in use.")
        if category == "FLOOR" and floor_shells:
            geom = _quad_geometry(nodes, xyz, horizontal=True)
            if geom["normal_z"] < 0.0:
                nodes.reverse()  # horizontal quad only: normalize shell normal to +Z
            spec = floor_sections.get(prop)
            if not isinstance(spec, dict):
                raise ValueError(f"No floor_sections entry for ETABS property {prop!r} (object {obj}).")
            e, nu, thickness = float(spec["E_kN_m2"]), float(spec["poisson_ratio"]), float(spec["thickness_m"])
            if e <= 0 or not -0.99 < nu < 0.5 or thickness <= 0:
                raise ValueError(f"Invalid elastic slab section for property {prop!r}.")
            # rho=0 is deliberate: do not silently double count mass. Transfer
            # seismic mass once from the verified project story-weight ledger.
            sec_key = f"{prop}|{e}|{nu}|{thickness}"
            if sec_key not in section_defs:
                sec_tag = int(spec["section_tag"])
                if sec_tag in section_defs.values():
                    sec_tag = max(section_defs.values()) + 1
                ops.section("ElasticMembranePlateSection", sec_tag, e, nu, thickness, 0.0)
                section_defs[sec_key] = sec_tag
            ops.element("ShellMITC4", tag, *nodes, section_defs[sec_key])
            used_tags.add(tag); floor_count += 1
            element_audit.append({"object": obj, "tag": tag, "category": category, "property": prop,
                                  "nodes": nodes, "area_m2": geom["area_m2"], "section_tag": section_defs[sec_key]})
        elif category == "SHEAR WALL" and nonlinear_wall_panels:
            geom = _quad_geometry(nodes, xyz, horizontal=False)
            target_name = etabs_wall_map.get(prop)
            spec = wall_library.get(target_name) if target_name else None
            if not isinstance(spec, dict):
                # Backward-compatible direct config; new configs should use
                # the explicit ETABS property -> OpenSees wall section mapping.
                spec = wall_properties.get(prop)
            if not isinstance(spec, dict):
                raise ValueError(f"No OpenSees wall section mapping/definition for ETABS property {prop!r} (object {obj}). Set etabs_to_opensees_wall_mapping and opensees_wall_sections in the area config.")
            thickness = float(spec["thickness_m"])
            try:
                fsam = int(spec["fsam_material_tag"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"OpenSees wall target {target_name or prop!r} has no usable FSAM material tag. Define calibrated ConcreteCM/SteelMPF/FSAM materials first, then enter the FSAM tag in the OpenSees area config.") from exc
            source = str(spec.get("material_calibration_source", "")).strip()
            if thickness <= 0 or fsam <= 0 or not source:
                raise ValueError(f"Wall {prop!r} requires positive thickness, existing FSAM tag, and a traceable calibration citation.")
            if float(spec.get("quad_width_tolerance_m", 0.0)) < 0:
                raise ValueError(f"Invalid quad width tolerance for wall property {prop!r}.")
            # Multiple separated axial fibers are required to represent flexure.
            fibers=int(spec.get("macro_fibers",5))
            if fibers<2:raise ValueError("Use at least two separated E_SFI axial fibers; verify discretization convergence")
            ops.element("E_SFI_MVLEM_3D", tag, *nodes, fibers,
                        "-thick", *[thickness]*fibers, "-width", *[geom["edge_ij_m"]/fibers]*fibers,
                        "-mat", *[fsam]*fibers, "-CoR", float(spec.get("center_of_rotation", 0.4)),
                        "-ThickMod", float(spec.get("out_of_plane_thickness_modifier", 0.63)),
                        "-Poisson", float(spec.get("poisson_ratio", 0.25)),
                        "-Density", 0.0)
            used_tags.add(tag); wall_count += 1
            element_audit.append({"object": obj, "tag": tag, "category": category, "property": prop,
                                  "opensees_wall_section": target_name,
                                  "nodes": nodes, "area_m2": geom["area_m2"], "thickness_m": thickness,
                                  "fsam_material_tag": fsam, "material_calibration_source": source,
                                  "reference": E_SFI_REFERENCE})

    if floor_shells and floor_count == 0:
        warnings.append("No FLOOR area quads were instantiated.")
    if nonlinear_wall_panels and wall_count == 0:
        warnings.append("No SHEAR WALL area quads were instantiated.")
    if floor_count and nonlinear_wall_panels and not cfg.get("floor_shell_nonlinearity_verified", False):
        warnings.append("Floor ShellMITC4 sections are elastic; they do not model nonlinear RC slab cracking/yielding.")
    warnings += [
        "Area loads and seismic mass are not applied by this function. Use a reconciled load ledger and merge nodal mass once.",
        "ETABS wall panels are preserved as separate quads, including any absent panel/opening; confirm wall object connectivity and local winding in the exported HTML before analysis.",
        "Rigid diaphragms plus shell slabs need a deliberate compatibility/constraint review. Do not assign both shell mass and master-node mass for the same weight.",
        "E-SFI wall panels require an OpenSees build with E_SFI_MVLEM_3D, FSAM, ConcreteCM and SteelMPF; run a material and single-panel benchmark before full-building NLTHA.",
    ]
    report = {"source_topology": str(Path(topology_json).resolve()),
              "source_area_assignment_audit": str(Path(area_assignment_csv).resolve()),
              "area_element_method": "ETABS four-node area mesh; missing wall panels remain gaps",
              "floor_shell_formulation": "linear ElasticMembranePlateSection + ShellMITC4; no shell mass",
              "wall_panel_formulation": "nonlinear E_SFI_MVLEM_3D with multiple axial macro-fibers per exported ETABS wall quad",
              "floor_shell_count": floor_count, "nonlinear_wall_panel_count": wall_count,
              "element_audit": element_audit, "warnings": warnings, "analysis_ready": False}
    Path(cfg["audit_output_json"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def calculate_area_seismic_mass_contribution(*, load_assignment_csv: str | Path,
                                              topology_json: str | Path,
                                              pattern_factors: dict[str, float],
                                              gravity_m_s2: float = 9.80665,
                                              raw_force_to_kN: float = 1.0) -> dict[int, float]:
    """Compute area-load-derived nodal translational mass in kN*s²/m.

    This returns only the selected area-load contribution. The caller must add
    ETABS frame/wall self-weight and other mass sources, reconcile the sum to
    the ETABS seismic-weight report, then assign the combined nodal masses.
    `pattern_factors` must implement the chosen NBC 105:2025 Table 5-1 factors
    and must not include Roof Live. No ETABS units/factors are inferred.
    """
    if gravity_m_s2 <= 0 or raw_force_to_kN <= 0:
        raise ValueError("g and raw-force conversion to kN must be positive.")
    node_map, _ = _load_topology(topology_json)
    etabs_to_tag = {str(n["etabs_point_name"]): int(n["opensees_node_tag"])
                    for n in json.loads(Path(topology_json).read_text(encoding="utf-8-sig")).get("node_map", [])}
    masses: dict[int, float] = {}
    with Path(load_assignment_csv).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            pattern = str(row.get("pattern", "")).strip()
            if pattern not in pattern_factors:
                continue
            if pattern.casefold() == "roof live":
                raise ValueError("NBC 105:2025 Table 5-1 excludes roof live load from seismic weight.")
            down_force = -_area_global_vertical_force(row) * raw_force_to_kN
            if down_force < 0:
                raise ValueError(f"Area {row.get('object')} / {pattern} is upward; reconcile its seismic-weight treatment instead of taking an absolute value.")
            factor = float(pattern_factors[pattern])
            if factor < 0:
                raise ValueError("Seismic mass factors must be non-negative.")
            try:
                etabs_names = ast.literal_eval(row["node_names"])
            except Exception as exc:
                raise ValueError(f"Cannot parse area-load ETABS node list for area {row.get('object')}: {exc}") from exc
            if len(etabs_names) != 4:
                raise ValueError(f"Area-load object {row.get('object')} does not have four corner nodes.")
            nodal_mass = down_force * factor / gravity_m_s2 / 4.0
            for name in etabs_names:
                tag = etabs_to_tag.get(str(name))
                if tag is None or tag not in node_map:
                    raise ValueError(f"ETABS area-load node {name} is missing from the exported topology map.")
                masses[tag] = masses.get(tag, 0.0) + nodal_mass
    return masses


def _area_global_vertical_force(row):
    """Return signed global Fz; CSI 6 is +Z and 10 is gravity (-Z).

    The converter has already normalized total_force_raw_units to global Z.
    Never negate that total a second time. Check older exports against the
    original signed pressure when available so an old abs(value) error fails.
    """
    direction = str(row.get("direction_code", "")).strip().casefold().replace(" ", "")
    if str(row.get("coordinate_system", "")).strip().casefold() != "global" or direction not in ("6", "globalz", "10", "gravity"):
        raise ValueError(f"Area {row.get('object')} is not a global-Z or Gravity assignment.")
    force = float(row["total_force_raw_units"])
    if not math.isfinite(force):
        raise ValueError("Area vertical force must be finite.")
    if str(row.get("value", "")).strip() and str(row.get("area_m2", "")).strip():
        expected = float(row["value"]) * float(row["area_m2"]) * (-1 if direction in ("10", "gravity") else 1)
        if not math.isclose(force, expected, rel_tol=1e-8, abs_tol=1e-8):
            raise ValueError("Area force sign/magnitude disagrees with signed ETABS pressure; re-export with the updated converter.")
    return force


def apply_etabs_area_uniform_loads(ops, *, load_assignment_csv: str | Path,
                                   topology_json: str | Path,
                                   pattern_specs: dict[str, dict[str, float]],
                                   raw_force_to_kN: float,
                                   allowed_categories: tuple[str, ...] = ("FLOOR",)) -> dict[str, Any]:
    """Apply selected ETABS global-Z area loads as four-corner nodal loads.

    `pattern_specs` is explicit, for example ``{"Dead": {"pattern_tag": 901,
    "time_series_tag": 901, "factor": 1.0}}``. Verify `raw_force_to_kN` from
    the active ETABS units and select factors for the particular gravity/P-Δ
    case yourself. This applies only extracted area loads; it does not infer
    member/wall self-weight or combine the sources automatically.
    """
    if raw_force_to_kN <= 0:
        raise ValueError("raw_force_to_kN must be a positive, user-verified conversion factor.")
    data = json.loads(Path(topology_json).read_text(encoding="utf-8-sig"))
    etabs_to_tag = {str(n["etabs_point_name"]): int(n["opensees_node_tag"])
                    for n in data.get("node_map", [])}
    records = {str(e.get("etabs_object")): e for e in data.get("elements", [])
               if e.get("dimension") == "area_polygon"}
    if not etabs_to_tag or not records:
        raise ValueError("Topology JSON needs node_map and four-node area_polygon records.")
    get_patterns = getattr(ops, "getLoadPatternTags", None) or getattr(ops, "getPatterns", None)
    existing_lp = set(int(x) for x in (get_patterns() if callable(get_patterns) else []))
    existing_ts = set(int(x) for x in (ops.getTimeSeriesTags() if hasattr(ops, "getTimeSeriesTags") else []))
    for name, spec in pattern_specs.items():
        lp, ts = int(spec["pattern_tag"]), int(spec["time_series_tag"])
        if lp <= 0 or ts <= 0 or lp in existing_lp or ts in existing_ts:
            raise ValueError(f"Area-load pattern/time-series tags must be positive and unused; conflict for {name!r}.")
        if not math.isfinite(float(spec["factor"])):
            raise ValueError(f"Area-load factor for {name!r} must be finite.")
        existing_lp.add(lp); existing_ts.add(ts)
    allowed = {str(c).strip().upper() for c in allowed_categories}
    totals: dict[str, float] = {name: 0.0 for name in pattern_specs}
    applied_rows = 0
    # Validate and group all rows before changing the live domain.
    grouped = {name: [] for name in pattern_specs}
    with Path(load_assignment_csv).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            name = str(row.get("pattern", "")).strip()
            if name not in pattern_specs:
                continue
            vertical_force = _area_global_vertical_force(row)
            rec = records.get(str(row.get("object", "")).strip())
            if rec is None:
                raise ValueError(f"Area-load object {row.get('object')} is absent from exported topology.")
            if str(rec.get("category", "")).upper() not in allowed:
                continue
            try:
                etabs_names = ast.literal_eval(row["node_names"])
            except Exception as exc:
                raise ValueError(f"Cannot parse ETABS point list for area {row.get('object')}: {exc}") from exc
            if len(etabs_names) != 4:
                raise ValueError(f"Area-load object {row.get('object')} needs exactly four corner points.")
            force_kN = vertical_force * raw_force_to_kN * float(pattern_specs[name]["factor"])
            nodal = force_kN / 4.0
            for point in etabs_names:
                node = etabs_to_tag.get(str(point))
                if node is None:
                    raise ValueError(f"ETABS point {point} from area {row.get('object')} is not mapped to an OpenSees node.")
                grouped[name].append((node, nodal))
            totals[name] += force_kN
            applied_rows += 1
    # OpenSees load() adds to the current Plain pattern: create each pattern
    # immediately before applying that pattern's own loads.
    for name, spec in pattern_specs.items():
        ops.timeSeries("Linear", int(spec["time_series_tag"]))
        ops.pattern("Plain", int(spec["pattern_tag"]), int(spec["time_series_tag"]))
        for node, nodal in grouped[name]:
            ops.load(node, 0.0, 0.0, nodal, 0.0, 0.0, 0.0)
    return {"applied_area_rows": applied_rows, "total_vertical_force_kN_by_pattern": totals,
            "patterns_and_factors": pattern_specs, "allowed_categories": sorted(allowed),
            "raw_force_to_kN": raw_force_to_kN,
            "coverage_note": "Area loads only; member/wall self-weight, complete ETABS story weights, and seismic mass still require separate accounting.",
            "analysis_ready": False}


def launch_area_integration_gui(parent=None, export_dir=None):
    """Write a reviewed area-stage call for insertion into the model builder."""
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("ETABS area mesh → OpenSeesPy | floors + nonlinear walls")
    win.geometry("1050x540")
    win.minsize(850, 470)
    paths = {key: tk.StringVar() for key in ("topology", "audit", "config", "output")}
    if export_dir is not None:
        folder=Path(export_dir).expanduser().resolve()
        for key,name in (('topology','OpenSees_Element_Connectivity.json'),('audit','OpenSees_Area_Section_Assignment_Audit.csv'),('config','OpenSees_Area_Model_Config_V116.json')):
            if (folder/name).is_file(): paths[key].set(str(folder/name))
    rows = (
        ("ETABS topology JSON", "topology", "Select OpenSees_Element_Connectivity.json"),
        ("Area section audit CSV", "audit", "Select OpenSees_Area_Section_Assignment_Audit.csv"),
        ("Reviewed integration config", "config", "Select OpenSees_Area_Model_Config_V116.json"),
    )
    root = ttk.Frame(win, padding=14); root.pack(fill="both", expand=True)
    ttk.Label(root, text="AREA ELEMENT INTEGRATION — V116", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    ttk.Label(root, text="The exported topology contains 350 floor quads and 375 wall quads. This writes a call to add elastic ShellMITC4 floor panels and nonlinear E-SFI-MVLEM_3D wall panels to your existing OpenSees model after nodes and materials are defined. The ETABS wall mesh is preserved; missing quads remain opening gaps.", wraplength=1000).pack(anchor="w", pady=(6, 12))
    for label, key, title in rows:
        row = ttk.Frame(root); row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=28).pack(side="left")
        ttk.Entry(row, textvariable=paths[key]).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=lambda k=key, t=title: paths[k].set(filedialog.askopenfilename(title=t, parent=win, filetypes=[("JSON/CSV", "*.json *.csv"), ("All files", "*.*")]))).pack(side="left", padx=5)
    ttk.Label(root, text="The starter config is deliberately unapproved: set source_reviewed_by_user=true only after confirming ETABS units and material/property assignments, then provide calibrated FSAM tags and citations. Area load and seismic mass remain a separate, reconciled stage.", wraplength=1000, foreground="#8a3412").pack(anchor="w", pady=10)
    floors = tk.BooleanVar(value=False)
    walls = tk.BooleanVar(value=True)
    ttk.Checkbutton(root,text="Add floor ShellMITC4 elements (leave off if floors already exist)",variable=floors).pack(anchor="w")
    ttk.Checkbutton(root,text="Add nonlinear wall panels",variable=walls).pack(anchor="w")
    ttk.Label(root,text="Walls-only adds no floor elements and does not remove existing floors or diaphragm constraints. Do not run this additive helper over existing wall elements. Rigid in-plane constraints do not replace slab vertical bending/load transfer.",wraplength=1000).pack(anchor="w")
    def write_call():
        if not all(paths[k].get().strip() for k in ("topology", "audit", "config")):
            messagebox.showerror("Select inputs", "Choose the topology JSON, area section audit CSV and reviewed config JSON.", parent=win); return
        target = filedialog.asksaveasfilename(title="Save area integration call", parent=win, defaultextension=".py", initialfile="OpenSees_Area_Integration_Call_V116.py", filetypes=[("Python files", "*.py")])
        if not target: return
        def q(value): return repr(str(Path(value).expanduser().resolve()))
        source = (
            "# Add this block after model nodes and required materials are defined.\n"
            "# Execution is deliberately OFF until the ETABS area inputs are reviewed.\n"
            "AREA_STAGE_EXECUTION = False\n"
            "if AREA_STAGE_EXECUTION:\n"
            "    from OpenSees_Area_Element_Integration_V116 import (instantiate_area_elements,\n"
            "        apply_etabs_area_uniform_loads, calculate_area_seismic_mass_contribution)\n"
            f"    AREA_REPORT = instantiate_area_elements(ops, topology_json={q(paths['topology'].get())},\n"
            f"        area_assignment_csv={q(paths['audit'].get())}, config_json={q(paths['config'].get())},\n"
            f"        floor_shells={floors.get()!r}, nonlinear_wall_panels={walls.get()!r})\n"
            "    print(AREA_REPORT)\n"
            "\n"
            "# Optional area gravity load transfer — set only after confirming ETABS raw units,\n"
            "# load signs, and the factors for this exact gravity/P-Delta case:\n"
            "# AREA_LOADS = apply_etabs_area_uniform_loads(ops, load_assignment_csv=r'PATH_TO_OpenSees_Load_Assignments.csv',\n"
            "#     topology_json=r'PATH_TO_OpenSees_Element_Connectivity.json', raw_force_to_kN=USER_VERIFIED_FACTOR,\n"
            "#     pattern_specs={'Floor Finish': {'pattern_tag': 901, 'time_series_tag': 901, 'factor': USER_FACTOR},\n"
            "#                    'Partition': {'pattern_tag': 902, 'time_series_tag': 902, 'factor': USER_FACTOR},\n"
            "#                    'Live': {'pattern_tag': 903, 'time_series_tag': 903, 'factor': USER_FACTOR}})\n"
            "# AREA_MASS_NODAL = calculate_area_seismic_mass_contribution(load_assignment_csv=r'PATH_TO_OpenSees_Load_Assignments.csv',\n"
            "#     topology_json=r'PATH_TO_OpenSees_Element_Connectivity.json',\n"
            "#     pattern_factors={'Floor Finish': 1.0, 'Partition': 1.0, 'Live': NBC105_VERIFIED_LL_FACTOR},\n"
            "#     raw_force_to_kN=USER_VERIFIED_FACTOR)\n"
            "# Merge AREA_MASS_NODAL with frame/wall self-weight and all other ETABS mass sources,\n"
            "# reconcile every floor to the ETABS seismic-weight report, then assign combined nodal mass once.\n"
        )
        Path(target).write_text(source, encoding="utf-8")
        paths["output"].set(target)
        messagebox.showinfo("Integration call created", f"Review and insert this block into your model-builder after all ETABS nodes and FSAM materials are defined:\n\n{target}\n\nThis helper does not create gravity loads, total seismic mass, P-Delta preload, or an NLTHA-ready model.", parent=win)
    ttk.Button(root, text="Write reviewed area-stage call", command=write_call).pack(anchor="w", pady=8)
    ttk.Label(root, text="References: Kolozvari, Lopez & Massone (2023), Engineering Structures 294, 116700, doi:10.1016/j.engstruct.2023.116700; E-SFI-MVLEM-3D user docs at github.com/kkolozvari/E-SFI-MVLEM-3D. NBC 105:2025 §7.3.12 governs wall segment/coupling beam representation. ShellMITC4 + elastic plate section is a linear floor panel, not nonlinear slab RC.", wraplength=1000).pack(anchor="w", pady=(8, 0))
    return win

