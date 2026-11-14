"""Adversarial format tests for CPU-mode GPU scene upload descriptors."""

import random
import struct
import unittest

from gpu_slot_packet_abi import (SlotPacket, UINT32_MAX, FLAG_TOMBSTONE,
                                 WIRE_MAGIC, packet_current, next_epoch)


class PacketABITests(unittest.TestCase):
    """Round-trip, stale-version and corrupted input tests."""

    def test_little_endian_layout(self):
        """The byte offsets and magic are explicit for a future shader contract."""
        p = SlotPacket(2, 7, 9, 3, 16, 48)
        blob = p.pack()
        self.assertEqual(len(blob), 32)
        self.assertEqual(blob[:4], b'WSP1')
        self.assertEqual(struct.unpack('<8I', blob), (WIRE_MAGIC, 2, 7, 9, 3, 16, 48, 0))
        self.assertEqual(SlotPacket.unpack(blob), p)

    def test_tombstone(self):
        """A tombstone has no payload and may use the terminal generation."""
        p = SlotPacket(0, UINT32_MAX, 1, 1, 0, 0, FLAG_TOMBSTONE)
        self.assertEqual(SlotPacket.unpack(p.pack()), p)
        p.validate_payload(0)
        with self.assertRaises(ValueError):
            SlotPacket(0, 3, 1, 1, 16, 8, FLAG_TOMBSTONE)

    def test_stale_generation_revision_epoch(self):
        """Any one mismatched identity rejects an old scene upload."""
        p = SlotPacket(17, 3, 5, 9, 0, 16)
        self.assertTrue(packet_current(p, 3, 5, 9))
        self.assertFalse(packet_current(p, 4, 5, 9))
        self.assertFalse(packet_current(p, 3, 6, 9))
        self.assertFalse(packet_current(p, 3, 5, 10))

    def test_payload_bounds_and_alignment(self):
        """Require aligned payload starts and reject truncated staging ranges."""
        p = SlotPacket(1, 1, 1, 1, 32, 17)
        p.validate_payload(49)
        for size in (48, -1, UINT32_MAX + 1, True):
            with self.subTest(size=size), self.assertRaises(ValueError):
                p.validate_payload(size)
        with self.assertRaises(ValueError):
            SlotPacket(1, 1, 1, 1, 15, 2)
        with self.assertRaises(ValueError):
            SlotPacket(1, 1, 1, 1, UINT32_MAX - 15, 32)

    def test_reject_unknown_flags_and_invalid_live_terminal(self):
        """Future format bits must fail closed until explicitly supported."""
        for flags in (2, 4, UINT32_MAX):
            with self.assertRaises(ValueError):
                SlotPacket(0, 1, 1, 1, 0, 16, flags)
        with self.assertRaises(ValueError):
            SlotPacket(0, UINT32_MAX, 1, 1, 0, 16)
        with self.assertRaises(ValueError):
            SlotPacket(0, 1, 1, 1, 0, 0)

    def test_reject_bad_header_and_zero_identity(self):
        """Reject old format versions, truncated headers and zero epochs."""
        good = SlotPacket(2, 3, 4, 5, 0, 4).pack()
        for bad in (b'OLD!' + good[4:], good[:-1], good + b'\x00'):
            with self.assertRaises(ValueError):
                SlotPacket.unpack(bad)
        for f in ('generation', 'revision', 'scene_epoch'):
            kwargs = dict(slot=2, generation=3, revision=4, scene_epoch=5, offset=0, length=4)
            kwargs[f] = 0
            with self.assertRaises(ValueError):
                SlotPacket(**kwargs)

    def test_numeric_validation_no_python_wrap(self):
        """Invalid values must not silently wrap through struct.pack()."""
        for value in (-1, UINT32_MAX + 1, True, 2.5, '1'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SlotPacket(value, 1, 1, 1, 0, 4)
        with self.assertRaises(ValueError):
            packet_current(None, 1, 1, 1)

    def test_epoch_advance_fails_at_limit(self):
        """Epoch wrap requires a new device identity, not reuse of old epochs."""
        self.assertEqual(next_epoch(1), 2)
        self.assertEqual(next_epoch(UINT32_MAX - 1), UINT32_MAX)
        for value in (0, UINT32_MAX, -1, True):
            with self.assertRaises((OverflowError, ValueError)):
                next_epoch(value)

    def test_seeded_roundtrip_and_corruption(self):
        """1,000 deterministic valid packets and altered version headers."""
        rng = random.Random(90214)
        for _ in range(1000):
            offset = rng.randrange(0, 3000) * 16
            p = SlotPacket(rng.randrange(2**20), rng.randrange(1, UINT32_MAX),
                           rng.randrange(1, UINT32_MAX), rng.randrange(1, UINT32_MAX),
                           offset, rng.randrange(1, 1000))
            blob = bytearray(p.pack())
            self.assertEqual(SlotPacket.unpack(blob), p)
            blob[0] ^= 0x01
            with self.assertRaises(ValueError):
                SlotPacket.unpack(blob)


if __name__ == '__main__':
    unittest.main()
