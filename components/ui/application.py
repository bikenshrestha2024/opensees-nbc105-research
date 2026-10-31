# -*- coding: utf-8 -*-
"""
ETABS -> OpenSeesPy CONNECTIVITY + LOAD AUDIT + SECTION REVIEW (V110 gravity workflow) + NBC ESM INPUTS

Purpose:
- Open the selected ETABS EDB through the proven CSI ETABS helper sequence.
- Extract ETABS joint coordinates and object connectivity.
- Read assigned area uniform loads from AreaElm.GetLoadUniform and frame distributed loads.
- Convert verified global-gravity area loads (Floor Finish, Live, Partition, Roof Live)
  into equivalent nodal loads on the area's corner nodes for visual auditing.
- Generate an OpenSeesPy script, JSON/CSV audit, and interactive Plotly HTML load view.

CODE ORGANIZATION / READING GUIDE:
01. Python imports; ETABS import and load-pattern configuration
02. ETABS API helpers and ETABS section property extraction
03. ETABS story / level extraction
04. ETABS -> OpenSeesPy import, audit, export, and visualization pipeline
05-09. ETABS units, OpenSees node crosswalk, topology, section mapping, supports
10. ETABS loads -> OpenSees load audit / equivalent-force preview
11-12. OpenSees-oriented ETABS visualization and data exports
13. ETABS import / OpenSees analysis GUI

IMPORTANT LIMITATIONS:
- The base converter remains an ETABS extraction/audit workflow, not a complete thesis structural model.
- Section properties are extracted where the ETABS API exposes them; uncertain properties remain blank and flagged.
- Define_Section_V109.py holds independent library definitions. Its preset sizes/material parameters are not
  automatically populated from ETABS section-property tables; map and reconcile each source property first.
- The committed frame export uses mapped nonlinear fiber sections with forceBeamColumn. It is not a complete
  NLTHA model: area elements, mass, loads, dampers, analysis stages, and result checks remain separate.
- A section review/edit GUI is generated for frame members.
- 3D click selection highlights only the selected trace; it avoids recomputing all trace visibility on every click.
- Nonlinear RC analysis is blocked until calibrated fiber/rebar definitions are supplied.
- Area loads are converted only when their area-object connectivity maps cleanly to ETABS point names.
- ~LLRF is excluded by default. Supported global frame line-load assignments are imported by the
  mapped forceBeamColumn exporter after direction/type/units and member mapping checks; other
  records remain in the ETABS/OpenSees audit with explicit skip reasons.
- User must verify ETABS present units, area object/element naming correspondence, and load signs.

CODE / DATA PROVENANCE (checked 2026-10-20):
- Nepal seismic provisions: NBC 105:2025; RC design: NBC 110; occupancy loads: NBC 103.
  DUDBC official index: https://www.dudbc.gov.np/pages/24231978/
- Dead-load unit weights should come from the ETABS material/project specifications or applicable
  IS 875 (Part 1); BIS currently lists a 2026 edition. Do not replace measured/project inputs with
  tutorial-example values. https://standards.bis.gov.in/website/standard-details
- Supplemental concrete modulus estimate is documented in Define_Section_V109.py (IS 456:2000 §6.2.3.1).
These references establish the standards to consult; they do not certify this conversion or model.
"""

from OpenSees_Timing_V130 import timed_outputs

__release__ = '134'
# ============================================================================
# SECTION 01 — PYTHON IMPORTS
# ============================================================================
import os, sys, json, ast, csv, math, re, time, traceback, importlib.util, subprocess, tkinter as tk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tkinter import filedialog, messagebox, ttk

try:
    import comtypes.client
except Exception:
    comtypes = None
try:
    import openseespy.opensees as ops
except Exception:
    ops = None
try:
    import plotly.graph_objects as go
except Exception:
    go = None

# ============================================================================
# SECTION 01B — ETABS IMPORT / LOAD-PATTERN CONFIGURATION
# ============================================================================
# Keep conservative load-pattern allowlists here. Do not add patterns until
# their ETABS units, direction, sign, and physical meaning have been checked.
SAFE_AREA_PATTERNS = {"dead", "dl", "super dead", "sdead", "floor finish", "live", "ll", "partition", "roof live", "rooflive"}
EXCLUDED_PATTERNS = {"~LLRF"}

# BEGIN USER-COMMITTED ETABS SECTION MAPPINGS
ETABS_TO_OPENSEES_SECTION = {
    "Col 1100*1100": "RC_COLUMN_1100x1100_FIBER",
    "Col 1250*1250": "RC_COLUMN_1250x1250_FIBER",
    "Beam 600*800": "RC_BEAM_600x800_FIBER",
    "350*350*16 SHS": "SHS_350x350x16_STEEL_FIBER",
}
# END USER-COMMITTED ETABS SECTION MAPPINGS

# BEGIN USER-COMMITTED ETABS WALL AREA MAPPINGS
# ETABS area-wall properties map separately from line-member sections. The
# target definition is resolved by OpenSees_Area_Element_Integration_V116.py.
# FSAM tag 0 is intentionally a blocking placeholder; supply a calibrated,
# already-defined FSAM material tag in the area-model config before building.
ETABS_TO_OPENSEES_WALL_SECTION = {
    "Wall 600": "RC_WALL_600_E_SFI_MVLEM3D",
}
# END USER-COMMITTED ETABS WALL AREA MAPPINGS

# Optional one-for-one replacements for selected ETABS BRACE objects. Use
# exact ETABS frame object IDs as keys. Leave empty until parameters are
# calibrated and expressed in generated-model kN-m-s units.
# FVD entry: {"type":"FVD", "material_tag":801, "K":..., "Cd":..., "alpha":...}
# BRB entry: {"type":"BRB", "material_tag":802, "Fy":..., "E0":..., "b":...,
#  "R0":..., "cR1":..., "cR2":..., "a1":..., "a2":..., "a3":..., "a4":..., "core_area":...}
ETABS_DEVICE_ASSIGNMENTS = {}


# ============================================================================
# SECTION 02 — ETABS API HELPERS
# These helpers decode CSI COM return values and extract model data.
# ============================================================================
def _parse_names(ret):
    """Decode CSI GetNameList return shapes seen with comtypes."""
    if not isinstance(ret, (tuple, list)): return []
    for item in ret:
        if isinstance(item, (tuple, list)) and all(isinstance(x, (str, int)) for x in item):
            vals = [str(x) for x in item]
            if vals and not (len(vals) == 1 and vals[0].isdigit()): return vals
        if isinstance(item, str) and item.strip().startswith(("(", "[")):
            try:
                v = ast.literal_eval(item)
                if isinstance(v, (tuple, list)): return [str(x) for x in v]
            except Exception: pass
    # Common CSI form: [count, "('1','2',...)", ret]
    if len(ret) >= 2 and isinstance(ret[1], str):
        try:
            v = ast.literal_eval(ret[1])
            if isinstance(v, (tuple, list)): return [str(x) for x in v]
        except Exception: pass
    return []


def _api_names(obj, method="GetNameList"):
    try: return _parse_names(getattr(obj, method)())
    except Exception: return []


def _connect_etabs(edb, log):
    if comtypes is None: raise RuntimeError("comtypes is unavailable. Run in your ETABS Python environment.")
    if not os.path.isfile(edb): raise FileNotFoundError(edb)
    helper = comtypes.client.CreateObject("ETABSv1.Helper")
    try: helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
    except Exception: pass
    errors=[]
    for progid in ("CSI.ETABS.API.ETABSObject",):
        try:
            etabs = helper.CreateObjectProgID(progid)
            etabs.ApplicationStart()
            sap = etabs.SapModel
            ret = sap.File.OpenFile(os.path.abspath(edb))
            if isinstance(ret, (int, float)) and ret != 0: raise RuntimeError(f"OpenFile return code {ret}")
            try: sap.SetPresentUnits(6)  # kN, m, C; confirm in the output log
            except Exception: pass
            log("Connected to ETABS; requested present units kN-m-C (API enum 6).")
            return etabs, sap
        except Exception as e: errors.append(repr(e))
    raise RuntimeError("Could not open ETABS model: " + " | ".join(errors))


def _point_coords(sap, names):
    pts={}
    for n in names:
        try:
            r=sap.PointObj.GetCoordCartesian(str(n))
            if isinstance(r,(list,tuple)) and len(r)>=3:
                xyz=tuple(float(v) for v in r[:3])
                if all(math.isfinite(v) for v in xyz): pts[str(n)]=xyz
        except Exception: pass
    return pts


def _get_points(api_obj, name):
    """Decode CSI GetPoints results while preserving numeric ETABS point names.

    ETABS point IDs are commonly numeric strings ("1", "221", ...). Do not
    discard numeric strings as if they were API status codes. A trailing integer
    in the flat COM tuple is treated as the return code; nested arrays are treated
    as point-name arrays and retain numeric strings.
    """
    try:
        r = api_obj.GetPoints(str(name))
    except Exception:
        return []
    if not isinstance(r, (tuple, list)):
        return []

    # Prefer nested point-name arrays, including numeric string names.
    candidates = []
    for item in r:
        if isinstance(item, (tuple, list)) and item:
            vals = [str(v).strip() for v in item if isinstance(v, (str, int))]
            vals = [v for v in vals if v and v.casefold() not in {"none", "null"}]
            if len(vals) >= 2:
                candidates.append(vals)
        elif isinstance(item, str) and item.strip().startswith(("(", "[")):
            try:
                parsed = ast.literal_eval(item)
                if isinstance(parsed, (tuple, list)):
                    vals = [str(v).strip() for v in parsed if isinstance(v, (str, int))]
                    vals = [v for v in vals if v and v.casefold() not in {"none", "null"}]
                    if len(vals) >= 2:
                        candidates.append(vals)
            except Exception:
                pass
    if candidates:
        return max(candidates, key=len)

    # Flat COM form: ('pointName1', 'pointName2', 0). Keep numeric strings,
    # but omit a trailing numeric return code when represented as an integer.
    flat = []
    for i, item in enumerate(r):
        if isinstance(item, str):
            value = item.strip()
            if value and not value.startswith(("(", "[")):
                flat.append(value)
        elif isinstance(item, int) and i < len(r) - 1:
            flat.append(str(item))
    flat = list(dict.fromkeys(flat))
    return flat if len(flat) >= 2 else []


def _call_variants(method, name, variants):
    last=None
    for extra in variants:
        try:
            r=method(str(name), *extra)
            if isinstance(r,dict) and "error" in r: continue
            return r
        except Exception as e: last=e
    return {"error":repr(last) if last else "No API variant succeeded"}


def _read_load_set_table(sap, key):
    """Read-only CSI database table. Values use the exporter's kN-m units."""
    result=sap.DatabaseTables.GetTableForDisplayArray(key,[],"",0,[],0,[])
    if not isinstance(result,(list,tuple)) or len(result)!=6 or int(result[-1])!=0:
        raise ValueError(f"{key}: database API failed: {result!r}")
    _,version,fields,count,flat,_=result
    fields=list(fields or []);flat=list(flat or []);count=int(count)
    if count==0:return [],dict(table=key,version=version,fields=fields,records=0)
    if not fields or len(flat)!=count*len(fields):raise ValueError(key+": invalid database row dimensions")
    norm=lambda text: ''.join(c.lower() for c in str(text) if c.isalnum())
    return [dict(zip(map(norm,fields),flat[i:i+len(fields)])) for i in range(0,len(flat),len(fields))],dict(table=key,version=version,fields=fields,records=count)


def _extract_uniform_load_sets(sap,area_names,log):
    """Expand assigned load sets, preserving each pattern and gravity sign.
    Does not edit ETABS, explode assignments there, or borrow other EDB data.
    """
    raw=[];expanded=[]
    try:
        assignments,audit=_read_load_set_table(sap,'Area Load Assignments - Uniform Load Sets');raw.append(audit)
        if not assignments:return [],raw
        definitions,audit=_read_load_set_table(sap,'Shell Uniform Load Sets');raw.append(audit)
        known=set(map(str,area_names));sets={};last=''
        for index,row in enumerate(definitions):
            name=str(row.get('name') or row.get('loadset') or last).strip();last=name
            pattern=str(row.get('loadpattern','')).strip();value=float(row['loadvalue'])
            if not name or not pattern or not math.isfinite(value):raise ValueError('Incomplete uniform load-set definition')
            sets.setdefault(name,[]).append((pattern,value,index))
        seen=set()
        for row in assignments:
            obj=str(row.get('uniquename','')).strip();name=str(row.get('loadset','')).strip()
            if not name or name.casefold()=='none':continue
            if obj not in known:raise ValueError('Load-set assignment lacks exact area unique-name connectivity: '+obj)
            if obj in seen:raise ValueError('Multiple load-set assignment rows for area '+obj)
            seen.add(obj)
            if name not in sets:raise ValueError('Missing load-set definition: '+name)
            factor=float(row.get('scalefactor') or 1.)
            if not math.isfinite(factor):raise ValueError('Nonfinite load-set scale')
            for pattern,value,index in sets[name]:
                expanded.append(dict(object=obj,pattern=pattern,coordinate_system='Global',direction_code=10,value=value*factor,api='DatabaseTables.UniformLoadSets',load_set=name,load_set_component=index,load_set_scale=factor))
        raw.append(dict(kind='uniform_load_sets',status='expanded',assigned_areas=len(seen),expanded_components=len(expanded),assignments=assignments,definitions=definitions))
        log(f'Uniform load sets: {len(seen)} assigned areas expanded into {len(expanded)} pattern components; gravity direction, kN/m2.')
        return expanded,raw
    except Exception as exc:
        raw.append(dict(kind='uniform_load_sets',status='UNVERIFIED',error=str(exc)))
        log('LOAD COMPLETENESS UNVERIFIED: uniform load sets could not be read/expanded: '+str(exc))
        return [],raw


def _extract_area_assignments(sap, area_names, log):
    rows=[]; raw=[]
    # Read object assignments directly: AreaElm can return status 1 before
    # an analysis mesh exists. Never substitute another model's saved loads.
    api=getattr(sap,"AreaObj",None)
    api_name="AreaObj.GetLoadUniform"
    if api is None:
        log("AreaObj API unavailable; area assignments could not be verified.")
        return rows,raw
    failures=0
    for name in area_names:
        try:
            r=api.GetLoadUniform(str(name))
            raw.append({"kind":"area","name":name,"api":api_name,"raw":r})
            if not isinstance(r,(tuple,list)) or len(r)<7 or int(r[-1])!=0:
                failures+=1
                continue
            count=int(r[0]); objnames=list(r[1]); patterns=list(r[2]); csys=list(r[3]); dirs=list(r[4]); vals=list(r[5])
            if any(len(v)<count for v in (objnames,patterns,csys,dirs,vals)):
                failures+=1
                continue
            for i in range(count):
                rows.append({"object":str(objnames[i]),"pattern":str(patterns[i]),
                             "coordinate_system":str(csys[i]),"direction_code":dirs[i],
                             "value":float(vals[i]),"api":api_name})
        except Exception as exc:
            failures+=1
            raw.append({"kind":"area","name":name,"api":api_name,"error":repr(exc)})
    log(f"Area object load queries: {len(area_names)} objects; {failures} failed; {len(rows)} assignments. Failed queries do not mean zero load.")
    raw.append(dict(kind='direct_uniform_loads',status='UNVERIFIED' if failures else 'READ',failed_queries=failures))
    set_rows,set_raw=_extract_uniform_load_sets(sap,area_names,log)
    rows.extend(set_rows);raw.extend(set_raw)
    # De-duplicate exact API repeats (same assignment may be returned through alias names).
    seen=set(); unique=[]
    for r in rows:
        key=(r['object'],r['pattern'],str(r['coordinate_system']),str(r['direction_code']),round(r['value'],9),r.get('api'),r.get('load_set'),r.get('load_set_component'))
        if key not in seen: seen.add(key); unique.append(r)
    return unique,raw


def _extract_frame_distributed(sap, frame_names):
    rows=[]; raw=[]; api=sap.FrameObj
    variants=[(),("",0,0,0,0,0,0,"Global",0),("",0,0,0,0,0,0,"Global"),("",)]
    for name in frame_names:
        r=_call_variants(api.GetLoadDistributed,name,variants)
        raw_item={"kind":"ETABS frame distributed load","name":name,"raw":r}
        raw.append(raw_item)
        if not isinstance(r,(tuple,list)) or len(r)<12:
            raw_item["parse_error"]="ETABS API return did not contain the expected output arrays; inspect raw response and ETABS API version."
            continue
        try:
            count=int(r[0]); objs=list(r[1]); pats=list(r[2]); types=list(r[3]); csys=list(r[4]); dirs=list(r[5])
            # CSI GetLoadDistributed arrays follow its API order:
            # FrameName, LoadPat, MyType, CSys, Dir, RD1, RD2, Dist1,
            # Dist2, Val1, Val2. RD1/RD2 are relative/absolute flags;
            # Dist1/Dist2 are the actual start/end distances.
            vals=list(r[10]) if len(r)>10 and isinstance(r[10],(tuple,list)) else []
            vals2=list(r[11]) if len(r)>11 and isinstance(r[11],(tuple,list)) else []
            rel1=list(r[6]) if len(r)>6 and isinstance(r[6],(tuple,list)) else []
            rel2=list(r[7]) if len(r)>7 and isinstance(r[7],(tuple,list)) else []
            starts=list(r[8]) if len(r)>8 and isinstance(r[8],(tuple,list)) else []
            ends=list(r[9]) if len(r)>9 and isinstance(r[9],(tuple,list)) else []
            for i in range(count):
                rows.append({"object":str(objs[i] if i<len(objs) else name),"pattern":str(pats[i]),
                             "load_type":types[i] if i<len(types) else None,
                             "coordinate_system":str(csys[i] if i<len(csys) else ""),
                             "direction_code":dirs[i] if i<len(dirs) else None,
                             "value_start":float(vals[i]) if i<len(vals) else None,
                             "value_end":float(vals2[i]) if i<len(vals2) else None,
                             "relative_start":bool(rel1[i]) if i<len(rel1) else None,
                             "relative_end":bool(rel2[i]) if i<len(rel2) else None,
                             "distance_start":float(starts[i]) if i<len(starts) else None,
                             "distance_end":float(ends[i]) if i<len(ends) else None,
                             "raw_numeric_arrays": [list(x) if isinstance(x,(tuple,list)) else x for x in r[6:12]],
                             "api":"FrameObj.GetLoadDistributed","query_object":str(name)})
        except Exception as exc:
            raw_item["parse_error"]=repr(exc)
    return rows,raw


def _extract_etabs_self_weight_patterns(sap):
    """Audit ETABS load-pattern self-weight multipliers without double-applying them.

    ETABS applies these multipliers internally to member/area weight; they are
    not explicit FrameObj/AreaObj assignment rows. CSI API reference:
    https://docs.csiamerica.com/help-files/etabs-api-2016/html/bd768e86-81f8-31dc-6a99-0ffe4a5f0538.htm.
    The value is recorded for
    reconciliation, not automatically converted into OpenSees gravity loads.
    """
    api=getattr(sap,"LoadPatterns",None)
    if api is None:
        return [{"pattern":"UNKNOWN","multiplier":None,"raw":None,
                 "status":"LoadPatterns API unavailable; self-weight source must be checked in ETABS"}]
    names=_api_names(api)
    audit=[]
    for name in names:
        try:
            result=api.GetSelfWTMultiplier(str(name))
            candidates=result if isinstance(result,(tuple,list)) else (result,)
            vals=[]
            for value in candidates:
                if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(float(value)):
                    vals.append(float(value))
            # CSI COM returns output arguments followed by the integer status;
            # the self-weight output is the first numeric value in this call.
            multiplier=vals[0] if vals else None
            audit.append({"pattern":str(name),"multiplier":multiplier,"raw":result,
                          "status":"read; verify exactly one intended dead-load pattern carries self-weight" if multiplier is not None else "could not decode API output; inspect raw result"})
        except Exception as exc:
            audit.append({"pattern":str(name),"multiplier":None,"raw":repr(exc),"status":"API read failed; verify self-weight multiplier directly in ETABS"})
    if not audit:
        audit.append({"pattern":"UNKNOWN","multiplier":None,"raw":None,"status":"No ETABS load patterns enumerated; verify self-weight in ETABS"})
    return audit



# ============================================================================
# SECTION 02B — ETABS SECTION PROPERTY EXTRACTION (BEST EFFORT; NO GUESSES)
# ============================================================================
def _numeric_values(ret):
    vals=[]
    def visit(x):
        if isinstance(x,(tuple,list)):
            for y in x: visit(y)
        elif isinstance(x,(int,float)) and not isinstance(x,bool):
            try:
                v=float(x)
                if math.isfinite(v): vals.append(v)
            except Exception: pass
        elif isinstance(x,str):
            try:
                v=float(x.strip())
                if math.isfinite(v): vals.append(v)
            except Exception: pass
    visit(ret)
    return vals

def _extract_etabs_material_values(mat_api, material_name):
    """Read material-dialog mechanical and unit-weight fields from CSI API.

    Values are reported in the active ETABS units. Failed API calls remain None;
    no material property is inferred from the material name.
    CSI API references (ETABS 2016 method contracts):
    GetMPIsotropic: https://docs.csiamerica.com/help-files/etabs-api-2016/html/37a96800-64b4-3964-8db0-477d27b6b8f7.htm
    GetWeightAndMass: https://docs.csiamerica.com/help-files/etabs-api-2016/html/4cccc937-c097-be94-2e42-e0d360d4d761.htm
    """
    result={"material_name":material_name,"E":None,"poisson_ratio":None,
            "thermal_coefficient":None,"G":None,"G_from_E_nu":None,"weight_per_volume":None,
            "mass_per_volume":None,"material_type_code":None,"raw":{}}
    if mat_api is None or not material_name:
        result["status"]="ETABS material API/name unavailable"
        return result
    def seq(x): return list(x) if isinstance(x,(tuple,list)) else []
    def num(x):
        if isinstance(x,bool): return None
        try:
            v=float(x); return v if math.isfinite(v) else None
        except Exception: return None
    def ok(x):
        a=seq(x); return bool(a) and num(a[-1])==0
    for meth in ("GetMPIsotropic","GetMPIsotropic_2"):
        fn=getattr(mat_api,meth,None)
        if fn is None: continue
        try:
            raw=fn(str(material_name)); result["raw"][meth]=repr(raw); a=seq(raw)
            # CSI API documents GetMPIsotropic as E, U (Poisson), A (thermal
            # coefficient), G, then return code. Preserve CSI's reported G;
            # also retain the isotropic-relation cross-check separately.
            if len(a)>=5 and ok(raw):
                E,nu,alpha,G=num(a[0]),num(a[1]),num(a[2]),num(a[3])
                if E is not None and E>0 and nu is not None and -1<nu<0.5:
                    result.update(E=E,poisson_ratio=nu,thermal_coefficient=alpha,
                                  G=G if G is not None and G>0 else None,
                                  G_from_E_nu=E/(2*(1+nu)))
            break
        except Exception as exc: result["raw"][meth]=repr(exc)
    fn=getattr(mat_api,"GetWeightAndMass",None)
    if fn is not None:
        try:
            raw=fn(str(material_name)); result["raw"]["GetWeightAndMass"]=repr(raw); a=seq(raw)
            # CSI returns W, M, ret (active ETABS units; W is force/volume).
            if len(a)>=3 and ok(raw):
                result["weight_per_volume"],result["mass_per_volume"]=num(a[0]),num(a[1])
        except Exception as exc: result["raw"]["GetWeightAndMass"]=repr(exc)
    fn=getattr(mat_api,"GetTypeOAPI",None)
    if fn is not None:
        try:
            raw=fn(str(material_name)); result["raw"]["GetTypeOAPI"]=repr(raw); a=seq(raw)
            if len(a)>=3 and ok(raw): result["material_type_code"]=num(a[0])
        except Exception as exc: result["raw"]["GetTypeOAPI"]=repr(exc)
    result["status"]="CSI material API values; units are the ETABS display units at extraction"
    return result

def _extract_frame_section_assignments(sap, frame_names, log):
    """Extract only fields whose CSI API return signature can be interpreted safely.

    Raw return values are retained. Material moduli are not accepted unless the
    API reports success and the expected isotropic fields are valid. No section
    properties are synthesized from section names.
    """
    assignments=[]; prop_defs={}; frame_api=getattr(sap,"FrameObj",None)
    prop_api=getattr(sap,"PropFrame",None); mat_api=getattr(sap,"PropMaterial",None)

    def seq(v):
        if isinstance(v,(tuple,list)): return list(v)
        return []

    def scalar(v):
        if isinstance(v,bool): return None
        try:
            x=float(v)
            return x if math.isfinite(x) else None
        except Exception: return None

    def api_ok(ret):
        a=seq(ret)
        rc=scalar(a[-1]) if a else None
        return rc == 0

    for obj in frame_names:
        prop_name=""; auto_select=""; raw=None
        try:
            raw=frame_api.GetSection(str(obj))
            if isinstance(raw,(tuple,list)):
                strings=[str(v).strip() for v in raw if isinstance(v,str) and str(v).strip()]
                prop_name=strings[0] if strings else ""
                auto_select=strings[1] if len(strings)>1 else ""
        except Exception as exc: raw={"error":repr(exc)}

        # ETABS may return the literal text "None" for an unassigned property.
        if prop_name.casefold() in {"none", "null", ""}: prop_name=""
        if prop_name and prop_name not in prop_defs:
            d={"section_name":prop_name,"section_type":"unknown","material_name":None,
               "width_m":None,"depth_m":None,"E_kN_m2":None,"G_kN_m2":None,
               "poisson_ratio":None,"thermal_coefficient":None,"G_from_E_nu":None,"weight_per_volume":None,
               "mass_per_volume":None,"material_type_code":None,"material_values_status":None,
               "status":"section name only; manual review required","raw":{}}
            if prop_api is not None:
                # GetRectangle's CSI signature is interpreted only when its
                # return code is zero and its documented positional fields exist.
                for meth in ("GetRectangle", "GetRectangle_2"):
                    fn=getattr(prop_api,meth,None)
                    if fn is None: continue
                    try:
                        rr=fn(prop_name); d["raw"][meth]=repr(rr)
                        a=seq(rr)
                        if len(a)>=8 and api_ok(a):
                            mat_label=str(a[1]).strip() if a[1] is not None else ""
                            # A label such as M45 is a material name; GUID is
                            # deliberately not substituted for it.
                            if mat_label and mat_label.casefold() not in {"none","null"}:
                                d["material_name"]=mat_label
                            t3,t2=scalar(a[2]),scalar(a[3])
                            if t3 is not None and t2 is not None and t3>0 and t2>0:
                                d["depth_m"],d["width_m"]=t3,t2
                                d["section_type"]="rectangle (dimensions are candidates; verify units/local axes)"
                                d["status"]="rectangle dimensions returned by successful API call; verify units and local axes"
                            break
                    except Exception as exc: d["raw"][meth]=repr(exc)

                # CSI documented tube signature: FileName, MatProp, T3, T2,
                # Tf, Tw, Color, Notes, GUID, return code. Preserve raw values.
                if d["section_type"]=="unknown":
                    for meth in ("GetTube", "GetTube_2"):
                        fn=getattr(prop_api,meth,None)
                        if fn is None: continue
                        try:
                            rr=fn(prop_name); d["raw"][meth]=repr(rr); a=seq(rr)
                            if len(a)>=10 and api_ok(rr):
                                mat_label=str(a[1]).strip() if a[1] is not None else ""
                                if mat_label and mat_label.casefold() not in {"none","null"}: d["material_name"]=mat_label
                                t3,t2,tf,tw=scalar(a[2]),scalar(a[3]),scalar(a[4]),scalar(a[5])
                                if t3 is not None and t2 is not None and t3>0 and t2>0:
                                    d["depth_m"],d["width_m"]=t3,t2
                                    d["section_type"]="tube (T3/T2 dimensions; Tf/Tw wall thicknesses)"
                                    d["tube_flange_thickness_m"]=tf if tf is not None and tf>0 else None
                                    d["tube_web_thickness_m"]=tw if tw is not None and tw>0 else None
                                    d["status"]="tube dimensions returned by successful API call; verify units and local axes"
                            break
                        except Exception as exc: d["raw"][meth]=repr(exc)

            if d.get("material_name"):
                mv=_extract_etabs_material_values(mat_api,d["material_name"])
                d["raw"]["material_values"]=mv.get("raw")
                d["E_kN_m2"]=mv.get("E"); d["G_kN_m2"]=mv.get("G")
                d["poisson_ratio"]=mv.get("poisson_ratio")
                d["thermal_coefficient"]=mv.get("thermal_coefficient")
                d["G_from_E_nu"]=mv.get("G_from_E_nu")
                d["weight_per_volume"]=mv.get("weight_per_volume")
                d["mass_per_volume"]=mv.get("mass_per_volume")
                d["material_type_code"]=mv.get("material_type_code")
                d["material_values_status"]=mv.get("status")
            prop_defs[prop_name]=d

        d=prop_defs.get(prop_name,{}) if prop_name else {}
        assignments.append({"etabs_object":str(obj),"assigned_section":prop_name or None,
            "auto_select_section":auto_select or None,"section_type":d.get("section_type","unknown"),
            "material_name":d.get("material_name"),"width_m":d.get("width_m"),"depth_m":d.get("depth_m"),
            "tube_flange_thickness_m":d.get("tube_flange_thickness_m"),"tube_web_thickness_m":d.get("tube_web_thickness_m"),
            "E_kN_m2":d.get("E_kN_m2"),"G_kN_m2":d.get("G_kN_m2"),
            "poisson_ratio":d.get("poisson_ratio"),"thermal_coefficient":d.get("thermal_coefficient"),
            "G_from_E_nu":d.get("G_from_E_nu"),
            "weight_per_volume":d.get("weight_per_volume"),"mass_per_volume":d.get("mass_per_volume"),
            "material_type_code":d.get("material_type_code"),
            "material_values_status":d.get("material_values_status"),
            "A_m2":None,"Iy_m4":None,"Iz_m4":None,"J_m4":None,
            "extraction_status":d.get("status","NO SECTION ASSIGNMENT — resolve in ETABS"),
            "raw_get_section":repr(raw)})
    assigned=sum(bool(r.get("assigned_section")) for r in assignments)
    log(f"Frames with a non-empty section assignment: {assigned}/{len(assignments)}")
    log(f"Frames with no section assignment returned by ETABS API: {len(assignments)-assigned}")
    log(f"Distinct assigned frame properties found: {len(set(r['assigned_section'] for r in assignments if r.get('assigned_section')))}")
    log("Section API parsing is conservative: failed return codes are not interpreted as valid properties; review raw return values and units.")
    return assignments,prop_defs


def _extract_area_section_assignments(sap, area_names, log):
    """Extract AreaObj property assignments and conservatively read slab/wall/deck thickness.

    The raw API responses are always preserved. Only the well-known CSI positional
    signatures below are interpreted, and only when the final return code is zero.
    This is an audit stage; it does not instantiate shell elements.
    """
    rows=[]; defs={}
    area_api=getattr(sap,"AreaObj",None); prop_api=getattr(sap,"PropArea",None)
    mat_api=getattr(sap,"PropMaterial",None)
    def seq(v): return list(v) if isinstance(v,(tuple,list)) else []
    def num(v):
        if isinstance(v,bool): return None
        try:
            x=float(v); return x if math.isfinite(x) else None
        except Exception: return None
    def ok(v):
        a=seq(v); return bool(a) and num(a[-1])==0
    for obj in area_names:
        prop_name=""; raw_assign=None; error=None
        try:
            fn=getattr(area_api,"GetProperty",None)
            raw_assign=fn(str(obj)) if fn else None
            a=seq(raw_assign)
            if a and ok(a):
                prop_name=str(a[0]).strip() if a[0] is not None else ""
            elif a and len(a)>=2 and num(a[-1])==0:
                prop_name=str(a[0]).strip() if a[0] is not None else ""
            else:
                error="AreaObj.GetProperty did not return a recognized successful result"
        except Exception as exc: error=repr(exc)
        if prop_name.casefold() in {"none","null"}: prop_name=""
        if prop_name and prop_name not in defs:
            d={"property_name":prop_name,"property_type":"unknown","material_name":None,
               "thickness_m":None,"raw_property_api":{},"extraction_status":"property assignment found; review required"}
            if prop_api is not None:
                # CSI ETABS PropArea.GetSlab signature: ShellType, SlabType,
                # MatProp, Thickness, Color, Notes, GUID, ret.
                for meth in ("GetSlab","GetSlab_2"):
                    fn=getattr(prop_api,meth,None)
                    if fn is None: continue
                    try:
                        rr=fn(prop_name); d["raw_property_api"][meth]=repr(rr); a=seq(rr)
                        if len(a)>=8 and ok(rr):
                            d["property_type"]="slab"
                            d["material_name"]=str(a[2]).strip() if a[2] else None
                            th=num(a[3])
                            if th is not None and th>0: d["thickness_m"]=th
                            d["extraction_status"]="slab property read from successful ETABS API; verify units and shell type"
                            break
                    except Exception as exc: d["raw_property_api"][meth]=repr(exc)
                # CSI ETABS PropArea.GetWall signature: WallPropType, ShellType, MatProp,
                # Thickness, Color, Notes, GUID, ret.
                if d["property_type"]=="unknown":
                    for meth in ("GetWall","GetWall_2"):
                        fn=getattr(prop_api,meth,None)
                        if fn is None: continue
                        try:
                            rr=fn(prop_name); d["raw_property_api"][meth]=repr(rr); a=seq(rr)
                            if len(a)>=8 and ok(rr) and isinstance(a[2],str):
                                d["property_type"]="wall"
                                d["material_name"]=str(a[2]).strip() if a[2] else None
                                th=num(a[3])
                                if th is not None and th>0: d["thickness_m"]=th
                                d["extraction_status"]="wall property read from successful ETABS API; verify units and shell type"
                                break
                        except Exception as exc: d["raw_property_api"][meth]=repr(exc)
                # Deck APIs differ by ETABS version; preserve raw response and do
                # not infer rib geometry until its exact signature is confirmed.
                if d["property_type"]=="unknown":
                    for meth in ("GetDeck","GetDeck_2"):
                        fn=getattr(prop_api,meth,None)
                        if fn is None: continue
                        try:
                            rr=fn(prop_name); d["raw_property_api"][meth]=repr(rr)
                            if ok(rr):
                                d["property_type"]="deck"
                                d["extraction_status"]="deck property API succeeded; deck geometry needs schema-aware review"
                                break
                        except Exception as exc: d["raw_property_api"][meth]=repr(exc)
            if d.get("material_name"):
                d["material_values"]=_extract_etabs_material_values(mat_api,d["material_name"])
            defs[prop_name]=d
        d=defs.get(prop_name,{}) if prop_name else {}
        rows.append({"etabs_area_object":str(obj),"assigned_property":prop_name or None,
          "property_type":d.get("property_type","unknown"),"material_name":d.get("material_name"),
          "thickness_m":d.get("thickness_m"),"extraction_status":d.get("extraction_status",error or "NO AREA PROPERTY ASSIGNMENT — resolve in ETABS"),
          "material_values":d.get("material_values"),
          "raw_get_property":repr(raw_assign),"raw_property_api":d.get("raw_property_api",{})})
    assigned=sum(bool(r.get("assigned_property")) for r in rows)
    log(f"Area property assignments found: {assigned}/{len(rows)}")
    log(f"Distinct assigned area properties found: {len(defs)}")
    log("Area property audit includes slab/wall thickness only when a recognized API signature succeeds; deck geometry remains raw for review.")
    return rows,defs


# ============================================================================
# SECTION 03 — ETABS STORY / LEVEL EXTRACTION
# ============================================================================
def _extract_etabs_story_levels(sap, log):
    """Read story names and absolute elevations from ETABS Story API.

    Returns [(1-based display number, ETABS story name, bottom elevation,
    top elevation)] sorted from lowest to highest. Does not infer heights from
    a fixed storey-height constant. Uses Story.GetNameList + GetElevation when
    available, and falls back to Story.GetStories only if needed.
    """
    story_api = getattr(sap, "Story", None)
    if story_api is None:
        log("WARNING: ETABS Story API unavailable; cannot read official story elevations.")
        return []

    def parse_name_list(ret):
        if not isinstance(ret, (tuple, list)):
            return []
        candidates = []
        for item in ret:
            vals = []
            if isinstance(item, (tuple, list)):
                vals = [str(x).strip() for x in item if isinstance(x, str) and str(x).strip()]
            elif isinstance(item, str) and item.strip().startswith(("[", "(")):
                try:
                    q = ast.literal_eval(item)
                    if isinstance(q, (tuple, list)):
                        vals = [str(x).strip() for x in q if str(x).strip()]
                except Exception:
                    pass
            if vals:
                candidates.append(vals)
        # CSI GetNameList commonly returns (count, names, ret); select the
        # largest plausible string list, not a status/count field.
        return max(candidates, key=len) if candidates else []

    def elevation_for(name):
        for method_name in ("GetElevation", "GetElevation_2"):
            method = getattr(story_api, method_name, None)
            if method is None:
                continue
            try:
                r = method(str(name))
            except Exception:
                continue
            vals = []
            if isinstance(r, (tuple, list)):
                for x in r:
                    if isinstance(x, (int, float)) and not isinstance(x, bool):
                        vals.append(float(x))
                    elif isinstance(x, str):
                        try:
                            vals.append(float(x))
                        except Exception:
                            pass
            elif isinstance(r, (int, float)):
                vals.append(float(r))
            # Elevation is usually the first numeric return, status is last.
            if vals:
                value = vals[0]
                if math.isfinite(value):
                    return value
        return None

    names = []
    try:
        names = parse_name_list(story_api.GetNameList())
    except Exception as exc:
        log(f"Story.GetNameList failed: {exc!r}")

    elevated = []
    for name in names:
        z = elevation_for(name)
        if z is not None:
            elevated.append((name, z))
    # Remove duplicate story names/elevations and the base datum (normally 0 m).
    dedup = {}
    for name, z in elevated:
        if z > 1e-6:
            dedup[name.casefold()] = (name, z)
    elevated = sorted(dedup.values(), key=lambda item: item[1])
    # A story's ETABS elevation is its top elevation; its bottom is the previous
    # story elevation (or 0 m for the first level).
    levels = []
    bottom = 0.0
    for i, (name, top) in enumerate(elevated, 1):
        if top <= bottom + 1e-6:
            continue
        levels.append((i, name, bottom, top))
        bottom = top

    if levels:
        log(f"ETABS story levels read from Story.GetNameList/GetElevation: {len(levels)}")
        log("ETABS story elevations: " + "; ".join(
            f"Storey {i} ({name}): {lo:g}–{hi:g} m" for i, name, lo, hi in levels
        ))
        return levels

    # Fallback to GetStories. Do not silently claim success if its arrays are
    # ambiguous; log the result so the user can diagnose the ETABS API shape.
    try:
        ret = story_api.GetStories()
    except Exception as exc:
        log(f"WARNING: ETABS Story.GetStories failed: {exc!r}")
        return []
    if isinstance(ret, (tuple, list)) and len(ret) >= 3:
        def as_list(value):
            if isinstance(value, (tuple, list)):
                return list(value)
            if isinstance(value, str) and value.strip().startswith(("[", "(")):
                try:
                    q = ast.literal_eval(value)
                    if isinstance(q, (tuple, list)):
                        return list(q)
                except Exception:
                    pass
            return []
        nms, heights = as_list(ret[1]), as_list(ret[2])
        records = []
        for name, height in zip(nms, heights):
            try:
                h = float(height)
                if str(name).strip() and math.isfinite(h) and h > 0:
                    records.append((str(name).strip(), h))
            except Exception:
                continue
        if records:
            # CSI often returns highest storey first. Use the same reported
            # heights but accumulate from the base in reverse order.
            bottom = 0.0
            for i, (name, h) in enumerate(reversed(records), 1):
                levels.append((i, name, bottom, bottom + h))
                bottom += h
            log("WARNING: Story.GetElevation unavailable; used GetStories heights fallback.")
            log("Fallback ETABS story count: " + str(len(levels)))
            return levels
    log(f"WARNING: Could not decode ETABS story names/elevations. GetStories result: {ret!r}")
    return []


def _extract_point_diaphragm_assignments(sap, point_names, log):
    """Read ETABS point diaphragm assignments through PointObj.GetDiaphragm.

    Only named, explicit diaphragm assignments are returned. Disconnected or
    program/shell-inherited assignments are not guessed into a rigid floor tie.
    """
    api=getattr(sap,"PointObj",None)
    method=getattr(api,"GetDiaphragm",None) if api is not None else None
    if method is None:
        log("WARNING: PointObj.GetDiaphragm unavailable; no ETABS rigid diaphragm memberships will be exported.")
        return {}
    assignments={}; failures=0
    for point in point_names:
        raw=None
        try:
            raw=method(str(point))
        except TypeError:
            try: raw=method(str(point),0,"")
            except Exception: failures+=1; continue
        except Exception:
            failures+=1; continue
        values=list(raw) if isinstance(raw,(tuple,list)) else [raw]
        strings=[str(v).strip() for v in values if isinstance(v,str) and str(v).strip()]
        if not strings:
            continue
        # CSI documents DiaphragmName as populated only for DefinedDiaphragm.
        # Take the final non-empty string from the Python COM result tuple.
        name=strings[-1]
        if name.casefold() in {"none","null","<none>","disconnect","program determined","from shell object"}:
            continue
        option=next((v for v in values if isinstance(v,(int,float)) and not isinstance(v,bool)),None)
        assignments[str(point)]={"diaphragm_name":name,"option_raw":option,"raw":repr(raw)}
    named=len(assignments)
    log(f"ETABS named point diaphragm assignments extracted: {named}/{len(point_names)}; API read failures={failures}")
    return assignments


def _write_section_review_gui(path, audit_json_path, connectivity_path):
    """Create a standalone GUI for reviewing extracted frame properties."""
    template = r'''# -*- coding: utf-8 -*-
"""Review/edit frame section assignments. Does not modify the ETABS EDB."""
import json, csv, math, ast, importlib.util, tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
AUDIT_PATH = Path("__AUDIT__")
CONNECTIVITY_PATH = Path("__CONNECTIVITY__")
NBC105_SETTINGS_PATH = Path("__NBC_SETTINGS__")
FIELDS = ["etabs_object","geometry_category","review_group","assigned_section","section_type","material_name","material_type_code","width_m","depth_m","tube_flange_thickness_m","tube_web_thickness_m","E_kN_m2","G_kN_m2","A_m2","Iy_m4","Iz_m4","J_m4","review_status","review_note"]
NUMERIC = {"material_type_code","width_m","depth_m","E_kN_m2","G_kN_m2","A_m2","Iy_m4","Iz_m4","J_m4"}
def num(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception: return None
def _report_gui_error(root,typ,value,tb):
    import traceback,datetime
    folder=Path(__file__).resolve().parent/'Startup_Logs';folder.mkdir(exist_ok=True)
    path=folder/'callback_errors.log'
    with path.open('a',encoding='utf8') as stream:
        stream.write(datetime.datetime.now().astimezone().isoformat()+'\n')
        traceback.print_exception(typ,value,tb,file=stream)
    messagebox.showerror('Interface error',str(value)+'\nLog: '+str(path),parent=root)

def main():
    payload=json.loads(AUDIT_PATH.read_text(encoding="utf-8")); rows=[]
    for src in payload.get("frame_assignments",[]):
        r={k:src.get(k) for k in FIELDS}; r["review_status"]="NEEDS REVIEW"
        r["review_note"]="Not approved. Verify against ETABS section/material tables and units."
        rows.append(r)
    root=tk.Tk(); root.title("OpenSeesPy — Frame Section Review / Edit"); root.geometry("1450x780")
    shell=ttk.Frame(root,padding=12); shell.pack(fill="both",expand=True)
    ttk.Label(shell,text="FRAME SECTION ASSIGNMENT REVIEW — BEAMS / COLUMNS / BRACES & OUTRIGGER CANDIDATES",font=("Segoe UI",16,"bold")).pack(anchor="w")
    ttk.Label(shell,text="Double-click a cell to edit. Blank values are never inferred. Area/slab/wall property audit is saved separately as OpenSees_Area_Section_Assignment_Audit.csv/.json.",wraplength=1300).pack(anchor="w",pady=(4,8))
    tf=ttk.Frame(shell); tf.pack(fill="both",expand=True)
    tree=ttk.Treeview(tf,columns=FIELDS,show="headings",selectmode="browse")
    widths={"etabs_object":90,"geometry_category":110,"review_group":230,"assigned_section":130,"section_type":190,"material_name":120,"material_type_code":100,"width_m":85,"depth_m":85,"E_kN_m2":105,"G_kN_m2":105,"A_m2":90,"Iy_m4":90,"Iz_m4":90,"J_m4":90,"review_status":120,"review_note":270}
    for f in FIELDS: tree.heading(f,text=f); tree.column(f,width=widths.get(f,100),minwidth=60,stretch=False)
    ys=ttk.Scrollbar(tf,orient="vertical",command=tree.yview); xs=ttk.Scrollbar(tf,orient="horizontal",command=tree.xview)
    tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set); tree.grid(row=0,column=0,sticky="nsew"); ys.grid(row=0,column=1,sticky="ns"); xs.grid(row=1,column=0,sticky="ew")
    tf.rowconfigure(0,weight=1); tf.columnconfigure(0,weight=1); iid_idx={}
    def refresh():
        for iid in tree.get_children(): tree.delete(iid)
        iid_idx.clear()
        for i,r in enumerate(rows):
            iid=tree.insert("","end",values=["" if r.get(f) is None else str(r.get(f)) for f in FIELDS]); iid_idx[iid]=i
    refresh(); edit=[None]
    def begin_edit(event):
        iid=tree.identify_row(event.y); col=tree.identify_column(event.x)
        if not iid or not col: return
        field=FIELDS[int(col[1:])-1]
        if field=="etabs_object": return
        b=tree.bbox(iid,col)
        if not b:return
        if edit[0] is not None: edit[0].destroy()
        x,y,w,h=b; entry=ttk.Entry(tree); edit[0]=entry; entry.place(x=x,y=y,width=w,height=h); entry.insert(0,tree.set(iid,field)); entry.focus_set()
        def save(_=None):
            if edit[0] is None:return
            value=entry.get().strip(); entry.destroy(); edit[0]=None; r=rows[iid_idx[iid]]
            r[field]=num(value) if field in NUMERIC and value else (value if value else None)
            r["review_status"]="EDITED — VERIFY"; r["review_note"]="Edited but not approved; compare against ETABS."; refresh()
        entry.bind("<Return>",save); entry.bind("<FocusOut>",save); entry.bind("<Escape>",lambda e: entry.destroy())
    tree.bind("<Double-1>",begin_edit)
    def save_audit():
        out=filedialog.asksaveasfilename(title="Save reviewed section assignments",defaultextension=".json",filetypes=[("JSON","*.json")],initialfile="OpenSees_Section_Assignment_Reviewed.json")
        if not out:return
        payload["frame_assignments_reviewed"]=rows; payload["reviewed_audit_path"]=out
        Path(out).write_text(json.dumps(payload,indent=2,default=str),encoding="utf-8")
        with open(str(Path(out).with_suffix(".csv")),"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
        messagebox.showinfo("Saved",f"Reviewed JSON and CSV saved.\\n{out}")
    def row_problems(r):
        problems=[]
        sec=str(r.get("assigned_section") or "").strip()
        if not sec or sec.casefold() in {"none","null","unassigned"}: problems.append("assigned_section")
        mat=str(r.get("material_name") or "").strip()
        if not mat or mat.casefold() in {"none","null"}: problems.append("material_name")
        typ=str(r.get("section_type") or "").strip().casefold()
        if not typ or typ=="unknown": problems.append("section_type")
        for k in ["width_m","depth_m","E_kN_m2","G_kN_m2","A_m2","Iy_m4","Iz_m4","J_m4"]:
            v=num(r.get(k))
            if v is None or v<=0: problems.append(k)
        if r.get("review_status") != "APPROVED": problems.append("review_status not APPROVED")
        return problems
    def approve_section_group():
        sel=tree.selection()
        if not sel:
            messagebox.showwarning("Select a row","Select a frame row for the section group to review."); return
        r=rows[iid_idx[sel[0]]]; sec=str(r.get("assigned_section") or "").strip()
        if not sec or sec.casefold() in {"none","null","unassigned"}:
            messagebox.showerror("Approval blocked","This frame has no valid section assignment. Resolve it in ETABS first."); return
        problems=[p for p in row_problems({**r,"review_status":"APPROVED"}) if p!="review_status not APPROVED"]
        if problems:
            messagebox.showerror("Approval blocked","Complete and verify these fields before approval:\\n\\n"+", ".join(problems)); return
        if not messagebox.askyesno("Confirm section approval",f"Approve the reviewed properties for ALL frame objects assigned to '{sec}'?\\n\\nConfirm only after comparing section dimensions, material properties, A/Iy/Iz/J and units with ETABS."):
            return
        copy_fields=["section_type","material_name","material_type_code","width_m","depth_m","tube_flange_thickness_m","tube_web_thickness_m","E_kN_m2","G_kN_m2","A_m2","Iy_m4","Iz_m4","J_m4"]
        count=0
        for target in rows:
            if str(target.get("assigned_section") or "").strip()==sec:
                for k in copy_fields: target[k]=r.get(k)
                target["review_status"]="APPROVED"
                target["review_note"]="User confirmed against ETABS; section-group approval."
                count+=1
        refresh(); messagebox.showinfo("Section group approved",f"Approved {count} frame rows for section '{sec}'. Save the reviewed audit.")
    def validate():
        blocked=[]
        for r in rows:
            probs=row_problems(r)
            if probs: blocked.append((r.get("etabs_object"),probs))
        approved=len(rows)-len(blocked)
        msg=f"Frame objects: {len(rows)}\\nRows passing all checks and explicitly approved: {approved}\\nRows blocked: {len(blocked)}\\n\\nMapped forceBeamColumn frame export: {'READY FOR GENERATION' if not blocked else 'BLOCKED'}\\nThe export includes supported global ETABS distributed frame loads on mapped beams, columns and inclined braces. Calibrate and validate sections before analysis; slab/wall area loads, automatic self-weight, device weights, mass, damping and NLTHA controls remain separate."
        if blocked: msg+="\\n\\nFirst blocked rows:\\n"+"\\n".join(f"{o}: {','.join(m)}" for o,m in blocked[:10])
        messagebox.showinfo("Section validation",msg)
    def export_force_beam_column():
        """Export approved frame connectivity as mapped nonlinear forceBeamColumn elements."""
        blocked=[]
        for r in rows:
            probs=row_problems(r)
            if probs: blocked.append((r.get('etabs_object'),probs))
        if blocked:
            messagebox.showerror('Export blocked',f'{len(blocked)} frame rows need verified properties and APPROVED status.'); return
        if not CONNECTIVITY_PATH.exists(): messagebox.showerror('Missing connectivity',str(CONNECTIVITY_PATH)); return
        try: tree_ast=ast.parse(CONNECTIVITY_PATH.read_text(encoding='utf-8'))
        except Exception as exc: messagebox.showerror('Connectivity error',str(exc)); return
        nodes=None; elems=None; diaphragm_groups=None; node_crosswalk=None
        for node in tree_ast.body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Name) and target.id in {'NODES','ELEMENT_CONNECTIVITY','ETABS_TO_OPENSEES_NODE_TAG','DIAPHRAGM_GROUPS'}:
                        try:
                            v=ast.literal_eval(node.value)
                            if target.id=='NODES': nodes=v
                            elif target.id=='ELEMENT_CONNECTIVITY': elems=v
                            elif target.id=='ETABS_TO_OPENSEES_NODE_TAG': node_crosswalk=v
                            elif target.id=='DIAPHRAGM_GROUPS': diaphragm_groups=v
                        except Exception: pass
        if not isinstance(nodes,dict) or not isinstance(elems,list): messagebox.showerror('Connectivity error','Could not parse literal NODES/ELEMENT_CONNECTIVITY data.'); return
        node_crosswalk=node_crosswalk if isinstance(node_crosswalk,dict) else {}
        diaphragm_groups=diaphragm_groups if isinstance(diaphragm_groups,list) else []
        secmap={str(r['etabs_object']):r for r in rows}
        eligible=[e for e in elems if e.get('dimension')=='line_2_node' and e.get('category') in {'BEAM','COLUMN','BRACE','OTHER FRAME'}]
        device_assignments=ETABS_DEVICE_ASSIGNMENTS if isinstance(ETABS_DEVICE_ASSIGNMENTS,dict) else {}
        eligible_by_name={str(e.get('etabs_object')):e for e in eligible}
        missing=[str(e.get('etabs_object')) for e in eligible if str(e.get('etabs_object')) not in secmap and str(e.get('etabs_object')) not in device_assignments]
        if missing: messagebox.showerror('Section mapping error','Frame objects lack review rows: '+', '.join(missing[:12])); return
        mapping=__MAPPING__
        unknown_devices=sorted(set(device_assignments)-set(eligible_by_name))
        if unknown_devices: messagebox.showerror('Device mapping error','Device assignments must use exact eligible ETABS frame object IDs:\n'+'\n'.join(unknown_devices[:12])); return
        for obj,device in device_assignments.items():
            if not isinstance(device,dict) or str(device.get('type','')).upper() not in ('FVD','BRB'):
                messagebox.showerror('Device mapping error',f'{obj}: device type must be FVD or BRB.'); return
            if str(eligible_by_name[obj].get('category','')).upper()!='BRACE':
                messagebox.showerror('Device mapping error',f'{obj}: only ETABS objects classified BRACE can be assigned as a device.'); return
            required=({'material_tag','K','Cd','alpha'} if device['type'].upper()=='FVD' else {'material_tag','Fy','E0','b','R0','cR1','cR2','a1','a2','a3','a4','core_area'})
            missing_fields=required-set(device)
            if missing_fields: messagebox.showerror('Device mapping error',f'{obj}: missing calibrated fields: '+', '.join(sorted(missing_fields))); return
        material_tags=[int(d['material_tag']) for d in device_assignments.values()]
        if len(material_tags)!=len(set(material_tags)):
            messagebox.showerror('Device mapping error','This exporter defines one material per replaced brace. Give each assigned device a unique material_tag.'); return
        unmapped=sorted({str(secmap[str(e.get('etabs_object'))].get('assigned_section') or '') for e in eligible if str(e.get('etabs_object')) not in device_assignments and str(secmap[str(e.get('etabs_object'))].get('assigned_section') or '') not in mapping})
        if unmapped: messagebox.showerror('Section mappings missing','Commit ETABS-to-OpenSeesPy mappings in the main program first:\n\n'+'\n'.join(unmapped[:20])); return
        if not Path(__file__).resolve().with_name('Define_Section_V109.py').exists():
            messagebox.showerror('Define_Section_V109.py missing','Keep Define_Section_V109.py beside this program.'); return
        section_tags={'SHS_350x350x16_STEEL_FIBER':701,'RC_BEAM_600x800_FIBER':611,'RC_COLUMN_1100x1100_FIBER':621,'RC_COLUMN_1250x1250_FIBER':631}
        targets=sorted({mapping[str(secmap[str(e.get('etabs_object'))].get('assigned_section') or '')] for e in eligible if str(e.get('etabs_object')) not in device_assignments})
        unsupported=sorted(set(targets)-set(section_tags))
        if unsupported: messagebox.showerror('Unsupported target','Define_Section_V109.py lacks executable fiber sections for: '+', '.join(unsupported)); return
        out=filedialog.asksaveasfilename(title='Export mapped nonlinear forceBeamColumn frame model',defaultextension='.py',filetypes=[('Python','*.py')],initialfile='OpenSees_ForceBeamColumn_Frame_Model.py')
        if not out:return
        integration_tags={name:10001+i for i,name in enumerate(targets)}
        # Preserve ETABS object IDs while using the reserved OpenSees integer tag
        # as the actual ops.element tag.  Dimension is part of the key because
        # ETABS frame and area IDs can overlap.
        element_tag_map={(('FRAME' if e.get('dimension')=='line_2_node' else 'AREA'),str(e.get('etabs_object'))):int(e.get('tag',e.get('element_tag'))) for e in eligible}
        lines=['# Approved ETABS connectivity mapped to nonlinear OpenSeesPy fiber sections.',
          '# forceBeamColumn + Lobatto integration; calibrate and validate materials before NLTHA.',
          '# 3-D local axes: node order gives local x; vecxz is global Z for horizontal members and global X for near-vertical members.',
          '# Horizontal-member local z stays vertical; vertical-member local z points global X, matching the section-axis convention.',
          '# PDelta includes member P-Delta geometric stiffness; OpenSees PDelta does not include P-small-delta.',
          '# IS 16700:2023 §7.2(d) factor maps are exported for review; this script does not execute the factored static combination automatically.',
          '# NBC 105 elastic cracked-stiffness multipliers are not applied to these nonlinear fiber sections.',
          '# Imports supported ETABS global X/Y/Z/gravity distributed frame loads on mapped beams, columns and inclined braces.',
          '# IMPORTANT: this exporter is not a complete gravity/mass model. Area loads, slab and shear-wall self-weight/load transfer, device weights, seismic mass, and NLTHA controls are not complete. Review the load ledger and resolve every skipped category before analysis.',
          '# Keep the companion section/load/analysis helpers and V115 Step 13/device modules beside this exported script.', 'import openseespy.opensees as ops',
          'import math, json', 'ops.wipe()', 'ops.model("basic", "-ndm", 3, "-ndf", 6)', 'NODES = '+repr(nodes),
          'ETABS_TO_OPENSEES_NODE_TAG = '+repr(node_crosswalk),
          'DIAPHRAGM_GROUPS = '+repr(diaphragm_groups),
          'for tag, xyz in NODES.items(): ops.node(int(tag), *xyz)',
          'from Define_Section_V109 import define_all_fiber_sections',
          'from OpenSees_Step13_Analysis_Basis_V115 import NBC105_FLEXURAL_MODIFIERS, IS16700_SLAB_MODIFIERS, initial_pdelta_combinations, effective_flexural_modifier',
          'from NBC105_Analysis_Settings_V108 import CRACKED_STIFFNESS_MODIFIERS, NBC105_NLTHA_STIFFNESS_POLICY, NBC105_LOAD_FACTORS, UNFACTORED_LOAD_POLICY, LOAD_ACCOUNTING_COVERAGE',
          'from NBC105_Load_Accounting_V108 import perimeter_equivalent_line_load_kN_m, line_self_weight_kN_m, surface_self_weight_kN_m2, gravity_udl_local_components_kN_m, self_weight_policy, factored_component_loads',
          'from OpenSees_Analysis_Stack_V108 import ANALYSIS_MODE_CHOICES, NONLINEAR_ALGORITHM_CHOICES, configure_analysis_mode, configure_nonlinear_static, run_static_analysis, run_gravity_stage, freeze_gravity_loads, configure_nonlinear_transient, run_transient_analysis, configure_linear_static',
          'from OpenSees_FVD_BRB_Devices_V115 import define_fvd_material, add_fvd_link, define_brb_core_material, add_brb_corot_truss',
          '# Analysis helpers are imported but not run: complete and verify loads, masses, links, and records first.',
          '# After applying reviewed gravity patterns, call run_gravity_stage(ops, support_nodes, verified_total_downward_load_kN, nsteps=10). It checks reactions and freezes gravity at time zero only after equilibrium passes.',
          '# After defining the verified ground-motion pattern/record: run_transient_analysis(ops, nsteps, dt).',
          '# Helpers are available for verified inputs. The exporter deliberately does not guess support tributaries, device weights, or ETABS self-weight settings.',
          'SECTION_LIBRARY = define_all_fiber_sections(ops, unit_system="kN-m")',
          '# Step 13: initial P-Delta combinations follow IS 16700:2023 §7.2(d), separate from the gravity preload for time history.',
          'IS16700_INITIAL_PDELTA_COMBINATIONS = {**initial_pdelta_combinations("EL", ("X", "Y")), **initial_pdelta_combinations("WL", ("X", "Y"))}',
          '# V116 default elastic flexural modifier policy: NBC 105:2025 Table 3-1 for beams, columns, walls and flat slabs.',
          '# These are reference values only: this exporter creates no slab shell and does not modify nonlinear fiber materials.',
          'NBC105_EFFECTIVE_STIFFNESS_REFERENCE = NBC105_FLEXURAL_MODIFIERS',
          'IS16700_SLAB_EFFECTIVE_STIFFNESS = IS16700_SLAB_MODIFIERS',
          'NBC105_LOAD_COMBINATION_FACTORS = NBC105_LOAD_FACTORS',
          'LOAD_PATTERN_POLICY = UNFACTORED_LOAD_POLICY',
          'LOAD_COVERAGE_AND_OPEN_ITEMS = LOAD_ACCOUNTING_COVERAGE',
          'SECTION_TAGS = '+repr(section_tags), 'INTEGRATION_TAGS = '+repr(integration_tags),
          '# ETABS object identity -> actual OpenSees element tag (not a fabricated ETABS ID).',
          'ETABS_TO_OPENSEES_ELEMENT_TAG = '+repr({f'{k[0]}:{k[1]}':v for k,v in element_tag_map.items()}),
          'INTEGRATION_POINTS = 5  # verify by sensitivity study',
          'for name, tag in INTEGRATION_TAGS.items(): ops.beamIntegration("Lobatto", tag, SECTION_TAGS[name], INTEGRATION_POINTS)',
          'FRAME_SECTION_MAP = {']
        for e in eligible:
            obj=str(e.get('etabs_object'))
            if obj in device_assignments: continue
            r=secmap[obj]; source=str(r.get('assigned_section') or ''); target=mapping[source]
            lines.append('    '+repr(obj)+': '+repr({'etabs_section':source,'fiber_section':target,'section_tag':section_tags[target],'integration_tag':integration_tags[target],'review_status':r.get('review_status')})+',')
        lines += ['}', 'DEVICE_ASSIGNMENT_MAP = '+repr(device_assignments),
                  '# Device replacement entries are explicit project inputs; check the companion device audit before use.',
                  '# Fixed supports follow extracted base elevation; verify against ETABS.']
        base_z=min((float(xyz[2]) for xyz in nodes.values()),default=0.0)
        base_support_tags=[int(tag) for tag,xyz in nodes.items() if abs(float(xyz[2])-base_z)<1e-6]
        lines.append('FIXED_SUPPORT_NODE_TAGS = '+repr(base_support_tags)+'  # read by the gravity GUI')
        for tag,xyz in nodes.items():
            if abs(float(xyz[2])-base_z)<1e-6: lines.append(f'ops.fix({int(tag)}, 1, 1, 1, 1, 1, 1)')
        lines += ['', '# Rigid diaphragms copied from explicit ETABS point diaphragm assignments.',
                  '# Each master retains UX, UY and RZ; UZ, RX and RY are restrained.',
                  'DIAPHRAGM_MASTER_TAGS = {}', 'DIAPHRAGM_CROSSWALK = {}']
        _node_ints={int(tag) for tag in nodes}
        for group in diaphragm_groups:
            master=int(group['master_tag'])
            slaves=[int(t) for t in group['slave_node_tags'] if int(t) in _node_ints]
            if len(slaves)<3: continue
            xyz=group['master_xyz']
            key=f'{group["storey_number"]}:{group["diaphragm_name"]}'
            lines += [f'ops.node({master}, {float(xyz[0]):.10g}, {float(xyz[1]):.10g}, {float(xyz[2]):.10g})  # {group["diaphragm_name"]}, storey {group["storey_number"]}',
                      f'ops.fix({master}, 0, 0, 1, 1, 1, 0)',
                      f'ops.rigidDiaphragm(3, {master}, '+', '.join(map(str,slaves))+')',
                      f'DIAPHRAGM_MASTER_TAGS[{key!r}] = {master}',
                      f'DIAPHRAGM_CROSSWALK[{key!r}] = {{"etabs_diaphragm_id": {group["etabs_diaphragm_id"]!r}, "opensees_diaphragm_id": {group["opensees_diaphragm_id"]}, "master_node_tag": {master}}}']
        lines += ["# Use this handler in every analysis stage containing these multi-point constraints.",
                  "ops.constraints('Transformation')"]
        used=set(); created=0; actual_frame_tags={}
        for e in eligible:
            obj=str(e.get('etabs_object')); r=secmap.get(obj,{}); i,j=e.get('nodes',[None,None])[:2]
            xi=nodes.get(i,nodes.get(str(i))); xj=nodes.get(j,nodes.get(str(j)))
            if xi is None or xj is None: continue
            dx=float(xj[0])-float(xi[0]); dy=float(xj[1])-float(xi[1]); dz=float(xj[2])-float(xi[2]); length=math.sqrt(dx*dx+dy*dy+dz*dz)
            if length<=1e-10: continue
            try: etag=int(e.get('tag',e.get('element_tag')))
            except Exception: etag=None
            if etag is None or etag in used: etag=max(used,default=0)+1
            used.add(etag); transf=etag; vec=(1.0,0.0,0.0) if abs(dz)/length>0.90 else (0.0,0.0,1.0)
            actual_frame_tags[obj]=etag
            device=device_assignments.get(obj)
            if device:
                kind=str(device['type']).upper()
                if kind=='FVD':
                    lines.append(f'FVD_MATERIAL_{etag} = define_fvd_material(ops, material_tag={int(device["material_tag"])}, K={float(device["K"]):.12g}, Cd={float(device["Cd"]):.12g}, alpha={float(device["alpha"]):.12g}, unit_note="kN-m-s; cite datasheet/test")  # ETABS brace {obj}; verify the damper line of action')
                    lines.append(f'FVD_ELEMENT_{etag} = add_fvd_link(ops, element_tag={etag}, i_node={int(i)}, j_node={int(j)}, material_tag={int(device["material_tag"])}, do_rayleigh=False)')
                else:
                    lines.append(f'BRB_MATERIAL_{etag} = define_brb_core_material(ops, material_tag={int(device["material_tag"])}, Fy={float(device["Fy"]):.12g}, E0={float(device["E0"]):.12g}, b={float(device["b"]):.12g}, R0={float(device["R0"]):.12g}, cR1={float(device["cR1"]):.12g}, cR2={float(device["cR2"]):.12g}, a1={float(device["a1"]):.12g}, a2={float(device["a2"]):.12g}, a3={float(device["a3"]):.12g}, a4={float(device["a4"]):.12g}, unit_note="kN-m-s; cite brace test/calibration")  # calibrated BRB core only')
                    lines.append(f'BRB_ELEMENT_{etag} = add_brb_corot_truss(ops, element_tag={etag}, i_node={int(i)}, j_node={int(j)}, core_area={float(device["core_area"]):.12g}, material_tag={int(device["material_tag"])})  # ETABS brace {obj}')
                created+=1
                continue
            lines.append(f'ops.geomTransf("PDelta", {transf}, {vec[0]}, {vec[1]}, {vec[2]})  # local x = node i -> j; PDelta for seismic NLTHA; verify ETABS object {obj}')
            target=mapping[str(r.get('assigned_section') or '')]; integ=integration_tags[target]
            lines.append(f'ops.element("forceBeamColumn", {etag}, {int(i)}, {int(j)}, {transf}, {integ}, "-iter", 20, 1.0e-10)  # ETABS frame object {obj} -> OpenSees element {etag}; {r.get("assigned_section")} -> {target}')
            created+=1
        # Convert imported ETABS frame distributed assignments to native eleLoad
        # commands. Load patterns are created after elements and preserve ETABS names.
        imported_loads=[]; skipped_loads=[]; load_patterns={}
        _eligible_by_obj={str(e.get('etabs_object')):e for e in eligible}
        for load in payload.get('frame_distributed_load_assignments',[]):
            obj=str(load.get('object','')); elem=_eligible_by_obj.get(obj); reason=None
            if elem is None or obj not in actual_frame_tags: reason='frame element was not exported'
            elif int(load.get('load_type') or 0)!=1: reason='ETABS assignment is not force per unit length'
            elif str(load.get('coordinate_system','')).strip().casefold()!='global': reason='coordinate system is not Global'
            elif int(load.get('direction_code') or 0) not in (4,5,6,10): reason='direction is not Global X, Global Y, Global Z, or Gravity'
            elif load.get('value_start') is None or load.get('value_end') is None: reason='load intensity is missing'
            if reason:
                skipped_loads.append({**load,'skip_reason':reason}); continue
            ni,nj=elem.get('nodes',[None,None])[:2]
            xi=nodes.get(ni,nodes.get(str(ni))); xj=nodes.get(nj,nodes.get(str(nj)))
            if xi is None or xj is None: reason='endpoint coordinates are unavailable'
            else:
                dx=float(xj[0])-float(xi[0]); dy=float(xj[1])-float(xi[1]); dz=float(xj[2])-float(xi[2]); length=math.sqrt(dx*dx+dy*dy+dz*dz)
                if length<=1e-10: reason='frame element has zero/invalid length'
            if reason:
                skipped_loads.append({**load,'skip_reason':reason}); continue
            d1=float(load.get('distance_start') or 0.0); d2=float(load.get('distance_end') or 0.0)
            if load.get('relative_start'): d1*=length
            if load.get('relative_end'): d2*=length
            # CSI GetLoadDistributed Dist1/Dist2 both measure from the I-end.
            a=max(0.0,min(1.0,d1/length)); b=max(0.0,min(1.0,d2/length))
            if b<=a:
                skipped_loads.append({**load,'skip_reason':'invalid or zero-length load interval'}); continue
            direction=int(load['direction_code']); v1=float(load['value_start']); v2=float(load['value_end'])
            # Project Global X/Y/Z or gravity vector into the emitted OpenSees
            # local x/y/z axes. This supports vertical columns and inclined
            # braces as well as horizontal beams; preserve exact member orientation.
            ux,uy,uz=dx/length,dy/length,dz/length
            ref=(1.0,0.0,0.0) if abs(dz)/length>0.90 else (0.0,0.0,1.0)
            # Same vecxz used by ops.geomTransf above; local y = vecxz x local x.
            lyx=ref[1]*uz-ref[2]*uy; lyy=ref[2]*ux-ref[0]*uz; lyz=ref[0]*uy-ref[1]*ux
            ynorm=math.sqrt(lyx*lyx+lyy*lyy+lyz*lyz)
            if ynorm<=1e-12:
                skipped_loads.append({**load,'skip_reason':'could not construct stable OpenSees local axes'}); continue
            lyx,lyy,lyz=lyx/ynorm,lyy/ynorm,lyz/ynorm
            lzx=uy*lyz-uz*lyy; lzy=uz*lyx-ux*lyz; lzz=ux*lyy-uy*lyx
            if direction==4: gx,gy,gz=1.0,0.0,0.0
            elif direction==5: gx,gy,gz=0.0,1.0,0.0
            elif direction==6: gx,gy,gz=0.0,0.0,1.0
            else: gx,gy,gz=0.0,0.0,-1.0  # CSI positive gravity is downward
            wyproj=gx*lyx+gy*lyy+gz*lyz; wzproj=gx*lzx+gy*lzy+gz*lzz; wxproj=gx*ux+gy*uy+gz*uz
            wy1=v1*wyproj; wy2=v2*wyproj
            wz1=v1*wzproj; wz2=v2*wzproj
            wx1=v1*wxproj; wx2=v2*wxproj
            pattern=str(load.get('pattern') or 'UNNAMED'); etag=actual_frame_tags[obj]
            load_patterns.setdefault(pattern,[]).append((etag,wy1,wz1,wx1,wy2,wz2,wx2,a,b,obj))
            imported_loads.append({**load,'opensees_element_tag':etag,'opensees_Wy_start':wy1,'opensees_Wz_start':wz1,'opensees_Wx_start':wx1,'opensees_Wy_end':wy2,'opensees_Wz_end':wz2,'opensees_Wx_end':wx2,'global_Z_start':v1*gz,'global_Z_end':v2*gz,'start_over_L':a,'end_over_L':b,'element_length_m':length})
        lines += ['', '# Imported ETABS frame loads: reviewed force-per-length Global X/Y/Z or gravity assignments.',
                  '# Projected to local Wy/Wz/Wx using the same local-axis definition as the emitted OpenSees geometric transformation.',
                  '# CSI gravity direction is downward; verify units and direction codes against the source ETABS model.',
                  '# Imported ETABS reference loads are UNFACTORED. Keep DL/LL patterns separate. For gravity preload use reviewed service-level DL + sustained LL, converge, then ops.loadConst("-time", 0.0). Do not apply ULS factors to a ground-motion record. NBC 105:2025 §3.6 combinations are post-analysis/design combinations.',
                  '# Other load types/directions are recorded in the JSON review file, not silently applied.']
        for pidx,(pattern,loads_for_pattern) in enumerate(sorted(load_patterns.items()),start=1):
            ltag=50000+pidx
            lines += [f'ops.timeSeries("Linear", {ltag})',f'ops.pattern("Plain", {ltag}, {ltag})  # ETABS pattern: {pattern}']
            for etag,wy1,wz1,wx1,wy2,wz2,wx2,a,b,obj in loads_for_pattern:
                if abs(a)<1e-12 and abs(b-1.0)<1e-12 and abs(wy1-wy2)+abs(wz1-wz2)+abs(wx1-wx2)<1e-12:
                    lines.append(f'ops.eleLoad("-ele", {etag}, "-type", "-beamUniform", {wy1:.12g}, {wz1:.12g}, {wx1:.12g})  # ETABS frame {obj}; {pattern}; full-span uniform')
                else:
                    lines.append(f'ops.eleLoad("-ele", {etag}, "-type", "-beamUniform", {wy1:.12g}, {wz1:.12g}, {wx1:.12g}, {a:.12g}, {b:.12g}, {wy2:.12g}, {wz2:.12g}, {wx2:.12g})  # ETABS frame {obj}; {pattern}; partial/trapezoidal')
        _gravity_vertical_integral=sum(float(q.get("element_length_m",0.0))*(float(q.get("end_over_L",0.0))-float(q.get("start_over_L",0.0)))*(float(q.get("global_Z_start",0.0))+float(q.get("global_Z_end",0.0)))/2.0 for q in imported_loads)
        _gravity_total_downward=-_gravity_vertical_integral
        gravity_gui_inputs={"support_node_tags":base_support_tags,"total_downward_load_kN":_gravity_total_downward,"load_steps":10,"load_total_source":"Integrated global-Z component of imported ETABS frame line loads.","load_total_units_note":"Assumes ETABS API line-load values are kN/m. Verify active ETABS units before analysis.","coverage_note":"Does not include ETABS automatic self-weight, slab/wall area loads, or device weights; reconcile these independently before gravity analysis."}
        lines += ['GRAVITY_GUI_INPUTS = '+repr(gravity_gui_inputs)+'  # read by the gravity GUI',
          'with open("OpenSees_Committed_Section_Map.json", "w", encoding="utf-8") as f:',
          '    json.dump({"frame_section_map": FRAME_SECTION_MAP, "device_assignment_map": DEVICE_ASSIGNMENT_MAP, "etabs_to_opensees_element_tag": ETABS_TO_OPENSEES_ELEMENT_TAG, "created_elements": len(ops.getEleTags()), "frame_distributed_loads_applied": '+repr(imported_loads)+', "frame_distributed_loads_skipped": '+repr(skipped_loads)+', "NBC105_effective_stiffness_reference": NBC105_EFFECTIVE_STIFFNESS_REFERENCE, "IS16700_slab_effective_stiffness": IS16700_SLAB_EFFECTIVE_STIFFNESS, "IS16700_initial_pdelta_combinations": IS16700_INITIAL_PDELTA_COMBINATIONS, "NBC105_load_combination_factors": NBC105_LOAD_COMBINATION_FACTORS, "unfactored_load_policy": LOAD_PATTERN_POLICY, "load_accounting_coverage_and_open_items": LOAD_COVERAGE_AND_OPEN_ITEMS, "analysis_ready": False}, f, indent=2)',
          'print("Nodes:", len(ops.getNodeTags()))', 'print("forceBeamColumn elements:", len(ops.getEleTags()))',
          'print("ETABS distributed frame loads imported:", '+str(len(imported_loads))+')', 'print("ETABS distributed frame loads skipped for review:", '+str(len(skipped_loads))+')',
          'print("Frame domain created; no analysis was run.")',
          'print("Analysis helpers loaded: nonlinear static gravity and nonlinear Newmark transient NLTHA.")']
        module_source=Path(__file__).resolve().with_name('Define_Section_V109.py')
        module_copy=Path(out).resolve().with_name('Define_Section_V109.py')
        nbc_source=Path(NBC105_SETTINGS_PATH).resolve()
        nbc_copy=Path(out).resolve().with_name('NBC105_Analysis_Settings_V108.py')
        if nbc_source!=nbc_copy:
            nbc_copy.write_text(nbc_source.read_text(encoding='utf-8'),encoding='utf-8')
        if module_source.resolve()!=module_copy:
            module_copy.write_text(module_source.read_text(encoding='utf-8'),encoding='utf-8')
        accounting_source=Path(__file__).resolve().with_name('NBC105_Load_Accounting_V108.py')
        accounting_copy=Path(out).resolve().with_name('NBC105_Load_Accounting_V108.py')
        if not accounting_source.exists():
            messagebox.showerror('Load accounting module missing',str(accounting_source)); return
        if accounting_source.resolve()!=accounting_copy:
            accounting_copy.write_text(accounting_source.read_text(encoding='utf-8'),encoding='utf-8')
        analysis_source=Path(__file__).resolve().with_name('OpenSees_Analysis_Stack_V108.py')
        analysis_copy=Path(out).resolve().with_name('OpenSees_Analysis_Stack_V108.py')
        if not analysis_source.exists():
            messagebox.showerror('Analysis stack module missing',str(analysis_source)); return
        if analysis_source.resolve()!=analysis_copy:
            analysis_copy.write_text(analysis_source.read_text(encoding='utf-8'),encoding='utf-8')
        for helper_name in ('OpenSees_Step13_Analysis_Basis_V115.py','OpenSees_FVD_BRB_Devices_V115.py'):
            helper_source=Path(__file__).resolve().with_name(helper_name)
            helper_copy=Path(out).resolve().with_name(helper_name)
            if not helper_source.exists():
                messagebox.showerror('Required helper module missing',str(helper_source)); return
            if helper_source.resolve()!=helper_copy:
                helper_copy.write_text(helper_source.read_text(encoding='utf-8'),encoding='utf-8')
        Path(out).write_text(chr(10).join(lines)+chr(10),encoding='utf-8')
        try: compile(Path(out).read_text(encoding='utf-8'),out,'exec')
        except Exception as exc: Path(out).unlink(missing_ok=True); messagebox.showerror('Generated syntax error',str(exc)); return
        reviewed_path=str(Path(out).with_name('OpenSees_Section_Assignment_Reviewed.json'))
        payload['frame_assignments_reviewed']=rows; payload['committed_model_path']=out
        Path(reviewed_path).write_text(json.dumps(payload,indent=2,default=str),encoding='utf-8')
        with open(str(Path(out).with_name('OpenSees_Section_Assignment_Reviewed.csv')),'w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
        messagebox.showinfo('OpenSees forceBeamColumn export complete',f'Exported {created} mapped forceBeamColumn elements.\nImported ETABS frame distributed loads: {len(imported_loads)}\nSkipped for review: {len(skipped_loads)}\n\nModel: {out}\nLoad details and skip reasons: OpenSees_Committed_Section_Map.json\n\nThis is still a partial model: area-load transfer, ETABS automatic self-weight, device weights/elements, seismic mass, and analysis stages are not all implemented. Review every load and mass ledger before analysis.')
    bar=ttk.Frame(shell); bar.pack(fill="x",pady=(8,0))
    ttk.Button(bar,text="Approve selected section group",command=approve_section_group).pack(side="left",padx=(0,8))
    ttk.Button(bar,text="Validate section data",command=validate).pack(side="left",padx=(0,8))
    ttk.Button(bar,text="Save reviewed audit (JSON + CSV)",command=save_audit).pack(side="left",padx=(0,8))
    ttk.Button(bar,text="Export mapped forceBeamColumn model",command=export_force_beam_column).pack(side="left",padx=(0,8))
    ttk.Button(bar,text="Close",command=root.destroy).pack(side="right")
    if __import__('os').environ.get('OPENSEES_STARTUP_SMOKE')=='1':root.after(1500,root.destroy)
    root.mainloop()
if __name__=="__main__": main()
'''
    settings_path=str(Path(__file__).resolve().with_name("NBC105_Analysis_Settings_V108.py"))
    template = template.replace("__AUDIT__", audit_json_path.replace("\\", "\\\\")).replace("__CONNECTIVITY__", connectivity_path.replace("\\", "\\\\")).replace("__NBC_SETTINGS__", settings_path.replace("\\", "\\\\")).replace("__MAPPING__", repr(ETABS_TO_OPENSEES_SECTION))
    Path(path).write_text(template, encoding="utf-8")


# ============================================================================
# SECTION 04 — ETABS → OPENSEESPY IMPORT, AUDIT, EXPORT AND VIEWS
# This function coordinates ETABS extraction and OpenSees-oriented audit exports.
# It is deliberately an audit/connectivity stage, not a completed analysis model.
# ============================================================================
@timed_outputs('ETABS complete conversion','outdir')
def convert_model(edb, outdir, log, include_live=True):
    if ops is None: raise RuntimeError("OpenSeesPy not installed in this environment.")
    os.makedirs(outdir,exist_ok=True)
    etabs=sap=None
    _conversion_started=time.perf_counter(); _step_started=None; _step_name=None; _conversion_succeeded=False
    def _begin_step(name):
        nonlocal _step_started,_step_name
        if _step_name is not None:
            log(f"[STEP OK] {_step_name} — {time.perf_counter()-_step_started:.2f} s")
        _step_name=str(name); _step_started=time.perf_counter()
        log(f"[STEP START] {_step_name}")
    def _finish_step(status="OK"):
        nonlocal _step_started,_step_name
        if _step_name is None: return
        log(f"[STEP {status}] {_step_name} — {time.perf_counter()-_step_started:.2f} s")
        _step_name=None; _step_started=None
    try:
        # --------------------------------------------------------------------
        # SECTION 05 — ETABS SOURCE UNITS AND MODEL EXTRACTION
        # ETABS present units are requested as kN-m-C (CSI enum 6). The audit
        # records this request; always verify the active units in the log.
        # --------------------------------------------------------------------
        _begin_step("ETABS connection and source model extraction")
        etabs,sap=_connect_etabs(edb,log)
        point_names=_api_names(sap.PointObj)
        frame_names=_api_names(sap.FrameObj)
        area_names=_api_names(sap.AreaObj)
        link_api=getattr(sap,"LinkObj",None)
        link_names=_api_names(link_api) if link_api is not None else []
        log(f"ETABS object counts: points={len(point_names)}, frames={len(frame_names)}, areas={len(area_names)}, links={len(link_names)}")
        coords=_point_coords(sap,point_names)
        etabs_story_levels = _extract_etabs_story_levels(sap, log)
        # Normalize point names consistently between connectivity and coordinate lookup.
        coords={str(k).strip(): v for k, v in coords.items()}
        point_diaphragms=_extract_point_diaphragm_assignments(sap,point_names,log)
        frame_conn={str(n).strip():[str(p).strip() for p in _get_points(sap.FrameObj,n)] for n in frame_names}
        area_conn={str(n).strip():[str(p).strip() for p in _get_points(sap.AreaObj,n)] for n in area_names}
        link_conn={str(n).strip():[str(p).strip() for p in _get_points(link_api,n)] for n in link_names} if link_api is not None else {}
        frame_section_assignments, frame_section_defs = _extract_frame_section_assignments(sap, frame_names, log)
        area_section_assignments, area_section_defs = _extract_area_section_assignments(sap, area_names, log)
        section_by_obj={str(r["etabs_object"]):r for r in frame_section_assignments}
        area_section_by_obj={str(r.get("etabs_area_object")):r for r in area_section_assignments}
        area_loads,area_raw=_extract_area_assignments(sap,area_names,log)
        frame_loads,frame_raw=_extract_frame_distributed(sap,frame_names)
        self_weight_pattern_audit=_extract_etabs_self_weight_patterns(sap)
        log("ETABS load-pattern self-weight multipliers (audit only; no OpenSees recreation): " + ", ".join(f"{q['pattern']}={q['multiplier']}" for q in self_weight_pattern_audit))
        if any(q.get("multiplier") not in (None,0,0.0) for q in self_weight_pattern_audit):
            log("REVIEW REQUIRED: ETABS auto self-weight is active. Confirm it is assigned once (normally one dead-load pattern), then transfer section/material self-weight to OpenSees or apply a verified ETABS-consistent gravity load. Avoid double counting.")
        log(f"ETABS frame distributed loads returned: {len(frame_loads)}; patterns: " + ", ".join(sorted({str(q.get('pattern')) for q in frame_loads}) or ["none"]))
        log(f"ETABS frame load parse/API records: {sum(1 for q in frame_raw if q.get('parse_error'))} parsing issue(s); inspect raw ETABS API responses in the audit JSON.")
        frame_lookup={str(k).strip().casefold():v for k,v in frame_conn.items()}
        log(f"Connectivity extraction: frame endpoints mapped={sum(1 for v in frame_conn.values() if len(v)>=2 and all(p in coords for p in v[:2]))}/{len(frame_conn)}; area polygons mapped={sum(1 for v in area_conn.values() if len(v)>=3 and all(p in coords for p in v))}/{len(area_conn)}")
        # Build robust exact/normalized aliases. CSI sometimes returns numeric IDs
        # with whitespace or a numeric-string representation that differs only in formatting.
        area_conn_by_name={}
        for k, v in area_conn.items():
            if len(v) >= 3 and all(str(p) in coords for p in v):
                area_conn_by_name[str(k).strip()] = v
                area_conn_by_name[str(k).strip().casefold()] = v
                try:
                    area_conn_by_name[str(int(str(k).strip()))] = v
                except Exception:
                    pass
        # Area API can identify area elements rather than objects; only map exact IDs/names, no guessed nearest mapping.
        applied=[]; skipped=[]; nodal={}
        wanted=SAFE_AREA_PATTERNS if include_live else {"dead","dl","super dead","sdead","floor finish","partition","roof live","rooflive"}
        for a in area_loads:
            pat=a['pattern']
            if pat.casefold() in {x.casefold() for x in EXCLUDED_PATTERNS}:
                skipped.append({**a,"reason":"Excluded special pattern; magnitude/sign not interpreted"}); continue
            if pat.casefold() not in {x.casefold() for x in wanted}:
                skipped.append({**a,"reason":"Pattern name is not in the conservative area-load allowlist; add its exact verified ETABS name to SAFE_AREA_PATTERNS"}); continue
            try: area_dir=int(a['direction_code'])
            except (TypeError,ValueError): area_dir=-1
            if str(a['coordinate_system']).strip().casefold()!="global" or area_dir not in (6,10):
                skipped.append({**a,"reason":"Only Global Z (direction 6, upward) or Gravity (direction 10, downward) uniform area loads are imported"}); continue
            obj=str(a['object'])
            pts=area_conn_by_name.get(obj.strip(), area_conn_by_name.get(obj.strip().casefold()))
            if not pts:
                try: pts=area_conn_by_name.get(str(int(obj.strip())))
                except Exception: pts=None
            if not pts:
                skipped.append({**a,"reason":"No exact AreaObj connectivity match; no guessed mapping"}); continue
            xyz=[coords[p] for p in pts]
            # Compute area for a planar polygon with Newell's method.
            nx=ny=nz=0.0
            for i in range(len(xyz)):
                x1,y1,z1=xyz[i]; x2,y2,z2=xyz[(i+1)%len(xyz)]
                nx+=(y1-y2)*(z1+z2); ny+=(z1-z2)*(x1+x2); nz+=(x1-x2)*(y1+y2)
            area=0.5*math.sqrt(nx*nx+ny*ny+nz*nz)
            if not math.isfinite(area) or area<=1e-8:
                skipped.append({**a,"reason":"Invalid/zero polygon area"}); continue
            # ETABS 2016+ uses direction 6=global +Z and direction 10=gravity -Z;
            # Preserve signed intensity: negative global-Z pressure is downward;
            # positive Gravity pressure is downward. Never discard its sign.
            total=(1.0 if area_dir==6 else -1.0)*float(a['value'])*area
            # Equivalent nodal force divided equally among corner nodes for visualization/checking only.
            for p in pts:
                nodal.setdefault(p,{})[pat]=nodal.setdefault(p,{}).get(pat,0.0)+total/len(pts)
            applied.append({**a,"area_m2":area,"total_force_raw_units":total,"node_names":pts,"note":"Equal corner-node distribution; audit equivalent, not shell finite-element load"})
        # Convert verified ETABS gravity-direction frame UDLs to equivalent END-NODE
        # vertical forces for the load-only OpenSeesPy audit model. This does NOT
        # replace element-level eleLoad: this script intentionally creates no elements.
        applied_frame_loads=[]; skipped_frame_loads=[]; frame_equiv_count=0
        model_patterns=set(wanted)
        for fl in frame_loads:
            pat=str(fl.get("pattern", "")).strip()
            csys=str(fl.get("coordinate_system", "")).strip().casefold()
            direction=str(fl.get("direction_code", "")).strip()
            if pat.casefold() != "wall":
                skipped_frame_loads.append({**fl, "reason":"Only Wall pattern is enabled for frame UDL equivalent nodal loads"}); continue
            if csys != "global" or direction != "10":
                skipped_frame_loads.append({**fl, "reason":"Not confirmed as Global Gravity direction (ETABS direction code 10)"}); continue
            try:
                w1=float(fl.get("value_start")); w2=float(fl.get("value_end"))
            except (TypeError, ValueError):
                skipped_frame_loads.append({**fl, "reason":"Missing/invalid UDL end intensities"}); continue
            if not (math.isfinite(w1) and math.isfinite(w2)):
                skipped_frame_loads.append({**fl, "reason":"Non-finite UDL intensity"}); continue
            obj=str(fl.get("object", "")).strip()
            pts=frame_conn.get(obj, frame_lookup.get(obj.casefold(), []))
            if len(pts)<2 or pts[0] not in coords or pts[1] not in coords:
                skipped_frame_loads.append({**fl, "reason":"Frame endpoints could not be mapped exactly"}); continue
            p1,p2=pts[0],pts[1]
            x1,y1,z1=coords[p1]; x2,y2,z2=coords[p2]
            length=math.sqrt((x2-x1)**2+(y2-y1)**2+(z2-z1)**2)
            if not math.isfinite(length) or length<=1e-8:
                skipped_frame_loads.append({**fl, "reason":"Invalid frame length"}); continue
            # ETABS direction 10 is gravity. For the observed positive 4/7 kN/m
            # assignments, gravity acts in global -Z. Linear/trapezoidal UDL end
            # equivalents: L(2w1+w2)/6 and L(w1+2w2)/6.
            f1=-length*(2.0*w1+w2)/6.0
            f2=-length*(w1+2.0*w2)/6.0
            nodal.setdefault(p1,{})[pat]=nodal.setdefault(p1,{}).get(pat,0.0)+f1
            nodal.setdefault(p2,{})[pat]=nodal.setdefault(p2,{}).get(pat,0.0)+f2
            applied_frame_loads.append({**fl, "length_m":length, "equivalent_node_1":p1,
                "equivalent_node_2":p2, "node_1_Fz_kN":f1, "node_2_Fz_kN":f2,
                "method":"Equivalent endpoint forces for load-only audit; not element-level eleLoad"})
            frame_equiv_count += 1
            model_patterns.add(pat)
        log(f"Frame UDLs converted to equivalent nodal forces: {frame_equiv_count}; skipped: {len(skipped_frame_loads)}")

        # --------------------------------------------------------------------
        # SECTION 06 — OPENSEES NODE TAGS + ETABS/OPENSEES NODE CROSSWALK
        # A stable OpenSees integer tag is assigned to each extracted ETABS point.
        # Coordinates are assumed to be in metres because kN-m-C was requested.
        # --------------------------------------------------------------------
        _begin_step("Node numbering, ETABS/OpenSees crosswalk, and rigid diaphragms")
        # OpenSees domain with nodes and load patterns; no structural elements/materials are fabricated.
        ops.wipe(); ops.model("basic","-ndm",3,"-ndf",6)
        _base_z_for_tags=min((float(xyz[2]) for xyz in coords.values()),default=0.0)
        _tag_tol=max(1.0e-5,1.0e-7*max(1.0,abs(_base_z_for_tags)))
        def _storey_for_tag_elevation(z):
            """Return 0 for base; otherwise ETABS story number containing z."""
            z=float(z)
            if z <= _base_z_for_tags+_tag_tol: return 0
            for _si,_sname,_zlo,_zhi in (etabs_story_levels or []):
                if float(_zlo)-_tag_tol <= z <= float(_zhi)+_tag_tol: return int(_si)
            if etabs_story_levels:
                return int(etabs_story_levels[-1][0])
            # Fallback when ETABS story metadata is unavailable: each distinct
            # non-base node elevation becomes an ordered pseudo-storey.
            elevations=sorted({round(float(xyz[2]),6) for xyz in coords.values() if float(xyz[2])>_base_z_for_tags+_tag_tol})
            return max(1,next((i for i,lev in enumerate(elevations,1) if z<=lev+_tag_tol),len(elevations)))
        _node_groups={}
        for _name in coords:
            _node_groups.setdefault(_storey_for_tag_elevation(coords[_name][2]),[]).append(_name)
        # ETABS named diaphragm assignments identify each story's rigid floor.
        # For a single diaphragm on a story, include every connected structural
        # point at that floor elevation, even if its point-level assignment was
        # inherited or omitted by the API.
        _diaphragm_source_groups={}
        # Candidate floor slaves are every ETABS point attached to a frame,
        # area, or link object (including brace/damper connection points).
        _structural_points=set()
        for _conn in (frame_conn,area_conn,link_conn):
            for _connected_points in _conn.values():
                _structural_points.update(str(p).strip() for p in _connected_points if str(p).strip() in coords)
        _named_diaphragms_by_story={}
        _story_top_z={int(si):float(zhi) for si,_sn,_zlo,zhi in (etabs_story_levels or [])}
        _diaphragm_tol=max(1.0e-4,1.0e-7*max(1.0,max((abs(z) for z in _story_top_z.values()),default=1.0)))
        for _point,_assignment in point_diaphragms.items():
            if _point not in coords: continue
            _dname=str(_assignment.get("diaphragm_name") or "").strip()
            if not _dname: continue
            _z=float(coords[_point][2])
            _story=next((si for si,z in _story_top_z.items() if abs(_z-z)<=_diaphragm_tol),None)
            # The ETABS API may expose only a diaphragm control point for each
            # floor. Its name still identifies the story diaphragm; slave nodes
            # are collected from every connected structural object below.
            if _story is not None:
                _named_diaphragms_by_story.setdefault(int(_story),set()).add(_dname)
        for _story,_names in _named_diaphragms_by_story.items():
            if len(_names)==1:
                # A single explicit ETABS diaphragm name identifies the floor.
                # Include all structural joints at that story elevation even if
                # ETABS did not return a point-level name for every connected
                # frame/wall/link joint.
                _dname=next(iter(_names)); _floor_z=_story_top_z[_story]
                _members=sorted(p for p in _structural_points if abs(float(coords[p][2])-_floor_z)<=_diaphragm_tol)
                if len(_members)>=3: _diaphragm_source_groups[(_story,_dname)]=_members
            else:
                # Multiple ETABS diaphragm names at one story are distinct
                # physical constraint groups; retain exact point memberships.
                for _point,_assignment in point_diaphragms.items():
                    _dname=str(_assignment.get("diaphragm_name") or "").strip()
                    if _dname not in _names or _point not in _structural_points: continue
                    if abs(float(coords[_point][2])-_story_top_z[_story])<=_diaphragm_tol:
                        _diaphragm_source_groups.setdefault((_story,_dname),[]).append(_point)
        _diaphragm_source_groups={k:sorted(set(v)) for k,v in _diaphragm_source_groups.items() if len(set(v))>=3}
        _diaphragm_count_by_story={}
        for _story,_dname in _diaphragm_source_groups:
            _diaphragm_count_by_story[_story]=_diaphragm_count_by_story.get(_story,0)+1
        # Reserve local tag slots for every separate diaphragm master per storey.
        _tag_digits=max(2,len(str(max((len(v)+_diaphragm_count_by_story.get(s,0) for s,v in _node_groups.items()),default=1))))
        _story_tag_multiplier=10**_tag_digits
        node_tag={}
        for _story,_names in sorted(_node_groups.items()):
            _names.sort(key=lambda x:(coords[x][0],coords[x][1],coords[x][2],x))
            for _local_index,_name in enumerate(_names,1):
                node_tag[_name]=_local_index if _story==0 else _story*_story_tag_multiplier+_local_index
        diaphragm_groups=[]; _master_slot_by_story={}
        for (_story,_dname),_points in sorted(_diaphragm_source_groups.items()):
            _master_slot_by_story[_story]=_master_slot_by_story.get(_story,0)+1
            _master_local=len(_node_groups.get(_story,[]))+_master_slot_by_story[_story]
            _master_tag=_story*_story_tag_multiplier+_master_local
            _xyz=[coords[p] for p in _points]
            _master_xyz=((min(q[0] for q in _xyz)+max(q[0] for q in _xyz))/2.0,
                         (min(q[1] for q in _xyz)+max(q[1] for q in _xyz))/2.0,
                         sum(q[2] for q in _xyz)/len(_xyz))
            diaphragm_groups.append({"storey_number":int(_story),"diaphragm_name":_dname,
                "etabs_diaphragm_id":_dname,
                "etabs_point_names":_points,"slave_node_tags":[int(node_tag[p]) for p in _points],
                "master_tag":int(_master_tag),"master_xyz":_master_xyz})
        # rigidDiaphragm has no native tag: this is a crosswalk ID; master_tag is the node tag.
        for _opensees_diaphragm_id,_g in enumerate(diaphragm_groups,1):
            _g["opensees_diaphragm_id"]=_opensees_diaphragm_id
        for _g in diaphragm_groups:
            log(f"Rigid diaphragm prepared: storey={_g['storey_number']}, ETABS diaphragm={_g['etabs_diaphragm_id']}, OpenSees diaphragm ID={_g['opensees_diaphragm_id']}, master node={_g['master_tag']}, structural slave nodes={len(_g['slave_node_tags'])}")
        if not diaphragm_groups:
            log(f"WARNING: No rigid diaphragm groups prepared. Named point assignments={len(point_diaphragms)}; story elevations={len(_story_top_z)}; connected structural points={len(_structural_points)}; stories with a named diaphragm point={len(_named_diaphragms_by_story)}. Check the detailed API values and floor elevations.")
        else:
            log(f"Rigid diaphragm summary: {len(diaphragm_groups)} floor groups; {sum(len(g['slave_node_tags']) for g in diaphragm_groups)} structural slave-node memberships; {len(diaphragm_groups)} independent master nodes reserved.")
        for name,tag in node_tag.items(): ops.node(tag,*coords[name])
        # Keep CSI/ETABS point names distinct from OpenSees integer node tags.
        # This explicit crosswalk is useful when checking 3D coordinates,
        # connectivity, restraints, and later model-generation stages.
        import csv
        node_map_csv=os.path.join(outdir,"ETABS_to_OpenSees_Node_Mapping.csv")
        with open(node_map_csv,"w",newline="",encoding="utf-8-sig") as nf:
            nw=csv.writer(nf); nw.writerow(["etabs_point_name","opensees_node_tag","etabs_storey_number","x_m","y_m","z_m"])
            for point_name,tag in node_tag.items():
                x,y,z=coords[point_name]
                nw.writerow([point_name,tag,_storey_for_tag_elevation(z),x,y,z])

        # --------------------------------------------------------------------
        # SECTION 07 — ETABS CONNECTIVITY → OPENSEES TOPOLOGY AUDIT
        # Classify ETABS frames as beam/column/brace and areas as floor/wall/
        # spandrel. This creates audit records only, NOT ops.element commands.
        # --------------------------------------------------------------------
        _begin_step("Element connectivity and ETABS/OpenSees element mapping")
        # Build explicit ETABS-to-OpenSees ELEMENT CONNECTIVITY records first.
        # These are topology records only: do not invent section/material properties.
        def _frame_kind(pts):
            if len(pts) < 2 or any(str(q) not in coords for q in pts[:2]): return "OTHER FRAME"
            a,b=(coords[str(q)] for q in pts[:2]); dx=b[0]-a[0]; dy=b[1]-a[1]; dz=b[2]-a[2]
            length=max(math.sqrt(dx*dx+dy*dy+dz*dz),1e-12)
            if abs(dz)/length >= 0.90: return "COLUMN"
            if math.hypot(dx,dy)/length >= 0.90 and abs(dz)/length <= 0.10: return "BEAM"
            if abs(dz)>0.05 and math.hypot(dx,dy)>0.05: return "BRACE"
            return "OTHER FRAME"
        def _area_kind(pts):
            if len(pts)<3 or any(str(q) not in coords for q in pts): return "OTHER AREA"
            zz=[coords[str(q)][2] for q in pts]
            if max(zz)-min(zz)<0.15: return "FLOOR"
            if max(zz)-min(zz)>1.0: return "SHEAR WALL"
            return "SPANDREL"
        element_records=[]
        missing_frame=[]; missing_area=[]
        for obj, pts in frame_conn.items():
            if len(pts)<2 or any(str(q) not in coords for q in pts[:2]):
                missing_frame.append(obj); continue
            _frame_z=sum(float(coords[str(q)][2]) for q in pts[:2])/2.0
            _element_storey=_storey_for_tag_elevation(_frame_z)
            element_records.append({"etabs_object":str(obj),"opensees_element_tag":None,"element_tag":None,"storey_number":_element_storey,"category":_frame_kind(pts),"dimension":"line_2_node","node_names":[str(pts[0]),str(pts[1])],"node_tags":[node_tag[str(pts[0])],node_tag[str(pts[1])]],"section_tag":None,"material_tag":None,"assigned_section":section_by_obj.get(str(obj),{}).get("assigned_section"),"ready_for_analysis":False})
        for obj, pts in area_conn.items():
            if len(pts)<3 or any(str(q) not in coords for q in pts):
                missing_area.append(obj); continue
            _area_z=sum(float(coords[str(q)][2]) for q in pts)/len(pts)
            _element_storey=_storey_for_tag_elevation(_area_z)
            element_records.append({"etabs_object":str(obj),"opensees_element_tag":None,"element_tag":None,"storey_number":_element_storey,"category":_area_kind(pts),"dimension":"area_polygon","node_names":[str(q) for q in pts],"node_tags":[node_tag[str(q)] for q in pts],"section_tag":None,"material_tag":None,"ready_for_analysis":False})
        _element_counts_by_storey={}
        for _rec in element_records:
            _element_counts_by_storey[_rec["storey_number"]]=_element_counts_by_storey.get(_rec["storey_number"],0)+1
        _element_tag_digits=max(2,len(str(max(_element_counts_by_storey.values(),default=1))))
        _element_tag_multiplier=10**_element_tag_digits
        _element_local_counters={}
        for _rec in element_records:
            _story=_rec["storey_number"]
            _element_local_counters[_story]=_element_local_counters.get(_story,0)+1
            _local=_element_local_counters[_story]
            _tag=_local if _story==0 else _story*_element_tag_multiplier+_local
            _rec["opensees_element_tag"]=_tag
            _rec["element_tag"]=_tag
        element_counts={}
        for rec in element_records: element_counts[rec["category"]]=element_counts.get(rec["category"],0)+1
        connectivity_json=os.path.join(outdir,"OpenSees_Element_Connectivity.json")
        Path(connectivity_json).write_text(json.dumps({"source_edb":edb,"note":"Connectivity topology only. Element commands intentionally not created until verified material, section and element formulations are assigned.","node_count":len(node_tag),"node_tag_convention":"Storey encoded: base tags start at 1; floor tags use storey*10^digits + local index (for <=99 points/floor this is 101..., 201...). See node_map and ETABS_to_OpenSees_Node_Mapping.csv.","element_tag_convention":"Storey encoded using the same pattern; tags are reserved until corresponding verified ops.element commands are instantiated.","node_map":[{"etabs_point_name":str(name),"opensees_node_tag":int(tag),"etabs_storey_number":_storey_for_tag_elevation(coords[name][2]),"coordinates_m":list(coords[name])} for name,tag in node_tag.items()],"etabs_point_diaphragm_assignments":point_diaphragms,"rigid_diaphragm_groups":diaphragm_groups,"rigid_diaphragm_note":"For a story with one explicit ETABS diaphragm name, all points connected to ETABS frame, area, or link objects at that story-top elevation are included. Multiple diaphragm names retain separate explicit point memberships. Groups with fewer than 3 points are omitted.","element_record_count":len(element_records),"element_counts":element_counts,"unmapped_frame_objects":missing_frame,"unmapped_area_objects":missing_area,"elements":element_records},indent=2),encoding="utf-8")
        connectivity_csv=os.path.join(outdir,"OpenSees_Element_Connectivity.csv")
        with open(connectivity_csv,"w",newline="",encoding="utf-8-sig") as cf:
            cw=csv.DictWriter(cf,fieldnames=["etabs_object","opensees_element_tag","element_tag","storey_number","category","dimension","node_names","node_tags","section_tag","material_tag","assigned_section","ready_for_analysis"]); cw.writeheader()
            for rec in element_records:
                row=dict(rec); row["node_names"]=";".join(row["node_names"]); row["node_tags"]=";".join(map(str,row["node_tags"])); cw.writerow(row)
        element_id_map_csv=os.path.join(outdir,"ETABS_to_OpenSees_Element_Mapping.csv")
        with open(element_id_map_csv,"w",newline="",encoding="utf-8-sig") as ef:
            ew=csv.writer(ef); ew.writerow(["object_dimension","ETABS_object_ID","OpenSees_element_tag","storey_number","category","ETABS_node_IDs","OpenSees_node_tags"])
            for rec in element_records:
                dim="FRAME" if rec["dimension"]=="line_2_node" else "AREA"
                ew.writerow([dim,rec["etabs_object"],rec["opensees_element_tag"],rec["storey_number"],rec["category"],";".join(rec["node_names"]),";".join(map(str,rec["node_tags"]))])
        # --------------------------------------------------------------------
        # SECTION 08 — ETABS SECTION ASSIGNMENT / OPENSEES SECTION MAP REVIEW
        # Frame members only in this stage. Missing values remain blank; no area
        # elements or nonlinear fiber sections are fabricated.
        # --------------------------------------------------------------------
        _begin_step("Section/material audit and review files")
        frame_category_by_obj={str(r["etabs_object"]):r.get("category") for r in element_records if r.get("dimension")=="line_2_node"}
        for sr in frame_section_assignments:
            sr["geometry_category"]=frame_category_by_obj.get(str(sr.get("etabs_object")),"UNMAPPED")
            sr["review_group"]=("FRAME / OUTRIGGER MEMBER — confirm role from ETABS framing plan" if sr["geometry_category"] in {"BEAM","BRACE"} else sr["geometry_category"])
        for ar in area_section_assignments:
            obj=str(ar.get("etabs_area_object"))
            ar["geometry_category"]=next((r.get("category") for r in element_records if r.get("dimension")=="area_polygon" and str(r.get("etabs_object"))==obj),"UNMAPPED")
        section_audit_json=os.path.join(outdir,"OpenSees_Section_Assignment_Audit.json")
        section_audit_csv=os.path.join(outdir,"OpenSees_Section_Assignment_Audit.csv")
        section_payload={"source_edb":edb,"units_requested":"kN-m-C (verify actual API values)","scope":"frame/area property and load audit; the forceBeamColumn export is not a complete gravity or mass model",
            "warning":"Review API return order, units, local axes, section dimensions and material properties before using them.",
            "load_code_basis":{"primary":"Applicable Nepal National Building Codes; NBC 105:2025 §§3.6-3.7 for combinations and NBC 105:2025 §5.2/Table 5-1 for seismic weight.","fallback":"Where the applicable Nepal standard is silent, use relevant Indian Standards and record the exact standard/clause and project assumption.","indian_load_references":"IS 875 Part 1 for dead-load unit weights; IS 875 Part 2 for imposed loads; use Nepal seismic combination rules where NBC 105 governs."},
            "load_combination_policy":"ETABS reference loads remain unfactored and separate by pattern. NBC 105:2025 §3.6 LSM combinations are applied to response combinations; §3.7 WSM combinations are excluded from this workflow. Do not place 1.2/1.5 factors inside imported source loads or scale NLTHA ground motion.",
            "self_weight_and_load_coverage":{"beam":"Not auto-added by this forceBeamColumn exporter; derive from verified section area and material unit weight only if ETABS DL excludes self-weight.","column":"Not auto-added; same duplicate-self-weight check required. For vertical members gravity is axial in local x; OpenSees 3D beamUniform argument order is Wy, Wz, Wx.","shear_wall":"Area property/load audit only; wall element, self-weight, and transferred area loads are not instantiated.","slab":"Area property/load audit only; no slab shell or validated tributary transfer to beams/walls is instantiated.","brace":"Connectivity can be audited as a frame, but physical steel self-weight must use verified brace area/unit weight and be applied once.","FVD":"Device/link element and self-weight are not generated; use manufacturer/ETABS device weight and explicit end nodes.","BRB":"Device/brace element and self-weight are not generated; do not infer weight from core yield strength; use verified physical area/unit weight or ETABS dead load.","mass":"NBC seismic mass factors are recorded in the NBC settings; complete nodal mass assignment is not generated here."},
            "analysis_ready":False,
            "frame_assignments":frame_section_assignments,"section_definitions":frame_section_defs,
            "frame_distributed_load_assignments":frame_loads,
            "area_assignments":area_section_assignments,"area_property_definitions":area_section_defs,
            "linear_model_ready":False,"nonlinear_model_ready":False}
        Path(section_audit_json).write_text(json.dumps(section_payload,indent=2,default=str),encoding="utf-8")
        import csv
        section_cols=["etabs_object","geometry_category","review_group","assigned_section","auto_select_section","section_type","material_name","width_m","depth_m","tube_flange_thickness_m","tube_web_thickness_m","E_kN_m2","G_kN_m2","A_m2","Iy_m4","Iz_m4","J_m4","extraction_status"]
        with open(section_audit_csv,"w",newline="",encoding="utf-8-sig") as sf:
            sw=csv.DictWriter(sf,fieldnames=section_cols); sw.writeheader()
            for sr in frame_section_assignments: sw.writerow({k:sr.get(k) for k in section_cols})
        area_section_json=os.path.join(outdir,"OpenSees_Area_Section_Assignment_Audit.json")
        area_section_csv=os.path.join(outdir,"OpenSees_Area_Section_Assignment_Audit.csv")
        Path(area_section_json).write_text(json.dumps({"source_edb":edb,"units_requested":"kN-m-C (verify API units)","note":"Area property assignments and candidate thickness only; no shell elements instantiated.","assignments":area_section_assignments,"property_definitions":area_section_defs},indent=2,default=str),encoding="utf-8")
        area_cols=["etabs_area_object","geometry_category","assigned_property","property_type","material_name","thickness_m","extraction_status","raw_get_property","raw_property_api"]
        with open(area_section_csv,"w",newline="",encoding="utf-8-sig") as af:
            aw=csv.DictWriter(af,fieldnames=area_cols); aw.writeheader()
            for ar in area_section_assignments:
                rr=dict(ar); rr["raw_property_api"]=json.dumps(rr.get("raw_property_api",{}),ensure_ascii=False)
                aw.writerow({k:rr.get(k) for k in area_cols})
        log(f"Area section assignment audit written: {area_section_csv}")
        # Explicit blank templates for future nonlinear fiber sections; no values are inferred.
        fiber_template_csv=os.path.join(outdir,"OpenSees_Nonlinear_Fiber_Section_Input_Template.csv")
        fiber_fields=["section_name","section_type_rect_or_other","width_m","depth_m","cover_m","fc_cover_kN_m2","epsc0_cover","fcu_cover_kN_m2","epsU_cover","fc_core_kN_m2","epsc0_core","fcu_core_kN_m2","epsU_core","fy_kN_m2","Es_kN_m2","steel_hardening_ratio","concrete_model_and_parameters","steel_model_and_parameters","calibration_reference","review_status"]
        unique_sections=sorted({r["assigned_section"] for r in frame_section_assignments if r.get("assigned_section")})
        with open(fiber_template_csv,"w",newline="",encoding="utf-8-sig") as ff:
            fw=csv.DictWriter(ff,fieldnames=fiber_fields); fw.writeheader()
            for secname in unique_sections: fw.writerow({"section_name":secname,"review_status":"REQUIRED INPUTS MISSING — DO NOT RUN NONLINEAR ANALYSIS"})
        bar_template_csv=os.path.join(outdir,"OpenSees_Nonlinear_Reinforcing_Bar_Coordinates_Template.csv")
        with open(bar_template_csv,"w",newline="",encoding="utf-8-sig") as bf:
            bw=csv.writer(bf); bw.writerow(["section_name","bar_id","local_y_m","local_z_m","bar_area_m2","steel_material_tag","source_drawing_or_ETABS_assignment","review_status"])
        section_gui_path=os.path.join(outdir,"OpenSees_Section_Review_GUI.py")
        _write_section_review_gui(section_gui_path, section_audit_json, os.path.join(outdir,"OpenSees_Element_Connectivity_Skeleton.py"))
        log(f"Section assignment audit written: {section_audit_csv}")
        log("Area property assignments/thickness audited; slab, floor, and shear-wall elements are still deferred until formulation and property review.")

        # --------------------------------------------------------------------
        # SECTION 08B — NBC 105:2025 EQUIVALENT-STATIC INPUT TEMPLATE
        # The current ETABS extraction does not validate total story seismic
        # weights or prove self-weight is included exactly once. Create an
        # explicit, editable weight sheet instead of silently estimating them.
        # --------------------------------------------------------------------
        _begin_step("NBC 105 seismic-weight template and ESM setup")
        esm_template_csv=os.path.join(outdir,"NBC105_ESM_Story_Weights_Input_V108.csv")
        esm_template_json=os.path.join(outdir,"NBC105_ESM_Story_Weights_Input_V108.json")
        _master_by_story={}
        for _g in diaphragm_groups:
            _master_by_story.setdefault(int(_g["storey_number"]),[]).append(int(_g["master_tag"]))
        _story_rows=[]
        _base_elev=min((float(q[2]) for q in coords.values()),default=0.0)
        for _si,_sname,_zlo,_zhi in (etabs_story_levels or []):
            _si=int(_si); _h=float(_zhi)-_base_elev
            if _h<=1.0e-6: continue
            _masters=_master_by_story.get(_si,[])
            _story_rows.append({"story_number":_si,"story_name":str(_sname),"height_m":_h,
                "master_node_tag":_masters[0] if len(_masters)==1 else "",
                "dead_load_kN":"","storage_live_load_kN":"","other_live_load_kN":"",
                "roof_live_load_kN_ignored":"","input_note":("Enter verified ETABS story seismic weight components in kN. Include member/slab/wall dead load exactly once. Roof live is excluded by NBC 105 Table 5-1." if _si==max((int(q[0]) for q in etabs_story_levels),default=_si) else "Enter verified ETABS story seismic weight components in kN. Include member/slab/wall dead load exactly once.")})
        with open(esm_template_csv,"w",newline="",encoding="utf-8-sig") as _ef:
            _ew=csv.DictWriter(_ef,fieldnames=["story_number","story_name","height_m","master_node_tag","dead_load_kN","storage_live_load_kN","other_live_load_kN","roof_live_load_kN_ignored","input_note"])
            _ew.writeheader(); _ew.writerows(_story_rows)
        Path(esm_template_json).write_text(json.dumps({"source_edb":edb,"standard":"NBC 105:2025 §§3.2.1, 4.1.1-4.1.5, 4.2, 5.1, 5.2, 6.1-6.4","story_rows":_story_rows,
            "required_user_review":["Confirm gravity-load totals by story using ETABS tables; avoid double counting self-weight.","For buildings taller than 40 m, confirm Vs,30 site classification from geotechnical data per §4.1.3.1.","Choose Z, importance class, lateral system Rμ/Ω, and adopted T1 from project/code checks.","Confirm ULS ESM eligibility under §3.2.1; a building over 40 m requires T1 < 0.5 s for the ULS ESM route."],
            "limitations":["No seismic-weight number is guessed by this exporter.","The existing converter does not instantiate slab/wall shell elements or a complete verified structural model.","This sheet is for a separately verified equivalent-static load calculation; do not treat the topology/load audit as a structural solver result."]},indent=2),encoding="utf-8")
        log(f"NBC 105 seismic-weight input sheet written: {esm_template_csv} ({len(_story_rows)} storeys; blank weights require ETABS verification)")
        log(f"NBC 105 ESM requirements and model limitations written: {esm_template_json}")
        log("Seismic-weight factors per NBC 105:2025 Table 5-1: storage=0.60, other live=0.30, roof live=0.00; dead=1.00. Values will be calculated only after verified story inputs are supplied.")
        if any(len(_master_by_story.get(int(r["story_number"]),[])) != 1 for r in _story_rows):
            log("WARNING: Some stories do not have exactly one detected rigid-diaphragm master. The ESM load runner will be blocked for those rows until master-node mapping is resolved.")

        # --------------------------------------------------------------------
        # SECTION 09 — OPENSEES SUPPORTS MAPPED FROM ETABS BASE ELEVATION
        # Determine base nodes before writing the skeleton, because the generated
        # Python file includes their fixed-support commands.
        base_z = min((float(v[2]) for v in coords.values()), default=0.0)
        base_tol = max(1.0e-5, 1.0e-7 * max(1.0, abs(base_z)))
        base_nodes = [name for name, xyz in coords.items() if abs(float(xyz[2]) - base_z) <= base_tol]
        connectivity_py=os.path.join(outdir,"OpenSees_Element_Connectivity_Skeleton.py")
        sk=["# Generated ETABS-to-OpenSeesPy element connectivity skeleton", "# IMPORTANT: this file records connectivity only; no element stiffness is created.", "# Assign and validate material/section tags and element formulations before analysis.", "import openseespy.opensees as ops", "ops.wipe()", 'ops.model("basic", "-ndm", 3, "-ndf", 6)', "# Node tag -> (x, y, z); coordinates are in the requested ETABS kN-m-C units.", "NODES = {"]
        for name,tag in node_tag.items(): sk.append(f"    {tag}: ({coords[name][0]:.10g}, {coords[name][1]:.10g}, {coords[name][2]:.10g}),  # ETABS point {name}; storey {_storey_for_tag_elevation(coords[name][2])}")
        sk += ["}", "ETABS_TO_OPENSEES_NODE_TAG = "+repr({str(k):int(v) for k,v in node_tag.items()}),
               "DIAPHRAGM_GROUPS = "+repr(diaphragm_groups),
               "POINT_DIAPHRAGM_ASSIGNMENTS = "+repr(point_diaphragms),
               "for tag, xyz in NODES.items(): ops.node(tag, *xyz)", "# Fixed supports: all six DOFs restrained at the base nodes."]
        for name in base_nodes: sk.append(f"ops.fix({node_tag[name]}, 1, 1, 1, 1, 1, 1)  # ETABS point {name}")
        sk += ["", "# Each record has element_tag, ETABS object, category, node tags, and dimension.", "# These are NOT ops.element commands yet; section/material formulations are intentionally unset.", "ELEMENT_CONNECTIVITY = ["]
        for rec in element_records: sk.append("    "+repr({"etabs_object":rec["etabs_object"],"opensees_element_tag":rec["opensees_element_tag"],"tag":rec["opensees_element_tag"],"storey_number":rec["storey_number"],"category":rec["category"],"nodes":rec["node_tags"],"dimension":rec["dimension"]})+",")
        sk += ["]", "print('Nodes:', len(ops.getNodeTags()))", "print('Connectivity records:', len(ELEMENT_CONNECTIVITY))", "print('No structural elements instantiated; assign validated sections and element formulations first.')"]
        Path(connectivity_py).write_text("\n".join(sk)+"\n",encoding="utf-8")

        # A separate, executable topology-stage OpenSeesPy file makes node tags
        # real in the OpenSees domain and reserves deterministic element tags.
        # IMPORTANT: OpenSees has no independent element-tag registry. An element
        # tag only exists in the domain after ops.element(...) is called. Since
        # verified section/material/formulation data are not yet guaranteed, this
        # script records reserved element tags and connectivity but deliberately
        # does not create fake/stiffness-free structural elements.
        tagged_model_py=os.path.join(outdir,"OpenSees_Tagged_Topology_Model.py")
        tm=["# ETABS -> OpenSeesPy tagged topology model (V108)",
            "# Creates real OpenSees nodes and base restraints; records reserved element tags.",
            "# No ops.element commands are issued until section/material/formulation are verified.",
            "import json", "import openseespy.opensees as ops", "ops.wipe()",
            'ops.model("basic", "-ndm", 3, "-ndf", 6)', "NODES = {"]
        for name,tag in node_tag.items():
            tm.append(f"    {tag}: ({coords[name][0]:.10g}, {coords[name][1]:.10g}, {coords[name][2]:.10g}),  # ETABS point {name}; storey {_storey_for_tag_elevation(coords[name][2])}")
        tm += ["}", "for node_tag, xyz in NODES.items(): ops.node(int(node_tag), *xyz)", "",
               "ETABS_TO_OPENSEES_NODE_TAG = {"]
        for name,tag in node_tag.items(): tm.append(f"    {str(name)!r}: {tag},  # storey {_storey_for_tag_elevation(coords[name][2])}")
        tm += ["}", "", "# All six DOFs fixed at extracted base nodes; verify support assumptions in ETABS."]
        for name in base_nodes: tm.append(f"ops.fix({node_tag[name]}, 1, 1, 1, 1, 1, 1)  # ETABS point {name}")
        # Optional rigid floor diaphragms. The generated topology model remains a
        # topology/audit model (no structural elements), but carries an explicit,
        # reviewable diaphragm switch and story-node grouping for the next model stage.
        # The user can change DIAPHRAGM_MODE to "NONE" in the generated script.
        tm += ["", "# Rigid diaphragms copied from explicit ETABS point assignments.",
               "# ETABS_NODE_IDS and OpenSees node tags remain available in the maps above.",
               "DIAPHRAGM_GROUPS = "+repr(diaphragm_groups),
               "DIAPHRAGM_MODE = 'RIGID' if DIAPHRAGM_GROUPS else 'NONE'",
               "DIAPHRAGM_MASTER_TAGS = {}",
               "DIAPHRAGM_CROSSWALK = {}",
               "for group in DIAPHRAGM_GROUPS:",
               "    master = int(group['master_tag'])",
               "    x_master, y_master, z_floor = group['master_xyz']",
               "    slaves = [int(t) for t in group['slave_node_tags']]",
               "    ops.node(master, x_master, y_master, z_floor)",
               "    ops.fix(master, 0, 0, 1, 1, 1, 0)",
               "    ops.rigidDiaphragm(3, master, *slaves)",
               "    key = f\"{group['storey_number']}:{group['diaphragm_name']}\"",
               "    DIAPHRAGM_MASTER_TAGS[key] = master",
               "    DIAPHRAGM_CROSSWALK[key] = {'etabs_diaphragm_id': group['etabs_diaphragm_id'], 'opensees_diaphragm_id': group['opensees_diaphragm_id'], 'master_node_tag': master}",
               "    print(f\"Storey {group['storey_number']} diaphragm: ETABS={group['etabs_diaphragm_id']}, OpenSees D{group['opensees_diaphragm_id']}, master node={master}; slaves={len(slaves)}\")",
               "if not DIAPHRAGM_GROUPS:",
               "    print('No explicit named ETABS diaphragm groups with at least three story-top points were found.')",
               "# RigidDiaphragm is an MP constraint; use Transformation in each analysis stage.",
               "ops.constraints('Transformation')",
               ""]
        tm += ["", "# Reserved deterministic element tags; these are NOT yet in ops.getEleTags().",
               "# Keys are (object_dimension, ETABS object ID) to avoid frame/area ID collisions.", "ETABS_TO_OPENSEES_ELEMENT_TAG = {"]
        for rec in element_records:
            dim="FRAME" if rec["dimension"]=="line_2_node" else "AREA"
            tm.append(f"    ({dim!r}, {str(rec['etabs_object'])!r}): {int(rec['opensees_element_tag'])},  # storey {rec['storey_number']}")
        tm += ["}", "", "ELEMENT_CONNECTIVITY = ["]
        for rec in element_records:
            dim="FRAME" if rec["dimension"]=="line_2_node" else "AREA"
            tm.append("    "+repr({"etabs_object":str(rec["etabs_object"]),"opensees_element_tag":int(rec["opensees_element_tag"]),"element_tag":int(rec["opensees_element_tag"]),"storey_number":int(rec["storey_number"]),"object_dimension":dim,"category":rec["category"],"node_tags":[int(x) for x in rec["node_tags"]],"dimension":rec["dimension"],"assigned_section":rec.get("assigned_section"),"instantiated":False})+",")
        tm += ["]", "", "# Export mappings for later verified element creation.",
               "with open('OpenSees_Tag_Map.json', 'w', encoding='utf-8') as f:",
               "    json.dump({'node_count': len(ops.getNodeTags()), 'reserved_element_count': len(ELEMENT_CONNECTIVITY), 'instantiated_element_count': len(ops.getEleTags()), 'node_map': ETABS_TO_OPENSEES_NODE_TAG, 'element_map': {f'{k[0]}:{k[1]}': v for k, v in ETABS_TO_OPENSEES_ELEMENT_TAG.items()}, 'elements': ELEMENT_CONNECTIVITY, 'diaphragm_mode': DIAPHRAGM_MODE, 'diaphragm_master_tags': DIAPHRAGM_MASTER_TAGS}, f, indent=2)",
               "print('OpenSees nodes created:', len(ops.getNodeTags()))",
               "print('Element tags reserved in mapping:', len(ETABS_TO_OPENSEES_ELEMENT_TAG))",
               "print('OpenSees elements actually instantiated:', len(ops.getEleTags()))",
               "print('Structural elements remain uninstantiated until section/material/formulation validation.')"]
        Path(tagged_model_py).write_text("\n".join(tm)+"\n",encoding="utf-8")
        log("Element connectivity records created: " + ", ".join(f"{k}={v}" for k,v in sorted(element_counts.items())))
        log(f"Unmapped connectivity: frames={len(missing_frame)}, areas={len(missing_area)}")
        log("Connectivity outputs: OpenSees_Element_Connectivity.csv / .json / _Skeleton.py")
        log("Dual ETABS/OpenSees element ID map: " + element_id_map_csv)
        log("Tagged topology model written: " + tagged_model_py)
        log("Storey-coded OpenSees node and element tags are generated; ETABS IDs remain in crosswalks. Element tags are reserved until verified elements can be created.")

        # Fully fixed base supports: constrain UX, UY, UZ, RX, RY, RZ at
        # every ETABS node lying on the lowest model elevation (normally Z=0).
        # Use the model's minimum Z rather than hard-coding zero, with a small tolerance.
        for name in base_nodes:
            ops.fix(node_tag[name], 1, 1, 1, 1, 1, 1)
        log(f"Fixed base supports applied: {len(base_nodes)} nodes at Z={base_z:.6g} m; all 6 DOFs fixed.")
        # --------------------------------------------------------------------
        # SECTION 10 — ETABS LOADS → OPENSEES LOAD AUDIT / EQUIVALENT FORCES
        # Area/frame load conversions below are for auditing only. In the next
        # structural-model stage, loads should be applied to validated elements
        # using appropriate eleLoad/shell loads/diaphragm distribution as needed.
        _begin_step("Load conversion and load-only audit model")
        # IMPORTANT: create loads while their own pattern is active. Do not create all
        # patterns first and then apply loads, which would assign every load to the last pattern.
        pat_tags={}
        for i,pat in enumerate(sorted(model_patterns),1):
            pat_tags[pat]=i
            ops.timeSeries("Linear",i); ops.pattern("Plain",i,i)
            for p, loads in nodal.items():
                if p not in node_tag or pat not in loads: continue
                # Global Z component, preserving extracted ETABS sign.
                ops.load(node_tag[p],0.0,0.0,float(loads[pat]),0.0,0.0,0.0)
        # Write a self-contained OpenSeesPy load-only model script.
        out_py=os.path.join(outdir,"OpenSees_Load_Only_Model.py")
        lines=["# Generated by ETABS-to-OpenSeesPy Load Audit V47", "# Nodes and equivalent nodal loads only; structural elements are not included.", "# Frame Wall UDLs are represented by equivalent endpoint Fz forces, not eleLoad.", "# Base nodes at the lowest model elevation are fully fixed in all 6 DOFs.", "# This remains a load-only audit model; do not run structural analysis until verified elements, materials, masses and analysis settings are added.", "import openseespy.opensees as ops", "ops.wipe()", 'ops.model("basic", "-ndm", 3, "-ndf", 6)']
        for name,tag in node_tag.items():
            x,y,z=coords[name]; lines.append(f"ops.node({tag}, {x:.9g}, {y:.9g}, {z:.9g})  # ETABS point {name}")
        for name in base_nodes:
            lines.append(f"ops.fix({node_tag[name]}, 1, 1, 1, 1, 1, 1)  # fixed base support; ETABS point {name}; Z={coords[name][2]:.9g} m")
        lines.append(f"# Fixed base support count: {len(base_nodes)} nodes; base elevation Z={base_z:.9g} m; six DOFs fixed at each node.")
        for pat,tag in pat_tags.items():
            lines += [f"ops.timeSeries('Linear', {tag})", f"ops.pattern('Plain', {tag}, {tag})  # {pat}"]
            for p,loads in nodal.items():
                if p in node_tag and pat in loads:
                    val=loads[pat]
                    lines.append(f"ops.load({node_tag[p]}, 0.0, 0.0, {val:.12g}, 0, 0, 0)  # point {p}; {pat}; equivalent area load")
        lines += ["# Note: this is a load-only audit model; add verified structural elements before analysis.", "print('Nodes:', len(ops.getNodeTags()))", "print('Load-only OpenSees domain created. No analysis was run.')"]
        Path(out_py).write_text("\n".join(lines)+"\n",encoding="utf-8")
        # --------------------------------------------------------------------
        # SECTION 12 — OPENSEES CSV / JSON / PYTHON EXPORTS + ETABS TRACEABILITY
        # --------------------------------------------------------------------
        # JSON audit
        audit={"source_edb":edb,"units_requested":"kN-m-C (ETABS enum 6; verify model units)","node_count":len(coords),"frame_count":len(frame_names),"area_count":len(area_names),"etabs_load_pattern_self_weight_multipliers":self_weight_pattern_audit,"self_weight_transfer_status":"NOT TRANSFERRED: multiplier metadata is audited only; member/area weight properties and exactly-once reconciliation are required.","area_load_assignments_extracted":len(area_loads),"area_load_assignments_applied":len(applied),"area_load_assignments_skipped":len(skipped),"frame_distributed_assignments_extracted":len(frame_loads),"applied_area_loads":applied,"skipped_area_loads":skipped,"frame_loads_not_applied":skipped_frame_loads,"applied_frame_loads_as_equivalent_nodal_forces":applied_frame_loads,"frame_loads_equivalent_nodal_count":frame_equiv_count,"raw_area_api":area_raw,"raw_frame_api":frame_raw,"node_tags":node_tag,"coordinates":{k:list(v) for k,v in coords.items()},"base_supports":{"type":"fully_fixed","base_elevation_m":base_z,"tolerance_m":base_tol,"node_names":base_nodes,"node_tags":[node_tag[n] for n in base_nodes],"dofs_fixed":[1,2,3,4,5,6]},"frame_connectivity":frame_conn,"area_connectivity":area_conn,"nodal_loads":nodal}
        audit["element_connectivity"]={"record_count":len(element_records),"counts_by_category":element_counts,"csv":connectivity_csv,"json":connectivity_json,"python_skeleton":connectivity_py,"unmapped_frame_objects":missing_frame,"unmapped_area_objects":missing_area,"elements_instantiated_in_domain":False,"section_assignment_audit_json":section_audit_json,"section_assignment_audit_csv":section_audit_csv,"section_review_gui":section_gui_path,"area_section_assignment_audit_json":area_section_json,"area_section_assignment_audit_csv":area_section_csv}
        audit_json=os.path.join(outdir,"OpenSees_Load_Conversion_Audit.json")
        audit['direct_uniform_loads_status']='UNVERIFIED' if any(r.get('kind')=='direct_uniform_loads' and r.get('status')=='UNVERIFIED' for r in area_raw) else 'READ'
        audit['source_extractor_release']='V142'
        audit['uniform_load_sets_status']='UNVERIFIED' if any(r.get('kind')=='uniform_load_sets' and r.get('status')=='UNVERIFIED' for r in area_raw) else 'READ'
        audit['uniform_load_set_components_extracted']=sum(1 for r in area_loads if r.get('load_set'))
        Path(audit_json).write_text(json.dumps(audit,indent=2,default=str),encoding="utf-8")
        self_weight_csv=os.path.join(outdir,"ETABS_Load_Pattern_SelfWeight_Audit.csv")
        with open(self_weight_csv,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=["pattern","multiplier","status","raw"]); w.writeheader(); w.writerows(self_weight_pattern_audit)
        # --------------------------------------------------------------------
        # SECTION 11 — OPENSEES-ORIENTED VISUALIZATION OF ETABS MODEL / LOADS
        # Includes storey overview, per-element connectivity filter, 3D loads,
        # and floor-plan load view. Views are audits, not analysis results.
        # --------------------------------------------------------------------
        _begin_step("Interactive 3D and floor-plan visualizations")
        # Two separate interactive visual modules: structural elements by storey, and loads.
        html_structure=os.path.join(outdir,"OpenSees_Structural_Elements_By_Storey.html")
        html_connectivity_3d=os.path.join(outdir,"OpenSees_Element_Connectivity_3D.html")
        html_loads=os.path.join(outdir,"OpenSees_Load_Assignment_3D.html")
        if go is not None:
            # Use official ETABS story heights/names. Base is Z=0; storey numbers
            # follow the ascending ETABS elevations rather than hard-coded heights.
            # If the ETABS Story API cannot be decoded, use coordinate-derived level
            # boundaries as a clearly logged fallback instead of assuming 3.5/3.8 m.
            max_z = max((v[2] for v in coords.values()), default=0.0)
            story_levels = list(etabs_story_levels)
            if not story_levels:
                z_levels=sorted(set(round(max(0.0,float(v[2])),5) for v in coords.values()))
                z_levels=[z for z in z_levels if z > 1e-5]
                story_levels=[]; lo=0.0
                for i, hi in enumerate(z_levels,1):
                    if hi-lo > 0.1:
                        story_levels.append((i, f"Coordinate level {i}", lo, hi)); lo=hi
                log("WARNING: Using coordinate-derived storey levels because ETABS story data was unavailable.")
            max_storey=max(1,len(story_levels))
            def story_bottom(si):
                if 1 <= si <= len(story_levels): return story_levels[si-1][2]
                return 0.0 if si <= 1 else story_levels[-1][3]
            def story_top(si):
                if 1 <= si <= len(story_levels): return story_levels[si-1][3]
                return story_levels[-1][3] if story_levels else max_z
            def story_index(z):
                z=max(0.0,float(z))
                for si, _name, lo, hi in story_levels:
                    if lo-1e-7 <= z <= hi+1e-7: return si
                if story_levels and abs(z-story_levels[-1][3]) <= 1e-6: return story_levels[-1][0]
                if story_levels and z < story_levels[0][2]: return 1
                if story_levels:
                    return min(max_storey, max(1, next((si for si,_,lo,hi in story_levels if z <= hi+1e-7), max_storey)))
                return 1
            def clipped_segment(a, b, zlo, zhi):
                # Clip a straight member to an elevation interval; works for columns
                # and sloping braces, and prevents Storey 2 columns starting at base.
                z1,z2=float(a[2]),float(b[2])
                dz=z2-z1
                if abs(dz) < 1e-9:
                    if zlo-1e-8 <= z1 <= zhi+1e-8: return a,b
                    return None
                t0=(zlo-z1)/dz; t1=(zhi-z1)/dz
                lo=max(0.0,min(t0,t1)); hi=min(1.0,max(t0,t1))
                if hi-lo <= 1e-9: return None
                def at(t): return tuple(float(a[i]) + t*(float(b[i])-float(a[i])) for i in range(3))
                return at(lo),at(hi)
            def normalized_object_name(value):
                value=str(value).strip().strip('\"\'')
                return ''.join(ch for ch in value.casefold() if ch.isalnum())
            def classify_frame(pts):
                if len(pts)<2 or any(str(p) not in coords for p in pts[:2]): return "OTHER FRAME"
                a,b=(coords[str(p)] for p in pts[:2]); dx=b[0]-a[0]; dy=b[1]-a[1]; dz=b[2]-a[2]
                horiz=math.hypot(dx,dy); vert=abs(dz)
                # Use relative orientation thresholds to avoid tiny coordinate noise.
                length=max(math.sqrt(dx*dx+dy*dy+dz*dz),1e-9)
                if vert/length >= 0.90: return "COLUMN"
                if horiz/length >= 0.90 and vert/length <= 0.10: return "BEAM"
                if vert > 0.05 and horiz > 0.05: return "BRACE"
                return "OTHER FRAME"
            colors={"BEAM":"#2563eb","COLUMN":"#dc2626","BRACE":"#7c3aed","FLOOR":"#059669","SHEAR WALL":"#f59e0b","SPANDREL":"#db2777","OTHER AREA":"#94a3b8","OTHER FRAME":"#64748b"}
            structural=[]
            # Group frame members by storey. Vertical/inclined members are clipped
            # to the storey band so selecting Storey 2 never displays the base segment.
            for category in ("BEAM","COLUMN","BRACE","OTHER FRAME"):
                groups={}
                for n,pts in frame_conn.items():
                    if classify_frame(pts)!=category or len(pts)<2 or any(p not in coords for p in pts[:2]): continue
                    a,b=coords[pts[0]],coords[pts[1]]
                    if category == "BEAM":
                        si=story_index((a[2]+b[2])/2)
                        segments=[(si,a,b)]
                    else:
                        zmin,zmax=sorted((a[2],b[2]))
                        first=max(1,story_index(zmin+1e-7))
                        last=max(first,story_index(zmax-1e-7))
                        segments=[]
                        for si in range(first,min(last,max_storey)+1):
                            seg=clipped_segment(a,b,story_bottom(si),story_top(si))
                            if seg is not None: segments.append((si,seg[0],seg[1]))
                    for si,aa,bb in segments:
                        sec=str(section_by_obj.get(str(n),{}).get("assigned_section") or "UNASSIGNED")
                        groups.setdefault((si,sec),([],[],[],[]))
                        x,y,z,cd=groups[(si,sec)]; x.extend([aa[0],bb[0],None]); y.extend([aa[1],bb[1],None]); z.extend([aa[2],bb[2],None]); _node_ids=f"ETABS {pts[0]} → OpenSees {node_tag.get(str(pts[0]), '?')}; ETABS {pts[1]} → OpenSees {node_tag.get(str(pts[1]), '?')}"; _ele_tag=next((int(rec['element_tag']) for rec in element_records if str(rec['etabs_object'])==str(n) and rec['dimension']=='line_2_node'),None); cd.extend([[str(n),category,si,_node_ids,sec,_ele_tag],[str(n),category,si,_node_ids,sec,_ele_tag],None])
                for (si,sec),(x,y,z,cd) in groups.items():
                    structural.append(go.Scatter3d(x=x,y=y,z=z,customdata=cd,mode="lines",name=f"{category} | Storey {si} | Section {sec}",legendgroup=category,line=dict(color=colors[category],width=4 if category!="BRACE" else 3),visible=True,hovertemplate="ETABS object ID: %{customdata[0]}<br>OpenSees element tag: %{customdata[5]}<br>Category: %{customdata[1]}<br>Storey: %{customdata[2]}<br>Node IDs: %{customdata[3]}<br>ETABS section: %{customdata[4]}<extra></extra>"))
            # Log category totals to make missing columns/beams immediately diagnosable.
            frame_category_counts={cat:sum(1 for pts in frame_conn.values() if classify_frame(pts)==cat) for cat in ("BEAM","COLUMN","BRACE","OTHER FRAME")}
            log("Structural visualization frame classification: " + ", ".join(f"{k}={v}" for k,v in frame_category_counts.items()))
            log(f"Frame connectivity mapped: {sum(1 for pts in frame_conn.values() if len(pts)>=2 and all(str(p) in coords for p in pts[:2]))}/{len(frame_conn)}")
            log(f"Wall distributed-load assignments extracted: {sum(1 for fl in frame_loads if str(fl.get('pattern','')).strip().casefold()=='wall')}")
            # Areas classified by geometry: horizontal polygons are floors; vertical polygons are wall/spandrel candidates.
            area_groups={}
            for n,pts in area_conn.items():
                if len(pts)<3 or any(p not in coords for p in pts): continue
                xyz=[coords[p] for p in pts]; xs0=[q[0] for q in xyz]; ys0=[q[1] for q in xyz]; zs0=[q[2] for q in xyz]
                if max(zs0)-min(zs0)<0.15: category="FLOOR"; si=story_index(sum(zs0)/len(zs0))
                else:
                    # ETABS geometry alone cannot reliably distinguish spandrels from wall piers.
                    category="SHEAR WALL" if (max(zs0)-min(zs0))>1.0 else "SPANDREL"
                    si=story_index(sum(zs0)/len(zs0))
                sec=str(area_section_by_obj.get(str(n),{}).get("assigned_property") or "UNASSIGNED")
                area_groups.setdefault((category,si,sec),[]).append((n,pts,xyz))
            for (category,si,sec),items in area_groups.items():
                xx=[]; yy=[]; zz=[]; cd=[]
                for n,pts,xyz in items:
                    poly=xyz+[xyz[0]]; xx.extend([q[0] for q in poly]+[None]); yy.extend([q[1] for q in poly]+[None]); zz.extend([q[2] for q in poly]+[None]); _node_ids="; ".join(f"ETABS {q} → OpenSees {node_tag.get(str(q), '?')}" for q in pts); _area_tag=next((int(rec['element_tag']) for rec in element_records if str(rec['etabs_object'])==str(n) and rec['dimension']=='area_polygon'),None); cd.extend([[str(n),category,si,_node_ids,sec,_area_tag] for _ in poly]+[None])
                structural.append(go.Scatter3d(x=xx,y=yy,z=zz,customdata=cd,mode="lines",name=f"{category} | Storey {si} | Property {sec}",legendgroup=category,line=dict(color=colors.get(category,"#94a3b8"),width=3),visible=True,hovertemplate="ETABS area object ID: %{customdata[0]}<br>OpenSees element tag: %{customdata[5]}<br>Category: %{customdata[1]}<br>Storey: %{customdata[2]}<br>Node IDs: %{customdata[3]}<br>ETABS area property: %{customdata[4]}<extra></extra>"))
            # Draw fixed-base supports as explicit symbols at the actual restrained ETABS nodes.
            # Assign them to Storey 1 so the storey filter can show/hide them predictably.
            support_xyz=[coords[n] for n in base_nodes if n in coords]
            if support_xyz:
                structural.append(go.Scatter3d(
                    x=[q[0] for q in support_xyz], y=[q[1] for q in support_xyz], z=[q[2] for q in support_xyz],
                    mode="markers", name="SUPPORTS | Storey 1", legendgroup="SUPPORTS",
                    marker=dict(symbol="diamond", size=7, color="#111827", line=dict(color="#ffffff", width=1.5)),
                    visible=True, customdata=[[n, "SUPPORT", 1, f"ETABS {n} → OpenSees {node_tag[n]}", "Base support", base_z, "UX UY UZ RX RY RZ"] for n in base_nodes if n in coords],
                    hovertemplate="FIXED BASE SUPPORT<br>ETABS node: %{customdata[0]}<br>OpenSees node: %{customdata[3]}<br>Z: %{customdata[5]:.4f} m<br>Restrained: %{customdata[6]}<extra></extra>"))
            # Controls combine storey and element type; default shows all structural geometry.
            all_types=["ALL ELEMENTS","BEAM","COLUMN","BRACE","FLOOR","SHEAR WALL SYSTEM","SUPPORTS","OTHER FRAME","OTHER AREA"]
            all_stories=["ALL LEVELS"]+[f"STOREY {i} — {story_levels[i-1][1]}" for i in range(1, max_storey + 1)]
            options=[("ALL STOREYS","ALL ELEMENTS")]
            options += [(st,ty) for st in all_stories[1:] for ty in all_types[1:]]
            options += [(st,"ALL ELEMENTS") for st in all_stories[1:]]
            fig_s=go.Figure(data=structural)
            # Add an always-visible elevation grid and labels at official ETABS storey elevations.
            # These traces are deliberately outside the element filter metadata so the whole-building
            # reference grid remains visible while inspecting one element/storey.
            xvals=[v[0] for v in coords.values()]; yvals=[v[1] for v in coords.values()]
            xmin,xmax=min(xvals),max(xvals); ymin,ymax=min(yvals),max(yvals)
            grid_x=[]; grid_y=[]; grid_z=[]
            for si, sname, zlo, zhi in story_levels:
                zz=float(zhi)
                grid_x.extend([xmin,xmax,None,xmin,xmax,None])
                grid_y.extend([ymin,ymin,None,ymax,ymax,None])
                grid_z.extend([zz,zz,None,zz,zz,None])
            fig_s.add_trace(go.Scatter3d(x=grid_x,y=grid_y,z=grid_z,mode="lines",name="Storey elevation grid",line=dict(color="#64748b",width=2,dash="dash"),hoverinfo="skip",showlegend=True))
            label_x=[]; label_y=[]; label_z=[]; label_text=[]
            for si, sname, zlo, zhi in story_levels:
                label_x.append(xmin-1.5); label_y.append(ymin-1.5); label_z.append(float(zhi))
                label_text.append(f"{sname} | Z={float(zhi):g} m")
            fig_s.add_trace(go.Scatter3d(x=label_x,y=label_y,z=label_z,mode="text",text=label_text,textposition="middle right",name="Storey elevations",textfont=dict(size=8,color="#334155"),hovertemplate="%{text}<extra></extra>",showlegend=False))
            fig_s.update_layout(title="ETABS → OpenSeesPy | Structural elements + ETABS storey elevations",scene=dict(xaxis_title="X (m)",yaxis_title="Y (m)",zaxis_title="Elevation Z (m)",aspectmode="manual",aspectratio=dict(x=1,y=0.6,z=2.2),camera=dict(eye=dict(x=1.7,y=1.7,z=1.25))),height=900,margin=dict(l=0,r=0,t=135,b=0),legend=dict(itemsizing="constant"))
            structure_meta=[]
            for tr in structural:
                name=str(tr.name)
                level_match=re.search(r"\| Storey (\d+)",name)
                sec_match=re.search(r"\| Section (.*)$",name) or re.search(r"\| Property (.*)$",name)
                structure_meta.append({"category":name.split(" | Storey ")[0],"level":int(level_match.group(1)) if level_match else 0,"section":sec_match.group(1) if sec_match else "(not applicable)"})
            structure_meta += [{"category":"__REFERENCE_GRID__","level":0},{"category":"__ELEVATION_LABELS__","level":0}]
            structure_postscript=r"""(function(){const gd=document.getElementById('{plot_id}');const meta=__META__;const bar=document.createElement('div');bar.style='position:relative;z-index:1;box-sizing:border-box;width:calc(100% - 24px);margin:8px 12px 8px 12px;display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:8px 12px;align-items:center;background:#fff;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;font:13px Arial;box-shadow:0 2px 8px #0001';bar.innerHTML='<label>Storey <select id="storyFilter"><option value="all">All storeys</option></select></label><label>Element <select id="typeFilter"><option value="all">All elements</option></select></label><label>ETABS section/property <select id="sectionFilter"><option value="all">All sections/properties</option></select></label><label>ETABS unique object ID <input id="etabsIdFilter" placeholder="251"></label><label>OpenSees topology tag <input id="opsIdFilter" placeholder="11031"></label><strong id="picked" style="grid-column:1 / -1;white-space:normal">Hover/click an object for ETABS and OpenSees IDs</strong>';gd.parentElement.insertBefore(bar,gd);const ss=bar.querySelector('#storyFilter'),tt=bar.querySelector('#typeFilter'),sf=bar.querySelector('#sectionFilter'),picked=bar.querySelector('#picked');[...new Set(meta.map(x=>x.level).filter(x=>x>0))].sort((a,b)=>a-b).forEach(v=>ss.add(new Option('Storey '+v,String(v))));['BEAM','COLUMN','BRACE','FLOOR','SHEAR WALL SYSTEM','SUPPORTS','OTHER FRAME','OTHER AREA'].forEach(v=>tt.add(new Option(v,v)));[...new Set(meta.map(x=>x.section).filter(x=>x&&x!=='(not applicable)'))].sort().forEach(v=>sf.add(new Option(v,v)));const ef=bar.querySelector('#etabsIdFilter'),of=bar.querySelector('#opsIdFilter');const original=gd.data.map(t=>({x:Array.from(t.x||[]),y:Array.from(t.y||[]),z:Array.from(t.z||[])}));ef.addEventListener('input',upd);of.addEventListener('input',upd);function upd(){const st=ss.value,ty=tt.value,sec=sf.value;const ei=ef.value.trim(),oi=of.value.trim();gd.data.forEach((t,i)=>{const keep=k=>{const c=(t.customdata||[])[k];return (!ei&&!oi)||(c&&(!ei||String(c[0])===ei)&&(!oi||String(c[5])===oi))};Plotly.restyle(gd,{x:[original[i].x.map((v,k)=>keep(k)?v:null)],y:[original[i].y.map((v,k)=>keep(k)?v:null)],z:[original[i].z.map((v,k)=>keep(k)?v:null)]},[i]);});const vis=meta.map(x=>x.category.startsWith('__REFERENCE_')||x.category==='__ELEVATION_LABELS__'||((st==='all'||String(x.level)===st)&&(ty==='all'||(ty==='SHEAR WALL SYSTEM'&&(x.category==='SHEAR WALL'||x.category==='SPANDREL'))||x.category===ty)&&(sec==='all'||x.section===sec)));Plotly.restyle(gd,{visible:vis});}ss.addEventListener('change',upd);tt.addEventListener('change',upd);sf.addEventListener('change',upd);gd.on('plotly_hover',function(ev){if(!ev||!ev.points||!ev.points.length)return;const cd=ev.points[0].customdata;if(!cd)return;picked.textContent='ETABS object ID: '+cd[0]+' | OpenSees element tag: '+(cd[1]==='SUPPORT'?'N/A (support node)':(cd[5]||'not instantiated in topology export'))+' | '+cd[1]+' | Storey '+cd[2]+' | Node IDs: '+(cd[3]||'')+' | Section/property: '+(cd[1]==='SUPPORT'?'BASE SUPPORT':(cd[4]||'N/A'));});gd.on('plotly_click',function(ev){if(!ev||!ev.points||!ev.points.length)return;const cd=ev.points[0].customdata;if(!cd)return;picked.textContent='SELECTED ETABS object ID: '+cd[0]+' | OpenSees element tag: '+(cd[1]==='SUPPORT'?'N/A (support node)':(cd[5]||'not instantiated in topology export'))+' | '+cd[1]+' | Storey '+cd[2]+' | Section/property: '+(cd[1]==='SUPPORT'?'BASE SUPPORT':(cd[4]||'N/A'))+' | Nodes: '+(cd[3]||'');});})();""".replace('__META__',json.dumps(structure_meta))
            fig_s.write_html(html_structure,include_plotlyjs=True,full_html=True,auto_open=False,post_script=structure_postscript,div_id='structurePlot')
            # Dedicated 3D connectivity inspector: one trace per original ETABS object,
            # with independent storey, category, and individual-object filters.
            fig_c = go.Figure()
            connectivity_meta = []
            frame_colors = {"BEAM":"#2563eb", "COLUMN":"#dc2626", "BRACE":"#7c3aed", "OTHER FRAME":"#64748b"}
            for obj, pts in frame_conn.items():
                if len(pts) < 2 or any(str(q) not in coords for q in pts[:2]):
                    continue
                a, b = coords[str(pts[0])], coords[str(pts[1])]
                cat = classify_frame(pts)
                midz = (a[2] + b[2]) / 2
                lev = story_index(midz)
                sec=str(section_by_obj.get(str(obj),{}).get("assigned_section") or "UNASSIGNED")
                idx = len(fig_c.data)
                _opensees_element_tag=next((int(rec['element_tag']) for rec in element_records if str(rec['etabs_object'])==str(obj) and rec['dimension']=='line_2_node'),None)
                fig_c.add_trace(go.Scatter3d(x=[a[0],b[0]], y=[a[1],b[1]], z=[a[2],b[2]],
                    mode="lines+markers", name=f"{cat} | {obj}",
                    line=dict(color=frame_colors.get(cat,"#64748b"), width=5),
                    marker=dict(size=2, color=frame_colors.get(cat,"#64748b")),
                    customdata=[[str(obj),cat,lev,f"ETABS {pts[0]} → OpenSees {node_tag.get(str(pts[0]), '?')}",f"ETABS {pts[1]} → OpenSees {node_tag.get(str(pts[1]), '?')}",sec,_opensees_element_tag]]*2,
                    hovertemplate="ETABS object ID: %{customdata[0]}<br>OpenSees element tag: %{customdata[6]}<br>Category: %{customdata[1]}<br>Approx. storey: %{customdata[2]}<br>Node 1: %{customdata[3]}<br>Node 2: %{customdata[4]}<br>ETABS section: %{customdata[5]}<extra></extra>",
                    visible=True, showlegend=False))
                connectivity_meta.append({"trace":idx,"object":str(obj),"element_tag":_opensees_element_tag,"category":cat,"level":lev,"nodes":f"ETABS {pts[0]} → OpenSees {node_tag.get(str(pts[0]), '?')}; ETABS {pts[1]} → OpenSees {node_tag.get(str(pts[1]), '?')}","section":sec})
            area_colors = {"FLOOR":"#059669", "SHEAR WALL":"#f59e0b", "SPANDREL":"#db2777", "OTHER AREA":"#94a3b8"}
            for obj, pts in area_conn.items():
                if len(pts) < 3 or any(str(q) not in coords for q in pts):
                    continue
                xyz = [coords[str(q)] for q in pts]
                zspan = max(q[2] for q in xyz)-min(q[2] for q in xyz)
                if zspan < 0.15:
                    cat = "FLOOR"
                elif zspan > 1.0:
                    cat = "SHEAR WALL"
                else:
                    cat = "SPANDREL"
                lev = story_index(sum(q[2] for q in xyz)/len(xyz))
                sec=str(area_section_by_obj.get(str(obj),{}).get("assigned_property") or "UNASSIGNED")
                poly = xyz + [xyz[0]]
                idx = len(fig_c.data)
                fig_c.add_trace(go.Scatter3d(x=[q[0] for q in poly],y=[q[1] for q in poly],z=[q[2] for q in poly],
                    mode="lines+markers",name=f"{cat} | {obj}",line=dict(color=area_colors.get(cat,"#94a3b8"),width=4),
                    marker=dict(size=2,color=area_colors.get(cat,"#94a3b8")),
                    customdata=[[str(obj),cat,lev,"; ".join(f"ETABS {q} → OpenSees {node_tag.get(str(q), '?')}" for q in pts),sec,next((int(rec['element_tag']) for rec in element_records if str(rec['etabs_object'])==str(obj) and rec['dimension']=='area_polygon'),None)]]*len(poly),
                    hovertemplate="ETABS area object ID: %{customdata[0]}<br>OpenSees element tag: %{customdata[5]}<br>Category: %{customdata[1]}<br>Approx. storey: %{customdata[2]}<br>Node IDs: %{customdata[3]}<br>ETABS area property: %{customdata[4]}<extra></extra>",
                    visible=True,showlegend=False))
                _area_opensees_element_tag=next((int(rec['element_tag']) for rec in element_records if str(rec['etabs_object'])==str(obj) and rec['dimension']=='area_polygon'),None)
                connectivity_meta.append({"trace":idx,"object":str(obj),"element_tag":_area_opensees_element_tag,"category":cat,"level":lev,"nodes":"; ".join(f"ETABS {q} → OpenSees {node_tag.get(str(q), '?')}" for q in pts),"section":sec})
            fig_c.update_layout(title="ETABS element connectivity — individual-object 3D inspection",
                scene=dict(xaxis_title="X (m)",yaxis_title="Y (m)",zaxis_title="Elevation Z (m)",aspectmode="data"),
                height=900,margin=dict(l=0,r=0,t=125,b=0))
            connectivity_postscript = r"""(function(){const gd=document.getElementById('{plot_id}');const meta=__META__;const bar=document.createElement('div');bar.style='position:relative;box-sizing:border-box;width:calc(100% - 24px);margin:8px 12px 4px 12px;display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:8px 12px;align-items:center;background:#fff;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;font:13px Arial;box-shadow:0 2px 8px #0001';bar.innerHTML='<label>Storey <select id="st"><option value="all">All storeys</option></select></label><label>Element type <select id="cat"><option value="all">All types</option></select></label><label>ETABS section/property <select id="sec"><option value="all">All sections/properties</option></select></label><label>ETABS object / OpenSees element / node IDs <select id="obj"><option value="all">All elements</option></select></label><strong id="sum">Click an element to inspect ETABS and OpenSees IDs</strong><button id="clearSel" type="button">Clear selection</button><span id="detail" style="flex-basis:100%;font-size:12px;color:#334155">Selected element details will appear here.</span>';gd.parentElement.insertBefore(bar,gd);const st=bar.querySelector('#st'),cat=bar.querySelector('#cat'),sec=bar.querySelector('#sec'),obj=bar.querySelector('#obj'),sum=bar.querySelector('#sum'),detail=bar.querySelector('#detail');let selected=null;[...new Set(meta.map(x=>x.level))].sort((a,b)=>a-b).forEach(v=>st.add(new Option('Storey '+v,String(v))));[...new Set(meta.map(x=>x.category))].sort().forEach(v=>cat.add(new Option(v,v)));[...new Set(meta.map(x=>x.section||'UNASSIGNED'))].sort().forEach(v=>sec.add(new Option(v,v)));function fillObjects(){const old=obj.value;obj.innerHTML='<option value="all">All elements</option>';meta.filter(x=>(cat.value==='all'||x.category===cat.value)&&(st.value==='all'||String(x.level)===st.value)&&(sec.value==='all'||(x.section||'UNASSIGNED')===sec.value)).sort((a,b)=>a.object.localeCompare(b.object,undefined,{numeric:true})).forEach(x=>obj.add(new Option(x.category+' — ETABS '+x.object+' ↔ OpenSees '+(x.element_tag||'not instantiated')+' — '+(x.section||'UNASSIGNED'),x.object)));if([...obj.options].some(o=>o.value===old))obj.value=old;else obj.value='all';}function upd(){fillObjects();const visible=Array(gd.data.length).fill(false);let count=0;meta.forEach(x=>{const ok=(st.value==='all'||String(x.level)===st.value)&&(cat.value==='all'||x.category===cat.value)&&(sec.value==='all'||(x.section||'UNASSIGNED')===sec.value)&&(obj.value==='all'||x.object===obj.value);visible[x.trace]=ok;if(ok)count++;});Plotly.restyle(gd,{visible:visible});sum.textContent=count+' elements shown';if(obj.value!=='all'){const x=meta.find(x=>x.object===obj.value);if(x)showDetail(x);}}function showDetail(x){selected=x;detail.textContent='SELECTED: '+x.category+' | ETABS object ID: '+x.object+' | OpenSees element tag: '+(x.element_tag||'reserved mapping only')+' | Storey: '+x.level+' | ETABS section/property: '+(x.section||'UNASSIGNED')+'. Node pairs: '+(x.nodes||'see hover tooltip');sum.textContent='Selected ETABS '+x.object+' ↔ OpenSees element '+(x.element_tag||'reserved');}st.addEventListener('change',upd);cat.addEventListener('change',()=>{obj.value='all';upd();});sec.addEventListener('change',()=>{obj.value='all';upd();});obj.addEventListener('change',()=>{if(obj.value==='all'){selected=null;detail.textContent='Selection cleared.';upd();}else{const x=meta.find(x=>x.object===obj.value);if(x)showDetail(x);upd();}});bar.querySelector('#clearSel').addEventListener('click',()=>{selected=null;obj.value='all';detail.textContent='Selection cleared.';upd();});gd.on('plotly_click',function(ev){if(!ev||!ev.points||!ev.points.length)return;const cd=ev.points[0].customdata;if(!cd)return;const x=meta.find(x=>x.object===String(cd[0])&&x.category===String(cd[1]));if(x)showDetail(x);});upd();})();""".replace('__META__',json.dumps(connectivity_meta))
            fig_c.write_html(html_connectivity_3d, include_plotlyjs=True, full_html=True, auto_open=False,
                post_script=connectivity_postscript, div_id='connectivity3dPlot')
            # Load view: translucent area surfaces (not oversized 3D cones), pattern colors,
            # compact legend, and a separate floor-plan view for inspecting individual storeys.
            fig_l=go.Figure()
            xs=[];ys=[];zs=[]
            for n,pts in frame_conn.items():
                if len(pts)>=2 and all(p in coords for p in pts[:2]):
                    a,b=coords[pts[0]],coords[pts[1]]; xs += [a[0],b[0],None]; ys += [a[1],b[1],None]; zs += [a[2],b[2],None]
            fig_l.add_trace(go.Scatter3d(x=xs,y=ys,z=zs,mode="lines",name="Frame skeleton",line=dict(color="#cbd5e1",width=2),hoverinfo="skip"))
            pat_colors={"Floor Finish":"#2563eb","Live":"#dc2626","Partition":"#7c3aed","Roof Live":"#059669"}
            # Same 3.5 m first storey + 3.8 m typical storeys as structural view.
            def level_for_points(pts):
                zz=[coords[p][2] for p in pts if p in coords]
                z=sum(zz)/len(zz) if zz else 0.0
                return story_index(z)
            load_trace_meta=[]
            for a in applied:
                pat=a["pattern"]; obj=str(a["object"]); pts=area_conn.get(obj,[])
                if len(pts)<3 or any(p not in coords for p in pts): continue
                xyz=[coords[p] for p in pts]; si=level_for_points(pts)
                # Triangulate as a fan so area loads appear as translucent colored surfaces.
                for j in range(1,len(xyz)-1):
                    tri=[xyz[0],xyz[j],xyz[j+1]]
                    idx=len(fig_l.data)
                    fig_l.add_trace(go.Mesh3d(x=[q[0] for q in tri],y=[q[1] for q in tri],z=[q[2] for q in tri],i=[0],j=[1],k=[2],color=pat_colors.get(pat,"#f59e0b"),opacity=0.48,name=f"{pat} | Storey {si}",legendgroup=pat,showlegend=(j==1),hovertemplate=f"Pattern: {pat}<br>Area object: {obj}<br>Storey: {si}<br>ETABS intensity: {a['value']}<br>Area: {a.get('area_m2',0):.3f} m²<extra></extra>"))
                    load_trace_meta.append((idx,pat,si,float(a["value"]),obj))
            # Highlight frame distributed loads (including Wall) in the 3D audit.
            # These traces are visual audit only; frame loads are not yet applied to OpenSees.
            frame_pat_colors={"Wall":"#ea580c"}
            shown_frame_patterns=set()
            # Build normalized aliases for frame IDs and query IDs. Some CSI COM
            # returns include formatting differences; use query_object as fallback.
            frame_conn_normalized={normalized_object_name(k):v for k,v in frame_conn.items()}
            for fl in frame_loads:
                obj=str(fl.get("object","")).strip(); query_obj=str(fl.get("query_object","")).strip(); pat=str(fl.get("pattern","")).strip()
                pts=frame_conn.get(obj, frame_lookup.get(obj.casefold(), []))
                if not pts: pts=frame_conn_normalized.get(normalized_object_name(obj), [])
                if not pts and query_obj:
                    pts=frame_conn.get(query_obj, frame_lookup.get(query_obj.casefold(), []))
                    if not pts: pts=frame_conn_normalized.get(normalized_object_name(query_obj), [])
                if len(pts)<2 or any(p not in coords for p in pts[:2]): continue
                a0,b0=coords[pts[0]],coords[pts[1]]
                # Clip frame load traces to the same selected storey band as columns.
                zmin,zmax=sorted((a0[2],b0[2]))
                first=max(1,story_index(zmin+1e-7)); last=max(first,story_index(zmax-1e-7))
                v0=fl.get("value_start"); v1=fl.get("value_end")
                val=float(v0 if v0 is not None else (v1 if v1 is not None else 0.0))
                for si in range(first,min(last,max_storey)+1):
                    seg=clipped_segment(a0,b0,story_bottom(si),story_top(si))
                    if seg is None: continue
                    aa,bb=seg
                    # Draw the wall line load as repeated downward UDL arrows, offset slightly
                    # above the loaded member so the arrows are visible against the frame skeleton.
                    # Arrow direction is a visual confirmation convention only; it does NOT
                    # assert the ETABS direction-code interpretation or apply the load to OpenSees.
                    arrow_color=frame_pat_colors.get(pat,"#ea580c")
                    dx,dy,dz=(bb[i]-aa[i] for i in range(3)); length=math.sqrt(dx*dx+dy*dy+dz*dz)
                    n_arrows=max(2,min(8,int(length/1.5)+1))
                    drop=max(0.45,min(1.1,0.08*max(xmax-xmin,ymax-ymin,1.0)))
                    ax=[]; ay=[]; az=[]
                    for ai in range(n_arrows):
                        t=(ai+0.5)/n_arrows
                        px=aa[0]+t*dx; py=aa[1]+t*dy; pz=aa[2]+t*dz
                        # Shaft: above the member down to member elevation.
                        ax.extend([px,px,None]); ay.extend([py,py,None]); az.extend([pz+drop,pz,None])
                        # Two short diagonal strokes form a clear downward arrow head.
                        head=max(0.18,min(0.35,length/max(n_arrows,1)*0.22))
                        ax.extend([px-head,px,None,px+head,px,None])
                        ay.extend([py,py,None,py,py,None])
                        az.extend([pz+head,pz,None,pz+head,pz,None])
                    idx=len(fig_l.data)
                    fig_l.add_trace(go.Scatter3d(
                        x=ax,y=ay,z=az,mode="lines",name=f"{pat} UDL arrows | Storey {si}",
                        legendgroup=pat,showlegend=pat not in shown_frame_patterns,
                        line=dict(color=arrow_color,width=5),
                        customdata=[[obj or query_obj,pat,si,val,v1,fl.get("direction_code"),fl.get("coordinate_system")]]*len(ax),
                        hovertemplate="Frame object %{customdata[0]}<br>Pattern: %{customdata[1]}<br>Storey: %{customdata[2]}<br>Load start: %{customdata[3]}<br>Load end: %{customdata[4]}<br>Direction code: %{customdata[5]}<br>Coordinate system: %{customdata[6]}<br>Visual UDL arrow (not yet applied)<extra></extra>"))
                    shown_frame_patterns.add(pat)
                    load_trace_meta.append((idx,pat,si,val,"FRAME:"+(obj or query_obj),float(v1) if v1 is not None else val))
            fig_l.update_layout(title="Load assignments — downward UDL arrow preview (visual only)",scene=dict(xaxis_title="X (m)",yaxis_title="Y (m)",zaxis_title="Z (m)",aspectmode="data",camera=dict(eye=dict(x=1.7,y=1.7,z=1.15))),height=900,legend=dict(itemsizing="constant",groupclick="togglegroup"),margin=dict(l=0,r=10,t=145,b=0))
            load_meta=[{"trace":item[0],"pattern":item[1],"level":item[2],"value":item[3],"object":item[4],**({"value_end":item[5]} if len(item)>5 else {})} for item in load_trace_meta]
            load_postscript=r"""(function(){const gd=document.getElementById('{plot_id}');const meta=__META__;const bar=document.createElement('div');bar.style='position:relative;box-sizing:border-box;width:calc(100% - 24px);margin:8px 12px 4px 12px;display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:8px 12px;align-items:center;background:#fff;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;font:14px Arial;box-shadow:0 2px 8px #0001';bar.innerHTML='<label>Storey <select id="storyFilter"><option value="all">All storeys</option></select></label><label>Load pattern <select id="patternFilter"><option value="all">All patterns</option></select></label><label>UDL value <select id="valueFilter"><option value="all">All values</option></select></label><strong id="loadSummary">All assignments</strong>';gd.parentElement.insertBefore(bar,gd);const ss=bar.querySelector('#storyFilter'),pp=bar.querySelector('#patternFilter'),vv=bar.querySelector('#valueFilter'),sum=bar.querySelector('#loadSummary');[...new Set(meta.map(x=>x.level))].sort((a,b)=>a-b).forEach(v=>ss.add(new Option('Storey '+v,String(v))));[...new Set(meta.map(x=>x.pattern))].sort().forEach(v=>pp.add(new Option(v,v)));[...new Set(meta.filter(x=>String(x.object).startsWith('FRAME:')).flatMap(x=>[Number(x.value.toFixed(3)),...(x.value_end===undefined?[]:[Number(Number(x.value_end).toFixed(3))])]).filter(v=>Number.isFinite(v)))].sort((a,b)=>a-b).forEach(v=>vv.add(new Option(v+' kN/m',String(v))));function upd(){const st=ss.value,pat=pp.value,val=vv.value;const vis=Array(gd.data.length).fill(false);vis[0]=true;const chosen=meta.filter(x=>(st==='all'||String(x.level)===st)&&(pat==='all'||x.pattern===pat)&&(val==='all'||!String(x.object).startsWith('FRAME:')||(Math.abs(x.value-Number(val))<0.001)||(x.value_end!==undefined&&Math.abs(Number(x.value_end)-Number(val))<0.001)));chosen.forEach(x=>vis[x.trace]=true);Plotly.restyle(gd,{visible:vis});const vals=chosen.map(x=>x.value);const uniq=[...new Set(vals.map(v=>Number(v.toPrecision(5))))];const frameCount=chosen.filter(x=>String(x.object).startsWith('FRAME:')).length;sum.textContent=chosen.length+' load traces/triangles • '+(frameCount?frameCount+' frame-load traces; ':'')+(uniq.length===1&&uniq.length?'value: '+uniq[0]:'values: '+(vals.length?Math.min(...vals).toPrecision(4)+' to '+Math.max(...vals).toPrecision(4):'none'));Plotly.relayout(gd,{title:'Load assignments — UDL arrow preview (visual only) • '+(st==='all'?'all storeys':'Storey '+st)+' • '+(pat==='all'?'all patterns':pat)});}ss.addEventListener('change',upd);pp.addEventListener('change',upd);vv.addEventListener('change',upd);upd();})();""".replace('__META__',json.dumps(load_meta))
            fig_l.write_html(html_loads,include_plotlyjs=True,full_html=True,auto_open=False,post_script=load_postscript,div_id='loadPlot')

            # Additional plan-view page: much easier to confirm which floor areas are loaded.
            html_plan=os.path.join(outdir,"OpenSees_Load_Assignment_Floor_Plan.html")
            fig_p=go.Figure()
            plan_meta=[]; shown_plan_load_legend=set()
            for a in applied:
                pat=a["pattern"]; obj=str(a["object"]); pts=area_conn.get(obj,[])
                if len(pts)<3 or any(p not in coords for p in pts): continue
                xyz=[coords[p] for p in pts]; si=level_for_points(pts)
                xx=[q[0] for q in xyz]+[xyz[0][0]]; yy=[q[1] for q in xyz]+[xyz[0][1]]
                idx=len(fig_p.data)
                _legend_key=(pat,si); _show_load_legend=_legend_key not in shown_plan_load_legend; shown_plan_load_legend.add(_legend_key)
                fig_p.add_trace(go.Scatter(x=xx,y=yy,mode="lines",fill="toself",fillcolor=pat_colors.get(pat,"#f59e0b"),opacity=0.52,line=dict(color=pat_colors.get(pat,"#f59e0b"),width=1.5),name=f"{pat} | Storey {si}",legendgroup=f"LOAD:{pat}:{si}",showlegend=_show_load_legend,customdata=[[obj,pat,si,a['value'],a.get('area_m2',0)]]*(len(xx)),hovertemplate="Object %{customdata[0]}<br>Pattern %{customdata[1]}<br>Level %{customdata[2]}<br>Intensity %{customdata[3]}<br>Area %{customdata[4]:.3f} m²<extra></extra>"))
                plan_meta.append((idx,pat,si,float(a["value"]),obj,"load"))
            # Diaphragm layer: display all structural slave joints at each
            # ETABS floor and its separate OpenSees master node. This shows
            # constraint membership without implying a modeled slab boundary.
            _point_by_tag={int(tag):str(point) for point,tag in node_tag.items()}
            for group in diaphragm_groups:
                _story=int(group["storey_number"]); _dname=str(group["diaphragm_name"])
                _slave_tags=[int(t) for t in group["slave_node_tags"]]
                _points=[_point_by_tag[t] for t in _slave_tags if t in _point_by_tag]
                if not _points: continue
                _xx=[float(coords[p][0]) for p in _points]; _yy=[float(coords[p][1]) for p in _points]
                _custom=[[p,node_tag[p],_story,_dname,group["opensees_diaphragm_id"]] for p in _points]
                idx=len(fig_p.data)
                fig_p.add_trace(go.Scatter(x=_xx,y=_yy,mode="markers",name=f"Diaphragm slaves | Storey {_story} | ETABS {_dname} / OpenSees D{group['opensees_diaphragm_id']}",legendgroup=f"DIAPHRAGM:{_story}:{_dname}",showlegend=True,marker=dict(color="#06b6d4",size=8,symbol="circle",line=dict(color="#0e7490",width=1)),customdata=_custom,hovertemplate="ETABS point %{customdata[0]}<br>OpenSees node %{customdata[1]}<br>Storey %{customdata[2]}<br>ETABS diaphragm %{customdata[3]}<br>OpenSees diaphragm ID %{customdata[4]}<br>Rigid diaphragm slave<extra></extra>"))
                plan_meta.append((idx,f"{_dname}",_story,0.0,f"DIAPHRAGM:{_dname}","diaphragm"))
                _master=group["master_xyz"]
                idx=len(fig_p.data)
                fig_p.add_trace(go.Scatter(x=[float(_master[0])],y=[float(_master[1])],mode="markers",name=f"Diaphragm master | Storey {_story} | ETABS {_dname} / OpenSees D{group['opensees_diaphragm_id']}",legendgroup=f"DIAPHRAGM:{_story}:{_dname}",showlegend=True,marker=dict(color="#dc2626",size=13,symbol="diamond",line=dict(color="#7f1d1d",width=1.5)),customdata=[[group["master_tag"],_story,group["etabs_diaphragm_id"],group["opensees_diaphragm_id"]]],hovertemplate="OpenSees master node %{customdata[0]}<br>Storey %{customdata[1]}<br>ETABS diaphragm ID %{customdata[2]}<br>OpenSees diaphragm ID %{customdata[3]}<extra></extra>"))
                plan_meta.append((idx,f"{_dname}",_story,0.0,f"DIAPHRAGM_MASTER:{_dname}","diaphragm"))
            fig_p.update_layout(title="Floor plan load audit — choose storey and load pattern",xaxis_title="X (m)",yaxis_title="Y (m)",yaxis=dict(scaleanchor="x",scaleratio=1),height=850,margin=dict(l=30,r=30,t=145,b=30),legend=dict(itemsizing="constant"))
            plan_meta_json=[{"trace":idx,"pattern":p,"level":lev,"value":val,"object":obj,"kind":kind} for idx,p,lev,val,obj,kind in plan_meta]
            plan_postscript=r"""(function(){const gd=document.getElementById('{plot_id}');const meta=__META__;const bar=document.createElement('div');bar.style='position:relative;box-sizing:border-box;width:calc(100% - 24px);margin:8px 12px 4px 12px;display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:8px 12px;align-items:center;background:#fff;padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px;font:14px Arial;box-shadow:0 2px 8px #0001';bar.innerHTML='<label>View <select id="viewFilter"><option value="load">Loads</option><option value="diaphragm">Rigid diaphragms</option><option value="both">Loads + diaphragms</option></select></label><label>Storey <select id="storyFilter"><option value="all">All storeys</option></select></label><label>Load pattern <select id="patternFilter"><option value="all">All patterns</option></select></label><strong id="loadSummary">Choose a view</strong>';gd.parentElement.insertBefore(bar,gd);if(!meta.some(x=>x.kind==='load')){bar.insertAdjacentHTML('beforeend','<strong style="color:#b45309">No area loads extracted. Inspect API audit; this does not mean zero gravity load. Showing diaphragms.</strong>');bar.querySelector('#viewFilter').value='diaphragm';}const vv=bar.querySelector('#viewFilter'),ss=bar.querySelector('#storyFilter'),pp=bar.querySelector('#patternFilter'),sum=bar.querySelector('#loadSummary');[...new Set(meta.map(x=>x.level))].sort((a,b)=>a-b).forEach(v=>ss.add(new Option('Storey '+v,String(v))));[...new Set(meta.filter(x=>x.kind==='load').map(x=>x.pattern))].sort().forEach(v=>pp.add(new Option(v,v)));function upd(){const view=vv.value,st=ss.value,pat=pp.value;pp.disabled=view==='diaphragm';const vis=Array(gd.data.length).fill(false);const chosen=meta.filter(x=>(st==='all'||String(x.level)===st)&&(view==='both'||x.kind===view)&&(x.kind!=='load'||pat==='all'||x.pattern===pat));chosen.forEach(x=>vis[x.trace]=true);Plotly.restyle(gd,{visible:vis});const nLoads=chosen.filter(x=>x.kind==='load').length,nDia=chosen.filter(x=>x.kind==='diaphragm').length;sum.textContent=nLoads+' load areas • '+nDia+' diaphragm markers'+(view==='diaphragm'&&!nDia?' • no rigid diaphragms extracted':'');Plotly.relayout(gd,{title:'Floor plan — '+(view==='load'?'loads':view==='diaphragm'?'rigid diaphragm membership':'loads + diaphragm membership')+' • '+(st==='all'?'all storeys':'Storey '+st)});}vv.addEventListener('change',upd);ss.addEventListener('change',upd);pp.addEventListener('change',upd);upd();})();""".replace('__META__',json.dumps(plan_meta_json))
            fig_p.write_html(html_plan,include_plotlyjs=True,full_html=True,auto_open=False,post_script=plan_postscript,div_id='planPlot')
            import webbrowser
        # CSV report (standard library only)
        import csv
        csv_path=os.path.join(outdir,"OpenSees_Load_Assignments.csv")
        with open(csv_path,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.DictWriter(f,fieldnames=["object","pattern","coordinate_system","direction_code","value","area_m2","total_force_raw_units","node_names","note"]); w.writeheader()
            for r in applied: w.writerow({k:r.get(k,"") for k in w.fieldnames})
        log(f"OpenSees topology stage: {len(node_tag)} node tags created; {len(element_records)} element tags reserved in mapping; ETABS section/property names carried into tagged topology and 3D section filters.")
        log(f"Area assignments extracted={len(area_loads)}, applied={len(applied)}, skipped={len(skipped)}")
        log(f"Frame distributed assignments extracted={len(frame_loads)}; equivalent nodal loads applied={frame_equiv_count}; skipped={len(skipped_frame_loads)}.")
        log(f"Base supports: {len(base_nodes)} nodes fully fixed (UX, UY, UZ, RX, RY, RZ) at Z={base_z:.6g} m.")
        log("NOTE: Load/connectivity audit preserved. Review/edit frame properties inside this program using the integrated Section Mapping/Library and Fiber Section Builder windows. The generated OpenSees_Section_Review_GUI.py is retained as an optional standalone reviewer. NONLINEAR ANALYSIS BLOCKED until fiber-section inputs and reinforcing-bar coordinates are completed, checked, and calibrated against a documented reference.")
        log("Outputs:")
        for p in (out_py,audit_json,csv_path,html_structure,html_connectivity_3d,html_loads,os.path.join(outdir,"OpenSees_Load_Assignment_Floor_Plan.html"),connectivity_csv,connectivity_json,connectivity_py,tagged_model_py,section_audit_csv,section_audit_json,section_gui_path,fiber_template_csv,bar_template_csv,esm_template_csv,esm_template_json): log("  "+p)
        log("Review skipped assignments and the audit JSON before any structural analysis.")
        from OpenSees_Complete_Export_V118 import extract_source_metadata, prepare_complete_export
        _begin_step("Connected model assembly and analysis-file manifest")
        extract_source_metadata(sap, json.loads(Path(connectivity_json).read_text(encoding="utf-8-sig")),
            frame_section_assignments, Path(outdir)/"OpenSees_Source_Model_Metadata_V118.json")
        manifest, assembly_report=prepare_complete_export(outdir, frame_mapping=ETABS_TO_OPENSEES_SECTION)
        log("Complete export report: "+str(Path(outdir)/manifest['report']))
        log("Assembly errors: "+str(assembly_report['assembly_errors']))
        _finish_step("OK")
        # Shared controls must be installed before any browser tab opens.
        import webbrowser
        webbrowser.open(Path(html_structure).resolve().as_uri())
        webbrowser.open(Path(html_connectivity_3d).resolve().as_uri())
        webbrowser.open(Path(html_loads).resolve().as_uri())
        webbrowser.open(Path(html_plan).resolve().as_uri())
        _conversion_succeeded=True
        return out_py,html_loads,audit_json,section_gui_path
    except Exception as exc:
        _finish_step("FAILED")
        log(f"[CONVERSION FAILED] {type(exc).__name__}: {exc}")
        raise
    finally:
        if sap is not None:
            try:
                sap.File.Close(False)
                log("ETABS model file closed without saving.")
            except Exception: pass
        if etabs is not None:
            try: etabs.ApplicationExit(False); log("ETABS application closed without saving.")
            except Exception: pass
        _elapsed=time.perf_counter()-_conversion_started
        log(f"[CONVERSION {'COMPLETED' if _conversion_succeeded else 'INCOMPLETE'}] Total elapsed: {_elapsed:.2f} s ({_elapsed/60.0:.2f} min)")


# ============================================================================
# SECTION 13 — ETABS IMPORT / OPENSEES ANALYSIS GUI ENTRY POINT
# ============================================================================
class App:
    def __init__(self,root):
        self.root=root; root.title("ETABS → OpenSeesPy | NBC 105 Workflow — V161 literature materials and component research")
        root.geometry("1480x940"); root.minsize(1180,760); root.configure(bg="#eef2f7")
        source_folder=Path(__file__).resolve().parent/'components'
        if not source_folder.is_dir():source_folder=Path(__file__).resolve().parent/'OpenSees_Runtime_V118/components'
        ttk.Button(root,text="Open full implementation code (components folder)",command=lambda:os.startfile(str(source_folder))).pack(fill="x")
        self.edb=tk.StringVar(); self.out=tk.StringVar(value=os.environ.get("OPENSEES_PROJECT_FOLDER",r"D:\Thesis Opensees\Etabs Nodes Export"))
        self.include_live=tk.BooleanVar(value=True)
        ttk.Label(root,text='V161 running code: '+str(Path(__file__).resolve()),wraplength=1350).pack(fill='x')
        def repair_runtime():
            from OpenSees_Release_Health_V142 import repair
            try:repair(Path(__file__).resolve().parent,self.out.get());messagebox.showinfo('Runtime updated','Selected export runtime refreshed. Re-export loads if its audit has zero assignments; old analysis results were not recalculated.',parent=self.root)
            except Exception as exc:messagebox.showerror('Runtime repair',str(exc),parent=self.root)
        ttk.Button(root,text='Refresh selected export runtime / diagnose versions',command=repair_runtime).pack(fill='x')
        def open_saved(name):
            target=Path(self.out.get())/name
            if target.is_file():__import__('webbrowser').open(target.resolve().as_uri())
            else:messagebox.showinfo('Saved view missing','Run step 1 export first. Expected: '+str(target),parent=self.root)
        style=ttk.Style(root)
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("TFrame",background="#eef2f7"); style.configure("Card.TFrame",background="#ffffff")
        style.configure("TLabel",background="#eef2f7",foreground="#172033",font=("Segoe UI",10))
        style.configure("TButton",font=("Segoe UI",10),padding=4)
        style.configure("Primary.TButton",background="#2563eb",foreground="white",font=("Segoe UI",10,"bold"),padding=10)
        from OpenSees_Research_UI_V123 import scrollable_form
        shell=scrollable_form(root,padding=14,min_width=1180)
        head=tk.Frame(shell,bg="#152238",padx=20,pady=16); head.pack(fill="x",pady=(0,14))
        tk.Label(head,text="ETABS → OPENSEESPY | NBC 105:2025",bg="#152238",fg="white",font=("Segoe UI",18,"bold")).pack(anchor="w")
        tk.Label(head,text="Choose a workflow column: ETABS import, section/material mapping, or OpenSees analysis.",bg="#152238",fg="#cbd5e1",font=("Segoe UI",10)).pack(anchor="w",pady=(4,0))
        source=ttk.LabelFrame(shell,text="ETABS IMPORT — SOURCE MODEL AND EXPORT LOCATION",padding=10); source.pack(fill="x",pady=(0,8))
        source.columnconfigure(1,weight=1)
        ttk.Label(source,text="ETABS model (.EDB)").grid(row=0,column=0,sticky="w",padx=(0,8),pady=3)
        ttk.Entry(source,textvariable=self.edb).grid(row=0,column=1,sticky="ew",pady=3)
        ttk.Button(source,text="Browse…",command=self._browse_file).grid(row=0,column=2,padx=(8,0),pady=3)
        ttk.Label(source,text="OpenSees export folder").grid(row=1,column=0,sticky="w",padx=(0,8),pady=3)
        ttk.Entry(source,textvariable=self.out).grid(row=1,column=1,sticky="ew",pady=3)
        ttk.Button(source,text="Browse…",command=self._browse_dir).grid(row=1,column=2,padx=(8,0),pady=3)
        self.include_live.set(True)
        ttk.Checkbutton(source,text="Include live area load in ETABS load audit preview",variable=self.include_live).grid(row=2,column=0,columnspan=2,sticky="w",pady=(4,0))
        runbar=ttk.Frame(shell); runbar.pack(fill="x",pady=(0,8))
        self.runbtn=ttk.Button(runbar,text="RUN ETABS → OPENSEESPY EXPORT  |  Assemble model, loads, mass and analysis-file manifest",style="Primary.TButton",command=self._run)
        self.runbtn.pack(fill="x",ipady=5)
        ttk.Button(runbar,text="Rebuild assembled model from saved ETABS export",command=self._rebuild_complete_export).pack(anchor="w",pady=(4,0))
        columns=ttk.Frame(shell); columns.pack(fill="both",expand=True,pady=(0,8))
        for col in range(3): columns.columnconfigure(col,weight=1,uniform="workflow"); columns.rowconfigure(0,weight=1)
        etabs_col=ttk.LabelFrame(columns,text="1. ETABS IMPORTS & LOAD AUDIT",padding=10); etabs_col.grid(row=0,column=0,sticky="nsew",padx=(0,5))
        sections_col=ttk.LabelFrame(columns,text="2. ETABS ↔ OPENSEES SECTION / MATERIAL REVIEW",padding=10); sections_col.grid(row=0,column=1,sticky="nsew",padx=5)
        analysis_col=ttk.LabelFrame(columns,text="3. OPENSEES ANALYSIS — NBC 105:2025",padding=10); analysis_col.grid(row=0,column=2,sticky="nsew",padx=(5,0))
        ttk.Label(etabs_col,text="SECTION 01 — IMPORTS\nUse ETABS .EDB as the source. The top run button reads it without saving changes and creates audit/export files.",wraplength=360,justify="left").pack(anchor="w",pady=(0,8))
        ttk.Label(etabs_col,text='Direct saved 3D / plan views',font=('Segoe UI',10,'bold')).pack(anchor='w')
        for label,name in [('3D connectivity','OpenSees_Element_Connectivity_3D.html'),('3D structural frames / storeys','OpenSees_Structural_Elements_By_Storey.html'),('3D area + frame loads','OpenSees_Load_Assignment_3D.html'),('Floor load / diaphragm plan','OpenSees_Load_Assignment_Floor_Plan.html')]:
            ttk.Button(etabs_col,text=label,command=lambda name=name:open_saved(name)).pack(fill='x',pady=2)
        ttk.Button(etabs_col,text='Numbered workflow / input values',command=lambda:__import__('OpenSees_Workflow_V144').launch(self.root,self.out.get())).pack(fill='x',pady=2)
        ttk.Button(etabs_col,text="Open ETABS connectivity + load views",command=self._show_last_exports).pack(fill="x",pady=3)
        ttk.Button(etabs_col,text="ETABS / OpenSees ID lookup + Excel support audit",command=lambda: __import__("webbrowser").open((Path(self.out.get())/"OpenSees_ID_Lookup.html").resolve().as_uri())).pack(fill="x",pady=3)
        ttk.Button(etabs_col,text="Open ETABS frame / area load audit",command=self._open_load_audit_explanation).pack(fill="x",pady=3)
        ttk.Label(etabs_col,text="Area-load audit accepts verified Dead/DL/finish/live pattern names and Global Z or Gravity directions. Self-weight is controlled by ETABS pattern multipliers (not object load rows); multiplier audit is exported, but automatic self-weight transfer still needs checked section/material weights.",wraplength=360,justify="left",foreground="#8a3412").pack(anchor="w",pady=(8,3))
        ttk.Label(sections_col,text="ETABS source section names stay as-is; assign reviewed OpenSees fiber/device sections through the mapping audit.",wraplength=360,justify="left").pack(anchor="w",pady=(0,8))
        ttk.Button(sections_col,text="ETABS section mapping → OpenSees fiber sections",command=self._open_section_mapping).pack(fill="x",pady=3)
        ttk.Button(sections_col,text="OpenSees RC fiber section builder — Concrete01 + Steel02",command=self._open_fiber_section_builder).pack(fill="x",pady=3)
        ttk.Button(sections_col,text="ETABS RC column size / bar review",command=self._open_column_section_review).pack(fill="x",pady=3)
        ttk.Button(sections_col,text='Slab load path / mesh + Excel formulas',command=lambda:__import__('OpenSees_Load_Path_V141').launch(self.root,self.out.get())).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='ULS/SLS drift / deflection + combination / PDelta review',command=lambda:__import__('OpenSees_Case_Review_V142').launch(self.root,self.out.get())).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='NBC settings audit - values and unresolved inputs',command=lambda:__import__('components.validation.settings_audit',fromlist=['launch']).launch(self.root,self.out.get())).pack(fill='x',padx=12,pady=4)
        ttk.Label(sections_col,text='VALIDATION AND ETABS COMPARISON',font=('Segoe UI',10,'bold')).pack(fill='x',pady=4)
        ttk.Button(sections_col,text='ETABS comparison - modal / ESM / MRSM',command=lambda:__import__('components.validation.etabs_comparison',fromlist=['launch']).launch(self.root,self.out.get())).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='Literature profiles - exact values / formulation / run',command=lambda:__import__('components.validation.material_catalog',fromlist=['launch']).launch(self.root,self.out.get())).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='Saved component graphs - all 8 materials / devices',command=lambda:__import__('components.validation.research_results_gui',fromlist=['launch']).launch(self.root)).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='Individual material / device setup and tuning',command=lambda:__import__('components.validation.parameter_gui',fromlist=['launch']).launch(self.root,self.out.get())).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='Experimental Steel02 calibration - run / graphs / Excel',command=lambda:__import__('components.validation.steel_calibration_gui',fromlist=['launch']).launch(self.root,self.out.get())).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='Visual validation - Concrete01 / Steel02 / FVD / BRB / walls',command=lambda:__import__('components.validation.visual_workbench',fromlist=['launch']).launch(self.root)).pack(fill='x',pady=3)
        ttk.Button(sections_col,text='Wall validation - Kolozvari 2023 / Lu 2015',command=lambda:__import__('OpenSees_Wall_Validation_V147').launch(self.root)).pack(fill='x',pady=3)
        ttk.Button(sections_col,text="OpenSees material + section library — RC, walls, slab, SHS, FVD, BRB",command=self._open_material_values).pack(fill="x",pady=3)
        ttk.Button(sections_col,text="FVD / BRB ETABS brace replacement guide",command=self._open_fvd_brb_guide).pack(fill="x",pady=3)
        ttk.Label(analysis_col,text="Analysis controls operate on the reviewed OpenSees model/export. Complete load, mass, section and readiness checks before NLTHA.",wraplength=360,justify="left").pack(anchor="w",pady=(0,8))
        ttk.Button(analysis_col,text="OpenSees gravity analysis — run, plot + report",command=self._open_gravity_analysis).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="NBC 105: load combinations, stiffness + mass source",command=self._open_nbc105_settings).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="ULS / SLS design checks - combinations, drift, sections",command=lambda:__import__("OpenSees_Design_Checks_V135").launch(self.root,self.out.get())).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="NBC 105 formula reference — periods, ELF + drift",command=self._open_nbc105_formula_reference).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="Step 13 — P-Delta, stiffness modifiers + damping",command=self._open_step13_basis).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="OpenSees equivalent static analysis — ULS/SLS",command=self._open_nbc105_esm).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="OpenSees modal analysis + NBC checks",command=self._open_modal_audit).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="Site / record spectra and matching diagnostics",command=self._open_spectrum_diagnostics).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="Model response spectrum (CQC) - SLS / ULS",command=lambda:__import__('OpenSees_Model_Response_Spectrum_V132').launch(self.root,self.out.get())).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="Lateral deformation / drift outputs",command=lambda:__import__('OpenSees_Response_Checks_V132').launch_response_viewer(self.root,Path(self.out.get())/'OpenSees_Analysis_Results')).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="NBC 5.4 irregularity review",command=lambda:__import__('OpenSees_Response_Checks_V132').launch_irregularity(self.root,self.out.get())).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="OpenSees linear time history — paired NBC records",command=self._open_linear_time_history).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="OpenSees nonlinear paired time history — V116 gate",command=self._open_nonlinear_time_history).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="Literature nonlinear demo - run, compare + animate",command=lambda:__import__("OpenSees_Literature_Demo_GUI_V137").launch(self.root)).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="Building nonlinear research - frames + FSAM walls",command=lambda:__import__("OpenSees_Building_Exploratory_GUI_V138").launch(self.root,self.out.get())).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="ETABS area mesh → OpenSees floors/wall panels",command=self._open_area_integration).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="OpenSees stability + outrigger case progression",command=self._open_project_progression).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text="OpenSees result interpretation + mode shapes",command=self._open_result_interpretation).pack(fill="x",pady=3)
        ttk.Button(analysis_col,text='Nonlinear dependencies - available / missing inputs',command=lambda:__import__('components.model.nonlinear_preflight',fromlist=['launch']).launch(self.root,self.out.get())).pack(fill='x',pady=3)
        ttk.Button(analysis_col,text="OpenSees nonlinear readiness / calibration status",command=self._open_nonlinear_readiness).pack(fill="x",pady=3)
        logcard=ttk.Frame(shell,style="Card.TFrame",padding=10); logcard.pack(fill="both",expand=True)
        ttk.Label(logcard,text="ETABS → OPENSEESPY IMPORT / CONVERSION LOG",font=("Segoe UI",10,"bold"),background="#ffffff").pack(anchor="w",pady=(0,6))
        frm=ttk.Frame(logcard,style="Card.TFrame"); frm.pack(fill="both",expand=True)
        self.logbox=tk.Text(frm,bg="#0b1220",fg="#dbeafe",insertbackground="white",font=("Cascadia Mono",9),height=8,wrap="word",relief="flat")
        sb=ttk.Scrollbar(frm,command=self.logbox.yview); self.logbox.configure(yscrollcommand=sb.set); self.logbox.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        self.log("Select the ETABS EDB and run ETABS → OpenSeesPy Import + Audit. ETABS is closed without saving. The generated connectivity/load audit is not a fully load-complete analysis model; review self-weight multipliers and all skipped load records before analysis.")
    def _open_spectrum_diagnostics(self):
        from NBC105_Spectrum_Scaling_V115 import launch_spectrum_gui
        app=launch_spectrum_gui(self.root)
        from OpenSees_Linear_Autofill_V124 import populate_site
        populate_site(app,self.out.get())
        return app

    def _open_step13_basis(self):
        """Show the cited Step 13 combination, modifiers and damping basis."""
        try:
            from OpenSees_Step13_Analysis_Basis_V115 import open_step13_gui
            open_step13_gui(self.root)
        except Exception as exc:
            messagebox.showerror("Step 13 reference", str(exc), parent=self.root)

    def _open_nbc105_formula_reference(self):
        """Show the V116 formula map with NBC, mechanics and supplemental sources separated."""
        win=tk.Toplevel(self.root); win.title("NBC 105:2025 Formula Reference — V133")
        win.geometry("1080x760"); win.minsize(850,600); win.transient(self.root)
        outer=ttk.Frame(win,padding=14); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="FORMULA REFERENCE — YOUR KIRTIPUR CORE + OUTRIGGER STUDY",font=("Segoe UI",14,"bold")).pack(anchor="w")
        ttk.Label(outer,text="NBC 105:2025 is the seismic basis. The tutorial's ASCE example equations are identified as non-NBC. IS 16700 is shown only as a separately labeled tall-building supplement.",wraplength=1020).pack(anchor="w",pady=(5,10))
        txt=tk.Text(outer,wrap="word",font=("Cascadia Mono",9),height=30)
        scroll=ttk.Scrollbar(outer,orient="vertical",command=txt.yview); txt.configure(yscrollcommand=scroll.set)
        txt.pack(side="left",fill="both",expand=True); scroll.pack(side="right",fill="y")
        summary=(
            "NBC 105:2025 CODE FORMULAS\n"
            "• Period, §5.1: Rayleigh T_R = 2π√[Σ(Wi di²)/(g Σ(Fi di))]. Empirical period is multiplied by 1.25 (§5.1.3); adopt the lesser of T_R and 1.25 T_emp for design action. Calculate X/Y separately.\n"
            "• Concrete shear-wall empirical period, §5.1.2: T_emp = kt H^(3/4), kt=0.075/√Aw; Aw=Σ Awi[0.2+(Lwi/H)²], with code geometry restrictions. The opening direction requires net pier/segment geometry; do not use gross length over openings.\n"
            "• Cracked flexural stiffness, §3.4 Table 3-1 (ULS/SLS): beam .35/.70; column .70/.90; cracked wall .50/.70; uncracked wall .80/.90; flat slab .25/.50; steel 1/1. Your floor is a conventional slab: Table 3-1 has no general conventional-slab factor, so use documented rational cracked stiffness or verified ETABS effective stiffness. Do not also scale nonlinear fiber/FSAM material response.\n"
            "• Seismic mass, §5.2/Table 5-1: Wi includes dead load plus occupancy-dependent seismic live load (storage .60, other .30, roof 0). Convert weight to mass by m= W/g. A rectangular-floor Jm expression is invalid for this asymmetric/open plan unless actual mass is uniform over that rectangle.\n"
            "• ESM, §§6.1–6.4: use NBC spectra and ULS/SLS coefficients; V=Cd(T1)W; Fi=V Wi hi^k/Σ(Wj hj^k), k=1 for T≤0.5 s, k=2 for T≥2.5 s, linear between; apply forces per eccentricity provisions.\n"
            "• Drift, §§5.5, 6.5, 9.3.3: ULS elastic ESM/MRSM deflections use NBC Rμ and applicable ESM kd; SLS remains elastic. Drift limits .025 ULS and .006 SLS. Do not use ASCE Cd/Ie amplification in the NBC workflow.\n"
            "• P-Delta: include geometric second-order effects. Run and converge both IS 16700:2023 §7.2(d) initial cases, 1.2DL+0.5IL±1.5EL/WL, as a REQUIRED project gate before the NBC equivalent-static earthquake analysis; they retain their IS source and are not represented as an NBC combination. NBC §3.6 seismic limit-state combinations still apply. Optional IS §7.3.10 screen: θ=PiΔi/(Vi hi-1 R)≤.20.\n\n"
            "GENERAL MECHANICS / NUMERICAL CHECKS — NOT NBC-SPECIFIC\n"
            "A=bh; rectangular Iy/Iz depend on the chosen local axes; G=E/[2(1+ν)] only under isotropic elasticity; eigenproblem (K−ω²M)φ=0; T=2π/ω; Rayleigh C=a0M+a1K. For rectangle torsion use Saint-Venant J, not Iy+Iz. Ec=4700√fc′ MPa is not an NBC 105 equation; prefer verified ETABS/material-standard values.\n"
            "Use global force equilibrium ΣR=ΣP and gravity load/mass reconciliation as model checks. Member hand identities require their stated supports/loading. Mode character in your asymmetric core must be read from shapes and participation, not mode number alone.\n\n"
            "PROJECT-SPECIFIC LIMITS\n"
            "Inspect the selected export's current load/mass and diaphragm audit; a historical blank-weight warning is not the status of a rebuilt export. Conventional-slab bending modifiers use the documented IS 16700 basis (0.25 ULS / 0.35 SLS); physical load/mass reconciliation, coupling-beam/opening/offset geometry and nonlinear material/device calibration still need project evidence. ULS-ineligible ESM can run as a labelled comparison after physical/P-Delta prerequisites. NLTHA retains the readiness checklist. See DECISIONS_AND_SOURCES_V133.md and REQUEST_COVERAGE_V133.md."
        )
        txt.insert("1.0",summary); txt.configure(state="disabled")
        bar=ttk.Frame(outer); bar.pack(fill="x",pady=(8,0))
        ttk.Button(bar,text="Open full formula/citation document",command=lambda: os.startfile(str(Path(__file__).resolve().with_name("NBC105_FORMULA_REFERENCE_V116.md")))).pack(side="left")
        ttk.Button(bar,text="Close",command=win.destroy).pack(side="right")

    def _open_result_interpretation(self):
        """Explain force conventions and show the live-model result export helpers."""
        win=tk.Toplevel(self.root); win.title("Part IV — Results Interpretation and Verification")
        win.geometry("1020x760"); win.minsize(820,600); win.transient(self.root)
        outer=ttk.Frame(win,padding=16); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="PART IV — INTERPRETATION AND VERIFICATION",font=("Segoe UI",15,"bold")).pack(anchor="w")
        body=(
            "GLOBAL VERSUS LOCAL ELEMENT FORCES\n"
            "ops.eleForce(tag) returns the element resisting-force vector in global axes. "
            "ops.eleResponse(tag, 'localForce') returns the element resisting-force vector in local axes. "
            "Both exclude inertial forces. Capture after the analysis case/step you intend to review; these are not automatically an envelope or a design check.\n\n"
            "For a 3D forceBeamColumn returning the standard 12-value localForce vector, the helper labels the entries in this order:\n"
            "[N_i, Vy_i, Vz_i, T_i, My_i, Mz_i, N_j, Vy_j, Vz_j, T_j, My_j, Mz_j].\n"
            "This mapping is applied only when the response has exactly 12 values. For links, trusses, walls, or other element types, the helper preserves raw indexed values instead of guessing their meaning. Check the element formulation and local-axis orientation before interpreting signs.\n\n"
            "ACTUAL MODEL EXPORT\n"
            "Import OpenSees_Result_Interpretation_V115.py from the same folder as your model script. Call write_element_force_snapshot(ops, [(elementTag, iNode, jNode), ...], outputFolder, case_name='gravity_or_case') immediately after each case. It writes JSON and CSV, with separate global/local vectors and named local end components when supported. The helper reads the live OpenSees model; it does not fabricate forces from the example values in the thesis text.\n\n"
            "MODE SHAPES\n"
            "Use write_modal_shape_snapshot after eigenanalysis, supplying floor-ordered node IDs and the relevant DOF (1=UX, 2=UY, 6=RZ in a 3D, six-DOF model). It exports raw and max-absolute-normalized eigenvector components for plotting. Normalization changes plot scale only. Confirm each mode's translational/torsional character from the shape and participation ratios; period ordering alone does not identify a mode.\n\n"
            "MODEL-SPECIFIC INTERPRETATION\n"
            "Overturning-induced axial redistribution, beam end-moment imbalance, torsion, and mode-shape patterns depend on the actual geometry, connectivity, stiffness, mass, supports, and load case. The numerical force examples supplied in the accompanying write-up are illustrative and are not treated as results from this ETABS model."
        )
        view=tk.Text(outer,wrap="word",font=("Segoe UI",10)); view.insert("1.0",body); view.configure(state="disabled"); view.pack(fill="both",expand=True,pady=10)
        bar=ttk.Frame(outer); bar.pack(fill="x")
        ttk.Button(bar,text="Open result helper source",command=lambda: os.startfile(os.path.join(os.path.dirname(__file__),"OpenSees_Result_Interpretation_V115.py"))).pack(side="left")
        ttk.Button(bar,text="Close",command=win.destroy).pack(side="right")

    def _open_project_progression(self):
        """Open the NBC/IS stability note and staged brace replacement workflow."""
        from tkinter import filedialog, messagebox
        from OpenSees_Project_Progression_V116 import write_case_matrix, write_readiness_checklist, write_stability_input_template, write_stability_report
        win=tk.Toplevel(self.root); win.title("Stability + Damped Outrigger Study Progression")
        win.geometry("1060x790"); win.minsize(860,620); win.transient(self.root)
        outer=ttk.Frame(win,padding=16); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="GOVERNING BASIS AND MODEL COMPLETENESS",font=("Segoe UI",15,"bold")).pack(anchor="w")
        body=(
            "STABILITY BASIS\n"
            "NBC 105:2025 requires P-Δ effects in structural, elastic time-history, and nonlinear time-history analysis (§7.3.9, §8.1.1.3, §9.3.1.3). Per this project basis, IS 16700:2023 §7.2(d) plus/minus initial P-Delta combinations must converge before the NBC ESM run; the ESM runner validates an explicit four-case X/Y result map with audit paths from the model builder. IS §7.3.10 provides the separate θᵢ = PᵢΔᵢ/(Vᵢ hᵢ₋₁ R) ≤ 0.20 stability screen within its tall-building scope (>50 m and ≤250 m). Enter reviewed quantities; the program does not infer missing loads or results.\n\n"
            "MODEL PROGRESSION — RUN EACH CASE ON A CLONED, FROZEN BASELINE\n"
            "1. Reconcile ETABS object/node/section crosswalks and units; preserve the asymmetric plan and actual mass/stiffness eccentricity.\n"
            "2. Convert and verify RC beams/columns, the central core wall piers around each opening plus coupling/spandrel beams, conventional slab openings and diaphragm groups. Provide rational/ETABS conventional-slab effective stiffness; do not use the NBC flat-slab modifier. Use rigid diaphragm constraints only if in-plane stiffness and opening layout justify that idealization.\n"
            "3. Close gravity, seismic mass, self-weight, area-load transfer, support and foundation assumptions; verify reactions, modal periods/mass, floor drifts, torsion and P-Δ.\n"
            "4. Establish C0 baseline with all outrigger, belt-truss and cap-truss members as the mapped SHS system.\n"
            "5. Run C1 partial FVD replacement, then C2 all eligible FVD; return to baseline before C3 partial BRB, C4 all eligible BRB, and C5 selected mixed FVD+BRB+retained SHS. Do not progressively mutate a previous case.\n"
            "6. For every scenario, regenerate the model from the same audited ETABS base; update section/device assignments, gravity and mass ledgers; repeat modal analysis, NBC record scaling and both direction permutations, then nonlinear response-history runs and identical response extraction. FVD/BRB parameters, connection/arm stiffness, stroke/capacity, hysteresis, and damping assumptions require traceable test/manufacturer/literature sources.\n\n"
            "CURRENT CONVERTER COVERAGE\n"
            "V116 adds an ETABS area-stage integration call for floor ShellMITC4 panels and nonlinear E-SFI-MVLEM_3D wall panels, plus a separate NBC 105 nonlinear paired-record runner with a strict readiness manifest. It consumes the exported four-node area mesh without filling missing wall panels. Area loads/mass, coupling-beam classification, project FSAM calibration, full mass reconciliation, and device-specific FVD/BRB placement still require review and explicit inputs; the model must not be reported as run-ready until every readiness gate is evidenced. The separate linear time-history tool remains for elastic checks only."
        )
        view=tk.Text(outer,wrap="word",font=("Segoe UI",10)); view.insert("1.0",body); view.configure(state="disabled"); view.pack(fill="both",expand=True,pady=10)
        bar=ttk.Frame(outer); bar.pack(fill="x")
        def make_templates():
            baseline=filedialog.askopenfilename(parent=win,title="Select frozen ETABS database or reviewed OpenSees model-builder script",filetypes=[("ETABS / Python model", "*.edb *.py"),("All files", "*.*")])
            if not baseline: return
            folder=filedialog.askdirectory(parent=win,title="Select study output folder")
            if not folder: return
            import os
            matrix=write_case_matrix(os.path.join(folder,"Damped_Outrigger_Case_Matrix.csv"), base_model_path=baseline, results_root=os.path.join(folder,"cases"))
            stability=write_stability_input_template(os.path.join(folder,"Stability_Input_Template.csv"))
            readiness=write_readiness_checklist(os.path.join(folder,"OpenSees_Model_Readiness_Checklist_V116.md"),"markdown")
            messagebox.showinfo("Templates written",f"Case matrix:\n{matrix}\n\nStability input:\n{stability}\n\nReadiness checklist:\n{readiness}",parent=win)
        def evaluate_stability():
            source=filedialog.askopenfilename(parent=win,title="Select completed stability input CSV",filetypes=[("CSV files","*.csv")])
            if not source: return
            import os
            from tkinter import simpledialog
            height=simpledialog.askstring("Building height","Building height H in metres (used only to report IS 16700 scope):",parent=win)
            target=filedialog.asksaveasfilename(parent=win,title="Save stability report",defaultextension=".csv",initialfile="Stability_IS16700_Supplemental_Report.csv",filetypes=[("CSV files","*.csv")])
            if not target: return
            try:
                result=write_stability_report(source,target,height)
                messagebox.showinfo("Supplemental stability report",result["governing_basis_note"]+"\n\n"+result["scope_note"]+f"\n\nRows: {result['rows']}\nReport: {result['report_csv']}",parent=win)
            except Exception as exc:
                messagebox.showerror("Could not calculate stability check",str(exc),parent=win)
        ttk.Button(bar,text="Create case matrix + stability input template",command=make_templates).pack(side="left")
        ttk.Button(bar,text="Evaluate supplemental IS 16700 θ CSV",command=evaluate_stability).pack(side="left",padx=8)
        ttk.Button(bar,text="Open cited references",command=lambda: os.startfile(os.path.join(os.path.dirname(__file__),"REFERENCES_AND_LEARNING_RESOURCES_V116.md"))).pack(side="left",padx=8)
        ttk.Button(bar,text="Close",command=win.destroy).pack(side="right")
    def _open_fvd_brb_guide(self):
        from OpenSees_Results_UI_V127 import device_guide
        return device_guide(self.root,self.out.get())

    def _open_nonlinear_readiness(self):
        """Show explicit prerequisites; this window does not falsely enable analysis."""
        win=tk.Toplevel(self.root)
        win.title("Nonlinear Analysis Readiness — Calibration Gate")
        win.geometry("850x600"); win.minsize(700,480); win.transient(self.root)
        outer=ttk.Frame(win,padding=18); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="NONLINEAR ANALYSIS: BLOCKED PENDING VALIDATION",font=("Segoe UI",15,"bold")).pack(anchor="w")
        ttk.Label(outer,text="The program deliberately does not run nonlinear analysis from incomplete or uncalibrated section templates.",wraplength=800).pack(anchor="w",pady=(5,12))
        checks=[
            "Complete fiber-section geometry and material parameters for every nonlinear frame section.",
            "Enter reinforcing-bar coordinates, bar areas, and steel-material assignments from verified drawings / ETABS data.",
            "Check cover/core boundaries, patch overlap, bar placement, section tags, material tags, and consistent kN–m units.",
            "Calibrate concrete and steel constitutive parameters against a cited experimental or otherwise justified reference.",
            "Validate section response (at minimum axial force–moment behavior and expected strength/stiffness) before mapping to members.",
            "Review ETABS-to-OpenSeesPy mapping compatibility; do not map an RC fiber section to an SHS or incompatible member.",
            "Run and record both IS 16700:2023 §7.2(d) initial P-Delta cases (1.2DL+0.5IL±1.5EL/WL) before NBC ESM; use the required conventional-slab stiffness input rather than a flat-slab factor.",
            "Complete geometry/load/mass checks: verify every core opening, wall pier, spandrel/coupling beam, floor opening, diaphragm constraint, ETABS story weight, area/frame load, and no-double-counted self-weight.",
            "Only then implement and verify element formulations, gravity preload, modal checks, FVD/BRB case assignments, and nonlinear analysis controls. The NLTHA readiness manifest checks these items."
        ]
        for item in checks:
            row=ttk.Frame(outer); row.pack(fill="x",anchor="w",pady=5)
            ttk.Label(row,text="☐",font=("Segoe UI",12,"bold")).pack(side="left",anchor="n",padx=(0,8))
            ttk.Label(row,text=item,wraplength=760,justify="left").pack(side="left",fill="x",expand=True)
        ttk.Separator(outer).pack(fill="x",pady=12)
        ttk.Label(outer,text="Generated audit templates are written to the selected output folder: OpenSees_Nonlinear_Fiber_Section_Input_Template.csv and OpenSees_Nonlinear_Reinforcing_Bar_Coordinates_Template.csv. Completing these files alone does not prove calibration; review evidence and checks are required.",wraplength=800).pack(anchor="w")
        ttk.Button(outer,text="Close",command=win.destroy).pack(anchor="e",pady=(12,0))

    def _open_material_values(self):
        from OpenSees_Results_UI_V127 import library_window
        return library_window(self.root,self.out.get())

    def _open_nbc105_esm(self):
        """Launch the separate NBC ESM input/calculation GUI."""
        gui_path=Path(__file__).resolve().with_name("OpenSees_Earthquake_Analysis_NBC105_V111.py")
        if not gui_path.is_file():
            messagebox.showerror("NBC ESM GUI missing",f"Keep {gui_path.name} beside the main program.")
            return
        try:
            # Pass the converter output folder so the GUI opens the matching ETABS exports.
            subprocess.Popen([sys.executable,str(gui_path),self.out.get().strip()],cwd=str(gui_path.parent), env={**dict(__import__('os').environ),'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
        except Exception as exc:
            messagebox.showerror("Could not open NBC ESM GUI",str(exc))

    def _open_gravity_analysis(self):
        """Open the gravity-analysis runner and reporting GUI."""
        gui_path=Path(__file__).resolve().with_name("OpenSees_Gravity_GUI_V110.py")
        if not gui_path.exists():
            messagebox.showerror("Gravity GUI missing",f"Keep OpenSees_Gravity_GUI_V110.py beside this program.\n\n{gui_path}")
            return
        try:
            spec=importlib.util.spec_from_file_location("opensees_gravity_gui",gui_path)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            from OpenSees_Complete_Export_V118 import autoselect_inputs
            autoselect_inputs(module.launch(self.root), self.out.get(), 'gravity_model_script')
        except Exception as exc:
            messagebox.showerror("Could not open gravity GUI",str(exc),parent=self.root)

    def _open_modal_audit(self):
        """Open the NBC 105:2025 modal mass / eigenperiod audit GUI."""
        gui_path=Path(__file__).resolve().with_name("OpenSees_Modal_GUI_NBC105_V111.py")
        if not gui_path.is_file():
            messagebox.showerror("Modal audit GUI missing",f"Keep {gui_path.name} beside this program.")
            return
        try:
            spec=importlib.util.spec_from_file_location("opensees_modal_gui_nbc105",gui_path)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            from OpenSees_Complete_Export_V118 import autoselect_inputs
            gui=module.ModalAuditGUI(self.root)
            autoselect_inputs(gui, self.out.get(), 'modal_model_script'); gui.run()
        except Exception as exc:
            messagebox.showerror("Could not open modal audit GUI",str(exc),parent=self.root)

    def _open_linear_time_history(self):
        """Open the separate NBC 105:2025 elastic time-history workflow."""
        gui_path=Path(__file__).resolve().with_name("OpenSees_Linear_Time_History_NBC105_V115.py")
        if not gui_path.is_file():
            messagebox.showerror("Linear time-history GUI missing",f"Keep {gui_path.name} beside this program.",parent=self.root)
            return
        try:
            spec=importlib.util.spec_from_file_location("opensees_linear_time_history_nbc105",gui_path)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            from OpenSees_Complete_Export_V118 import autoselect_inputs
            gui=module.LinearTimeHistoryGUI(self.root)
            autoselect_inputs(gui, self.out.get(), 'linear_model_script'); gui.run()
        except Exception as exc:
            messagebox.showerror("Could not open linear time-history GUI",str(exc),parent=self.root)

    def _open_nonlinear_time_history(self):
        """Open V116 nonlinear paired-record runner, separate from the linear tool."""
        gui_path=Path(__file__).resolve().with_name("OpenSees_Nonlinear_Time_History_NBC105_V116.py")
        if not gui_path.is_file():
            messagebox.showerror("Nonlinear time-history GUI missing",f"Keep {gui_path.name} beside this program.",parent=self.root); return
        try:
            spec=importlib.util.spec_from_file_location("opensees_nonlinear_time_history_nbc105_v116",gui_path)
            module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            from OpenSees_Complete_Export_V118 import autoselect_inputs
            autoselect_inputs(module.launch_nonlinear_time_history_gui(self.root), self.out.get(), 'nonlinear_model_script')
        except Exception as exc:
            messagebox.showerror("Could not open nonlinear time-history GUI",str(exc),parent=self.root)

    def _open_area_integration(self):
        """Open the area-element stage that consumes the exported ETABS quad mesh."""
        gui_path=Path(__file__).resolve().with_name("OpenSees_Area_Element_Integration_V116.py")
        if not gui_path.is_file():
            messagebox.showerror("Area integration GUI missing",f"Keep {gui_path.name} beside this program.",parent=self.root); return
        try:
            spec=importlib.util.spec_from_file_location("opensees_area_element_integration_v116",gui_path)
            module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            module.launch_area_integration_gui(self.root, export_dir=self.out.get())
        except Exception as exc:
            messagebox.showerror("Could not open area integration GUI",str(exc),parent=self.root)

    def _open_nbc105_settings(self):
        """Display the code-based analysis factors and user-specified mass source."""
        win=tk.Toplevel(self.root); win.title("NBC 105:2025 — Load Combinations, Stiffness Modifiers, Mass Source")
        win.geometry("1250x780"); win.minsize(950,600); win.transient(self.root)
        outer=ttk.Frame(win,padding=14); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="NBC 105:2025 ANALYSIS SETTINGS",font=("Segoe UI",15,"bold")).pack(anchor="w")
        ttk.Label(outer,text="Design basis: NBC 105:2025 Limit State Method only. Sources: §3.4 Table 3-1 (ultimate/serviceability effective stiffness); §3.6.1 (parallel combinations and λ); §3.6.2 (non-parallel directional combinations). WSM §3.7 combinations are excluded. Mass-source factors follow your stated requirement.",wraplength=1200).pack(anchor="w",pady=(5,10))
        columns=("category","item","ultimate","serviceability","notes")
        tv=ttk.Treeview(outer,columns=columns,show="headings",height=24)
        for col,title,width in [("category","Category",165),("item","Setting / combination",360),("ultimate","ULS combination / factor",180),("serviceability","SLS combination / factor",180),("notes","Interpretation",340)]:
            tv.heading(col,text=title); tv.column(col,width=width,anchor="w",stretch=(col=="notes"))
        tv.pack(fill="both",expand=True)
        settings_path=Path(__file__).resolve().with_name("NBC105_Analysis_Settings_V108.py")
        try:
            spec=importlib.util.spec_from_file_location("nbc105_analysis_settings",settings_path)
            mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            tv.insert("","end",values=("Design method",mod.DESIGN_METHOD,"NBC §§3.4, 3.6","SLS checks retained","NBC §3.7 WSM combinations are not included in this project workflow."))
            stack=mod.OPENSEES_ANALYSIS_STACK
            tv.insert("","end",values=("Analysis stack","Constraints / numberer / system",stack["constraints"],stack["numberer"],stack["system"]))
            tv.insert("","end",values=("Analysis mode",stack["primary_mode"],", ".join(stack["mode_choices"]),"NLTHA focus","Mode selects the solver setup; it does not replace nonlinear materials with elastic materials."))
            tv.insert("","end",values=("Nonlinear algorithms",", ".join(stack["nonlinear_algorithm_choices"]),"Newton default","NLTHA","Use alternatives only after checking the convergence cause."))
            for name,description in stack["optional_systems"].items():
                tv.insert("","end",values=("Optional system",name,"—","—",description))
            for stage_key,stage_name in [("nonlinear_static","Nonlinear gravity/static"),("nonlinear_transient","Nonlinear NLTHA")]:
                stage=stack[stage_key]
                tv.insert("","end",values=("Analysis stack",stage_name,f'{stage["algorithm"]} + {stage["integrator"]}',stage["analysis"],f'{stage["test"]} tol={stage["tolerance"]:g}, maxIter={stage["max_iterations"]}'))
            tv.insert("","end",values=("Analysis stack","Elastic check only",stack["elastic_check_only"]["algorithm"],"Static","Never use the Linear algorithm for nonlinear fiber response."))
            for label,values in mod.CRACKED_STIFFNESS_MODIFIERS.items():
                if isinstance(values,dict):
                    tv.insert("","end",values=("NBC stiffness reference",label,values.get("ultimate"),values.get("serviceability"),"NBC 105:2025 Table 3-1; elastic reference only, not applied to nonlinear fiber/FSAM materials."))
                else:
                    tv.insert("","end",values=("NBC stiffness reference",label,values,"—","Beam torsion only for compatibility torsion; otherwise retain gross J"))
            tv.insert("","end",values=("NBC stiffness reference","Flat slab only",0.25,0.50,"NBC 105:2025 Table 3-1 ULS / SLS; not applicable to this conventional slab."))
            tv.insert("","end",values=("Project slab stiffness","Conventional RC slab",0.25,0.35,"Project-adopted IS 16700:2023 Table 5; strength / serviceability flexural Ig. Axial/membrane area remains gross; NBC flat-slab row is not used."))
            tv.insert("","end",values=("REQUIRED project initial P-Delta","EL/WL positive", "1.2 DL + 0.5 IL + 1.5 EL/WL","—","IS 16700:2023 §7.2(d); must converge before the NBC ESM runner."))
            tv.insert("","end",values=("REQUIRED project initial P-Delta","EL/WL negative", "1.2 DL + 0.5 IL − 1.5 EL/WL","—","Run applicable X/Y and wind directions/signs; log completed results."))
            for title,items in [("NBC LSM / strength + seismic",mod.PARALLEL_SYSTEM_COMBINATIONS),("NBC LSM / non-parallel",mod.NONPARALLEL_SYSTEM_COMBINATIONS)]:
                for item in items: tv.insert("","end",values=(title,item["name"],item["expression"],item["expression"],"Same NBC §3.6 combination form for ULS and SLS; use the state-specific seismic action/coefficient. λ depends on occupancy."))
            tv.insert("","end",values=("NBC gravity factors","LSM-01 gravity","1.2 DL + 1.5 LL","1.2 DL + 1.5 LL","NBC 105:2025 §3.6.1; same displayed combination form; apply factors to combinations, not source loads."))
            tv.insert("","end",values=("Load handling","Source patterns","Unfactored","—","Preserve separate ETABS DL/LL patterns; avoid duplicated self-weight."))
            for key,value in mod.LOAD_ACCOUNTING_COVERAGE.items():
                tv.insert("","end",values=("Load coverage",key,value,"—","Current exporter coverage / required review"))
            tv.insert("","end",values=("Combination factors","λ for storage facilities",mod.LIVE_LOAD_FACTORS["storage_facilities"],"—","Use with live load in seismic combinations"))
            tv.insert("","end",values=("Combination factors","λ for other occupancy",mod.LIVE_LOAD_FACTORS["other_occupancy"],"—","Use with live load in seismic combinations"))
            for key,value in [("Dead load factor",mod.EARTHQUAKE_MASS_SOURCE["dead_load_factor"]),("Storage live factor",mod.EARTHQUAKE_MASS_SOURCE["storage_live_factor"]),("Other live factor",mod.EARTHQUAKE_MASS_SOURCE["other_live_factor"]),("Roof live factor",mod.EARTHQUAKE_MASS_SOURCE["roof_live_factor"])]:
                tv.insert("","end",values=("Earthquake mass source",key,value,"—","Roof live excluded" if key=="Roof live factor" else "User-specified seismic mass coefficient"))
            for key in ("dead_pattern_names","storage_pattern_names","other_live_pattern_names","roof_live_pattern_names"):
                tv.insert("","end",values=("ETABS pattern matching",key,", ".join(mod.EARTHQUAKE_MASS_SOURCE[key]),"—","Edit names in NBC105_Analysis_Settings_V108.py to match the ETABS model"))
        except Exception as exc:
            tv.insert("","end",values=("ERROR",str(exc),"—","—",str(settings_path)))
        ttk.Label(outer,text="LSM only: NBC §3.7 WSM combinations are excluded. NBC §3.6 combinations govern seismic design. NBC Table 3-1 flat-slab values apply only to flat slabs; your conventional slab needs documented rational cracked stiffness or verified ETABS stiffness. IS 16700:2023 §7.2(d) plus/minus initial P-Delta cases are a REQUIRED project precondition before NBC ESM (the runner validates four X/Y case records and audit paths). §7.3.10 is a separate stability screen. The initial static P-Delta check is distinct from the sustained gravity preload retained for time history. This viewer does not solve the initial cases or alter ETABS shell properties.",wraplength=1200,foreground="#8a3412").pack(anchor="w",pady=(8,8))
        ttk.Button(outer,text="Close",command=win.destroy).pack(anchor="e")

    def _row(self,parent,label,var,cmd):
        row=ttk.Frame(parent,style="Card.TFrame"); row.pack(fill="x",pady=5)
        ttk.Label(row,text=label,width=22,background="#ffffff").pack(side="left")
        ttk.Entry(row,textvariable=var).pack(side="left",fill="x",expand=True,padx=8)
        ttk.Button(row,text="Browse…",command=cmd).pack(side="left")
    def _open_column_section_review(self):
        """Geometry-only section reviewer integrated into the main application GUI."""
        win=tk.Toplevel(self.root); win.title("RC Column Section Size Review — Perimeter Bars"); win.geometry("980x700"); win.transient(self.root)
        outer=ttk.Frame(win,padding=14); outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="REINFORCED CONCRETE COLUMN — PERIMETER BAR LAYOUT",font=("Segoe UI",15,"bold")).pack(anchor="w")
        ttk.Label(outer,text="Column reinforcement is currently perimeter-only. No interior bars are placed. The bar count depends on the number of positions per side.",wraplength=900).pack(anchor="w",pady=(4,10))
        body=ttk.Frame(outer); body.pack(fill="both",expand=True)
        controls=ttk.Frame(body,padding=4); controls.pack(side="left",fill="y")
        drawing=ttk.Frame(body); drawing.pack(side="left",fill="both",expand=True,padx=(12,0))
        defaults=[("Section width (mm)","1100"),("Section depth (mm)","1100"),("Clear cover to tie (mm)","40"),("Tie diameter (mm)","12"),("Longitudinal bar diameter (mm)","25"),("Bars per side (including corners)","5")]
        vars_={}
        for label,value in defaults:
            ttk.Label(controls,text=label).pack(anchor="w",pady=(5,1)); v=tk.StringVar(value=value); vars_[label]=v; ttk.Entry(controls,textvariable=v,width=18).pack(anchor="w")
        summary=tk.StringVar(value="")
        ttk.Label(controls,textvariable=summary,justify="left",wraplength=250).pack(anchor="w",pady=12)
        canvas=tk.Canvas(drawing,bg="#111827",highlightthickness=0); canvas.pack(fill="both",expand=True)
        def redraw(_event=None):
            canvas.delete("all")
            try:
                w=float(vars_["Section width (mm)"].get()); d=float(vars_["Section depth (mm)"].get()); c=float(vars_["Clear cover to tie (mm)"].get()); tie=float(vars_["Tie diameter (mm)"].get()); bar=float(vars_["Longitudinal bar diameter (mm)"].get()); n=int(vars_["Bars per side (including corners)"].get())
                if min(w,d,c,tie,bar)<=0 or n<2 or 2*(c+tie+bar/2)>=min(w,d): raise ValueError("Dimensions invalid or reinforcement does not fit.")
                spacing_x=(w-2*(c+tie+bar/2))/(n-1); spacing_y=(d-2*(c+tie+bar/2))/(n-1)
                summary.set(f"Perimeter bars: {4*n-4}\nBars per side: {n} (including corners)\nInterior bars: 0\nSpacing X: {spacing_x:.2f} mm\nSpacing Y: {spacing_y:.2f} mm\nBar centre offset: {c+tie+bar/2:.2f} mm")
                cw=max(canvas.winfo_width(),450); ch=max(canvas.winfo_height(),400); margin=65; scale=min((cw-2*margin)/w,(ch-2*margin)/d); ww=w*scale; hh=d*scale; x0=(cw-ww)/2; y0=(ch-hh)/2; x1=x0+ww; y1=y0+hh
                canvas.create_rectangle(x0,y0,x1,y1,outline="white",width=3)
                inset=(c+tie/2)*scale
                canvas.create_rectangle(x0+inset,y0+inset,x1-inset,y1-inset,outline="#22c55e",width=2)
                off=c+tie+bar/2
                coords=[]
                # Perimeter-only bars: top/bottom rows plus side bars excluding duplicate corners.
                for ix in range(n):
                    x=off+ix*spacing_x
                    coords.extend([(x,off),(x,d-off)])
                for iy in range(1,n-1):
                    y=off+iy*spacing_y
                    coords.extend([(off,y),(w-off,y)])
                for bx,by in coords:
                    x=x0+bx*scale; y=y1-by*scale
                    r=max(3,bar*scale/2); canvas.create_oval(x-r,y-r,x+r,y+r,fill="#ef4444",outline="white",width=1)
                canvas.create_text(cw/2,22,text=f"{w:g} × {d:g} mm  |  {len(coords)} perimeter bars (0 interior)",fill="white",font=("Segoe UI",12,"bold"))
                canvas.create_text(cw/2,ch-22,text=f"Ø{bar:g} longitudinal bars  •  Ø{tie:g} ties  •  cover {c:g} mm",fill="#d1d5db",font=("Segoe UI",10))
            except Exception as exc:
                summary.set("Check inputs.\n"+str(exc)); canvas.create_text(20,25,anchor="nw",text="Invalid section parameters",fill="#fca5a5")
        for v in vars_.values(): v.trace_add("write",lambda *_: redraw())
        canvas.bind("<Configure>",redraw)
        def export():
            try:
                w=float(vars_["Section width (mm)"].get()); d=float(vars_["Section depth (mm)"].get()); c=float(vars_["Clear cover to tie (mm)"].get()); tie=float(vars_["Tie diameter (mm)"].get()); bar=float(vars_["Longitudinal bar diameter (mm)"].get()); n=int(vars_["Bars per side (including corners)"].get())
                spacing_x=(w-2*(c+tie+bar/2))/(n-1); spacing_y=(d-2*(c+tie+bar/2))/(n-1)
                if min(w,d,c,tie,bar,spacing_x,spacing_y)<=0 or n<2: raise ValueError("Invalid dimensions")
                data={"section_width_mm":w,"section_depth_mm":d,"clear_cover_to_tie_mm":c,"tie_diameter_mm":tie,"longitudinal_bar_diameter_mm":bar,"bars_per_side":n,"longitudinal_bar_count":4*n-4,"interior_bar_count":0,"bar_layout":"perimeter only; no interior bars","bar_spacing_x_mm":spacing_x,"bar_spacing_y_mm":spacing_y,"bar_centre_offset_mm":c+tie+bar/2,"scope":"geometry only; not a code compliance check"}
                path=filedialog.asksaveasfilename(parent=win,title="Export column section geometry",defaultextension=".json",initialfile="RC_Column_Section_Geometry.json",filetypes=[("JSON","*.json"),("CSV","*.csv")])
                if not path:return
                if path.lower().endswith(".csv"):
                    with open(path,"w",newline="",encoding="utf-8-sig") as f:
                        wr=csv.writer(f); wr.writerow(["parameter","value"]); wr.writerows(data.items())
                else: Path(path).write_text(json.dumps(data,indent=2),encoding="utf-8")
                messagebox.showinfo("Export complete",f"Section geometry exported to:\n{path}",parent=win)
            except Exception as exc: messagebox.showerror("Export failed",str(exc),parent=win)
        btns=ttk.Frame(controls); btns.pack(anchor="w",pady=8); ttk.Button(btns,text="Refresh drawing",command=redraw).pack(fill="x",pady=3); ttk.Button(btns,text="Export JSON/CSV",command=export).pack(fill="x",pady=3); ttk.Label(controls,text="Red dots = perimeter longitudinal bars only\nGreen outline = tie centreline (schematic)",wraplength=240).pack(anchor="w",pady=8)
        redraw()
    def _open_fiber_section_builder(self):
        """GUI for rectangular RC fiber sections: perimeter-only columns and perimeter beam, Concrete01 plus Steel02/SteelMPF."""
        win=tk.Toplevel(self.root); win.title("RC Fiber Section Builder — Concrete01 + Steel02 / SteelMPF"); win.geometry("1180x820"); win.transient(self.root)
        outer=ttk.Frame(win,padding=12); outer.pack(fill="both",expand=True)
        from OpenSees_Mapping_GUI_V125 import show_parameter_sources
        ttk.Button(outer,text='Parameter values, calibration status and citations',command=lambda:show_parameter_sources(win)).pack(anchor='w')
        ttk.Label(outer,text="RC BEAM / COLUMN FIBER SECTION — COLUMN / BEAM PERIMETER BARS",font=("Segoe UI",15,"bold")).pack(anchor="w")
        ttk.Label(outer,text="Presets: Beam 600×800 mm; Column 1100×1100 mm; Column 1250×1250 mm. RC values are existing illustrative M35/Fe550 templates, not calibrated values for the source M45 model. Open parameter citations before adopting them. Units in generated source: kN, m. Exports a section definition only.",wraplength=1100).pack(anchor="w",pady=(4,10))
        body=ttk.Frame(outer); body.pack(fill="both",expand=True)
        left=ttk.Frame(body,padding=4); left.pack(side="left",fill="y")
        right=ttk.Frame(body); right.pack(side="left",fill="both",expand=True,padx=(12,0))
        preset_row=ttk.Frame(left); preset_row.pack(fill="x",pady=(0,6))
        ttk.Label(preset_row,text="Section preset",width=29).pack(side="left")
        preset=tk.StringVar(value="Column 1100×1100")
        preset_box=ttk.Combobox(preset_row,textvariable=preset,state="readonly",width=20,values=["Beam 600×800","Column 1100×1100","Column 1250×1250"])
        preset_box.pack(side="left",padx=(4,0))
        defaults=[
            ("Section width (mm)","1100"),("Section depth (mm)","1100"),("Clear cover to tie (mm)","40"),("Tie diameter (mm)","12"),("Longitudinal bar diameter (mm)","25"),("Bars per side incl. corners","5"),
            ("Concrete f'c (MPa, positive)","35"),("Cover residual fcu (MPa, positive)","0"),("Core f'cc (MPa, positive)","44.1"),("Core residual fpcu (MPa, positive)","8.8"),
            ("Cover epsc0 (negative)","-0.002"),("Cover epsU (negative)","-0.005"),("Core epsc0 (negative)","-0.0046"),("Core epsU (negative)","-0.015"),
            ("Steel fy (MPa)","550"),("Steel E (MPa)","200000"),("RCC unit weight (kN/m³)","25.0"),("Steel hardening ratio b","0.01"),("Steel02 R0","20"),("Steel02 cR1","0.925"),("Steel02 cR2","0.15"),
            ("Cover fibers per side","8"),("Core fibers per side","16"),("Section tag","621"),("Cover material tag","622"),("Core material tag","623"),("Steel material tag","624")]
        steel_model=tk.StringVar(value="Steel02")
        steel_row=ttk.Frame(left); steel_row.pack(fill="x",pady=(0,5))
        ttk.Label(steel_row,text="Longitudinal steel model",width=29).pack(side="left")
        steel_box=ttk.Combobox(steel_row,textvariable=steel_model,state="readonly",width=18,values=["Steel02","SteelMPF"]); steel_box.pack(side="left",padx=(4,0))
        vars_={}
        for label,val in defaults:
            row=ttk.Frame(left); row.pack(fill="x",pady=1)
            ttk.Label(row,text=label,width=29).pack(side="left")
            v=tk.StringVar(value=val); vars_[label]=v; ttk.Entry(row,textvariable=v,width=10).pack(side="left",padx=(4,0))
        def apply_preset(_event=None):
            name=preset.get()
            values={
                "Beam 600×800": {"Section width (mm)":"600","Section depth (mm)":"800","Clear cover to tie (mm)":"25","Tie diameter (mm)":"12","Longitudinal bar diameter (mm)":"16","Bars per side incl. corners":"4","Section tag":"611","Cover material tag":"612","Core material tag":"613","Steel material tag":"614","Concrete f'c (MPa, positive)":"35","Cover residual fcu (MPa, positive)":"0","Core f'cc (MPa, positive)":"44.1","Core residual fpcu (MPa, positive)":"8.8","Cover epsc0 (negative)":"-0.002","Cover epsU (negative)":"-0.005","Core epsc0 (negative)":"-0.0046","Core epsU (negative)":"-0.015","Steel fy (MPa)":"550"},
                "Column 1100×1100": {"Section width (mm)":"1100","Section depth (mm)":"1100","Clear cover to tie (mm)":"40","Tie diameter (mm)":"12","Longitudinal bar diameter (mm)":"25","Bars per side incl. corners":"5","Section tag":"621","Cover material tag":"622","Core material tag":"623","Steel material tag":"624","Concrete f'c (MPa, positive)":"35","Cover residual fcu (MPa, positive)":"0","Core f'cc (MPa, positive)":"44.1","Core residual fpcu (MPa, positive)":"8.8","Cover epsc0 (negative)":"-0.002","Cover epsU (negative)":"-0.005","Core epsc0 (negative)":"-0.0046","Core epsU (negative)":"-0.015","Steel fy (MPa)":"550"},
                "Column 1250×1250": {"Section width (mm)":"1250","Section depth (mm)":"1250","Clear cover to tie (mm)":"40","Tie diameter (mm)":"12","Longitudinal bar diameter (mm)":"25","Bars per side incl. corners":"5","Section tag":"631","Cover material tag":"632","Core material tag":"633","Steel material tag":"634","Concrete f'c (MPa, positive)":"35","Cover residual fcu (MPa, positive)":"0","Core f'cc (MPa, positive)":"44.1","Core residual fpcu (MPa, positive)":"8.8","Cover epsc0 (negative)":"-0.002","Cover epsU (negative)":"-0.005","Core epsc0 (negative)":"-0.0046","Core epsU (negative)":"-0.015","Steel fy (MPa)":"550"}}
            for key,value in values[name].items(): vars_[key].set(value)
        preset_box.bind("<<ComboboxSelected>>",apply_preset)
        apply_preset()  # synchronize displayed values with the selected preset on startup
        section_module_path = Path(__file__).resolve().parent / "components" / "sections" / "definitions.py"
        if not section_module_path.is_file():
            section_module_path = Path(__file__).resolve().parent / "OpenSees_Runtime_V118" / "components" / "sections" / "definitions.py"
        preset_to_config = {"Beam 600×800":"RC_BEAM_600x800_FIBER", "Column 1100×1100":"RC_COLUMN_1100x1100_FIBER", "Column 1250×1250":"RC_COLUMN_1250x1250_FIBER"}
        gui_to_config = {
            "Section width (mm)":"width_mm", "Section depth (mm)":"depth_mm", "Clear cover to tie (mm)":"cover_mm",
            "Tie diameter (mm)":"tie_diameter_mm", "Longitudinal bar diameter (mm)":"bar_diameter_mm",
            "Bars per side incl. corners":"bars_per_side", "Concrete f'c (MPa, positive)":"cover_fc_mpa",
            "Cover residual fcu (MPa, positive)":"cover_fcu_mpa", "Core f'cc (MPa, positive)":"core_fcc_mpa",
            "Core residual fpcu (MPa, positive)":"core_fpcu_mpa", "Cover epsc0 (negative)":"cover_epsc0",
            "Cover epsU (negative)":"cover_epsU", "Core epsc0 (negative)":"core_epsc0", "Core epsU (negative)":"core_epsU",
            "Steel fy (MPa)":"fy_rebar_mpa", "Steel E (MPa)":"E0_mpa", "RCC unit weight (kN/m³)":"unit_weight_kN_m3", "Steel hardening ratio b":"steel_b",
            "Steel02 R0":"steel_R0", "Steel02 cR1":"steel_cR1", "Steel02 cR2":"steel_cR2",
            "Cover fibers per side":"cover_fibers", "Core fibers per side":"core_fibers",
            "Section tag":"section_tag", "Cover material tag":"cover_tag", "Core material tag":"core_tag", "Steel material tag":"rebar_tag",
        }
        def read_define_section_config():
            tree=ast.parse(section_module_path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="RC_SECTION_CONFIG" for t in node.targets):
                    value=ast.literal_eval(node.value)
                    if isinstance(value,dict): return value
            raise ValueError("RC_SECTION_CONFIG was not found as a literal in Define_Section_V109.py")
        preset_box.bind("<<ComboboxSelected>>", lambda _event: (apply_preset(), refresh_from_define_section()))
        def refresh_from_define_section():
            try:
                key=preset_to_config[preset.get()]
                cfg=read_define_section_config()[key]
                for label,cfg_key in gui_to_config.items():
                    if cfg_key in cfg: vars_[label].set(str(cfg[cfg_key]))
                redraw()
                status.set(f"Loaded {preset.get()} values from Define_Section_V109.py. Review the fields, then commit if desired.")
            except Exception as exc:
                messagebox.showerror("Could not refresh from Define_Section_V109.py",str(exc),parent=win)
        def commit_to_define_section():
            try:
                q=get_data(); key=preset_to_config[preset.get()]
                config=read_define_section_config()
                record={cfg_key: (int(q[label]) if label in {"Bars per side incl. corners","Cover fibers per side","Core fibers per side","Section tag","Cover material tag","Core material tag","Steel material tag"} else float(q[label])) for label,cfg_key in gui_to_config.items() if label in q}
                # q uses compact names; construct the persisted record explicitly.
                record={
                    "width_mm":q["w"],"depth_mm":q["d"],"cover_mm":q["c"],"tie_diameter_mm":q["tie"],"bar_diameter_mm":q["db"],"bars_per_side":q["n"],
                    "section_tag":q["sec"],"cover_tag":q["coverTag"],"core_tag":q["coreTag"],"rebar_tag":q["steelTag"],
                    "cover_fc_mpa":q["fc"],"cover_epsc0":q["epsc0"],"cover_fcu_mpa":q["fcu_cover"],"cover_epsU":q["epsU"],
                    "core_fcc_mpa":q["fcc"],"core_epsc0":q["epsc0_core"],"core_fpcu_mpa":q["fpcu"],"core_epsU":q["epsU_core"],
                    "fy_rebar_mpa":q["fy"],"E0_mpa":q["Es"],"unit_weight_kN_m3":q["unit_weight_kN_m3"],"steel_b":q["b"],"steel_R0":q["R0"],"steel_cR1":q["cR1"],"steel_cR2":q["cR2"],
                    "cover_fibers":q["nc"],"core_fibers":q["ncore"],
                }
                config[key]=record
                import pprint
                start_marker="# BEGIN GUI-COMMITTED RC SECTION CONFIG"
                end_marker="# END GUI-COMMITTED RC SECTION CONFIG"
                block=start_marker+"\nRC_SECTION_CONFIG = "+pprint.pformat(config,sort_dicts=True,width=110)+"\n# Set defaults for GUI-optional settings.\nfor _section_config in RC_SECTION_CONFIG.values():\n    _section_config.setdefault('cover_fibers', 8)\n    _section_config.setdefault('core_fibers', 16)\n    _section_config.setdefault('steel_b', 0.01)\n    _section_config.setdefault('steel_R0', 20.0)\n    _section_config.setdefault('steel_cR1', 0.925)\n    _section_config.setdefault('steel_cR2', 0.15)\n"+end_marker
                source=section_module_path.read_text(encoding="utf-8")
                a=source.index(start_marker); b=source.index(end_marker,a)+len(end_marker)
                updated=source[:a]+block+source[b:]
                compile(updated,str(section_module_path),"exec")
                temp=section_module_path.with_name(section_module_path.name+".tmp")
                temp.write_text(updated,encoding="utf-8"); temp.replace(section_module_path)
                status.set(f"Committed {preset.get()} section values into Define_Section_V109.py.")
                messagebox.showinfo("Section values committed",f"Saved {preset.get()} parameters to:\n{section_module_path}\n\nThe next section-library export will use these values.",parent=win)
            except Exception as exc:
                messagebox.showerror("Could not commit section values",str(exc),parent=win)
        summary=tk.StringVar(value="")
        ttk.Label(left,textvariable=summary,justify="left",wraplength=310).pack(anchor="w",pady=8)
        canvas=tk.Canvas(right,bg="#111827",highlightthickness=0); canvas.pack(fill="both",expand=True)
        status=tk.StringVar(value="Ready. Defaults are illustrative, not calibrated.")
        ttk.Label(outer,textvariable=status).pack(anchor="w",pady=(8,0))
        def get_data():
            def f(k): return float(vars_[k].get())
            def i(k): return int(vars_[k].get())
            w,d,c,tie,db=[f(k) for k in ("Section width (mm)","Section depth (mm)","Clear cover to tie (mm)","Tie diameter (mm)","Longitudinal bar diameter (mm)")]
            n=i("Bars per side incl. corners"); fc=f("Concrete f'c (MPa, positive)"); fcu_cover=f("Cover residual fcu (MPa, positive)"); fcc=f("Core f'cc (MPa, positive)"); fpcu=f("Core residual fpcu (MPa, positive)")
            epsc0=f("Cover epsc0 (negative)"); epsU=f("Cover epsU (negative)"); epsc0_core=f("Core epsc0 (negative)"); epsU_core=f("Core epsU (negative)")
            fy=f("Steel fy (MPa)"); Es=f("Steel E (MPa)"); unit_weight_kN_m3=f("RCC unit weight (kN/m³)"); b=f("Steel hardening ratio b")
            R0=f("Steel02 R0"); cR1=f("Steel02 cR1"); cR2=f("Steel02 cR2"); nc=i("Cover fibers per side"); ncore=i("Core fibers per side")
            sec,coverTag,coreTag,steelTag=[i(k) for k in ("Section tag","Cover material tag","Core material tag","Steel material tag")]
            if min(w,d,c,tie,db,fc,fcc,fpcu,fy,Es,unit_weight_kN_m3,R0,cR1,cR2)<=0 or fcu_cover<0 or n<2 or nc<2 or ncore<2 or b<0 or epsc0>=0 or epsU>=epsc0 or epsc0_core>=0 or epsU_core>=epsc0_core:
                raise ValueError("Check positive dimensions/material values, n >= 2, and separate cover/core strain ordering.")
            if len({sec,coverTag,coreTag,steelTag})<4: raise ValueError("Section tag and all three material tags must be unique. Use distinct integers.")
            off=c+tie+db/2
            if 2*off>=min(w,d): raise ValueError("Longitudinal bars do not fit inside the section.")
            sx=(w-2*off)/(n-1); sy=(d-2*off)/(n-1); coords=[]
            is_column=preset.get().startswith("Column")
            if is_column:
                # Perimeter-only column bars; no interior bars for the current review stage.
                for ix in range(n):
                    x=-w/2+off+ix*sx
                    coords.extend([(x,-d/2+off),(x,d/2-off)])
                for iy in range(1,n-1):
                    y=-d/2+off+iy*sy
                    coords.extend([(-w/2+off,y),(w/2-off,y)])
                layout="perimeter only (no interior bars)"
            else:
                # Beam preset retains perimeter bars only; corners are counted once.
                for j in range(n):
                    x=-w/2+off+j*sx; coords.extend([(x,-d/2+off),(x,d/2-off)])
                for j in range(1,n-1):
                    y=-d/2+off+j*sy; coords.extend([(-w/2+off,y),(w/2-off,y)])
                layout="perimeter only"
            coreoff=c+tie/2
            return dict(w=w,d=d,c=c,tie=tie,db=db,n=n,fc=fc,fcu_cover=fcu_cover,fcc=fcc,fpcu=fpcu,epsc0=epsc0,epsU=epsU,epsc0_core=epsc0_core,epsU_core=epsU_core,fy=fy,Es=Es,b=b,R0=R0,cR1=cR1,cR2=cR2,nc=nc,ncore=ncore,sec=sec,coverTag=coverTag,coreTag=coreTag,steelTag=steelTag,off=off,coreoff=coreoff,sx=sx,sy=sy,coords=coords,layout=layout,is_column=is_column)
        def redraw(_event=None):
            canvas.delete("all")
            try:
                q=get_data(); cw=max(canvas.winfo_width(),500); ch=max(canvas.winfo_height(),450); margin=75
                scale=min((cw-2*margin)/q['w'],(ch-2*margin)/q['d']); ww=q['w']*scale; hh=q['d']*scale; x0=(cw-ww)/2; y0=(ch-hh)/2; x1=x0+ww; y1=y0+hh
                canvas.create_rectangle(x0,y0,x1,y1,outline="white",width=3)
                inset=(q['c']+q['tie']/2)*scale; canvas.create_rectangle(x0+inset,y0+inset,x1-inset,y1-inset,outline="#38bdf8",dash=(6,3),width=2)
                for bx,by in q['coords']:
                    x=cw/2+bx*scale; y=ch/2-by*scale; r=max(4,q['db']*scale/2); canvas.create_oval(x-r,y-r,x+r,y+r,fill="#ef4444",outline="white",width=1)
                canvas.create_text(cw/2,24,text=f"{q['w']:g} × {q['d']:g} mm | {len(q['coords'])} bars ({q['layout']})",fill="white",font=("Segoe UI",12,"bold"))
                canvas.create_text(cw/2,ch-24,text="Blue dashed line = tie centreline (schematic)",fill="#cbd5e1",font=("Segoe UI",10))
                summary.set(f"Longitudinal bars: {len(q['coords'])}\nLayout: {q['layout']}\nGrid points per side: {q['n']}\nX spacing: {q['sx']:.2f} mm\nY spacing: {q['sy']:.2f} mm\nBar-centre offset: {q['off']:.2f} mm\nCover/core materials: Concrete01\nSteel model: {steel_model.get()}\nSection/material tags: {q['sec']} / {q['coverTag']}, {q['coreTag']}, {q['steelTag']}")
            except Exception as e: summary.set("Check inputs: "+str(e)); canvas.create_text(15,15,anchor="nw",text=str(e),fill="#fca5a5")
        for v in vars_.values(): v.trace_add("write",lambda *_: redraw())
        steel_box.bind("<<ComboboxSelected>>",redraw)
        canvas.bind("<Configure>",redraw)
        def generate_source(q):
            # kN-m units: MPa -> kN/m^2 (multiply by 1000); mm -> m.
            fc=q['fc']*1000; fcc=q['fcc']*1000; fpcu=q['fpcu']*1000; fy=q['fy']*1000; Es=q['Es']*1000; area=math.pi*(q['db']/1000)**2/4
            w=q['w']/1000; d=q['d']/1000; off=q['off']/1000; coreoff=q['coreoff']/1000
            ratio=max(w,d)/min(w,d); ratios=(1.0,1.2,1.5,2.0,2.5,3.0,4.0,5.0,10.0,1.0e6); betas=(0.1406,0.1661,0.1958,0.2287,0.2494,0.2633,0.2808,0.2913,0.3123,1.0/3.0)
            beta=betas[-1] if ratio>=ratios[-1] else (betas[0] if ratio<=1 else next((betas[i]+(betas[i+1]-betas[i])*(ratio-ratios[i])/(ratios[i+1]-ratios[i]) for i in range(len(ratios)-1) if ratios[i]<=ratio<=ratios[i+1]),betas[-1]))
            J=beta*max(w,d)*min(w,d)**3; G=5000*math.sqrt(q['fc'])/(2*(1+0.20))*1000; q['GJ']=G*J  # IS 456 Ec estimate; nu=0.20 assumption; kN/m^2 times m^4
            # Four cover patches form a non-overlapping cover ring around a confined core.
            lines=[
                "# RC fiber section generated by ETABS -> OpenSeesPy GUI; units: kN, m",
                "# Review/validate parameters and confinement before analysis.",
                f"# Preset: {preset.get()}; section dimensions {q['w']:g} x {q['d']:g} mm; reinforcement layout: {q['layout']}; {len(q['coords'])} bars.",
                f"# M35 cover/core and Fe550 steel values are supplied project definitions; verify before analysis.",
                "import openseespy.opensees as ops", "",
                f"SECTION_TAG = {q['sec']}", f"COVER_CONCRETE_TAG = {q['coverTag']}", f"CORE_CONCRETE_TAG = {q['coreTag']}", f"STEEL_TAG = {q['steelTag']}",
                f"ops.uniaxialMaterial('Concrete01', COVER_CONCRETE_TAG, {-fc:.8g}, {q['epsc0']:.8g}, {-q['fcu_cover']*1000:.8g}, {q['epsU']:.8g})",
                f"ops.uniaxialMaterial('Concrete01', CORE_CONCRETE_TAG, {-fcc:.8g}, {q['epsc0_core']:.8g}, {-fpcu:.8g}, {q['epsU_core']:.8g})",
                (f"ops.uniaxialMaterial('Steel02', STEEL_TAG, {fy:.8g}, {Es:.8g}, {q['b']:.8g}, {q['R0']:.8g}, {q['cR1']:.8g}, {q['cR2']:.8g})" if steel_model.get()=="Steel02" else f"ops.uniaxialMaterial('SteelMPF', STEEL_TAG, {fy:.8g}, {-fy:.8g}, {Es:.8g}, {q['b']:.8g}, {q['b']:.8g}, a1=0.0, a2=1.0, a3=0.0, a4=1.0)"),
                f"ops.section('Fiber', SECTION_TAG, '-GJ', {q['GJ']:.12g})",
                "# Concrete cover ring: four non-overlapping rectangular patches to tie centreline; bars sit inward of that line.",
                f"ops.patch('rect', COVER_CONCRETE_TAG, {q['nc']}, 1, {-w/2:.8g}, {-d/2:.8g}, {w/2:.8g}, {-d/2+coreoff:.8g})",
                f"ops.patch('rect', COVER_CONCRETE_TAG, {q['nc']}, 1, {-w/2:.8g}, {d/2-coreoff:.8g}, {w/2:.8g}, {d/2:.8g})",
                f"ops.patch('rect', COVER_CONCRETE_TAG, 1, {q['nc']}, {-w/2:.8g}, {-d/2+coreoff:.8g}, {-w/2+coreoff:.8g}, {d/2-coreoff:.8g})",
                f"ops.patch('rect', COVER_CONCRETE_TAG, 1, {q['nc']}, {w/2-coreoff:.8g}, {-d/2+coreoff:.8g}, {w/2:.8g}, {d/2-coreoff:.8g})",
                f"ops.patch('rect', CORE_CONCRETE_TAG, {q['ncore']}, {q['ncore']}, {-w/2+off:.8g}, {-d/2+coreoff:.8g}, {w/2-coreoff:.8g}, {d/2-coreoff:.8g})",
                f"BAR_AREA = {area:.12g}", f"# Longitudinal steel fibers: {q['layout']}; {len(q['coords'])} bars."]
            for x,y in q['coords']: lines.append(f"ops.fiber({x/1000:.10g}, {y/1000:.10g}, BAR_AREA, STEEL_TAG)")
            lines += ["", "# NOTE: Fiber section only; no beam-column element, loads, or analysis is created.", "# Concrete01 parameters are placeholders; calibrate cover/core separately to test data.", "# SteelMPF uses symmetric +/- Fy and equal positive/negative hardening ratio here; calibrate if asymmetry is needed.", "# Core boundary offset is cover + tie_diameter/2; longitudinal bar centres use cover + tie_diameter + bar_diameter/2."]
            return "\n".join(lines)+"\n"
        def generate_full_library_source():
            """Generate a thin runner that calls the separate Define_Section module."""
            lines = [
                "# OpenSeesPy section/material library runner; units: kN, m, s.",
                "# RC material parameters are the supplied M35 / Fe550 definitions.",
                "# SHS uses the supplied 350x350x16 mm geometry and expected Fy=379.5 MPa.",
                "# FVD and BRB materials are in separate commented blocks in Define_Section_V109.py.",
                "# Confirm FVD coefficient units and material calibration before analysis.",
                "# Keep Define_Section_V109.py beside this file when running it.",
                "import openseespy.opensees as ops",
                "from Define_Section_V109 import define_all_sections",
                "SECTION_LIBRARY = define_all_sections(ops, unit_system='kN-m')",
                "print('Defined fiber sections:', ', '.join(SECTION_LIBRARY['fiber_sections']))",
                "print('Defined auxiliary materials:', ', '.join(SECTION_LIBRARY['auxiliary_materials']))",
                "# This file defines materials/sections only; create elements and run analysis separately.",
                "",
            ]
            return "\n".join(lines)

        def export_full_library():
            try:
                code=generate_full_library_source()
                path=filedialog.asksaveasfilename(parent=win,title="Export combined OpenSeesPy materials + sections",defaultextension=".py",initialfile="OpenSeesPy_Define_Sections.py",filetypes=[("Python","*.py")])
                if not path: return
                Path(path).write_text(code,encoding="utf-8")
                status.set("Section runner exported: SHS + RC beam/columns from Define_Section_V109.py. No elements or analysis were created.")
                messagebox.showinfo("Combined library exported",f"Saved section-library runner to:\n{path}\n\nIt calls Define_Section_V109.py for the SHS 350×350×16, RC beam 600×800, RC columns 1100×1100 and 1250×1250, and the separate FVD and BRB material blocks. Keep that module beside the runner. Verify FVD coefficient units. No elements or analysis are created.",parent=win)
            except Exception as e:
                messagebox.showerror("Library export failed",str(e),parent=win)

        def export():
            try:
                q=get_data(); code=generate_source(q)
                default_name={"Beam 600×800":"RC_Beam_600x800_FiberSection_Concrete01_Steel02.py","Column 1100×1100":"RC_Column_1100x1100_FiberSection_Concrete01_Steel02.py","Column 1250×1250":"RC_Column_1250x1250_FiberSection_Concrete01_Steel02.py"}.get(preset.get(),"RC_FiberSection_Concrete01_Steel02.py")
                path=filedialog.asksaveasfilename(parent=win,title="Save OpenSeesPy fiber section",defaultextension=".py",initialfile=default_name,filetypes=[("Python","*.py")])
                if not path:return
                Path(path).write_text(code,encoding="utf-8")
                status.set("Fiber-section source exported. No analysis was run.")
                messagebox.showinfo("Export complete",f"Saved fiber section source:\n{path}",parent=win)
            except Exception as e: messagebox.showerror("Export failed",str(e),parent=win)
        ttk.Button(left,text="Refresh values from Define_Section_V109.py",command=refresh_from_define_section).pack(fill="x",pady=3)
        ttk.Button(left,text="Commit values to Define_Section_V109.py",command=commit_to_define_section).pack(fill="x",pady=3)
        ttk.Button(left,text="Refresh preview",command=redraw).pack(fill="x",pady=3)
        ttk.Button(left,text="Export Concrete01 + selected steel section",command=export).pack(fill="x",pady=3)
        ttk.Button(left,text="Export sections + FVD + BRB materials",command=export_full_library).pack(fill="x",pady=3)
        ttk.Label(left,text="Exports a runner for Define_Section_V109.py: SHS 350×350×16, mapped RC fiber sections, plus separate FVD and BRB material blocks. Verify project units and calibrate before analysis. No elements or analysis are created.",wraplength=310).pack(anchor="w",pady=6)
        refresh_from_define_section()
        redraw()

    def _open_section_mapping(self):
        from OpenSees_Mapping_GUI_V125 import launch
        return launch(self.root,self.out.get())

    def _browse_file(self):
        p=filedialog.askopenfilename(title="Select ETABS model",filetypes=[("ETABS model","*.edb"),("All files","*.*")]);
        if p:self.edb.set(p)
    def _browse_dir(self):
        p=filedialog.askdirectory(title="Select output folder");
        if p:self.out.set(p)
    def _show_last_exports(self):
        """Open the most recent ETABS load visualization or select one from disk."""
        target=None
        if getattr(self,"_last_exports",None): target=self._last_exports[1]
        if not target or not os.path.isfile(target):
            target=filedialog.askopenfilename(parent=self.root,title="Select OpenSees/ETABS load-view HTML",filetypes=[("HTML files","*.html"),("All files","*.*")])
        if target:
            try: os.startfile(target)
            except Exception as exc: messagebox.showerror("Could not open ETABS load view",str(exc),parent=self.root)
    def _open_load_audit_explanation(self):
        from OpenSees_Mapping_GUI_V125 import show_load_audit
        return show_load_audit(self.root,self.out.get())
    def log(self,msg):
        line=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
        self.logbox.insert("end",line+"\n"); self.logbox.see("end"); self.root.update_idletasks()
        log_path=getattr(self,"_log_path",None)
        if log_path:
            try:
                with open(log_path,"a",encoding="utf-8") as lf: lf.write(line+"\n")
            except Exception: pass
    def _run(self):
        if not self.edb.get().strip(): messagebox.showerror("Missing model","Select an ETABS EDB first."); return
        self.runbtn.configure(state="disabled")
        try:
            log_dir=Path(self.out.get().strip() or ".").expanduser()
            log_dir.mkdir(parents=True,exist_ok=True)
            self._log_path=log_dir/"ETABS_OpenSees_Conversion_Log.txt"
            with open(self._log_path,"w",encoding="utf-8") as lf:
                lf.write(f"ETABS to OpenSeesPy conversion log\nStarted: {time.strftime('%Y-%m-%d %H:%M:%S')}\nSource EDB: {self.edb.get().strip()}\n\n")
            self.log(f"Detailed timestamped log: {self._log_path}")
            result=convert_model(self.edb.get().strip(),self.out.get().strip(),self.log,self.include_live.get())
            self._last_exports=result
            report_path=Path(self.out.get())/'OpenSees_Complete_Export_Report_V118.json'
            assembly=json.loads(report_path.read_text(encoding='utf-8-sig'))
            if assembly['assembly_errors']:
                messagebox.showwarning('Export created — model assembly needs inputs',
                    'Analysis files are linked automatically. The model entry reports these unresolved inputs:\n\n'+'\n'.join(assembly['assembly_errors'])+'\n\nReport: '+str(report_path),parent=self.root)
            else:
                messagebox.showinfo('Connected OpenSees export created',
                    f"Assembled {assembly['frame_segments']} frame segments and {assembly['shell_mesh_cells']} wall/slab shell cells.\nGravity loads, source self-weight, seismic mass and rigid floors are included.\n\nGravity, Modal, Linear TH and Nonlinear TH windows now select their matching entry automatically.\n\nElastic conversion model: compare reactions, mass and periods with ETABS. Nonlinear execution still requires calibrated materials.\n\nReport: {report_path}",parent=self.root)
        except Exception as e:
            self.log("ERROR: "+repr(e)); self.log(traceback.format_exc()); messagebox.showerror("Conversion failed",str(e))
        finally:self.runbtn.configure(state="normal")

    def _rebuild_complete_export(self):
        """Regenerate model entries after editing the V118 config; no ETABS run."""
        try:
            from OpenSees_Complete_Export_V118 import prepare_complete_export
            manifest,report=prepare_complete_export(self.out.get(),frame_mapping=ETABS_TO_OPENSEES_SECTION)
            self.log('Rebuilt complete-model entries; report: '+str(Path(self.out.get())/manifest['report']))
            if report['assembly_errors']:
                messagebox.showwarning('Assembly needs inputs','\n'.join(report['assembly_errors']),parent=self.root)
            else:
                messagebox.showinfo('Assembled model export rebuilt','Gravity/model/story files will be selected automatically in their analysis windows.\n\n'+str(Path(self.out.get())/manifest['report']),parent=self.root)
        except Exception as exc:
            messagebox.showerror('Could not rebuild export',str(exc),parent=self.root)


def main():
    root=tk.Tk()
    from OpenSees_Window_Manager_V129 import install_windows_menu
    install_windows_menu(root)
    root.report_callback_exception=lambda typ,value,tb: _report_gui_error(root,typ,value,tb)
    app=App(root)
    print('V161 GUI constructed; entering event loop',flush=True)
    menu=tk.Menu(root,tearoff=False)
    menu.add_command(label='Nonlinear performance objectives / acceptance',command=lambda:__import__('components.validation.nonlinear_performance',fromlist=['launch']).launch(root,app.out.get()))
    existing=root.nametowidget(root.cget('menu')) if root.cget('menu') else tk.Menu(root)
    existing.add_cascade(label='Performance assessment',menu=menu);root.config(menu=existing)
    if __import__('os').environ.get('OPENSEES_STARTUP_SMOKE')=='1':root.after(1500,root.destroy)
    root.mainloop()
if __name__=="__main__": main()
















