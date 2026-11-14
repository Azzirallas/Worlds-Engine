"""No-GPU tests for the guarded Vulkan-compatible indirect draw packet."""

import random
import unittest
from indirect_draw_reference import (DrawCommand, VisibilityCounters, finalize_draw,
    FLAG_OUTPUT_OVERFLOW, FLAG_INVALID_DATA, FLAG_STALE_GENERATION, U32_MAX)


class IndirectPacketTests(unittest.TestCase):
    """Verify visibility/command contract under valid and adverse scenarios."""

    def test_empty_output_is_valid_zero_draw(self):
        """Empty visible set is a normal zero-instance draw, not a fallback."""
        r = finalize_draw(VisibilityCounters(0), 0, 3)
        self.assertEqual(r.command, DrawCommand(3, 0))
        self.assertFalse(r.fallback_required)

    def test_normal_visible_instances(self):
        """Correct count maps into the indirect instance count."""
        r = finalize_draw(VisibilityCounters(17), 64, 36)
        self.assertEqual(r.command, DrawCommand(36, 17))
        self.assertFalse(r.fallback_required)

    def test_exact_capacity_is_allowed(self):
        """No false alarm when the output exactly fits."""
        self.assertFalse(finalize_draw(VisibilityCounters(16), 16, 3).fallback_required)

    def test_oversized_count_zeroes_draw_even_if_flag_missing(self):
        """Defend against an overflow flag missing due to a dispatch bug."""
        r = finalize_draw(VisibilityCounters(17), 16, 3)
        self.assertEqual(r.command.instance_count, 0)
        self.assertTrue(r.fallback_required)

    def test_explicit_output_overflow_flag_zeroes_draw(self):
        """Never draw a truncated append output."""
        r = finalize_draw(VisibilityCounters(3, FLAG_OUTPUT_OVERFLOW), 16, 3)
        self.assertEqual(r.command.instance_count, 0)
        self.assertTrue(r.fallback_required)

    def test_invalid_candidate_flag_zeroes_draw(self):
        """Out-of-range candidate forces ordinary mesh fallback."""
        r = finalize_draw(VisibilityCounters(3, FLAG_INVALID_DATA), 16, 3)
        self.assertEqual(r.command.instance_count, 0)
        self.assertTrue(r.fallback_required)

    def test_stale_generation_flag_zeroes_draw(self):
        """Reused slots never permit accepting old GPU work."""
        r = finalize_draw(VisibilityCounters(3, FLAG_STALE_GENERATION), 16, 3)
        self.assertEqual(r.command.instance_count, 0)
        self.assertTrue(r.fallback_required)

    def test_future_unknown_flags_fail_closed(self):
        """Unrecognized error bits must never be ignored."""
        r = finalize_draw(VisibilityCounters(3, 1 << 30), 16, 3)
        self.assertEqual(r.command.instance_count, 0)
        self.assertTrue(r.fallback_required)

    def test_draw_budget_lower_than_output_budget(self):
        """Limit actual draw instances independently of append capacity."""
        r = finalize_draw(VisibilityCounters(12), 16, 3, max_instances=8)
        self.assertTrue(r.fallback_required)
        self.assertEqual(r.command.instance_count, 0)

    def test_mesh_must_have_vertices(self):
        """Zero vertex geometry is a configuration failure, not a valid draw."""
        r = finalize_draw(VisibilityCounters(1), 16, 0)
        self.assertTrue(r.fallback_required)
        self.assertEqual(r.command.instance_count, 0)

    def test_bad_input_is_rejected(self):
        """Negative, oversized and noninteger fields cannot wrap to valid commands."""
        bad = (-1, U32_MAX + 1, 1.5, True)
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    VisibilityCounters(value)
                with self.assertRaises(ValueError):
                    DrawCommand(3, value)
                with self.assertRaises(ValueError):
                    finalize_draw(VisibilityCounters(0), value, 3)
        with self.assertRaises(ValueError):
            finalize_draw(None, 1, 3)

    def test_little_endian_command_roundtrip(self):
        """Explicitly define byte order and four-u32 indirect ABI."""
        command = DrawCommand(0x01020304, 17, 13, 19)
        raw = command.to_bytes()
        self.assertEqual(len(raw), 16)
        self.assertEqual(raw[:4], bytes((4, 3, 2, 1)))
        self.assertEqual(DrawCommand.from_bytes(raw), command)
        with self.assertRaises(ValueError):
            DrawCommand.from_bytes(raw[:-1])

    def test_randomized_fail_closed(self):
        """Vary flags, sizes and budgets with a fixed seed for reproducibility."""
        rng = random.Random(2626)
        for _ in range(2500):
            capacity = rng.randrange(0, 256)
            count = rng.randrange(0, 320)
            flags = rng.choice((0, 0, 0, 1, 2, 4, 8))
            max_instances = rng.randrange(0, 256)
            r = finalize_draw(VisibilityCounters(count, flags), capacity, 3, max_instances)
            safe = flags == 0 and count <= capacity and count <= max_instances
            self.assertEqual(r.fallback_required, not safe)
            self.assertEqual(r.command.instance_count, count if safe else 0)
            self.assertEqual(DrawCommand.from_bytes(r.command.to_bytes()), r.command)


if __name__ == '__main__':
    unittest.main()
