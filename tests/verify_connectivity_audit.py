import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("load_connection_audit", ROOT / "20_AUDIT_LOAD_CONNECTIONS.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ConnectivityAuditChecks(unittest.TestCase):
    def test_reports_brace_and_wall_sharing_and_missing_nodes(self):
        data = {
            "nodes": {"1": [0, 0, 0], "2": [1, 0, 0], "3": [0, 1, 0], "4": [0, 0, 1]},
            "frames": [
                {"object": "brace", "category": "BRACE", "nodes": [1, 2]},
                {"object": "column", "category": "COLUMN", "nodes": [1, 4]},
            ],
            "shells": [
                {"object": "floor", "category": "FLOOR", "nodes": [1, 2, 3, 99]},
                {"object": "wall-a", "category": "SHEAR WALL", "nodes": [1, 3, 4, 99]},
                {"object": "wall-b", "category": "SHEAR WALL", "nodes": [1, 2, 4]},
                {"object": "wall-c", "category": "SHEAR WALL", "nodes": [2, 3, 4]},
            ],
            "supports": {"1": [1, 1, 1, 1, 1, 1]},
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            folder = Path(temp)
            (folder / "OpenSees_Complete_Model_Data_V118.json").write_text(json.dumps(data), encoding="utf-8")
            result = AUDIT.audit(folder)

        floor = result["slabs"][0]
        self.assertEqual(floor["shared_brace_nodes"], 2)
        self.assertEqual(result["walls"][0]["shared_other_wall_object_nodes"], 3)
        self.assertTrue(result["wall_object_connectivity"])
        self.assertEqual(result["summary"]["missing_node_reference_count"], 2)
        self.assertIn("does not prove a disconnected", result["scope"])

    def test_no_direct_wall_sharing_is_reported_as_review_not_failure(self):
        data = {
            "nodes": {
                "1": [0, 0, 0], "2": [1, 0, 0], "3": [0, 1, 0], "4": [1, 1, 0],
                "5": [2, 0, 0], "6": [3, 0, 0], "7": [2, 1, 0], "8": [3, 1, 0],
            },
            "frames": [],
            "shells": [
                {"object": "wall-a", "category": "SHEAR WALL", "nodes": [1, 2, 3, 4]},
                {"object": "wall-b", "category": "SHEAR WALL", "nodes": [5, 6, 7, 8]},
            ],
            "supports": {},
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            folder = Path(temp)
            (folder / "OpenSees_Complete_Model_Data_V118.json").write_text(json.dumps(data), encoding="utf-8")
            result = AUDIT.audit(folder)
        self.assertTrue(all(not row["shared_other_wall_object_nodes"] for row in result["walls"]))
        self.assertTrue(all(row["status"].startswith("no direct shared") for row in result["wall_object_connectivity"]))
        self.assertEqual(result["summary"]["missing_node_reference_count"], 0)


if __name__ == "__main__":
    unittest.main()
