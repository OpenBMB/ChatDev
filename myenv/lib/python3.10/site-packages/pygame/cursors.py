#    pygame - Python Game Library
#    Copyright (C) 2000-2003  Pete Shinners
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Library General Public
#    License as published by the Free Software Foundation; either
#    version 2 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Library General Public License for more details.
#
#    You should have received a copy of the GNU Library General Public
#    License along with this library; if not, write to the Free
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#    Pete Shinners
#    pete@shinners.org

"""Set of cursor resources available for use. These cursors come
in a sequence of values that are needed as the arguments for
pygame.mouse.set_cursor(). To dereference the sequence in place
and create the cursor in one step, call like this:
    pygame.mouse.set_cursor(*pygame.cursors.arrow).

Here is a list of available cursors:
    arrow, diamond, ball, broken_x, tri_left, tri_right

There is also a sample string cursor named 'thickarrow_strings'.
The compile() function can convert these string cursors into cursor byte data that can be used to
create Cursor objects.

Alternately, you can also create Cursor objects using surfaces or cursors constants,
such as pygame.SYSTEM_CURSOR_ARROW.
"""

import pygame

_cursor_id_table = {
    pygame.SYSTEM_CURSOR_ARROW: "SYSTEM_CURSOR_ARROW",
    pygame.SYSTEM_CURSOR_IBEAM: "SYSTEM_CURSOR_IBEAM",
    pygame.SYSTEM_CURSOR_WAIT: "SYSTEM_CURSOR_WAIT",
    pygame.SYSTEM_CURSOR_CROSSHAIR: "SYSTEM_CURSOR_CROSSHAIR",
    pygame.SYSTEM_CURSOR_WAITARROW: "SYSTEM_CURSOR_WAITARROW",
    pygame.SYSTEM_CURSOR_SIZENWSE: "SYSTEM_CURSOR_SIZENWSE",
    pygame.SYSTEM_CURSOR_SIZENESW: "SYSTEM_CURSOR_SIZENESW",
    pygame.SYSTEM_CURSOR_SIZEWE: "SYSTEM_CURSOR_SIZEWE",
    pygame.SYSTEM_CURSOR_SIZENS: "SYSTEM_CURSOR_SIZENS",
    pygame.SYSTEM_CURSOR_SIZEALL: "SYSTEM_CURSOR_SIZEALL",
    pygame.SYSTEM_CURSOR_NO: "SYSTEM_CURSOR_NO",
    pygame.SYSTEM_CURSOR_HAND: "SYSTEM_CURSOR_HAND",
}


class Cursor:
    def __init__(self, *args):
        """Cursor(size, hotspot, xormasks, andmasks) -> Cursor
        Cursor(hotspot, Surface) -> Cursor
        Cursor(constant) -> Cursor
        Cursor(Cursor) -> copies the Cursor object passed as an argument
        Cursor() -> Cursor

        pygame object for representing cursors

        You can initialize a cursor from a system cursor or use the
        constructor on an existing Cursor object, which will copy it.
        Providing a Surface instance will render the cursor displayed
        as that Surface when used.

        These Surfaces may use other colors than black and white."""
        if len(args) == 0:
            self.type = "system"
            self.data = (pygame.SYSTEM_CURSOR_ARROW,)
        elif len(args) == 1 and args[0] in _cursor_id_table:
            self.type = "system"
            self.data = (args[0],)
        elif len(args) == 1 and isinstance(args[0], Cursor):
            self.type = args[0].type
            self.data = args[0].data
        elif (
            len(args) == 2 and len(args[0]) == 2 and isinstance(args[1], pygame.Surface)
        ):
            self.type = "color"
            self.data = tuple(args)
        elif len(args) == 4 and len(args[0]) == 2 and len(args[1]) == 2:
            self.type = "bitmap"
            # pylint: disable=consider-using-generator
            # See https://github.com/pygame/pygame/pull/2509 for analysis
            self.data = tuple(tuple(arg) for arg in args)
        else:
            raise TypeError("Arguments must match a cursor specification")

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __getitem__(self, index):
        return self.data[index]

    def __eq__(self, other):
        return isinstance(other, Cursor) and self.data == other.data

    def __ne__(self, other):
        return not self.__eq__(other)

    def __copy__(self):
        """Clone the current Cursor object.
        You can do the same thing by doing Cursor(Cursor)."""
        return self.__class__(self)

    copy = __copy__

    def __hash__(self):
        return hash(tuple([self.type] + list(self.data)))

    def __repr__(self):
        if self.type == "system":
            id_string = _cursor_id_table.get(self.data[0], "constant lookup error")
            return f"<Cursor(type: system, constant: {id_string})>"
        if self.type == "bitmap":
            size = f"size: {self.data[0]}"
            hotspot = f"hotspot: {self.data[1]}"
            return f"<Cursor(type: bitmap, {size}, {hotspot})>"
        if self.type == "color":
            hotspot = f"hotspot: {self.data[0]}"
            surf = repr(self.data[1])
            return f"<Cursor(type: color, {hotspot}, surf: {surf})>"
        raise TypeError("Invalid Cursor")


# Python side of the set_cursor function: C side in mouse.c
def set_cursor(*args):
    """set_cursor(pygame.cursors.Cursor OR args for a pygame.cursors.Cursor) -> None
    set the mouse cursor to a new cursor"""
    cursor = Cursor(*args)
    pygame.mouse._set_cursor(**{cursor.type: cursor.data})


pygame.mouse.set_cursor = set_cursor
del set_cursor  # cleanup namespace


# Python side of the get_cursor function: C side in mouse.c
def get_cursor():
    """get_cursor() -> pygame.cursors.Cursor
    get the current mouse cursor"""
    return Cursor(*pygame.mouse._get_cursor())


pygame.mouse.get_cursor = get_cursor
del get_cursor  # cleanup namespace

arrow = Cursor(
    (16, 16),
    (0, 0),
    (
        0x00,
        0x00,
        0x40,
        0x00,
        0x60,
        0x00,
        0x70,
        0x00,
        0x78,
        0x00,
        0x7C,
        0x00,
        0x7E,
        0x00,
        0x7F,
        0x00,
        0x7F,
        0x80,
        0x7C,
        0x00,
        0x6C,
        0x00,
        0x46,
        0x00,
        0x06,
        0x00,
        0x03,
        0x00,
        0x03,
        0x00,
        0x00,
        0x00,
    ),
    (
        0x40,
        0x00,
        0xE0,
        0x00,
        0xF0,
        0x00,
        0xF8,
        0x00,
        0xFC,
        0x00,
        0xFE,
        0x00,
        0xFF,
        0x00,
        0xFF,
        0x80,
        0xFF,
        0xC0,
        0xFF,
        0x80,
        0xFE,
        0x00,
        0xEF,
        0x00,
        0x4F,
        0x00,
        0x07,
        0x80,
        0x07,
        0x80,
        0x03,
        0x00,
    ),
)

diamond = Cursor(
    (16, 16),
    (7, 7),
    (
        0,
        0,
        1,
        0,
        3,
        128,
        7,
        192,
        14,
        224,
        28,
        112,
        56,
        56,
        112,
        28,
        56,
        56,
        28,
        112,
        14,
        224,
        7,
        192,
        3,
        128,
        1,
        0,
        0,
        0,
        0,
        0,
    ),
    (
        1,
        0,
        3,
        128,
        7,
        192,
        15,
        224,
        31,
        240,
        62,
        248,
        124,
        124,
        248,
        62,
        124,
        124,
        62,
        248,
        31,
        240,
        15,
        224,
        7,
        192,
        3,
        128,
        1,
        0,
        0,
        0,
    ),
)

ball = Cursor(
    (16, 16),
    (7, 7),
    (
        0,
        0,
        3,
        192,
        15,
        240,
        24,
        248,
        51,
        252,
        55,
        252,
        127,
        254,
        127,
        254,
        127,
        254,
        127,
        254,
        63,
        252,
        63,
        252,
        31,
        248,
        15,
        240,
        3,
        192,
        0,
        0,
    ),
    (
        3,
        192,
        15,
        240,
        31,
        248,
        63,
        252,
        127,
        254,
        127,
        254,
        255,
        255,
        255,
        255,
        255,
        255,
        255,
        255,
        127,
        254,
        127,
        254,
        63,
        252,
        31,
        248,
        15,
        240,
        3,
        192,
    ),
)

broken_x = Cursor(
    (16, 16),
    (7, 7),
    (
        0,
        0,
        96,
        6,
        112,
        14,
        56,
        28,
        28,
        56,
        12,
        48,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        12,
        48,
        28,
        56,
        56,
        28,
        112,
        14,
        96,
        6,
        0,
        0,
    ),
    (
        224,
        7,
        240,
        15,
        248,
        31,
        124,
        62,
        62,
        124,
        30,
        120,
        14,
        112,
        0,
        0,
        0,
        0,
        14,
        112,
        30,
        120,
        62,
        124,
        124,
        62,
        248,
        31,
        240,
        15,
        224,
        7,
    ),
)

tri_left = Cursor(
    (16, 16),
    (1, 1),
    (
        0,
        0,
        96,
        0,
        120,
        0,
        62,
        0,
        63,
        128,
        31,
        224,
        31,
        248,
        15,
        254,
        15,
        254,
        7,
        128,
        7,
        128,
        3,
        128,
        3,
        128,
        1,
        128,
        1,
        128,
        0,
        0,
    ),
    (
        224,
        0,
        248,
        0,
        254,
        0,
        127,
        128,
        127,
        224,
        63,
        248,
        63,
        254,
        31,
        255,
        31,
        255,
        15,
        254,
        15,
        192,
        7,
        192,
        7,
        192,
        3,
        192,
        3,
        192,
        1,
        128,
    ),
)

tri_right = Cursor(
    (16, 16),
    (14, 1),
    (
        0,
        0,
        0,
        6,
        0,
        30,
        0,
        124,
        1,
        252,
        7,
        248,
        31,
        248,
        127,
        240,
        127,
        240,
        1,
        224,
        1,
        224,
        1,
        192,
        1,
        192,
        1,
        128,
        1,
        128,
        0,
        0,
    ),
    (
        0,
        7,
        0,
        31,
        0,
        127,
        1,
        254,
        7,
        254,
        31,
        252,
        127,
        252,
        255,
        248,
        255,
        248,
        127,
        240,
        3,
        240,
        3,
        224,
        3,
        224,
        3,
        192,
        3,
        192,
        1,
        128,
    ),
)


# Here is an example string resource cursor. To use this:
#    curs, mask = pygame.cursors.compile_cursor(pygame.cursors.thickarrow_strings, 'X', '.')
#    pygame.mouse.set_cursor((24, 24), (0, 0), curs, mask)
# Be warned, though, that cursors created from compiled strings do not support colors.

# sized 24x24
thickarrow_strings = (
    "XX                      ",
    "XXX                     ",
    "XXXX                    ",
    "XX.XX                   ",
    "XX..XX                  ",
    "XX...XX                 ",
    "XX....XX                ",
    "XX.....XX               ",
    "XX......XX              ",
    "XX.......XX             ",
    "XX........XX            ",
    "XX........XXX           ",
    "XX......XXXXX           ",
    "XX.XXX..XX              ",
    "XXXX XX..XX             ",
    "XX   XX..XX             ",
    "     XX..XX             ",
    "      XX..XX            ",
    "      XX..XX            ",
    "       XXXX             ",
    "       XX               ",
    "                        ",
    "                        ",
    "                        ",
)

# sized 24x16
sizer_x_strings = (
    "     X      X           ",
    "    XX      XX          ",
    "   X.X      X.X         ",
    "  X..X      X..X        ",
    " X...XXXXXXXX...X       ",
    "X................X      ",
    " X...XXXXXXXX...X       ",
    "  X..X      X..X        ",
    "   X.X      X.X         ",
    "    XX      XX          ",
    "     X      X           ",
    "                        ",
    "                        ",
    "                        ",
    "                        ",
    "                        ",
)

# sized 16x24
sizer_y_strings = (
    "     X          ",
    "    X.X         ",
    "   X...X        ",
    "  X.....X       ",
    " X.......X      ",
    "XXXXX.XXXXX     ",
    "    X.X         ",
    "    X.X         ",
    "    X.X         ",
    "    X.X         ",
    "    X.X         ",
    "    X.X         ",
    "    X.X         ",
    "XXXXX.XXXXX     ",
    " X.......X      ",
    "  X.....X       ",
    "   X...X        ",
    "    X.X         ",
    "     X          ",
    "                ",
    "                ",
    "                ",
    "                ",
    "                ",
)

# sized 24x16
sizer_xy_strings = (
    "XXXXXXXX                ",
    "X.....X                 ",
    "X....X                  ",
    "X...X                   ",
    "X..X.X                  ",
    "X.X X.X                 ",
    "XX   X.X    X           ",
    "X     X.X  XX           ",
    "       X.XX.X           ",
    "        X...X           ",
    "        X...X           ",
    "       X....X           ",
    "      X.....X           ",
    "     XXXXXXXX           ",
    "                        ",
    "                        ",
)

# sized 8x16
textmarker_strings = (
    "ooo ooo ",
    "   o    ",
    "   o    ",
    "   o    ",
    "   o    ",
    "   o    ",
    "   o    ",
    "   o    ",
    "   o    ",
    "   o    ",
    "   o    ",
    "ooo ooo ",
    "        ",
    "        ",
    "        ",
    "        ",
)


def compile(strings, black="X", white=".", xor="o"):
    """pygame.cursors.compile(strings, black, white, xor) -> data, mask
    compile cursor strings into cursor data

    This takes a set of strings with equal length and computes
    the binary data for that cursor. The string widths must be
    divisible by 8.

    The black and white arguments are single letter strings that
    tells which characters will represent black pixels, and which
    characters represent white pixels. All other characters are
    considered clear.

    Some systems allow you to set a special toggle color for the
    system color, this is also called the xor color. If the system
    does not support xor cursors, that color will simply be black.

    This returns a tuple containing the cursor data and cursor mask
    data. Both these arguments are used when setting a cursor with
    pygame.mouse.set_cursor().
    """
    # first check for consistent lengths
    size = len(strings[0]), len(strings)
    if size[0] % 8 or size[1] % 8:
        raise ValueError(f"cursor string sizes must be divisible by 8 {size}")

    for s in strings[1:]:
        if len(s) != size[0]:
            raise ValueError("Cursor strings are inconsistent lengths")

    # create the data arrays.
    # this could stand a little optimizing
    maskdata = []
    filldata = []
    maskitem = fillitem = 0
    step = 8
    for s in strings:
        for c in s:
            maskitem = maskitem << 1
            fillitem = fillitem << 1
            step = step - 1
            if c == black:
                maskitem = maskitem | 1
                fillitem = fillitem | 1
            elif c == white:
                maskitem = maskitem | 1
            elif c == xor:
                fillitem = fillitem | 1

            if not step:
                maskdata.append(maskitem)
                filldata.append(fillitem)
                maskitem = fillitem = 0
                step = 8

    return tuple(filldata), tuple(maskdata)


def load_xbm(curs, mask):
    """pygame.cursors.load_xbm(cursorfile, maskfile) -> cursor_args
    reads a pair of XBM files into set_cursor arguments

    Arguments can either be filenames or filelike objects
    with the readlines method. Not largely tested, but
    should work with typical XBM files.
    """

    def bitswap(num):
        val = 0
        for x in range(8):
            b = num & (1 << x) != 0
            val = val << 1 | b
        return val

    if hasattr(curs, "readlines"):
        curs = curs.readlines()
    else:
        with open(curs, encoding="ascii") as cursor_f:
            curs = cursor_f.readlines()

    if hasattr(mask, "readlines"):
        mask = mask.readlines()
    else:
        with open(mask, encoding="ascii") as mask_f:
            mask = mask_f.readlines()

    # avoid comments
    for i, line in enumerate(curs):
        if line.startswith("#define"):
            curs = curs[i:]
            break

    for i, line in enumerate(mask):
        if line.startswith("#define"):
            mask = mask[i:]
            break

    # load width,height
    width = int(curs[0].split()[-1])
    height = int(curs[1].split()[-1])
    # load hotspot position
    if curs[2].startswith("#define"):
        hotx = int(curs[2].split()[-1])
        hoty = int(curs[3].split()[-1])
    else:
        hotx = hoty = 0

    info = width, height, hotx, hoty

    possible_starts = ("static char", "static unsigned char")
    for i, line in enumerate(curs):
        if line.startswith(possible_starts):
            break
    data = " ".join(curs[i + 1 :]).replace("};", "").replace(",", " ")
    cursdata = []
    for x in data.split():
        cursdata.append(bitswap(int(x, 16)))
    cursdata = tuple(cursdata)
    for i, line in enumerate(mask):
        if line.startswith(possible_starts):
            break
    data = " ".join(mask[i + 1 :]).replace("};", "").replace(",", " ")
    maskdata = []
    for x in data.split():
        maskdata.append(bitswap(int(x, 16)))

    maskdata = tuple(maskdata)
    return info[:2], info[2:], cursdata, maskdata
