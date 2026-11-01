import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.nonlinear_time_history.building_exploratory import (
    diagnostic_record_inputs,
    run,
)

SPEC = importlib.util.spec_from_file_location(
    "trace_failed_element", ROOT / "21_TRACE_FAILED_ELEMENT.py"
)
trace_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trace_module)


class V168DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            (np.array([1.0, 2.0]), 0.01, "g"),
            (np.array([3.0, 4.0]), 0.01, "m/s2"),
        ]

    def test_probe_axis_and_orientation_preserve_only_selected_motion(self):
        xy = diagnostic_record_inputs(self.records, "XY", "X")
        self.assertEqual(xy[0][0].tolist(), [1.0, 2.0])
        self.assertEqual(xy[1][0].tolist(), [0.0, 0.0])
        yx = diagnostic_record_inputs(self.records, "YX", "X")
        self.assertEqual(yx[0][0].tolist(), [3.0, 4.0])
        self.assertEqual(yx[1][0].tolist(), [0.0, 0.0])
        zero = diagnostic_record_inputs(self.records, "XY", "ZERO")
        self.assertTrue(all(not values.any() for values, _, _ in zero))
        self.assertEqual(self.records[0][0].tolist(), [1.0, 2.0])

    def test_invalid_probe_settings_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "diagnostic_excitation"):
            diagnostic_record_inputs(self.records, "XY", "Z")
        with self.assertRaisesRegex(ValueError, "orientation"):
            diagnostic_record_inputs(self.records, "XX", "XY")

    def test_invalid_run_writes_traceback_and_selected_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "transient_system"):
                run({
                    "output_dir": folder,
                    "nonlinear_walls": True,
                    "transient_system": "UnknownSolver",
                })
            report = json.loads(
                (Path(folder) / "INCOMPLETE.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["profile"], "LITERATURE_BUILDING_NL_V161")
            self.assertEqual(report["stage"], "configuration_validation")
            self.assertEqual(report["error_type"], "ValueError")
            self.assertIn("transient_system", report["traceback"])

    def test_same_source_and_output_folder_is_rejected_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "outside the source model"):
                run({
                    "model_folder": folder,
                    "output_dir": folder,
                    "nonlinear_walls": True,
                })
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_conflicting_damping_probes_are_logged_as_invalid_config(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "only one diagnostic damping"):
                run({
                    "output_dir": folder,
                    "diagnostic_zero_damping": True,
                    "diagnostic_mass_damping": True,
                })
            report = json.loads(
                (Path(folder) / "INCOMPLETE.json").read_text(encoding="utf-8")
            )
            self.assertEqual(report["stage"], "configuration_validation")
            self.assertIn("only one diagnostic damping", report["error"])

    def test_failed_element_trace_maps_solver_tag_to_source_area(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder) / "isolated_model"
            model.mkdir()
            (model / trace_module.MAP_FILE).write_text(
                json.dumps({"AREA:wall-7": [111508]}), encoding="utf-8"
            )
            (model / trace_module.DATA_FILE).write_text(json.dumps({
                "nodes": {"1": [0.0, 0.0, 0.0], "2": [1.0, 0.0, 0.0]},
                "shells": [{
                    "object": "wall-7", "category": "SHEAR WALL",
                    "nodes": [1, 2], "properties": {"property": "Wall 600"},
                }],
            }), encoding="utf-8")
            report = trace_module.trace(model, 111508)
            self.assertEqual(len(report["matches"]), 1)
            self.assertEqual(report["matches"][0]["category"], "SHEAR WALL")
            self.assertEqual(
                report["matches"][0]["properties"]["property"], "Wall 600"
            )
            self.assertEqual(report["matches"][0]["node_coordinates"]["1"], [0.0, 0.0, 0.0])

    def test_failed_element_trace_returns_empty_for_unknown_tag(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder)
            (model / trace_module.MAP_FILE).write_text(
                json.dumps({"FRAME:beam-1": [100001]}), encoding="utf-8"
            )
            result = trace_module.trace(model, 999999)
            self.assertEqual(result["matches"], [])

    def test_failed_element_trace_uses_tag_ranges_when_map_was_not_written(self):
        with tempfile.TemporaryDirectory() as folder:
            model = Path(folder)
            (model / trace_module.DATA_FILE).write_text(json.dumps({
                "nodes": {"1": [0.0, 0.0, 0.0]},
                "frames": [{"object": "beam-1", "category": "BEAM", "nodes": [1]}],
                "shells": [{
                    "object": "wall-7", "category": "SHEAR WALL",
                    "nodes": [1], "properties": {"property": "Wall 600"},
                }],
            }), encoding="utf-8")
            result = trace_module.trace(model, 100002)
            self.assertFalse(result["element_map_found"])
            self.assertEqual(result["mapping_method"], "deterministic_tag_range_fallback")
            self.assertEqual(result["matches"][0]["source_key"], "AREA:wall-7")


if __name__ == "__main__":
    unittest.main()
