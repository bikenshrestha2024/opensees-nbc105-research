import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.validation.material_sensitivity import build_case_matrix, write_case_matrix
from OpenSees_Nonlinear_Time_History_NBC105_V116 import (
    LINEAR_SYSTEMS,
    _configure_nonlinear_transient,
)
from components.nonlinear_time_history.building_exploratory import (
    TRANSIENT_SYSTEMS,
    _run_material_sensitivity,
    configure_transient_system,
    profile_for_config,
)
from components.nonlinear_time_history.research_building_materials import (
    FRAME_OVERRIDE_TARGETS,
    brace_steel_parameters,
    validate_material_overrides,
    validate_frame_section_parameters,
)


class MaterialSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            "concrete_grade": "M35",
            "steel_grade": "Fe500",
            "bar_diameter_mm": "20",
            "bar_count": "4",
        }

    def test_one_factor_matrix_and_nominal_values(self):
        result = build_case_matrix(self.baseline)
        cases = result["cases"]
        self.assertEqual(len(cases), 15)
        self.assertEqual(cases[0]["case_id"], "BASELINE")
        self.assertEqual(cases[0]["concrete_fck_cube_MPa"], 35.0)
        self.assertEqual(cases[0]["steel_nominal_fy_MPa"], 500.0)
        self.assertFalse(cases[0]["constitutive_parameters_generated"])
        concrete_case = next(row for row in cases if row["case_id"] == "CONCRETE_M40")
        self.assertEqual(concrete_case["steel_grade"], "Fe500")
        self.assertEqual(concrete_case["bar_diameter_mm"], 20)
        bar_case = next(row for row in cases if row["case_id"] == "BAR_25MM")
        self.assertEqual(bar_case["bar_count_held_constant"], 4)
        self.assertTrue(bar_case["requires_rebar_layout_review"])
        expected = 100.0 * ((25.0 / 20.0) ** 2 - 1.0)
        self.assertAlmostEqual(bar_case["total_bar_area_change_percent"], expected)

    def test_invalid_grade_or_diameter_is_rejected(self):
        for key, value in (("concrete_grade", "M25"), ("steel_grade", "Fe600"),
                           ("bar_diameter_mm", "18"), ("bar_count", "0")):
            baseline = dict(self.baseline, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_case_matrix(baseline)

    def test_csv_and_json_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            json_path, csv_path = write_case_matrix(self.baseline, folder)
            self.assertTrue(json_path.is_file())
            with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 15)
            self.assertEqual(rows[0]["case_id"], "BASELINE")

    def test_nonlinear_solver_selection_and_validation(self):
        class FakeOps:
            def __init__(self):
                self.calls = []

            def __getattr__(self, name):
                return lambda *args: self.calls.append((name, args))

        for solver in LINEAR_SYSTEMS:
            ops = FakeOps()
            _configure_nonlinear_transient(ops, linear_solver=solver)
            self.assertIn(("system", (solver,)), ops.calls)
        with self.assertRaisesRegex(ValueError, "linear_solver"):
            _configure_nonlinear_transient(FakeOps(), linear_solver="Mumps")

    def test_exploratory_solver_selection_and_validation(self):
        class FakeOps:
            def __init__(self):
                self.calls = []

            def system(self, *args):
                self.calls.append(args)

        for solver in TRANSIENT_SYSTEMS:
            ops = FakeOps()
            configure_transient_system(ops, solver)
            expected = ("SparseGeneral", "-piv") if solver == "SparseGeneral" else ("UmfPack",)
            self.assertEqual(ops.calls, [expected])
        with self.assertRaisesRegex(ValueError, "transient_system"):
            configure_transient_system(FakeOps(), "Mumps")

    def test_incomplete_report_profile_matches_wall_configuration(self):
        self.assertEqual(
            profile_for_config({"nonlinear_walls": True}),
            "LITERATURE_BUILDING_NL_V161",
        )
        self.assertEqual(
            profile_for_config({"nonlinear_walls": False}),
            "LITERATURE_FRAME_NL_ELASTIC_WALL_V138",
        )

    def test_explicit_building_overrides_accept_345_mpa_and_reject_bad_inputs(self):
        self.assertEqual(
            validate_material_overrides({"brace.fy_mpa": "345", "brace.b": .01}),
            {"brace.fy_mpa": 345., "brace.b": .01},
        )
        self.assertEqual(
            brace_steel_parameters({"brace.fy_mpa": 345.})["fy_kN_m2"],
            345000.,
        )
        self.assertEqual(
            brace_steel_parameters({"brace.E_mpa": 200000.})["E_mpa"],
            200000.,
        )
        self.assertEqual(
            FRAME_OVERRIDE_TARGETS["frame.rebar_fy_mpa"],
            "fy_rebar_mpa",
        )
        with self.assertRaisesRegex(ValueError, "residual strength"):
            validate_frame_section_parameters({
                "cover_fc_mpa": 30., "cover_fcu_mpa": 35.,
                "cover_epsc0": -.002, "cover_epsU": -.006,
                "core_fcc_mpa": 40., "core_fpcu_mpa": 0.,
                "core_epsc0": -.002, "core_epsU": -.006,
            })
        for values in (
            {"brace.fy_mpa": float("nan")},
            {"brace.b": .6},
            {"unknown.parameter": 1.},
            {"wall.fpcc_mpa": 55.},
            {"wall.fyn_mpa": -500.},
            {"brace.fy_mpa": True},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                validate_material_overrides(values)

    def test_building_sensitivity_batch_exports_comparable_case_metrics(self):
        def fake_run(config):
            value = config["material_overrides"]["brace.fy_mpa"]
            return {"cases": [{
                "orientation": "XY",
                "status": "COMPLETED_TRUNCATED_TRIAL",
                "physical_time_s": .1,
                "full_record_duration_s": 40.94,
                "peak_roof_UX_m": value / 100000.,
                "peak_roof_UY_m": 0.0,
                "terminal_roof_UX_m": .001,
                "terminal_roof_UY_m": 0.0,
                "residual_roof_UX_m": None,
                "residual_roof_UY_m": None,
                "max_story_drift_X": .0001,
                "max_story_drift_Y": 0.0,
                "max_floor_edge_drift_X": .0002,
                "max_floor_edge_drift_Y": .0001,
                "peak_base_shear_X_kN": 100.,
                "peak_base_shear_Y_kN": 0.0,
                "peak_floor_relative_accel_X_m_s2": .2,
                "peak_floor_relative_accel_Y_m_s2": 0.0,
            }]}

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "model"
            source.mkdir()
            config = {
                "model_folder": str(source),
                "output_dir": str(root / "sweep"),
                "nonlinear_walls": True,
                "limit_state": "ULS",
                "sensitivity_parameter": "brace.fy_mpa",
                "sensitivity_values": [345., 379.5],
            }
            with patch(
                "components.nonlinear_time_history.building_exploratory.run",
                side_effect=fake_run,
            ):
                result = _run_material_sensitivity(config)
            self.assertEqual(result["status"], "COMPLETED")
            with (root / "sweep" / "Material_Sensitivity_Comparison.csv").open(
                    encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([float(row["candidate_value"]) for row in rows],
                             [345., 379.5])
            self.assertEqual(rows[0]["residual_roof_UX_m"], "")
            summary = json.loads(
                (root / "sweep" / "Material_Sensitivity_Summary.json").read_text())
            self.assertEqual(summary["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
