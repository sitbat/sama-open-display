import unittest

from sama_display.protocol import (
    Command, brightness_packet, command_packet, display_bitmap_header,
    encode_delta_stream, parse_device_identity, start_bitmap_packet,
    update_bitmap_packets,
)
from PIL import Image


class ProtocolTests(unittest.TestCase):
    def test_command_padding(self):
        packet = command_packet(Command.HELLO)
        self.assertEqual(len(packet), 250)
        self.assertEqual(packet[:3], b"\x01\xef\x69")

    def test_brightness(self):
        packet = brightness_packet(100)
        self.assertEqual(packet[10], 255)
        with self.assertRaises(ValueError):
            brightness_packet(101)

    def test_65inch_header(self):
        self.assertEqual(display_bitmap_header(), bytes.fromhex("C8 EF 69 00 44 E8 00 00"))

    def test_start_bitmap_padding(self):
        packet = start_bitmap_packet()
        self.assertEqual(len(packet), 250)
        self.assertEqual(set(packet), {0x2C})

    def test_parse_verified_65inch_identity(self):
        identity = parse_device_identity(b"chs_65inch.dev1_rom1.91")
        self.assertEqual(identity.model, "65inch")
        self.assertEqual(identity.device_revision, 1)
        self.assertEqual(identity.rom_family, 1)
        self.assertEqual(identity.rom_version, 91)

    def test_reject_invalid_identity(self):
        with self.assertRaises(ValueError):
            parse_device_identity("unknown")

    def test_delta_stream_matches_oem_singleton_vectors(self):
        old = bytes(400)
        new = bytearray(old)
        new[40:44] = bytes((1, 2, 3, 4))
        self.assertEqual(encode_delta_stream(old, bytes(new)), bytes.fromhex("80 00 0A 01 02 03 04"))

    def test_delta_stream_matches_oem_run_vector(self):
        old = bytes(400)
        new = bytearray(old)
        new[0:8] = bytes((1, 2, 3, 4, 1, 2, 3, 4))
        self.assertEqual(
            encode_delta_stream(old, bytes(new)),
            bytes.fromhex("00 00 00 00 02 01 02 03 04 01 02 03 04"),
        )

    def test_update_bitmap_header_uses_oem_metadata_layout(self):
        previous = Image.new("RGB", (1568, 720), "black")
        current = previous.copy()
        current.putpixel((0, 0), (0x11, 0x22, 0x33))
        result = update_bitmap_packets(previous, current, frame_id=7)
        self.assertIsNotNone(result)
        header, pixels = result
        self.assertEqual(len(header), 250)
        self.assertEqual(header[:4], bytes.fromhex("CC EF 69 00"))
        self.assertEqual(int.from_bytes(header[3:7], "big"), 9)
        self.assertEqual(int.from_bytes(header[10:14], "big"), 7)
        self.assertEqual(header[14:18], bytes(4))
        self.assertTrue(pixels.rstrip(b"\x00").endswith(bytes.fromhex("EF 69")))

    def test_landscape_top_left_uses_rotated_oem_pixel_index(self):
        previous = Image.new("RGB", (1568, 720), "black")
        current = previous.copy()
        current.putpixel((0, 0), (0x11, 0x22, 0x33))
        _header, pixels = update_bitmap_packets(previous, current, frame_id=0)
        # (0, 0) rotates to panel (719, 0), hence CC index 719 (0x02CF).
        self.assertEqual(pixels[:7], bytes.fromhex("80 02 CF 33 22 11 FF"))

    def test_update_bitmap_rejects_different_sizes(self):
        with self.assertRaises(ValueError):
            update_bitmap_packets(Image.new("RGB", (1568, 720)), Image.new("RGB", (10, 10)), 0)


if __name__ == "__main__":
    unittest.main()
