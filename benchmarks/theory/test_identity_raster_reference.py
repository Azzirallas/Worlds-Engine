"""CPU image-identity oracle tests; no graphics hardware or Godot required."""

import random
import unittest

from identity_raster_reference import (CLEAR, MAX_ENCODED_SLOT, RasterCapacityError,
                                       compare_images, decode_rgb, ids_in_image,
                                       render_ids, slot_rgb, triangle_for_slot)


class IdentityImageTests(unittest.TestCase):
    """Detect missing, swapped, duplicated and malformed instance draws."""

    def test_clear_image(self):
        """No selected instances must leave every pixel clear."""
        image = render_ids([])
        self.assertEqual(len(image), 64 * 64 * 4)
        self.assertEqual(image, bytes(CLEAR) * (64 * 64))
        self.assertEqual(ids_in_image(image), frozenset())

    def test_one_slot_draws_only_its_tile(self):
        """Procedural ID triangles cannot spill into adjacent slot tiles."""
        image = render_ids([0], width=16, height=8)
        self.assertEqual(ids_in_image(image), frozenset({0}))
        for y in range(8):
            for x in range(8, 16):
                self.assertEqual(image[4 * (y * 16 + x):4 * (y * 16 + x) + 4], bytes(CLEAR))

    def test_draw_order_independent(self):
        """Atomic GPU append order cannot affect final per-slot identity image."""
        slots = list(range(40))
        expected = render_ids(slots)
        random.Random(404).shuffle(slots)
        self.assertEqual(render_ids(slots), expected)
        self.assertEqual(ids_in_image(expected), frozenset(range(40)))

    def test_each_slot_has_unique_coverage(self):
        """Every slot has its own nonempty triangle under default geometry."""
        img = render_ids(range(64))
        self.assertEqual(ids_in_image(img), frozenset(range(64)))

    def test_missing_instance_detected_even_with_center_lit(self):
        """A center-only green probe would miss an omitted distant instance."""
        expected = render_ids([0, 1, 2, 3])
        actual = render_ids([0, 1, 2])
        diff = compare_images(expected, actual)
        self.assertFalse(diff.same)
        self.assertGreater(diff.mismatched_pixels, 0)
        self.assertEqual(diff.missing_slots, frozenset({3}))
        self.assertEqual(diff.unexpected_slots, frozenset())

    def test_swapped_instance_detected(self):
        """Wrong instance index becomes a detectable missing/unexpected slot."""
        expected = render_ids([1, 2])
        actual = render_ids([1, 3])
        diff = compare_images(expected, actual)
        self.assertEqual(diff.missing_slots, frozenset({2}))
        self.assertEqual(diff.unexpected_slots, frozenset({3}))

    def test_duplicate_id_fails_before_raster(self):
        """Repeated selected slots are not silently drawn twice."""
        with self.assertRaises(RasterCapacityError):
            render_ids([1, 1])

    def test_capacity_and_high_slot_overflow_fail_closed(self):
        """Do not truncate the frame or alias two IDs into the same grid tile."""
        with self.assertRaises(RasterCapacityError):
            render_ids([0, 1], max_visible=1)
        with self.assertRaises(RasterCapacityError):
            render_ids([64])
        with self.assertRaises(RasterCapacityError):
            slot_rgb(MAX_ENCODED_SLOT + 1)

    def test_rgb_identity_encoding(self):
        """RGB24 ID zero is reserved for clear and high byte changes are tested."""
        for slot in (0, 1, 254, 255, 256, 65535, MAX_ENCODED_SLOT):
            rgb = slot_rgb(slot)
            self.assertEqual(decode_rgb((*rgb, 255)), slot)
        self.assertIsNone(decode_rgb(CLEAR))

    def test_invalid_pixel_and_frame_sizes(self):
        """Reject malformed readbacks instead of trusting a partial framebuffer."""
        valid = render_ids([1], width=16, height=16)
        for invalid in (valid[:-1], valid + bytes(4)):
            with self.assertRaises(ValueError):
                compare_images(valid, invalid)
        with self.assertRaises(ValueError):
            ids_in_image(b'123')
        with self.assertRaises(ValueError):
            decode_rgb((2, 0, 0, 0))

    def test_boundary_and_small_tile_validation(self):
        """Pixel-grid capacity and tile geometry are explicit input contracts."""
        with self.assertRaises(ValueError):
            triangle_for_slot(0, 11, 16)
        with self.assertRaises(ValueError):
            render_ids([0], width=16, height=16, tile=4)
        with self.assertRaises(ValueError):
            render_ids([-1])
        with self.assertRaises(ValueError):
            render_ids([True])

    def test_seeded_random_masks_and_missing_slot(self):
        """Compare 200 seeded random subsets and deliberate single-slot omissions."""
        rng = random.Random(8771)
        for _ in range(200):
            slots = sorted(rng.sample(range(64), rng.randrange(1, 65)))
            expected = render_ids(slots)
            shuffled = slots[:]
            rng.shuffle(shuffled)
            self.assertTrue(compare_images(expected, render_ids(shuffled)).same)
            removed = rng.choice(slots)
            missing = render_ids([s for s in slots if s != removed])
            self.assertEqual(compare_images(expected, missing).missing_slots, frozenset({removed}))


if __name__ == '__main__':
    unittest.main()
