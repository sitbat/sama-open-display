import unittest

from sama_display import WIDTH, HEIGHT
from sama_display.render import dashboard_frame, hardware_test_card, text_frame


class RenderTests(unittest.TestCase):
    def test_dashboard_size(self):
        self.assertEqual(dashboard_frame().size, (WIDTH, HEIGHT))

    def test_text_size(self):
        self.assertEqual(text_frame("test").size, (WIDTH, HEIGHT))

    def test_hardware_card_geometry_and_channels(self):
        card = hardware_test_card()
        self.assertEqual(card.size, (WIDTH, HEIGHT))
        self.assertEqual(card.getpixel((50, 230)), (255, 0, 0))
        self.assertEqual(card.getpixel((WIDTH - 50, 230)), (0, 255, 0))
        self.assertEqual(card.getpixel((50, HEIGHT - 50)), (0, 0, 255))
        self.assertEqual(card.getpixel((WIDTH - 50, HEIGHT - 50)), (255, 255, 0))


if __name__ == "__main__":
    unittest.main()
