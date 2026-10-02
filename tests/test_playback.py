import unittest
from unittest.mock import patch

from PIL import Image

from sama_display.playback import DisplayFrame, play_frames


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []
        self.oversleep = 0.0
        self.on_sleep = None

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.advance(seconds + self.oversleep)
        if self.on_sleep:
            self.on_sleep()


class FakeController:
    def __init__(self, clock, transfer_seconds=0.1, changes=None):
        self.clock = clock
        self.transfer_seconds = transfer_seconds
        self.changes = iter(changes) if changes is not None else None
        self.images = []
        self.updates = []
        self.completed = []

    def _complete(self):
        self.clock.advance(self.transfer_seconds)
        self.completed.append(self.clock.now)

    def display(self, image, **_kwargs):
        self.images.append(image)
        self._complete()

    def update_frame(self, previous, current, frame_id, **_kwargs):
        self.updates.append((previous, current, frame_id))
        self._complete()
        return next(self.changes) if self.changes is not None else True


class InterruptingController:
    def __init__(self, signal_cancellation=True):
        self.signal_cancellation = signal_cancellation
        self.cancelled = False
        self.entered = False

    def display(self, _image, **kwargs):
        self.entered = True
        self.cancelled = self.signal_cancellation
        raise InterruptedError("cancelled between transfer blocks")


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.starts = []
        clock_patch = patch("sama_display.playback.monotonic", self.clock.monotonic)
        sleep_patch = patch("sama_display.playback.sleep", self.clock.sleep)
        clock_patch.start()
        sleep_patch.start()
        self.addCleanup(clock_patch.stop)
        self.addCleanup(sleep_patch.stop)

    def frames(self, count, durations=None, sampling=None):
        for index in range(count):
            self.starts.append(self.clock.now)
            self.clock.advance(sampling[index] if sampling is not None else 0.08)
            duration = durations[index] if durations is not None else 1000
            yield DisplayFrame(Image.new("RGB", (2, 2), (index, 0, 0)), duration, index)

    def assertTimes(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for observed, target in zip(actual, expected):
            self.assertAlmostEqual(observed, target, places=7)

    def test_sampling_and_transfer_share_frame_budget(self):
        controller = FakeController(self.clock)
        stats = play_frames(controller, self.frames(3), max_frames=3)
        self.assertTimes(self.starts, [0, 1, 2])
        self.assertTimes(controller.completed, [0.18, 1.18, 2.18])
        self.assertAlmostEqual(stats.startup_seconds, 0.18)
        self.assertAlmostEqual(stats.steady_elapsed_seconds, 1.0)
        self.assertAlmostEqual(stats.steady_fps, 1.0)
        self.assertAlmostEqual(stats.elapsed_seconds, 2.18)
        self.assertAlmostEqual(stats.effective_fps, 3 / 2.18)

    def test_slow_startup_and_later_frame_do_not_accumulate_catch_up(self):
        controller = FakeController(self.clock)
        stats = play_frames(
            controller,
            self.frames(5, sampling=[7.9, 0.08, 1.3, 0.08, 0.08]),
            max_frames=5,
        )
        self.assertTimes(self.starts, [0, 8, 9, 10.4, 11.4])
        self.assertTimes(controller.completed, [8, 8.18, 10.4, 10.58, 11.58])
        self.assertAlmostEqual(stats.startup_seconds, 8.0)
        self.assertAlmostEqual(stats.steady_elapsed_seconds, 3.4)
        self.assertAlmostEqual(stats.steady_fps, 3 / 3.4)

    def test_sleep_overshoot_uses_actual_clock_and_next_frame_start(self):
        self.clock.oversleep = 0.02
        controller = FakeController(self.clock)
        play_frames(controller, self.frames(3), max_frames=3)
        self.assertEqual(len(self.starts), 3)
        for previous, current in zip(self.starts, self.starts[1:]):
            self.assertGreaterEqual(current - previous, 1.0 - 1e-9)
            self.assertLessEqual(current - previous, 1.02 + 1e-9)
        self.assertTrue(self.clock.sleeps)
        self.assertTrue(all(0 < seconds <= 0.05 for seconds in self.clock.sleeps))

    def test_each_frame_uses_its_own_duration(self):
        controller = FakeController(self.clock)
        play_frames(controller, self.frames(4, durations=[1000, 500, 2000, 0]), max_frames=4)
        self.assertTimes(self.starts, [0, 1, 1.5, 3.5])

    def test_frame_limit(self):
        controller = FakeController(self.clock)
        stats = play_frames(controller, self.frames(4), max_frames=2)
        self.assertEqual(stats.frames, 2)
        self.assertTimes(self.starts, [0, 1])
        self.assertEqual(len(controller.images), 1)
        self.assertEqual(len(controller.updates), 1)
        self.assertEqual(controller.updates[0][2], 0)
        self.assertAlmostEqual(self.clock.now, 1.18)
        self.assertIsNone(stats.steady_fps)

    def test_zero_limit_and_short_sequences_have_no_steady_rate(self):
        for count, limit in [(4, 0), (0, None), (1, None), (2, None)]:
            with self.subTest(count=count, limit=limit):
                self.clock.now = 0.0
                self.starts.clear()
                controller = FakeController(self.clock)
                stats = play_frames(controller, self.frames(count), max_frames=limit)
                expected = 0 if limit == 0 else count
                self.assertEqual(stats.frames, expected)
                self.assertEqual(len(self.starts), expected)
                self.assertIsNone(stats.steady_fps)
                self.assertEqual(stats.steady_elapsed_seconds, 0.0)
                if expected == 0:
                    self.assertIsNone(stats.startup_seconds)
                else:
                    self.assertAlmostEqual(stats.startup_seconds, 0.18)

    def test_cancel_before_first_frame(self):
        controller = FakeController(self.clock)
        stats = play_frames(controller, self.frames(1), cancelled=lambda: True)
        self.assertEqual(stats.frames, 0)
        self.assertEqual(self.starts, [])
        self.assertEqual(controller.images, [])

    def test_cancel_after_sampling_does_not_send_frame(self):
        controller = FakeController(self.clock)
        cancellation = {"requested": False}

        def frames():
            for frame in self.frames(1):
                cancellation["requested"] = True
                yield frame

        stats = play_frames(controller, frames(), cancelled=lambda: cancellation["requested"])
        self.assertEqual(stats.frames, 0)
        self.assertEqual(self.starts, [0])
        self.assertEqual(controller.images, [])
        self.assertIsNone(stats.startup_seconds)

    def test_cancel_during_frame_stops_cleanly(self):
        controller = InterruptingController()
        stats = play_frames(controller, self.frames(1), cancelled=lambda: controller.cancelled)
        self.assertTrue(controller.entered)
        self.assertEqual(stats.frames, 0)
        self.assertIsNone(stats.startup_seconds)

    def test_unrelated_interrupted_error_is_not_suppressed(self):
        controller = InterruptingController(signal_cancellation=False)
        with self.assertRaises(InterruptedError):
            play_frames(controller, self.frames(1), cancelled=lambda: controller.cancelled)
        self.assertTrue(controller.entered)

    def test_cancel_while_waiting_does_not_sample_or_change_steady_window(self):
        controller = FakeController(self.clock)
        cancellation = {"requested": False}

        def cancel_after_third_frame():
            if self.clock.now >= 2.5:
                cancellation["requested"] = True

        self.clock.on_sleep = cancel_after_third_frame
        stats = play_frames(controller, self.frames(10), cancelled=lambda: cancellation["requested"])
        self.assertEqual(stats.frames, 3)
        self.assertTimes(self.starts, [0, 1, 2])
        self.assertGreaterEqual(stats.elapsed_seconds, 2.5)
        self.assertAlmostEqual(stats.steady_elapsed_seconds, 1.0)
        self.assertAlmostEqual(stats.steady_fps, 1.0)

    def test_callbacks_share_budget_but_last_callback_is_outside_steady_window(self):
        controller = FakeController(self.clock)

        def on_frame(count):
            self.clock.advance(2.0 if count == 1 else 0.5)

        stats = play_frames(controller, self.frames(4), max_frames=3, on_frame=on_frame)
        self.assertTimes(self.starts, [0, 2.18, 3.18])
        self.assertTimes(controller.completed, [0.18, 2.36, 3.36])
        self.assertAlmostEqual(stats.startup_seconds, 0.18)
        self.assertAlmostEqual(stats.elapsed_seconds, 3.86)
        self.assertAlmostEqual(stats.steady_elapsed_seconds, 1.0)
        self.assertAlmostEqual(stats.steady_fps, 1.0)

    def test_unchanged_frame_does_not_advance_hardware_frame_id(self):
        controller = FakeController(self.clock, changes=[False, True, True])
        stats = play_frames(controller, self.frames(4), max_frames=4)
        self.assertEqual([update[2] for update in controller.updates], [0, 0, 1])
        self.assertEqual(stats.frames, 4)
        self.assertAlmostEqual(stats.steady_fps, 1.0)


if __name__ == "__main__":
    unittest.main()
