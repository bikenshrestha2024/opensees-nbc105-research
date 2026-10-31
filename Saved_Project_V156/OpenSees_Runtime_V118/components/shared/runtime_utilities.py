"""Shared time-history tag allocation and workbook cell conversion.

OpenSees time series and load-pattern tags have separate namespaces.
loadConst freezes existing patterns; it does not release their tags.
Command reference: https://openseespydoc.readthedocs.io/en/latest/src/pathTs.html
"""

__release__ = '134'
import json
import math
from pathlib import Path


def excel_cell(value):
    """Keep scalar cells native and preserve nested audit values as JSON."""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else value


def add_path_excitation(ops, *, direction, dt, file_path, factor, base_tag=910000):
    """Create an excitation without reusing the model builder's gravity tags.

    Some OpenSeesPy builds cannot enumerate time-series tags. In those builds
    creation is the authoritative uniqueness check; failed duplicate inserts
    leave the existing series intact. Retry a bounded number of candidate tags,
    and propagate failure before running any transient steps.
    """
    path = Path(file_path)
    if not path.is_file() or not math.isfinite(float(dt)) or float(dt) <= 0 or not math.isfinite(float(factor)):
        raise ValueError("Excitation needs an existing record file, positive finite dt and finite factor.")
    if int(direction) not in (1, 2, 3):
        raise ValueError("UniformExcitation direction must be a translational DOF (1–3).")
    get_patterns = getattr(ops, "getLoadPatternTags", None) or getattr(ops, "getPatterns", None)
    if not callable(get_patterns):
        raise RuntimeError("This OpenSees build cannot enumerate load patterns; cannot safely allocate excitation tags.")
    used_patterns = set(map(int, get_patterns()))
    get_series = getattr(ops, "getTimeSeriesTags", None)
    used_series = set(map(int, get_series())) if callable(get_series) else set()
    tag = max(int(base_tag), 1)
    for _ in range(128):
        while tag in used_patterns or tag in used_series:
            tag += 1
        try:
            ops.timeSeries("Path", tag, "-dt", float(dt), "-filePath", str(path), "-factor", float(factor))
        except Exception as exc:
            if callable(get_series):
                raise RuntimeError(f"Could not create Path time series {tag}.") from exc
            # The API exposes only a generic error when an existing time-series
            # tag collides. A different candidate is safe to attempt.
            last_error = exc
            tag += 1
            continue
        ops.pattern("UniformExcitation", tag, int(direction), "-accel", tag)
        return tag, tag
    raise RuntimeError("Could not allocate an excitation time-series tag after 128 attempts; inspect the OpenSees errors and record input.") from last_error
