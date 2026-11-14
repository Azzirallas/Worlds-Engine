"""Deterministic CPU-only instance-ID raster oracle for future GPU comparison.

Each presentation slot owns one 8x8 (default) grid tile with a unique RGB ID.
This oracle is independent of Godot and does not validate actual GPU shading.
"""

from dataclasses import dataclass


CLEAR = (0, 0, 0, 255)
MAX_ENCODED_SLOT = 0xFFFFFE  # RGB24 reserves zero for the clear background.


class RasterCapacityError(ValueError):
    """A frame cannot be represented without losing or overlapping identities."""


def _integer(value, minimum=0):
    """Reject ambiguous values such as bool and floats before indexing buffers."""
    if type(value) is not int or value < minimum:
        raise ValueError('Expected integral value in range')
    return value


def slot_rgb(slot):
    """Encode slot+1 as 24-bit little-endian RGB; clear remains zero."""
    _integer(slot)
    if slot > MAX_ENCODED_SLOT:
        raise RasterCapacityError('Slot exceeds 24-bit image identity capacity')
    n = slot + 1
    return n & 255, (n >> 8) & 255, (n >> 16) & 255


def decode_rgb(color):
    """Recover the slot from RGBA8; None denotes a clear pixel."""
    if len(color) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in color):
        raise ValueError('Invalid RGBA8 pixel')
    if color[3] != 255:
        raise ValueError('Unexpected alpha: test uses opaque ID colors')
    encoded = color[0] | (color[1] << 8) | (color[2] << 16)
    return None if encoded == 0 else encoded - 1


def _edge(a, b, p):
    """Compute 2D oriented edge in exact integer twice-pixel coordinates."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _top_left(a, b):
    """Choose an unambiguous shared-edge owner for top-left screen coordinates."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    return dy < 0 or (dy == 0 and dx > 0)


def triangle_for_slot(slot, width, height, tile=8):
    """Create a triangle strictly within one slot's tile, in pixel coordinates."""
    _integer(slot)
    _integer(width, 1)
    _integer(height, 1)
    _integer(tile, 6)
    if width % tile or height % tile:
        raise ValueError('Image dimensions must be divisible by tile size')
    cols = width // tile
    rows = height // tile
    if slot >= cols * rows:
        raise RasterCapacityError('Slot outside unique tile grid')
    slot_rgb(slot)
    x = (slot % cols) * tile
    y = (slot // cols) * tile
    return ((x + 1, y + 1), (x + tile - 1, y + 1), (x + 1, y + tile - 1))


def _fill_triangle(pixels, width, height, points, color):
    """Rasterize at pixel centers with integer top-left triangle fill rules."""
    a, b, c = [tuple(coord * 2 for coord in p) for p in points]
    if _edge(a, b, c) <= 0:
        raise ValueError('Expected positive triangle winding')
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(height, max(ys) + 1)):
        for x in range(max(0, min(xs)), min(width, max(xs) + 1)):
            pixel = (2 * x + 1, 2 * y + 1)
            edges = ((_edge(a, b, pixel), _top_left(a, b)),
                     (_edge(b, c, pixel), _top_left(b, c)),
                     (_edge(c, a, pixel), _top_left(c, a)))
            if all(e > 0 or e == 0 and inclusive for e, inclusive in edges):
                i = 4 * (y * width + x)
                pixels[i:i + 4] = color


@dataclass(frozen=True)
class ImageDiff:
    """Full frame identity comparison with explicit missing and unexpected slots."""
    mismatched_pixels: int
    missing_slots: frozenset[int]
    unexpected_slots: frozenset[int]
    same: bool


def render_ids(slots, width=64, height=64, tile=8, max_visible=None):
    """Render a full immutable RGBA8 ID image or fail before returning partial data."""
    _integer(width, 1)
    _integer(height, 1)
    _integer(tile, 6)
    if width % tile or height % tile:
        raise ValueError('Image dimensions must be divisible by tile size')
    slots = tuple(slots)
    if max_visible is not None:
        _integer(max_visible)
        if len(slots) > max_visible:
            raise RasterCapacityError('Output capacity overflow; use conventional draw')
    if any(type(s) is not int or s < 0 for s in slots):
        raise ValueError('Invalid slot ID')
    if len(set(slots)) != len(slots):
        raise RasterCapacityError('Duplicate slot identity')
    if slots and max(slots) >= (width // tile) * (height // tile):
        raise RasterCapacityError('Insufficient image tiles for highest slot')
    pixels = bytearray(bytes(CLEAR) * (width * height))
    for slot in slots:
        coords = triangle_for_slot(slot, width, height, tile)
        color = (*slot_rgb(slot), 255)
        _fill_triangle(pixels, width, height, coords, color)
    return bytes(pixels)


def ids_in_image(image):
    """Enumerate IDs present in an RGBA8 frame, not just a center sample."""
    if len(image) % 4:
        raise ValueError('Incomplete pixel')
    ids = set()
    for i in range(0, len(image), 4):
        slot = decode_rgb(image[i:i + 4])
        if slot is not None:
            ids.add(slot)
    return frozenset(ids)


def compare_images(expected, actual):
    """Compare all pixels and all encoded slot identities, rejecting truncation."""
    if len(expected) != len(actual) or len(expected) % 4:
        raise ValueError('Inconsistent full frame byte sizes')
    n = sum(expected[i:i + 4] != actual[i:i + 4] for i in range(0, len(expected), 4))
    ex = ids_in_image(expected)
    got = ids_in_image(actual)
    return ImageDiff(n, ex - got, got - ex, n == 0)
