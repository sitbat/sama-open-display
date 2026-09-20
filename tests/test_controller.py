import unittest
from PIL import Image

from sama_display import WIDTH, HEIGHT
from sama_display.controller import AuthorizationRequired, ControllerState, DisplayController, full_frame_plan


class FakeTransport:
    def __init__(self, response=b"chs_65inch.dev1_rom1.89"):
        self.response = response
        self.opened = False
        self.writes = []

    def open(self):
        self.opened = True
        return self

    def close(self):
        self.opened = False

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read(self, _size):
        return self.response


class ControllerTests(unittest.TestCase):
    def test_hardware_gate(self):
        controller = DisplayController(FakeTransport())
        with self.assertRaises(AuthorizationRequired):
            controller.connect()
        self.assertEqual(controller.state, ControllerState.DISCONNECTED)

    def test_handshake_with_fake_transport(self):
        transport = FakeTransport()
        controller = DisplayController(transport)
        controller.connect(allow_hardware=True)
        response = controller.hello()
        self.assertTrue(response.startswith(b"chs_"))
        self.assertEqual(controller.state, ControllerState.READY)
        self.assertEqual(controller.identity.rom_version, 89)
        self.assertEqual(len(transport.writes[0]), 250)

    def test_display_is_sent_as_250_byte_blocks(self):
        transport = FakeTransport()
        controller = DisplayController(transport)
        controller.connect(allow_hardware=True)
        controller.hello()
        progress = []
        controller.display(Image.new("RGB", (WIDTH, HEIGHT), "black"), progress=lambda sent, total: progress.append((sent, total)))
        self.assertTrue(all(len(block) == 250 for block in transport.writes))
        self.assertEqual(progress[-1][0], progress[-1][1])

    def test_display_can_be_cancelled(self):
        transport = FakeTransport()
        controller = DisplayController(transport)
        controller.connect(allow_hardware=True)
        controller.hello()
        with self.assertRaises(InterruptedError):
            controller.display(Image.new("RGB", (WIDTH, HEIGHT), "black"), cancelled=lambda: True)
        self.assertEqual(controller.state, ControllerState.ERROR)

    def test_full_frame_plan_is_block_aligned(self):
        plan = full_frame_plan(Image.new("RGB", (WIDTH, HEIGHT), "red"))
        self.assertEqual([step.name for step in plan][-2:], ["pixels", "query-status"])
        self.assertTrue(all(len(step.data) % 250 == 0 for step in plan))
        self.assertGreater(len(plan[-2].data), 4_500_000)

    def test_delta_update_uses_block_writes_and_increments_count(self):
        transport = FakeTransport()
        controller = DisplayController(transport)
        controller.connect(allow_hardware=True)
        controller.hello()
        previous = Image.new("RGB", (WIDTH, HEIGHT), "black")
        current = previous.copy()
        current.putpixel((100, 120), (0, 255, 255))
        self.assertTrue(controller.update_frame(
            previous, current, 1, allow_experimental=True
        ))
        self.assertEqual(controller.update_count, 1)
        self.assertTrue(all(len(block) == 250 for block in transport.writes))

    def test_delta_update_is_disabled_by_default(self):
        transport = FakeTransport()
        controller = DisplayController(transport)
        controller.connect(allow_hardware=True)
        controller.hello()
        with self.assertRaisesRegex(AuthorizationRequired, "CC updates are disabled"):
            frame = Image.new("RGB", (WIDTH, HEIGHT))
            controller.update_frame(frame, frame, 0)


if __name__ == "__main__":
    unittest.main()
