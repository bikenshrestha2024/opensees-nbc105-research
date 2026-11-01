import unittest

from components.nonlinear_time_history.research_building_materials import (
    _steelmpf_transition,
)


class SteelMPFTransitionTests(unittest.TestCase):
    def test_documented_transition_retains_peer_cR2(self):
        transition = _steelmpf_transition("OPENSEES_DOCUMENTED")
        self.assertEqual(transition["R0"], 20.0)
        self.assertEqual(transition["cR1"], 0.925)
        self.assertEqual(transition["cR2"], 0.0015)
        self.assertIn("author-documented", transition["basis"])

    def test_peer_appendix_transition_is_available_exactly(self):
        transition = _steelmpf_transition("PEER_APPENDIX_EXACT")
        self.assertEqual(transition["R0"], 20.0)
        self.assertEqual(transition["cR1"], 18.5)
        self.assertEqual(transition["cR2"], 0.0015)
        self.assertIn("exact printed", transition["basis"])

    def test_unknown_transition_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Unknown SteelMPF transition"):
            _steelmpf_transition("UNRECOGNIZED")


if __name__ == "__main__":
    unittest.main()
