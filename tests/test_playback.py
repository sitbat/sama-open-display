import unittest
from PIL import Image

from sama_display import WIDTH, HEIGHT
from sama_display.media import MediaFrame
from sama_display.playback import play_frames


class FakeController:
    def __init__(self):
        self.images = []

    def display(self, image, **_kwargs):
        self.images.append(image)


class PlaybackTests(unittest.TestCase):
    def test_frame_limit(self):
        controller = FakeController()
        frames = [MediaFrame(Image.new("RGB", (WIDTH, HEIGHT)), 0, index) for index in range(4)]
        stats = play_frames(controller, frames, max_frames=2)
        self.assertEqual(stats.frames, 2)
        self.assertEqual(len(controller.images), 2)

    def test_cancel_before_first_frame(self):
        controller = FakeController()
        frames = [MediaFrame(Image.new("RGB", (WIDTH, HEIGHT)), 0, 0)]
        stats = play_frames(controller, frames, cancelled=lambda: True)
        self.assertEqual(stats.frames, 0)
        self.assertEqual(controller.images, [])


if __name__ == "__main__":
    unittest.main()

