import unittest
from PIL import Image

from sama_display import WIDTH, HEIGHT
from sama_display.playback import DisplayFrame, play_frames


class FakeController:
    def __init__(self):
        self.images = []
        self.updates = []

    def display(self, image, **_kwargs):
        self.images.append(image)

    def update_frame(self, previous, current, frame_id, **_kwargs):
        self.updates.append((previous, current, frame_id))
        return True


class InterruptingController:
    def display(self, _image, **kwargs):
        self.cancelled = kwargs["cancelled"]
        raise InterruptedError("cancelled between transfer blocks")


class PlaybackTests(unittest.TestCase):
    def test_frame_limit(self):
        controller = FakeController()
        frames = [DisplayFrame(Image.new("RGB", (WIDTH, HEIGHT)), 0, index) for index in range(4)]
        stats = play_frames(controller, frames, max_frames=2)
        self.assertEqual(stats.frames, 2)
        self.assertEqual(len(controller.images), 1)
        self.assertEqual(len(controller.updates), 1)
        self.assertEqual(controller.updates[0][2], 0)

    def test_cancel_before_first_frame(self):
        controller = FakeController()
        frames = [DisplayFrame(Image.new("RGB", (WIDTH, HEIGHT)), 0, 0)]
        stats = play_frames(controller, frames, cancelled=lambda: True)
        self.assertEqual(stats.frames, 0)
        self.assertEqual(controller.images, [])

    def test_cancel_during_frame_stops_cleanly(self):
        controller = InterruptingController()
        frames = [DisplayFrame(Image.new("RGB", (WIDTH, HEIGHT)), 0, 0)]
        checks = iter((False, True))
        stats = play_frames(controller, frames, cancelled=lambda: next(checks, True))
        self.assertEqual(stats.frames, 0)


if __name__ == "__main__":
    unittest.main()
