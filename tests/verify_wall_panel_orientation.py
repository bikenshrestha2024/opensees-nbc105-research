import unittest

from components.model.assembly import _cross, _sub, _wall_panel_nodes


class WallPanelOrientationTests(unittest.TestCase):
    def test_wall_panels_are_bottom_first_and_counterclockwise(self):
        panels = (
            [[0.0, 0.0, 0.0], [0.4, 0.0, 0.0],
             [0.4, 0.0, 2.3], [0.0, 0.0, 2.3]],
            [[0.4, 0.0, 0.0], [0.0, 0.0, 0.0],
             [0.0, 0.0, 2.3], [0.4, 0.0, 2.3]],
        )
        for panel in panels:
            with self.subTest(panel=panel):
                ordered = _wall_panel_nodes(panel, "test")
                self.assertEqual([point[2] for point in ordered[:2]], [0.0, 0.0])
                normal = _cross(
                    _sub(ordered[1], ordered[0]),
                    _sub(ordered[3], ordered[0]),
                )
                dominant = max(range(3), key=lambda index: abs(normal[index]))
                self.assertGreater(normal[dominant], 0.0)

    def test_rotated_wall_quad_is_started_at_its_bottom_edge(self):
        panel = [
            [0.0, 0.0, 2.3], [0.0, 0.0, 0.0],
            [0.4, 0.0, 0.0], [0.4, 0.0, 2.3],
        ]
        ordered = _wall_panel_nodes(panel, "rotated")
        self.assertEqual([point[2] for point in ordered[:2]], [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
