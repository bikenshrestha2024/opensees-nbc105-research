import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.validation.material_sensitivity import build_case_matrix, write_case_matrix
from OpenSees_Nonlinear_Time_History_NBC105_V116 import (
    LINEAR_SYSTEMS,
    _configure_nonlinear_transient,
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


if __name__ == "__main__":
    unittest.main()
