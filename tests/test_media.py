import tempfile
import unittest
from pathlib import Path
from PIL import Image

from sama_display.media import iter_gif, iter_video


class MediaTests(unittest.TestCase):
    def test_animated_gif_frames_and_timing(self):
        frames = [Image.new("RGB", (8, 12), color) for color in ("red", "blue")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "sample.gif")
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=[80, 120], loop=0)
            decoded = list(iter_gif(path, size=(72, 156), fit="contain"))
        self.assertEqual(len(decoded), 2)
        self.assertEqual([frame.duration_ms for frame in decoded], [80, 120])
        self.assertTrue(all(frame.image.size == (72, 156) for frame in decoded))

    def test_video_decode_and_throttle(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("optional OpenCV video support is not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "sample.avi")
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 20, (16, 12))
            if not writer.isOpened():
                self.skipTest("OpenCV video writer is unavailable")
            for value in range(8):
                writer.write(np.full((12, 16, 3), value * 20, dtype=np.uint8))
            writer.release()
            decoded = list(iter_video(path, size=(72, 156), fit="contain", max_fps=5))
        self.assertEqual(len(decoded), 2)
        self.assertTrue(all(frame.duration_ms == 200 for frame in decoded))
        self.assertTrue(all(frame.image.size == (72, 156) for frame in decoded))


if __name__ == "__main__":
    unittest.main()
