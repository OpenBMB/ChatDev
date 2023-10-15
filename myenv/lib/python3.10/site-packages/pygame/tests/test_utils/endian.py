# Module pygame.tests.test_utils.endian
#
# Machine independent conversion to little-endian and big-endian Python
# integer values.

import struct


def little_endian_uint32(i):
    """Return the 32 bit unsigned integer little-endian representation of i"""

    s = struct.pack("<I", i)
    return struct.unpack("=I", s)[0]


def big_endian_uint32(i):
    """Return the 32 bit unsigned integer big-endian representation of i"""

    s = struct.pack(">I", i)
    return struct.unpack("=I", s)[0]
