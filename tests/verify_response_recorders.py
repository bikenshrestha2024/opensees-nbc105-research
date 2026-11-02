import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.modal.analysis import (
    export_story_mode_shapes,
    modal_response_nodes,
)
from components.shared.response_recorders import (
    append_base_shear,
    frame_solver_tag_catalog,
    selected_member_response,
    support_resultants,
    write_base_shear_roof_curve,
)
from OpenSees_Analysis_Stack_V110 import run_gravity_stage


class RecorderOps:
    def __init__(self):
        self.time = 0.0
        self.increment = 0.5

    def reactions(self):
        pass

    def nodeReaction(self, node, dof):
        return {1: {1: -10.0, 3: 10.0}}.get(node, {}).get(dof, 0.0) * self.time

    def nodeEigenvector(self, node, mode, dof):
        return float(node * mode * dof)

    def wipeAnalysis(self):
        pass

    def constraints(self, *_):
        pass

    def numberer(self, *_):
        pass

    def system(self, *_):
        pass

    def test(self, *_):
        pass

    def algorithm(self, *_):
        pass

    def integrator(self, _, increment):
        self.increment = float(increment)

    def analysis(self, *_):
        pass

    def analyze(self, _):
        self.time += self.increment
        return 0

    def getTime(self):
        return self.time

    def nodeDisp(self, node, dof=None):
        result = [0.0, 0.0, -0.01 * self.time, 0.0, 0.0, 0.0]
        return result if dof is None else result[dof - 1]

    def nodeCoord(self, node):
        return [float(node), 0.0, 3.0 * node]

    def getNodeTags(self):
        return [1, 2]

    def loadConst(self, *_):
        pass


class ResponseRecorderTests(unittest.TestCase):
    def test_support_resultants_and_base_shear_are_signed_and_incremental(self):
        ops = RecorderOps()
        ops.time = 1.0
        baseline = support_resultants(ops, [1])
        ops.time = 2.0
        row = {"time_s": 0.1, "Storey_1_UX_m": 0.02,
               "Storey_1_UY_m": 0.0}
        append_base_shear(row, ops, [1], baseline)
        self.assertEqual(row["base_shear_X_kN"], 10.0)
        self.assertEqual(row["base_shear_Y_kN"], 0.0)
        self.assertEqual(row["support_reaction_Fz_kN"], 10.0)
        with tempfile.TemporaryDirectory() as folder:
            path = write_base_shear_roof_curve(
                Path(folder) / "curve.csv", [row], "Storey_1")
            with path.open(encoding="utf-8-sig", newline="") as stream:
                saved = next(csv.DictReader(stream))
            self.assertEqual(float(saved["roof_UX_m"]), 0.02)
            self.assertEqual(float(saved["base_shear_X_kN"]), 10.0)

    def test_modal_nodes_include_master_and_floor_extremes(self):
        data = {
            "nodes": {
                "1": [0.0, 0.0, 0.0],
                "2": [5.0, 0.0, 3.0],
                "3": [-5.0, 0.0, 3.0],
                "4": [0.0, -2.0, 3.0],
                "5": [0.0, 2.0, 3.0],
                "6": [0.0, 0.0, 3.0],
            },
            "diaphragms": [{
                "storey_number": 1, "master_tag": 6,
                "master_xyz": [0.0, 0.0, 3.0],
                "slave_node_tags": [2, 3, 4, 5],
            }],
        }
        selected = modal_response_nodes(data)
        self.assertEqual({row["role"] for row in selected},
                         {"master", "x_min", "x_max", "y_min", "y_max"})
        with tempfile.TemporaryDirectory() as folder:
            path = export_story_mode_shapes(
                RecorderOps(), [4.0], [3.14159], selected, folder)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), len(selected))
            self.assertEqual({row["mode"] for row in rows}, {"1"})
            self.assertTrue(all(float(row["translation_normalization"]) > 0
                                for row in rows))

    def test_gravity_writes_converged_step_and_response_recorders(self):
        ops = RecorderOps()
        with tempfile.TemporaryDirectory() as folder:
            result = run_gravity_stage(
                ops, [1], 10.0, model_nodes=[1, 2], nsteps=2,
                response_output_dir=folder,
                story_masters=[{"story_name": "Storey_1", "node": 2}],
            )
            self.assertTrue(result["gravity_frozen"])
            with (Path(folder) / "Gravity_Load_Settlement.csv").open(
                    encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertAlmostEqual(float(rows[-1]["load_factor"]), 1.0)
            self.assertTrue((Path(folder) / "Gravity_Support_Reactions.csv").is_file())
            self.assertTrue((Path(folder) / "Gravity_Node_Displacements.csv").is_file())
            self.assertTrue((Path(folder) / "Response_Recorder_Index.json").is_file())

    def test_selected_member_force_and_gravity_relative_axial_extension(self):
        class MemberOps:
            def nodeDisp(self, node):
                return {1: [0.1, 0., 0., 0., 0., 0.],
                        2: [0.3, 0., 0., 0., 0., 0.]}[node]

            def eleResponse(self, tag, response):
                self.assertion = (tag, response)
                return [125., -125.]

        ops = MemberOps()
        response = selected_member_response(
            ops, 42, [1, 2],
            {"1": [0., 0., 0.], "2": [2., 0., 0.]},
            {1: [0., 0., 0., 0., 0., 0.],
             2: [0.05, 0., 0., 0., 0., 0.]},
        )
        self.assertAlmostEqual(response["axial_extension_m"], .15)
        self.assertEqual(response["local_end_forces_kN_kNm"], [125., -125.])
        self.assertEqual(ops.assertion, (42, "localForce"))

    def test_selected_truss_can_use_axial_force_response(self):
        class TrussOps:
            def nodeDisp(self, node):
                return [0., 0., 0., 0., 0., 0.]

            def eleResponse(self, tag, response):
                return [] if response == "localForce" else 85.

        response = selected_member_response(
            TrussOps(), 7, [1, 2], {1: [0., 0., 0.], 2: [0., 3., 0.]},
            {1: [0., 0., 0., 0., 0., 0.],
             2: [0., 0., 0., 0., 0., 0.]},
        )
        self.assertEqual(response["local_end_forces_kN_kNm"], [85., -85.])
        self.assertEqual(response["axial_extension_m"], 0.)

    def test_frame_solver_tag_catalog_maps_to_source_objects(self):
        catalog = frame_solver_tag_catalog([
            {"object": "ETABS-1", "category": "BRACE",
             "properties": {"section": "SHS"}, "nodes": [10, 11],
             "release_i": True, "release_j": True},
            {"object": "ETABS-2", "category": "BEAM",
             "properties": {"section": "RC"}, "nodes": [11, 12]},
        ])
        self.assertEqual(catalog[0]["solver_tag"], 100001)
        self.assertEqual(catalog[0]["source_object"], "ETABS-1")
        self.assertEqual(catalog[1]["solver_tag"], 100002)
        self.assertEqual(catalog[1]["release_i"], False)


if __name__ == "__main__":
    unittest.main()
