import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from OpenSees_Analysis_Stack_V110 import (
    run_gravity_stage,
    save_gravity_diagnostics,
)


class FakeOps:
    def __init__(self):
        self.time = 0.0
        self.load_step = 0.05
        self.system_args = None

    def getTime(self):
        return self.time

    def wipeAnalysis(self):
        pass

    def constraints(self, *_):
        pass

    def numberer(self, *_):
        pass

    def system(self, *args):
        self.system_args = args

    def test(self, *_):
        pass

    def algorithm(self, *_):
        pass

    def integrator(self, _, increment):
        self.load_step = increment

    def analysis(self, *_):
        pass

    def analyze(self, *_):
        if self.time + self.load_step <= 0.15 + 1e-12:
            self.time += self.load_step
            return 0
        return -3

    def getNodeTags(self):
        return [1, 2]

    def nodeDisp(self, tag):
        return [float("nan"), 0.0, 0.0] if tag == 2 else [0.0, 0.0, -0.01]

    def getEleTags(self):
        return [11, 12]

    def eleResponse(self, tag, response):
        if tag == 11 and response == "localForce":
            return [1.0, 2.0]
        if tag == 12 and response == "localForce":
            raise RuntimeError("response not available")
        if tag == 12 and response == "basicDeformation":
            return [float("inf")]
        return None


class GravityFailureDiagnosticsTests(unittest.TestCase):
    def test_snapshot_contains_solver_state_and_anomalies(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Gravity_Failure_Diagnostics_ULS.json"
            result = save_gravity_diagnostics(
                FakeOps(), path, last_committed_factor=0.15,
                attempted_factor=0.20, return_code=-3,
                system="SparseGeneral", system_options=("-piv",),
                element_labels={12: {
                    "source_object": "355",
                    "category": "SHEAR WALL",
                    "property": "Wall 600",
                }},
            )
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(result["last_committed_load_factor"], 0.15)
            self.assertEqual(saved["attempted_load_factor"], 0.20)
            self.assertEqual(saved["linear_system_options"], ["-piv"])
            self.assertEqual(saved["nodes_scanned"], 2)
            self.assertEqual(saved["elements_scanned"], 2)
            self.assertEqual(saved["nonfinite_nodes"][0]["tag"], 2)
            self.assertEqual(saved["nonfinite_element_responses"][0]["tag"], 12)
            self.assertEqual(
                saved["nonfinite_element_responses"][0]["model_element"]["source_object"],
                "355",
            )
            self.assertEqual(saved["element_response_errors"][0]["tag"], 12)
            self.assertIn("not a stiffness", saved["scope"])
            self.assertTrue(math.isfinite(
                saved["largest_displacement_nodes"][0]["translation_norm_model_units"]
            ))

    def test_adaptive_gravity_writes_first_failure_and_all_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Gravity_Failure_Diagnostics_ULS.json"
            ops = FakeOps()
            with self.assertRaisesRegex(RuntimeError, "factor 0.15"):
                run_gravity_stage(
                    ops, [1], 100.0, nsteps=20, adaptive=True,
                    system="SparseGeneral", system_options=("-piv",),
                    diagnostic_path=path,
                    element_labels={12: {
                        "source_object": "355",
                        "category": "SHEAR WALL",
                        "property": "Wall 600",
                    }},
                )
            report = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(ops.system_args, ("SparseGeneral", "-piv"))
            self.assertAlmostEqual(report["last_committed_load_factor"], 0.15)
            self.assertAlmostEqual(report["attempted_load_factor"], 0.20)
            self.assertEqual(len(report["failed_attempts"]), 8)
            self.assertEqual(
                report["nonfinite_element_responses"][0]["model_element"]["source_object"],
                "355",
            )


if __name__ == "__main__":
    unittest.main()
