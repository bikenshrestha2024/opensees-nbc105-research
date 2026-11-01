import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.nonlinear_time_history.runner_and_gui import (
    _advance_nonlinear_interval,
)


class FakeOps:
    def __init__(self, return_codes, nonfinite=False):
        self.return_codes = iter(return_codes)
        self.nonfinite = nonfinite
        self.time = 0.0

    def analyze(self, _steps, dt):
        code = next(self.return_codes)
        if code == 0:
            self.time += dt
        return code

    def algorithm(self, _name):
        pass

    def test(self, *_args):
        pass

    def testIter(self):
        return 1

    def getTime(self):
        return self.time

    def getNodeTags(self):
        return [1]

    def nodeDisp(self, _tag):
        return [0.0] * 6

    def getEleTags(self):
        return [110280]

    def eleResponse(self, _tag, *args):
        if self.nonfinite and args == ("localForce",):
            return [math.nan]
        return [0.0]


class FailureEvidenceTests(unittest.TestCase):
    def test_nonfinite_failure_writes_source_mapped_evidence_before_stopping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            map_path = root / "element_map.json"
            map_path.write_text(
                json.dumps({"AREA:354": [110280]}), encoding="utf-8"
            )
            evidence_path = root / "First_Step_Failure_Evidence.json"
            with self.assertRaisesRegex(RuntimeError, "evidence saved to"):
                _advance_nonlinear_interval(
                    FakeOps([-3], nonfinite=True),
                    0.005,
                    diagnostics={
                        "evidence_output_path": str(evidence_path),
                        "element_map_path": str(map_path),
                    },
                )
            report = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(report["algorithm"], "Newton")
            self.assertEqual(report["nonfinite_elements"][0]["source"], "AREA:354")
            self.assertEqual(report["nonfinite_elements"][0]["tag"], 110280)
            self.assertTrue(report["warning"].startswith("Post-failure responses"))

    def test_recovered_fallback_removes_stale_failure_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            evidence_path = Path(folder) / "First_Step_Failure_Evidence.json"
            result = _advance_nonlinear_interval(
                FakeOps([-3, 0]),
                0.005,
                diagnostics={"evidence_output_path": str(evidence_path)},
            )
            self.assertEqual(result, 1)
            self.assertFalse(evidence_path.exists())


if __name__ == "__main__":
    unittest.main()
