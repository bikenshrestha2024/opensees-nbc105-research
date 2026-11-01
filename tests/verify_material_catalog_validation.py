import json
import unittest
from pathlib import Path

from components.validation.parameter_studies import SCHEMAS, card, check


ROOT = Path(__file__).resolve().parents[1]


class MaterialCatalogValidationTests(unittest.TestCase):
    def test_all_supported_material_cards_pass_input_validation(self):
        for model in SCHEMAS:
            with self.subTest(model=model):
                check(card(model))

    def test_invalid_material_inputs_are_rejected(self):
        cases = (
            ("Concrete01", "epsU", -0.001),
            ("Concrete02", "unloading_ratio", 1.1),
            ("ConcreteCM", "Ec", 0.0),
            ("Steel02", "R0", 0.0),
            ("SteelMPF", "cR1", 0.0),
            ("FVD", "alpha", 1.1),
            ("BRB", "core_area_m2", 0.0),
            ("SFI_MVLEM_3D", "fibers", 1),
        )
        for model, key, value in cases:
            data = card(model)
            data["parameters"][key] = value
            with self.subTest(model=model, key=key), self.assertRaises(ValueError):
                check(data)

    def test_esfi_patch_uses_documented_transition_and_peer_card_stays_exact(self):
        patch = json.loads(
            (ROOT / "Material_Catalog" / "PEER_Web_ESFI_Patch.json").read_text(
                encoding="utf-8-sig"
            )
        )
        peer = json.loads(
            (ROOT / "Material_Catalog" / "PEER_Web_SteelMPF.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(patch["wall_steel"]["cR1"], 0.925)
        self.assertEqual(patch["wall_steel"]["cR2"], 0.0015)
        self.assertEqual(peer["parameters"]["cR1"], 18.5)
        self.assertEqual(peer["parameters"]["cR2"], 0.0015)
        self.assertTrue(
            patch["provenance"]["steel_cR1"]["source"].startswith(
                "https://openseespydoc.readthedocs.io/"
            )
        )


if __name__ == "__main__":
    unittest.main()
