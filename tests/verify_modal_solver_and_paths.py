import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from components.model.load_and_diaphragm_audit import (
    implementation_digest,
    modal_numeric_digest,
)
from components.shared.eigen_solver import solve_eigen


class FakeOpenSees:
    def __init__(self, native_result=None, native_error=None, node_count=3):
        self.native_result=native_result
        self.native_error=native_error
        self.node_count=node_count
        self.calls=[]

    def getNodeTags(self):
        return list(range(self.node_count))

    def getEleTags(self):
        return [1]

    def eigen(self, *args):
        self.calls.append(args)
        if args[0]=="PythonSparse":
            return [1.0,2.0]
        if self.native_error:
            raise self.native_error
        return self.native_result


class ModalSolverAndPathTests(unittest.TestCase):
    def test_native_solver_failure_falls_back_to_python_sparse(self):
        ops=FakeOpenSees(native_error=RuntimeError("native eigensolver error"))
        self.assertEqual(solve_eigen(ops,2,"-genBandArpack"),[1.0,2.0])
        self.assertEqual([call[0] for call in ops.calls],["-genBandArpack","PythonSparse"])

    def test_fullgen_is_skipped_for_building_scale_model(self):
        ops=FakeOpenSees(node_count=11097)
        self.assertEqual(solve_eigen(ops,2,"-fullGenLapack"),[1.0,2.0])
        self.assertEqual([call[0] for call in ops.calls],["PythonSparse"])

    def test_partial_native_result_falls_back(self):
        ops=FakeOpenSees(native_result=[1.0])
        self.assertEqual(solve_eigen(ops,2,"-genBandArpack"),[1.0,2.0])
        self.assertEqual([call[0] for call in ops.calls],["-genBandArpack","PythonSparse"])

    def test_fingerprints_accept_project_components_and_facade_anchors(self):
        self.assertEqual(implementation_digest(ROOT),implementation_digest(ROOT/"components"))
        self.assertEqual(modal_numeric_digest(ROOT),modal_numeric_digest(ROOT/"components"))
        self.assertEqual(modal_numeric_digest(ROOT),modal_numeric_digest(Path.home()))


if __name__=="__main__":
    unittest.main()
