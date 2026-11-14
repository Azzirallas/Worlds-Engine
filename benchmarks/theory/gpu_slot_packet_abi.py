"""Hardware-free, versioned descriptor ABI for hypothetical GPU scene-slot uploads.

A packet describes a payload in a separately owned, aligned staging buffer. This
module does not allocate GPU memory or assume an actual Godot upload API.
"""

from dataclasses import dataclass
from struct import Struct

UINT32_MAX = 0xFFFFFFFF
WIRE_MAGIC = 0x31505357  # Little-endian ASCII 'WSP1'.
FLAG_TOMBSTONE = 1
DESCRIPTOR = Struct('<8I')  # Exactly 32 bytes; all fields use unsigned 32-bit.
PAYLOAD_ALIGNMENT = 16


def u32(value):
    """Reject bools, negative numbers and wrapping integer conversions."""
    if type(value) is not int or not 0 <= value <= UINT32_MAX:
        raise ValueError('Expected uint32')
    return value


@dataclass(frozen=True)
class SlotPacket:
    """Immutable CPU-side header; payload is a separate immutable staging range."""
    slot: int
    generation: int
    revision: int
    scene_epoch: int
    offset: int
    length: int
    flags: int = 0

    def __post_init__(self):
        """Fail closed on malformed layout, epochs and terminal generations."""
        for field in ('slot', 'generation', 'revision', 'scene_epoch',
                      'offset', 'length', 'flags'):
            u32(getattr(self, field))
        if self.generation == 0 or self.revision == 0 or self.scene_epoch == 0:
            raise ValueError('Zero generation, revision or epoch is invalid')
        if self.flags & ~FLAG_TOMBSTONE:
            raise ValueError('Unknown packet flags')
        if self.flags & FLAG_TOMBSTONE:
            if self.offset != 0 or self.length != 0:
                raise ValueError('Tombstone must not address a payload')
        else:
            if (self.generation == UINT32_MAX or self.length == 0
                    or self.offset % PAYLOAD_ALIGNMENT != 0
                    or self.offset + self.length > UINT32_MAX):
                raise ValueError('Invalid live packet payload bounds')

    def pack(self):
        """Serialize an eight-word std430-compatible descriptor header."""
        return DESCRIPTOR.pack(WIRE_MAGIC, self.slot, self.generation,
                               self.revision, self.scene_epoch, self.offset,
                               self.length, self.flags)

    @classmethod
    def unpack(cls, data):
        """Parse exactly one header and reject wrong versions or extra bytes."""
        if len(data) != DESCRIPTOR.size:
            raise ValueError('Expected a 32-byte packet')
        magic, *fields = DESCRIPTOR.unpack(data)
        if magic != WIRE_MAGIC:
            raise ValueError('Unrecognized descriptor format')
        return cls(*fields)

    def validate_payload(self, size):
        """Reject descriptors pointing beyond the actual available staging bytes."""
        if type(size) is not int or not 0 <= size <= UINT32_MAX:
            raise ValueError('Invalid staging allocation length')
        if not self.flags & FLAG_TOMBSTONE and self.offset + self.length > size:
            raise ValueError('Staging payload exceeds allocation')


def next_epoch(epoch):
    """Do not restart scene epochs at zero and accept stale old-world packets."""
    u32(epoch)
    if epoch == 0 or epoch == UINT32_MAX:
        raise OverflowError('Rebuild device identity instead of wrapping scene epoch')
    return epoch + 1


def packet_current(packet, slot_generation, slot_revision, scene_epoch):
    """Compare exact snapshot identity; only current packets are eligible to upload."""
    if not isinstance(packet, SlotPacket):
        raise ValueError('Missing validated packet')
    return (packet.generation == u32(slot_generation)
            and packet.revision == u32(slot_revision)
            and packet.scene_epoch == u32(scene_epoch))
