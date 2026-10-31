"""Shared motion catalogue, PEER/CSV parsing, selection and story geometry."""

__release__ = '134'
from pathlib import Path
import csv,re,math
LTH_DEFAULT_MODE = "Paired X/Y - bidirectional + swapped orientations"
LTH_X_ONLY_MODE = "X only - screening (not full paired 3D verification)"
LTH_MATCHING_METADATA = {"site_soil": "C", "period_range_s": [0.05, 6.0], "record_set": "Near- and far-field orthogonal pairs; both horizontal components matched in SeismoMatch; user-provided"}
LTH_DEFAULT_X_RECORDS = [
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\X Direction\Matched_RSN1505_CHICHI_TCU068-E.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\X Direction\Matched_KATNP.HNE.NQ.01_a_EW_PEER_Gorkha.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\X Direction\Matched_RSN879_LANDERS_LCN260.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\X Direction\Matched_RSN1086_NORTHR_SYL090.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\X Direction\Matched_RSN1120_KOBE_TAK000.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\X Direction\Matched_RSN1165_KOCAELI_IZT090.txt",
]
LTH_DEFAULT_Y_RECORDS = [
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\Y Direction\Matched_RSN1505_CHICHI_TCU068-N.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\Y Direction\Matched_KATNP.HNN.NQ.01_a_NS_PEER_Gorkha.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\Y Direction\Matched_RSN879_LANDERS_LCN345.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\Y Direction\Matched_RSN1086_NORTHR_SYL360.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\Y Direction\Matched_RSN1120_KOBE_TAK090.txt",
    r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Near Field\Y Direction\Matched_RSN1165_KOCAELI_IZT180.txt",
]
LTH_DEFAULT_PEER_PAIRS = [
    {"pair_id": Path(x).stem.removeprefix("Matched_"), "field_type": "Near-field", "x_path": x, "y_path": y}
    for x, y in zip(LTH_DEFAULT_X_RECORDS, LTH_DEFAULT_Y_RECORDS)
]
LTH_DEFAULT_PEER_PAIRS += [
    {"pair_id": "RSN1787_HECTOR", "field_type": "Far-field",
     "x_path": r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Far Field\X Direction\Matched_RSN1787_HECTOR_HEC000.txt",
     "y_path": r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Far Field\Y Direction\Matched_RSN1787_HECTOR_HEC090.txt"},
    {"pair_id": "RSN767_LOMAP", "field_type": "Far-field",
     "x_path": r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Far Field\X Direction\Matched_RSN767_LOMAP_G03000.txt",
     "y_path": r"D:\Thesis\Target Spectra\Soil Type C Matching 0.05-6\Far Field\Y Direction\Matched_RSN767_LOMAP_G03090.txt"},
]



# Optional portable bundle: never change record numeric values or motion scale.
import json as _record_json
for _base in (Path(__file__).resolve().parent,Path(__file__).resolve().parent.parent):
    _catalog=_base/'PACKAGED_MOTION_PAIRS_V141.json'
    if not _catalog.is_file():continue
    _items=_record_json.loads(_catalog.read_text(encoding='utf-8-sig')).get('pairs',[])
    if _items and all((_base/item[axis+'_path']).is_file() for item in _items for axis in ('x','y')):
        LTH_DEFAULT_PEER_PAIRS=[dict(item,x_path=str((_base/item['x_path']).resolve()),y_path=str((_base/item['y_path']).resolve())) for item in _items]
        LTH_DEFAULT_X_RECORDS=[item['x_path'] for item in LTH_DEFAULT_PEER_PAIRS]
        LTH_DEFAULT_Y_RECORDS=[item['y_path'] for item in LTH_DEFAULT_PEER_PAIRS]
        break

def _read_peer_text_record(path):
    """Read PEER/SeismoMatch text with Time(sec), Acc(g) columns or AT2 data."""
    lines = Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines()
    dt = None
    for line in lines[:30]:
        m = re.search(r"(?:Time\s*Step\s*:\s*|\bDT\s*=\s*)([0-9]*\.?[0-9]+)", line, re.I)
        if m:
            dt = float(m.group(1)); break
    has_time_column = any("time(sec)" in line.lower() and "acc" in line.lower() for line in lines[:40])
    samples, times = [], []
    numeric_rows = []
    for line in lines:
        parts = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?", line)
        if not parts: continue
        # Ignore metadata lines (NPTS, time step, PEER header, etc.).
        if re.search(r"NPTS|DT\s*=|time\s*step|accelerogram|matched|time\(sec\)|acc\(", line, re.I):
            continue
        try: numeric_rows.append([float(x) for x in parts])
        except ValueError: continue
    if has_time_column:
        for row in numeric_rows:
            if len(row) >= 2:
                times.append(row[0]); samples.append(row[1])
        if len(times) < 2: raise ValueError(f"No time/acceleration rows found in {path}")
        inferred = times[1] - times[0]
        if dt is None: dt = inferred
        if abs(times[0]) > 1e-8: raise ValueError(f"Time column must begin at 0 s: {path}")
        for i in range(1, len(times)):
            step = times[i] - times[i - 1]
            if abs(step - dt) > max(1e-8, dt * 1e-5):
                raise ValueError(f"Irregular time increment near sample {i + 1} in {path}; prepare/resample the record before analysis.")
    else:
        # Standard PEER AT2 files may have NPTS/DT metadata then one or more
        # acceleration values per line. Numeric rows are flattened in order.
        samples = [value for row in numeric_rows for value in row]
        if dt is None: raise ValueError(f"No PEER DT / Time Step metadata found in {path}")
    if not dt or dt <= 0 or len(samples) < 2 or not all(math.isfinite(x) for x in samples):
        raise ValueError(f"Invalid time interval or acceleration data in {path}")
    if abs(samples[0]) > 1e-8:
        raise ValueError(f"OpenSees Path records must start at zero acceleration; first sample in {path} is {samples[0]:g} g")
    units = "g" if any("acc(g)" in line.lower() for line in lines[:50]) or Path(path).suffix.lower() == ".at2" else "m/s2"
    return samples, dt, units

def _read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def _numeric_record(path):
    """Read a plain numeric acceleration record; commas/whitespace accepted."""
    raw = Path(path).read_text(encoding="utf-8-sig")
    tokens = [t for t in re.split(r"[\s,;]+", raw.strip()) if t]
    if not tokens:
        raise ValueError(f"Empty ground-motion file: {path}")
    try:
        values = [float(t) for t in tokens]
    except ValueError as exc:
        raise ValueError(f"Ground-motion file must contain numeric values only (no header): {path}") from exc
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError(f"Ground motion needs at least two finite acceleration values: {path}")
    if abs(values[0]) > 1e-12:
        raise ValueError(f"First acceleration sample must be zero for OpenSees Path series: {path}. Prepare the record correctly before analysis.")
    return values

def _read_manifest_component(path, manifest_dt, manifest_units):
    """Read PEER/SeismoMatch records with embedded metadata or numeric samples."""
    path = Path(path)
    head = path.read_text(encoding="utf-8-sig", errors="replace")[:4000]
    is_peer_text = bool(re.search(r"Time\s*Step\s*:|Time\s*\(sec\)|NPTS\s*=|PEER\s+NGA", head, re.I)) or path.suffix.lower() == ".at2"
    if is_peer_text:
        values, dt, units = _read_peer_text_record(path)
        if abs(dt - manifest_dt) > max(1e-8, dt * 1e-5):
            raise ValueError(f"Manifest dt {manifest_dt:g}s does not match embedded record dt {dt:g}s in {path}.")
        manifest_units = manifest_units.lower().replace("^", "").replace("²", "2").replace(" ", "")
        if units != manifest_units:
            raise ValueError(f"Manifest units {manifest_units} do not match detected units {units} in {path}.")
        return values, dt, units
    return _numeric_record(path), manifest_dt, manifest_units

def _read_inputs(config):
    if config.get("motion_mode", "PAIRED_3D") == "X_ONLY_SCREENING":
        parsed_motions = []
        paths = config.get("peer_x_paths", [])
        if len(paths) < 3: raise ValueError("NBC 105 requires at least three ground motions for a one-direction screening suite.")
        scale = float(config.get("x_scale_factor", 1.0))
        if not 0.33 <= scale <= 3.0: raise ValueError("Verified record scale factor must be within NBC §9.3.2.2 limits [0.33, 3.0].")
        for path in paths:
            p = Path(path).expanduser()
            values, dt, units = _read_peer_text_record(p)
            parsed_motions.append({"pair_id": p.stem, "x_path": str(p.resolve()), "x": values, "dt_x": dt, "scale": scale, "units": units, "mode": "X_ONLY"})
    else:
        parsed_motions = []
        if config.get("use_preloaded_peer_pairs"):
            scale = float(config.get("pair_scale_factor", 1.0))
            if not 0.33 <= scale <= 3.0:
                raise ValueError("The common scale factor applied to both components must be within NBC §9.3.2.2 limits [0.33, 3.0].")
            from OpenSees_Pair_Selection_V128 import filter_pairs
            pair_paths = filter_pairs(config.get("peer_pairs", LTH_DEFAULT_PEER_PAIRS),config)
            if len(pair_paths) < 3 and not config.get("preliminary_selection",False):
                raise ValueError("NBC 105:2025 §9.3.2 requires at least three orthogonal pairs for this 3D analysis.")
            for pair in pair_paths:
                px, py = Path(pair["x_path"]).expanduser(), Path(pair["y_path"]).expanduser()
                x, dx, ux = _read_peer_text_record(px)
                y, dy, uy = _read_peer_text_record(py)
                if ux != uy:
                    raise ValueError(f"Pair {pair['pair_id']} has different acceleration units (X={ux}, Y={uy}).")
                parsed_motions.append({"pair_id": pair["pair_id"], "field_type": pair.get("field_type", "Custom"),
                    "x_path": str(px.resolve()), "y_path": str(py.resolve()),
                    "dt_x": dx, "dt_y": dy, "scale": scale, "units": ux, "x": x, "y": y, "mode": "PAIRED_3D"})
        else:
            from OpenSees_Pair_Selection_V128 import filter_pairs
            motions = filter_pairs([r for r in _read_csv(config["motion_manifest"]) if str(r.get("pair_id", "")).strip()],config)
            for index, row in enumerate(motions, 2):
                if not str(row.get("pair_id", "")).strip():
                    continue
                try:
                    pair_id = row["pair_id"].strip()
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+", pair_id):
                        raise ValueError("pair_id may contain only letters, numbers, dot, underscore and hyphen.")
                    px = Path(row["component_x_path"])
                    py = Path(row["component_y_path"])
                    if not px.is_absolute(): px = Path(config["motion_manifest"]).parent / px
                    if not py.is_absolute(): py = Path(config["motion_manifest"]).parent / py
                    dx, dy = float(row["dt_x_s"]), float(row["dt_y_s"])
                    scale = float(row["scale_factor"])
                    units = row["units"].strip().lower()
                    if dx <= 0 or dy <= 0 or not (0.33 <= scale <= 3.0):
                        raise ValueError("dt must be positive and the verified scale factor must be in [0.33, 3.0].")
                    if units not in ("g", "m/s2", "m/s^2"):
                        raise ValueError("units must be g or m/s2.")
                    x_values, dx_actual, ux = _read_manifest_component(px, dx, units)
                    y_values, dy_actual, uy = _read_manifest_component(py, dy, units)
                    if ux != uy:
                        raise ValueError(f"X/Y acceleration units differ (X={ux}, Y={uy}); a pair must use consistent units.")
                    parsed_motions.append({"pair_id": pair_id, "field_type": row.get("field_type", "Custom").strip() or "Custom",
                        "x_path": str(px.resolve()), "y_path": str(py.resolve()),
                        "dt_x": dx_actual, "dt_y": dy_actual, "scale": scale, "units": ux,
                        "x": x_values, "y": y_values, "mode": "PAIRED_3D"})
                except Exception as exc:
                    raise ValueError(f"Motion manifest row {index}: {exc}") from exc
        if not parsed_motions:
            raise ValueError("The motion manifest contains no complete ground-motion pairs.")
        if len({m["pair_id"] for m in parsed_motions}) != len(parsed_motions):
            raise ValueError("Each motion pair must have a unique pair_id.")
        if config["torsion_sensitive"] and len(parsed_motions) < 3 and not config.get("preliminary_selection",False):
            raise ValueError("NBC 105:2025 §9.3.2 requires at least three orthogonal pairs for torsionally sensitive 3D analysis.")
    stories = _read_csv(config["story_nodes_csv"])
    parsed_stories = []
    for index, row in enumerate(stories, 2):
        try:
            parsed_stories.append({"story_number": int(row["story_number"]), "story_name": row.get("story_name", "").strip() or str(row["story_number"]),
                "node": int(row["master_node_tag"]), "elevation": float(row["elevation_m"])})
        except Exception as exc:
            raise ValueError(f"Story-node CSV row {index} needs story_number, story_name, master_node_tag and elevation_m: {exc}") from exc
    parsed_stories.sort(key=lambda r: r["elevation"])
    if not parsed_stories or len({r["node"] for r in parsed_stories}) != len(parsed_stories):
        raise ValueError("Story master-node tags must be nonempty and unique.")
    prev=float(config.get('base_elevation_m',0.))
    model_file=Path(config.get('model_script','')).parent/'OpenSees_Complete_Model_Data_V118.json'
    if model_file.is_file():
        import json
        prev=float(json.loads(model_file.read_text(encoding='utf-8-sig'))['base_z_m'])
    for r in parsed_stories:
        r["height"] = r["elevation"] - prev
        if r["height"] <= 0: raise ValueError("Story elevations must increase upward from the model base elevation.")
        prev = r["elevation"]
    return parsed_motions, parsed_stories
