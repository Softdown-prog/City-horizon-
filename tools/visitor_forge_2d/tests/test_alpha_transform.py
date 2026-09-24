"""Regression for colored RGB hidden behind transparent source pixels."""

import unittest

from PIL import Image

from visitor_forge_2d.core import LayerComposer


class AlphaTransformTests(unittest.TestCase):
    def test_transparent_source_color_does_not_bleed_into_articulated_edge(self) -> None:
        part = Image.new("RGBA", (16, 16), (255, 0, 0, 0))
        part.putpixel((7, 7), (0, 0, 255, 255))

        transformed = LayerComposer._transform_canvas(part, (1, 0, 0.5, 0, 1, 0.5))
        edge_pixels = [
            transformed.getpixel((x, y))
            for y in range(transformed.height)
            for x in range(transformed.width)
            if 0 < transformed.getpixel((x, y))[3] < 255
        ]

        self.assertTrue(edge_pixels)
        self.assertTrue(all(red == 0 and green == 0 and blue > 0 for red, green, blue, _ in edge_pixels))


if __name__ == "__main__":
    unittest.main()
