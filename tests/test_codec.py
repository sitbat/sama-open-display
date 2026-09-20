import unittest
from PIL import Image

from sama_display.codec import (
    changed_region, chunks, encode_full_frame, image_to_bgra,
    prepare_transfer_frame, rotate_for_panel,
)


class CodecTests(unittest.TestCase):
    def test_chunks(self):
        self.assertEqual(list(chunks(b"1234567", 3)), [b"123", b"456", b"7"])

    def test_bgra_order(self):
        image = Image.new("RGBA", (1, 1), (0x11, 0x22, 0x33, 0x44))
        self.assertEqual(image_to_bgra(image), b"\x33\x22\x11\x44")

    def test_full_frame_inserts_separator(self):
        image = Image.new("RGB", (5, 13), "red")
        encoded = encode_full_frame(image, 5, 13, panel_rotation=0)
        self.assertEqual(len(encoded), 5 * 13 * 4 + 1)
        self.assertEqual(encoded[249], 0)

    def test_clockwise_panel_rotation(self):
        image = Image.new("RGB", (2, 3), "black")
        image.putpixel((0, 0), (255, 0, 0))
        image.putpixel((0, 2), (0, 0, 255))
        rotated = rotate_for_panel(image, 90)
        self.assertEqual(rotated.size, (3, 2))
        self.assertEqual(rotated.getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(rotated.getpixel((2, 0)), (255, 0, 0))

    def test_landscape_canvas_becomes_portrait_scan_buffer(self):
        canvas = Image.new("RGB", (1568, 720), "red")
        canvas.putpixel((0, 0), (0, 255, 0))
        prepared = prepare_transfer_frame(canvas)
        self.assertEqual(prepared.size, (720, 1568))
        simulated_panel = prepared.transpose(Image.Transpose.ROTATE_90)
        self.assertEqual(simulated_panel.size, canvas.size)
        self.assertEqual(simulated_panel.tobytes(), canvas.tobytes())

    def test_portrait_canvas_cannot_be_rotated_after_layout(self):
        with self.assertRaisesRegex(ValueError, "canvas must be 1568x720"):
            prepare_transfer_frame(Image.new("RGB", (720, 1568)))

    def test_changed_region(self):
        before = Image.new("RGB", (20, 30), "black")
        after = before.copy()
        for x in range(5, 9):
            for y in range(7, 12):
                after.putpixel((x, y), (255, 0, 0))
        region = changed_region(before, after, margin=1)
        self.assertEqual((region.x, region.y, region.image.size), (4, 6, (6, 7)))
        self.assertIsNone(changed_region(after, after))

    def test_changed_region_requires_equal_sizes(self):
        with self.assertRaises(ValueError):
            changed_region(Image.new("RGB", (1, 1)), Image.new("RGB", (2, 2)))


if __name__ == "__main__":
    unittest.main()
