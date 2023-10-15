import math
import operator
import platform
import unittest
from collections.abc import Collection, Sequence

import pygame
from pygame.colordict import THECOLORS

IS_PYPY = "PyPy" == platform.python_implementation()
################################### CONSTANTS ##################################

rgba_vals = [0, 1, 62, 63, 126, 127, 255]

rgba_combinations = [
    (r, g, b, a)
    for r in rgba_vals
    for g in rgba_vals
    for b in rgba_vals
    for a in rgba_vals
]

################################################################################


def rgba_combos_Color_generator():
    for rgba in rgba_combinations:
        yield pygame.Color(*rgba)


# Python gamma correct
def gamma_correct(rgba_0_255, gamma):
    corrected = round(255.0 * math.pow(rgba_0_255 / 255.0, gamma))
    return max(min(int(corrected), 255), 0)


################################################################################

# TODO: add tests for
# correct_gamma()  -- test against statically defined verified correct values
# coerce ()        --  ??


def _assignr(x, y):
    x.r = y


def _assigng(x, y):
    x.g = y


def _assignb(x, y):
    x.b = y


def _assigna(x, y):
    x.a = y


def _assign_item(x, p, y):
    x[p] = y


class ColorTypeTest(unittest.TestCase):
    def test_new(self):
        c = pygame.Color.__new__(pygame.Color)
        self.assertEqual(c, pygame.Color(0, 0, 0, 255))
        self.assertEqual(len(c), 4)

    def test_init(self):
        c = pygame.Color(10, 20, 30, 200)
        self.assertEqual(c, (10, 20, 30, 200))
        c.set_length(3)
        self.assertEqual(len(c), 3)
        c.__init__(100, 110, 120, 128)
        self.assertEqual(len(c), 4)
        self.assertEqual(c, (100, 110, 120, 128))

    def test_invalid_html_hex_codes(self):
        # This was a problem with the way 2 digit hex numbers were
        # calculated. The test_hex_digits test is related to the fix.
        Color = pygame.color.Color
        self.assertRaises(ValueError, lambda: Color("# f000000"))
        self.assertRaises(ValueError, lambda: Color("#f 000000"))
        self.assertRaises(ValueError, lambda: Color("#-f000000"))

    def test_hex_digits(self):
        # This is an implementation specific test.
        # Two digit hex numbers are calculated using table lookups
        # for the upper and lower digits.
        Color = pygame.color.Color
        self.assertEqual(Color("#00000000").r, 0x00)
        self.assertEqual(Color("#10000000").r, 0x10)
        self.assertEqual(Color("#20000000").r, 0x20)
        self.assertEqual(Color("#30000000").r, 0x30)
        self.assertEqual(Color("#40000000").r, 0x40)
        self.assertEqual(Color("#50000000").r, 0x50)
        self.assertEqual(Color("#60000000").r, 0x60)
        self.assertEqual(Color("#70000000").r, 0x70)
        self.assertEqual(Color("#80000000").r, 0x80)
        self.assertEqual(Color("#90000000").r, 0x90)
        self.assertEqual(Color("#A0000000").r, 0xA0)
        self.assertEqual(Color("#B0000000").r, 0xB0)
        self.assertEqual(Color("#C0000000").r, 0xC0)
        self.assertEqual(Color("#D0000000").r, 0xD0)
        self.assertEqual(Color("#E0000000").r, 0xE0)
        self.assertEqual(Color("#F0000000").r, 0xF0)
        self.assertEqual(Color("#01000000").r, 0x01)
        self.assertEqual(Color("#02000000").r, 0x02)
        self.assertEqual(Color("#03000000").r, 0x03)
        self.assertEqual(Color("#04000000").r, 0x04)
        self.assertEqual(Color("#05000000").r, 0x05)
        self.assertEqual(Color("#06000000").r, 0x06)
        self.assertEqual(Color("#07000000").r, 0x07)
        self.assertEqual(Color("#08000000").r, 0x08)
        self.assertEqual(Color("#09000000").r, 0x09)
        self.assertEqual(Color("#0A000000").r, 0x0A)
        self.assertEqual(Color("#0B000000").r, 0x0B)
        self.assertEqual(Color("#0C000000").r, 0x0C)
        self.assertEqual(Color("#0D000000").r, 0x0D)
        self.assertEqual(Color("#0E000000").r, 0x0E)
        self.assertEqual(Color("#0F000000").r, 0x0F)

    def test_comparison(self):
        Color = pygame.color.Color

        # Check valid comparisons
        self.assertTrue(Color(255, 0, 0, 0) == Color(255, 0, 0, 0))
        self.assertTrue(Color(0, 255, 0, 0) == Color(0, 255, 0, 0))
        self.assertTrue(Color(0, 0, 255, 0) == Color(0, 0, 255, 0))
        self.assertTrue(Color(0, 0, 0, 255) == Color(0, 0, 0, 255))
        self.assertFalse(Color(0, 0, 0, 0) == Color(255, 0, 0, 0))
        self.assertFalse(Color(0, 0, 0, 0) == Color(0, 255, 0, 0))
        self.assertFalse(Color(0, 0, 0, 0) == Color(0, 0, 255, 0))
        self.assertFalse(Color(0, 0, 0, 0) == Color(0, 0, 0, 255))
        self.assertTrue(Color(0, 0, 0, 0) != Color(255, 0, 0, 0))
        self.assertTrue(Color(0, 0, 0, 0) != Color(0, 255, 0, 0))
        self.assertTrue(Color(0, 0, 0, 0) != Color(0, 0, 255, 0))
        self.assertTrue(Color(0, 0, 0, 0) != Color(0, 0, 0, 255))
        self.assertFalse(Color(255, 0, 0, 0) != Color(255, 0, 0, 0))
        self.assertFalse(Color(0, 255, 0, 0) != Color(0, 255, 0, 0))
        self.assertFalse(Color(0, 0, 255, 0) != Color(0, 0, 255, 0))
        self.assertFalse(Color(0, 0, 0, 255) != Color(0, 0, 0, 255))

        self.assertTrue(Color(255, 0, 0, 0) == (255, 0, 0, 0))
        self.assertTrue(Color(0, 255, 0, 0) == (0, 255, 0, 0))
        self.assertTrue(Color(0, 0, 255, 0) == (0, 0, 255, 0))
        self.assertTrue(Color(0, 0, 0, 255) == (0, 0, 0, 255))
        self.assertFalse(Color(0, 0, 0, 0) == (255, 0, 0, 0))
        self.assertFalse(Color(0, 0, 0, 0) == (0, 255, 0, 0))
        self.assertFalse(Color(0, 0, 0, 0) == (0, 0, 255, 0))
        self.assertFalse(Color(0, 0, 0, 0) == (0, 0, 0, 255))
        self.assertTrue(Color(0, 0, 0, 0) != (255, 0, 0, 0))
        self.assertTrue(Color(0, 0, 0, 0) != (0, 255, 0, 0))
        self.assertTrue(Color(0, 0, 0, 0) != (0, 0, 255, 0))
        self.assertTrue(Color(0, 0, 0, 0) != (0, 0, 0, 255))
        self.assertFalse(Color(255, 0, 0, 0) != (255, 0, 0, 0))
        self.assertFalse(Color(0, 255, 0, 0) != (0, 255, 0, 0))
        self.assertFalse(Color(0, 0, 255, 0) != (0, 0, 255, 0))
        self.assertFalse(Color(0, 0, 0, 255) != (0, 0, 0, 255))

        self.assertTrue((255, 0, 0, 0) == Color(255, 0, 0, 0))
        self.assertTrue((0, 255, 0, 0) == Color(0, 255, 0, 0))
        self.assertTrue((0, 0, 255, 0) == Color(0, 0, 255, 0))
        self.assertTrue((0, 0, 0, 255) == Color(0, 0, 0, 255))
        self.assertFalse((0, 0, 0, 0) == Color(255, 0, 0, 0))
        self.assertFalse((0, 0, 0, 0) == Color(0, 255, 0, 0))
        self.assertFalse((0, 0, 0, 0) == Color(0, 0, 255, 0))
        self.assertFalse((0, 0, 0, 0) == Color(0, 0, 0, 255))
        self.assertTrue((0, 0, 0, 0) != Color(255, 0, 0, 0))
        self.assertTrue((0, 0, 0, 0) != Color(0, 255, 0, 0))
        self.assertTrue((0, 0, 0, 0) != Color(0, 0, 255, 0))
        self.assertTrue((0, 0, 0, 0) != Color(0, 0, 0, 255))
        self.assertFalse((255, 0, 0, 0) != Color(255, 0, 0, 0))
        self.assertFalse((0, 255, 0, 0) != Color(0, 255, 0, 0))
        self.assertFalse((0, 0, 255, 0) != Color(0, 0, 255, 0))
        self.assertFalse((0, 0, 0, 255) != Color(0, 0, 0, 255))

        class TupleSubclass(tuple):
            pass

        self.assertTrue(Color(255, 0, 0, 0) == TupleSubclass((255, 0, 0, 0)))
        self.assertTrue(TupleSubclass((255, 0, 0, 0)) == Color(255, 0, 0, 0))
        self.assertFalse(Color(255, 0, 0, 0) != TupleSubclass((255, 0, 0, 0)))
        self.assertFalse(TupleSubclass((255, 0, 0, 0)) != Color(255, 0, 0, 0))

        # These are not supported so will be unequal.
        self.assertFalse(Color(255, 0, 0, 0) == "#ff000000")
        self.assertTrue(Color(255, 0, 0, 0) != "#ff000000")

        self.assertFalse("#ff000000" == Color(255, 0, 0, 0))
        self.assertTrue("#ff000000" != Color(255, 0, 0, 0))

        self.assertFalse(Color(255, 0, 0, 0) == 0xFF000000)
        self.assertTrue(Color(255, 0, 0, 0) != 0xFF000000)

        self.assertFalse(0xFF000000 == Color(255, 0, 0, 0))
        self.assertTrue(0xFF000000 != Color(255, 0, 0, 0))

        self.assertFalse(Color(255, 0, 0, 0) == [255, 0, 0, 0])
        self.assertTrue(Color(255, 0, 0, 0) != [255, 0, 0, 0])

        self.assertFalse([255, 0, 0, 0] == Color(255, 0, 0, 0))
        self.assertTrue([255, 0, 0, 0] != Color(255, 0, 0, 0))

        # Comparison is not implemented for invalid color values.
        class Test:
            def __eq__(self, other):
                return -1

            def __ne__(self, other):
                return -2

        class TestTuple(tuple):
            def __eq__(self, other):
                return -1

            def __ne__(self, other):
                return -2

        t = Test()
        t_tuple = TestTuple(("a", 0, 0, 0))
        black = Color("black")
        self.assertEqual(black == t, -1)
        self.assertEqual(t == black, -1)
        self.assertEqual(black != t, -2)
        self.assertEqual(t != black, -2)
        self.assertEqual(black == t_tuple, -1)
        self.assertEqual(black != t_tuple, -2)
        self.assertEqual(t_tuple == black, -1)
        self.assertEqual(t_tuple != black, -2)

    def test_ignore_whitespace(self):
        self.assertEqual(pygame.color.Color("red"), pygame.color.Color(" r e d "))

    def test_slice(self):
        # """|tags: python3_ignore|"""

        # slicing a color gives you back a tuple.
        # do all sorts of slice combinations.
        c = pygame.Color(1, 2, 3, 4)

        self.assertEqual((1, 2, 3, 4), c[:])
        self.assertEqual((1, 2, 3), c[:-1])

        self.assertEqual((), c[:-5])

        self.assertEqual((1, 2, 3, 4), c[:4])
        self.assertEqual((1, 2, 3, 4), c[:5])
        self.assertEqual((1, 2), c[:2])
        self.assertEqual((1,), c[:1])
        self.assertEqual((), c[:0])

        self.assertEqual((2,), c[1:-2])
        self.assertEqual((3, 4), c[-2:])
        self.assertEqual((4,), c[-1:])

        # NOTE: assigning to a slice is currently unsupported.

    def test_unpack(self):
        # should be able to unpack to r,g,b,a and r,g,b
        c = pygame.Color(1, 2, 3, 4)
        r, g, b, a = c
        self.assertEqual((1, 2, 3, 4), (r, g, b, a))
        self.assertEqual(c, (r, g, b, a))

        c.set_length(3)
        r, g, b = c
        self.assertEqual((1, 2, 3), (r, g, b))

        # Checking if DeprecationWarning is triggered
        # when function is called
        for i in range(1, 5):
            with self.assertWarns(DeprecationWarning):
                c.set_length(i)

    def test_length(self):
        # should be able to unpack to r,g,b,a and r,g,b
        c = pygame.Color(1, 2, 3, 4)
        self.assertEqual(len(c), 4)

        c.set_length(3)
        self.assertEqual(len(c), 3)

        # it keeps the old alpha anyway...
        self.assertEqual(c.a, 4)

        # however you can't get the alpha in this way:
        self.assertRaises(IndexError, lambda x: c[x], 4)

        c.set_length(4)
        self.assertEqual(len(c), 4)
        self.assertEqual(len(c), 4)

        self.assertRaises(ValueError, c.set_length, 5)
        self.assertRaises(ValueError, c.set_length, -1)
        self.assertRaises(ValueError, c.set_length, 0)
        self.assertRaises(ValueError, c.set_length, pow(2, 33))

    def test_case_insensitivity_of_string_args(self):
        self.assertEqual(pygame.color.Color("red"), pygame.color.Color("Red"))

    def test_color(self):
        """Ensures Color objects can be created."""
        color = pygame.Color(0, 0, 0, 0)

        self.assertIsInstance(color, pygame.Color)

    def test_color__rgba_int_args(self):
        """Ensures Color objects can be created using ints."""
        color = pygame.Color(10, 20, 30, 40)

        self.assertEqual(color.r, 10)
        self.assertEqual(color.g, 20)
        self.assertEqual(color.b, 30)
        self.assertEqual(color.a, 40)

    def test_color__rgba_int_args_without_alpha(self):
        """Ensures Color objects can be created without providing alpha."""
        color = pygame.Color(10, 20, 30)

        self.assertEqual(color.r, 10)
        self.assertEqual(color.g, 20)
        self.assertEqual(color.b, 30)
        self.assertEqual(color.a, 255)

    def test_color__rgba_int_args_invalid_value(self):
        """Ensures invalid values are detected when creating Color objects."""
        self.assertRaises(ValueError, pygame.Color, 257, 10, 105, 44)
        self.assertRaises(ValueError, pygame.Color, 10, 257, 105, 44)
        self.assertRaises(ValueError, pygame.Color, 10, 105, 257, 44)
        self.assertRaises(ValueError, pygame.Color, 10, 105, 44, 257)

    def test_color__rgba_int_args_invalid_value_without_alpha(self):
        """Ensures invalid values are detected when creating Color objects
        without providing an alpha.
        """
        self.assertRaises(ValueError, pygame.Color, 256, 10, 105)
        self.assertRaises(ValueError, pygame.Color, 10, 256, 105)
        self.assertRaises(ValueError, pygame.Color, 10, 105, 256)

    def test_color__color_object_arg(self):
        """Ensures Color objects can be created using Color objects."""
        color_args = (10, 20, 30, 40)
        color_obj = pygame.Color(*color_args)

        new_color_obj = pygame.Color(color_obj)

        self.assertIsInstance(new_color_obj, pygame.Color)
        self.assertEqual(new_color_obj, color_obj)
        self.assertEqual(new_color_obj.r, color_args[0])
        self.assertEqual(new_color_obj.g, color_args[1])
        self.assertEqual(new_color_obj.b, color_args[2])
        self.assertEqual(new_color_obj.a, color_args[3])

    def test_color__name_str_arg(self):
        """Ensures Color objects can be created using str names."""
        for name in ("aquamarine3", "AQUAMARINE3", "AqUAmArIne3"):
            color = pygame.Color(name)

            self.assertEqual(color.r, 102)
            self.assertEqual(color.g, 205)
            self.assertEqual(color.b, 170)
            self.assertEqual(color.a, 255)

    def test_color__name_str_arg_from_colordict(self):
        """Ensures Color objects can be created using str names
        from the THECOLORS dict."""
        for name, values in THECOLORS.items():
            color = pygame.Color(name)

            self.assertEqual(color.r, values[0])
            self.assertEqual(color.g, values[1])
            self.assertEqual(color.b, values[2])
            self.assertEqual(color.a, values[3])

    def test_color__html_str_arg(self):
        """Ensures Color objects can be created using html strings."""
        # See test_webstyle() for related tests.
        color = pygame.Color("#a1B2c3D4")

        self.assertEqual(color.r, 0xA1)
        self.assertEqual(color.g, 0xB2)
        self.assertEqual(color.b, 0xC3)
        self.assertEqual(color.a, 0xD4)

    def test_color__hex_str_arg(self):
        """Ensures Color objects can be created using hex strings."""
        # See test_webstyle() for related tests.
        color = pygame.Color("0x1a2B3c4D")

        self.assertEqual(color.r, 0x1A)
        self.assertEqual(color.g, 0x2B)
        self.assertEqual(color.b, 0x3C)
        self.assertEqual(color.a, 0x4D)

    def test_color__int_arg(self):
        """Ensures Color objects can be created using one int value."""
        for value in (0x0, 0xFFFFFFFF, 0xAABBCCDD):
            color = pygame.Color(value)

            self.assertEqual(color.r, (value >> 24) & 0xFF)
            self.assertEqual(color.g, (value >> 16) & 0xFF)
            self.assertEqual(color.b, (value >> 8) & 0xFF)
            self.assertEqual(color.a, value & 0xFF)

    def test_color__int_arg_invalid(self):
        """Ensures invalid int values are detected when creating Color objects."""
        with self.assertRaises(ValueError):
            color = pygame.Color(0x1FFFFFFFF)

    def test_color__sequence_arg(self):
        """Ensures Color objects can be created using tuples/lists."""
        color_values = (33, 44, 55, 66)
        for seq_type in (tuple, list):
            color = pygame.Color(seq_type(color_values))

            self.assertEqual(color.r, color_values[0])
            self.assertEqual(color.g, color_values[1])
            self.assertEqual(color.b, color_values[2])
            self.assertEqual(color.a, color_values[3])

    def test_color__sequence_arg_without_alpha(self):
        """Ensures Color objects can be created using tuples/lists
        without providing an alpha value.
        """
        color_values = (33, 44, 55)
        for seq_type in (tuple, list):
            color = pygame.Color(seq_type(color_values))

            self.assertEqual(color.r, color_values[0])
            self.assertEqual(color.g, color_values[1])
            self.assertEqual(color.b, color_values[2])
            self.assertEqual(color.a, 255)

    def test_color__sequence_arg_invalid_value(self):
        """Ensures invalid sequences are detected when creating Color objects."""
        cls = pygame.Color
        for seq_type in (tuple, list):
            self.assertRaises(ValueError, cls, seq_type((256, 90, 80, 70)))
            self.assertRaises(ValueError, cls, seq_type((100, 256, 80, 70)))
            self.assertRaises(ValueError, cls, seq_type((100, 90, 256, 70)))
            self.assertRaises(ValueError, cls, seq_type((100, 90, 80, 256)))

    def test_color__sequence_arg_invalid_value_without_alpha(self):
        """Ensures invalid sequences are detected when creating Color objects
        without providing an alpha.
        """
        cls = pygame.Color
        for seq_type in (tuple, list):
            self.assertRaises(ValueError, cls, seq_type((256, 90, 80)))
            self.assertRaises(ValueError, cls, seq_type((100, 256, 80)))
            self.assertRaises(ValueError, cls, seq_type((100, 90, 256)))

    def test_color__sequence_arg_invalid_format(self):
        """Ensures invalid sequences are detected when creating Color objects
        with the wrong number of values.
        """
        cls = pygame.Color
        for seq_type in (tuple, list):
            self.assertRaises(ValueError, cls, seq_type((100,)))
            self.assertRaises(ValueError, cls, seq_type((100, 90)))
            self.assertRaises(ValueError, cls, seq_type((100, 90, 80, 70, 60)))

    def test_rgba(self):
        c = pygame.Color(0)
        self.assertEqual(c.r, 0)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 0)
        self.assertEqual(c.a, 0)

        # Test simple assignments
        c.r = 123
        self.assertEqual(c.r, 123)
        self.assertRaises(ValueError, _assignr, c, 537)
        self.assertEqual(c.r, 123)
        self.assertRaises(ValueError, _assignr, c, -3)
        self.assertEqual(c.r, 123)

        c.g = 55
        self.assertEqual(c.g, 55)
        self.assertRaises(ValueError, _assigng, c, 348)
        self.assertEqual(c.g, 55)
        self.assertRaises(ValueError, _assigng, c, -44)
        self.assertEqual(c.g, 55)

        c.b = 77
        self.assertEqual(c.b, 77)
        self.assertRaises(ValueError, _assignb, c, 256)
        self.assertEqual(c.b, 77)
        self.assertRaises(ValueError, _assignb, c, -12)
        self.assertEqual(c.b, 77)

        c.a = 255
        self.assertEqual(c.a, 255)
        self.assertRaises(ValueError, _assigna, c, 312)
        self.assertEqual(c.a, 255)
        self.assertRaises(ValueError, _assigna, c, -10)
        self.assertEqual(c.a, 255)

    def test_repr(self):
        c = pygame.Color(68, 38, 26, 69)
        t = "(68, 38, 26, 69)"
        self.assertEqual(repr(c), t)

    def test_add(self):
        c1 = pygame.Color(0)
        self.assertEqual(c1.r, 0)
        self.assertEqual(c1.g, 0)
        self.assertEqual(c1.b, 0)
        self.assertEqual(c1.a, 0)

        c2 = pygame.Color(20, 33, 82, 193)
        self.assertEqual(c2.r, 20)
        self.assertEqual(c2.g, 33)
        self.assertEqual(c2.b, 82)
        self.assertEqual(c2.a, 193)

        c3 = c1 + c2
        self.assertEqual(c3.r, 20)
        self.assertEqual(c3.g, 33)
        self.assertEqual(c3.b, 82)
        self.assertEqual(c3.a, 193)

        c3 = c3 + c2
        self.assertEqual(c3.r, 40)
        self.assertEqual(c3.g, 66)
        self.assertEqual(c3.b, 164)
        self.assertEqual(c3.a, 255)

        # Issue #286: Is type checking done for Python 3.x?
        self.assertRaises(TypeError, operator.add, c1, None)
        self.assertRaises(TypeError, operator.add, None, c1)

    def test_sub(self):
        c1 = pygame.Color(0xFFFFFFFF)
        self.assertEqual(c1.r, 255)
        self.assertEqual(c1.g, 255)
        self.assertEqual(c1.b, 255)
        self.assertEqual(c1.a, 255)

        c2 = pygame.Color(20, 33, 82, 193)
        self.assertEqual(c2.r, 20)
        self.assertEqual(c2.g, 33)
        self.assertEqual(c2.b, 82)
        self.assertEqual(c2.a, 193)

        c3 = c1 - c2
        self.assertEqual(c3.r, 235)
        self.assertEqual(c3.g, 222)
        self.assertEqual(c3.b, 173)
        self.assertEqual(c3.a, 62)

        c3 = c3 - c2
        self.assertEqual(c3.r, 215)
        self.assertEqual(c3.g, 189)
        self.assertEqual(c3.b, 91)
        self.assertEqual(c3.a, 0)

        # Issue #286: Is type checking done for Python 3.x?
        self.assertRaises(TypeError, operator.sub, c1, None)
        self.assertRaises(TypeError, operator.sub, None, c1)

    def test_mul(self):
        c1 = pygame.Color(0x01010101)
        self.assertEqual(c1.r, 1)
        self.assertEqual(c1.g, 1)
        self.assertEqual(c1.b, 1)
        self.assertEqual(c1.a, 1)

        c2 = pygame.Color(2, 5, 3, 22)
        self.assertEqual(c2.r, 2)
        self.assertEqual(c2.g, 5)
        self.assertEqual(c2.b, 3)
        self.assertEqual(c2.a, 22)

        c3 = c1 * c2
        self.assertEqual(c3.r, 2)
        self.assertEqual(c3.g, 5)
        self.assertEqual(c3.b, 3)
        self.assertEqual(c3.a, 22)

        c3 = c3 * c2
        self.assertEqual(c3.r, 4)
        self.assertEqual(c3.g, 25)
        self.assertEqual(c3.b, 9)
        self.assertEqual(c3.a, 255)

        # Issue #286: Is type checking done for Python 3.x?
        self.assertRaises(TypeError, operator.mul, c1, None)
        self.assertRaises(TypeError, operator.mul, None, c1)

    def test_div(self):
        c1 = pygame.Color(0x80808080)
        self.assertEqual(c1.r, 128)
        self.assertEqual(c1.g, 128)
        self.assertEqual(c1.b, 128)
        self.assertEqual(c1.a, 128)

        c2 = pygame.Color(2, 4, 8, 16)
        self.assertEqual(c2.r, 2)
        self.assertEqual(c2.g, 4)
        self.assertEqual(c2.b, 8)
        self.assertEqual(c2.a, 16)

        c3 = c1 // c2
        self.assertEqual(c3.r, 64)
        self.assertEqual(c3.g, 32)
        self.assertEqual(c3.b, 16)
        self.assertEqual(c3.a, 8)

        c3 = c3 // c2
        self.assertEqual(c3.r, 32)
        self.assertEqual(c3.g, 8)
        self.assertEqual(c3.b, 2)
        self.assertEqual(c3.a, 0)

        # Issue #286: Is type checking done for Python 3.x?
        self.assertRaises(TypeError, operator.floordiv, c1, None)
        self.assertRaises(TypeError, operator.floordiv, None, c1)

        # Division by zero check
        dividend = pygame.Color(255, 255, 255, 255)
        for i in range(4):
            divisor = pygame.Color(64, 64, 64, 64)
            divisor[i] = 0
            quotient = pygame.Color(3, 3, 3, 3)
            quotient[i] = 0
            self.assertEqual(dividend // divisor, quotient)

    def test_mod(self):
        c1 = pygame.Color(0xFFFFFFFF)
        self.assertEqual(c1.r, 255)
        self.assertEqual(c1.g, 255)
        self.assertEqual(c1.b, 255)
        self.assertEqual(c1.a, 255)

        c2 = pygame.Color(2, 4, 8, 16)
        self.assertEqual(c2.r, 2)
        self.assertEqual(c2.g, 4)
        self.assertEqual(c2.b, 8)
        self.assertEqual(c2.a, 16)

        c3 = c1 % c2
        self.assertEqual(c3.r, 1)
        self.assertEqual(c3.g, 3)
        self.assertEqual(c3.b, 7)
        self.assertEqual(c3.a, 15)

        # Issue #286: Is type checking done for Python 3.x?
        self.assertRaises(TypeError, operator.mod, c1, None)
        self.assertRaises(TypeError, operator.mod, None, c1)

        # Division by zero check
        dividend = pygame.Color(255, 255, 255, 255)
        for i in range(4):
            divisor = pygame.Color(64, 64, 64, 64)
            divisor[i] = 0
            quotient = pygame.Color(63, 63, 63, 63)
            quotient[i] = 0
            self.assertEqual(dividend % divisor, quotient)

    def test_float(self):
        c = pygame.Color(0xCC00CC00)
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 0)
        self.assertEqual(float(c), float(0xCC00CC00))

        c = pygame.Color(0x33727592)
        self.assertEqual(c.r, 51)
        self.assertEqual(c.g, 114)
        self.assertEqual(c.b, 117)
        self.assertEqual(c.a, 146)
        self.assertEqual(float(c), float(0x33727592))

    def test_oct(self):
        c = pygame.Color(0xCC00CC00)
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 0)
        self.assertEqual(oct(c), oct(0xCC00CC00))

        c = pygame.Color(0x33727592)
        self.assertEqual(c.r, 51)
        self.assertEqual(c.g, 114)
        self.assertEqual(c.b, 117)
        self.assertEqual(c.a, 146)
        self.assertEqual(oct(c), oct(0x33727592))

    def test_hex(self):
        c = pygame.Color(0xCC00CC00)
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 0)
        self.assertEqual(hex(c), hex(0xCC00CC00))

        c = pygame.Color(0x33727592)
        self.assertEqual(c.r, 51)
        self.assertEqual(c.g, 114)
        self.assertEqual(c.b, 117)
        self.assertEqual(c.a, 146)
        self.assertEqual(hex(c), hex(0x33727592))

    def test_webstyle(self):
        c = pygame.Color("#CC00CC11")
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 17)
        self.assertEqual(hex(c), hex(0xCC00CC11))

        c = pygame.Color("#CC00CC")
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 255)
        self.assertEqual(hex(c), hex(0xCC00CCFF))

        c = pygame.Color("0xCC00CC11")
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 17)
        self.assertEqual(hex(c), hex(0xCC00CC11))

        c = pygame.Color("0xCC00CC")
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 255)
        self.assertEqual(hex(c), hex(0xCC00CCFF))

        self.assertRaises(ValueError, pygame.Color, "#cc00qq")
        self.assertRaises(ValueError, pygame.Color, "0xcc00qq")
        self.assertRaises(ValueError, pygame.Color, "09abcdef")
        self.assertRaises(ValueError, pygame.Color, "09abcde")
        self.assertRaises(ValueError, pygame.Color, "quarky")

    def test_int(self):
        # This will be a long
        c = pygame.Color(0xCC00CC00)
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 0)
        self.assertEqual(int(c), int(0xCC00CC00))

        # This will be an int
        c = pygame.Color(0x33727592)
        self.assertEqual(c.r, 51)
        self.assertEqual(c.g, 114)
        self.assertEqual(c.b, 117)
        self.assertEqual(c.a, 146)
        self.assertEqual(int(c), int(0x33727592))

    def test_long(self):
        # This will be a long
        c = pygame.Color(0xCC00CC00)
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 204)
        self.assertEqual(c.a, 0)
        self.assertEqual(int(c), int(0xCC00CC00))

        # This will be an int
        c = pygame.Color(0x33727592)
        self.assertEqual(c.r, 51)
        self.assertEqual(c.g, 114)
        self.assertEqual(c.b, 117)
        self.assertEqual(c.a, 146)
        self.assertEqual(int(c), int(0x33727592))

    def test_normalize(self):
        c = pygame.Color(204, 38, 194, 55)
        self.assertEqual(c.r, 204)
        self.assertEqual(c.g, 38)
        self.assertEqual(c.b, 194)
        self.assertEqual(c.a, 55)

        t = c.normalize()

        self.assertAlmostEqual(t[0], 0.800000, 5)
        self.assertAlmostEqual(t[1], 0.149016, 5)
        self.assertAlmostEqual(t[2], 0.760784, 5)
        self.assertAlmostEqual(t[3], 0.215686, 5)

    def test_len(self):
        c = pygame.Color(204, 38, 194, 55)
        self.assertEqual(len(c), 4)

    def test_get_item(self):
        c = pygame.Color(204, 38, 194, 55)
        self.assertEqual(c[0], 204)
        self.assertEqual(c[1], 38)
        self.assertEqual(c[2], 194)
        self.assertEqual(c[3], 55)

    def test_set_item(self):
        c = pygame.Color(204, 38, 194, 55)
        self.assertEqual(c[0], 204)
        self.assertEqual(c[1], 38)
        self.assertEqual(c[2], 194)
        self.assertEqual(c[3], 55)

        c[0] = 33
        self.assertEqual(c[0], 33)
        c[1] = 48
        self.assertEqual(c[1], 48)
        c[2] = 173
        self.assertEqual(c[2], 173)
        c[3] = 213
        self.assertEqual(c[3], 213)

        # Now try some 'invalid' ones
        self.assertRaises(TypeError, _assign_item, c, 0, 95.485)
        self.assertEqual(c[0], 33)
        self.assertRaises(ValueError, _assign_item, c, 1, -83)
        self.assertEqual(c[1], 48)
        self.assertRaises(TypeError, _assign_item, c, 2, "Hello")
        self.assertEqual(c[2], 173)

    def test_Color_type_works_for_Surface_get_and_set_colorkey(self):
        s = pygame.Surface((32, 32))

        c = pygame.Color(33, 22, 11, 255)
        s.set_colorkey(c)

        get_r, get_g, get_b, get_a = s.get_colorkey()

        self.assertTrue(get_r == c.r)
        self.assertTrue(get_g == c.g)
        self.assertTrue(get_b == c.b)
        self.assertTrue(get_a == c.a)

    ########## HSLA, HSVA, CMY, I1I2I3 ALL ELEMENTS WITHIN SPECIFIED RANGE #########

    def test_hsla__all_elements_within_limits(self):
        for c in rgba_combos_Color_generator():
            h, s, l, a = c.hsla
            self.assertTrue(0 <= h <= 360)
            self.assertTrue(0 <= s <= 100)
            self.assertTrue(0 <= l <= 100)
            self.assertTrue(0 <= a <= 100)

    def test_hsva__all_elements_within_limits(self):
        for c in rgba_combos_Color_generator():
            h, s, v, a = c.hsva
            self.assertTrue(0 <= h <= 360)
            self.assertTrue(0 <= s <= 100)
            self.assertTrue(0 <= v <= 100)
            self.assertTrue(0 <= a <= 100)

    def test_cmy__all_elements_within_limits(self):
        for c in rgba_combos_Color_generator():
            c, m, y = c.cmy
            self.assertTrue(0 <= c <= 1)
            self.assertTrue(0 <= m <= 1)
            self.assertTrue(0 <= y <= 1)

    def test_i1i2i3__all_elements_within_limits(self):
        for c in rgba_combos_Color_generator():
            i1, i2, i3 = c.i1i2i3
            self.assertTrue(0 <= i1 <= 1)
            self.assertTrue(-0.5 <= i2 <= 0.5)
            self.assertTrue(-0.5 <= i3 <= 0.5)

    def test_issue_269(self):
        """PyColor OverflowError on HSVA with hue value of 360

        >>> c = pygame.Color(0)
        >>> c.hsva = (360,0,0,0)
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
        OverflowError: this is not allowed to happen ever
        >>> pygame.ver
        '1.9.1release'
        >>>

        """

        c = pygame.Color(0)
        c.hsva = 360, 0, 0, 0
        self.assertEqual(c.hsva, (0, 0, 0, 0))
        c.hsva = 360, 100, 100, 100
        self.assertEqual(c.hsva, (0, 100, 100, 100))
        self.assertEqual(c, (255, 0, 0, 255))

    ####################### COLORSPACE PROPERTY SANITY TESTS #######################

    def colorspaces_converted_should_not_raise(self, prop):
        fails = 0

        x = 0
        for c in rgba_combos_Color_generator():
            x += 1

            other = pygame.Color(0)

            try:
                setattr(other, prop, getattr(c, prop))
                # eg other.hsla = c.hsla

            except ValueError:
                fails += 1

        self.assertTrue(x > 0, "x is combination counter, 0 means no tests!")
        self.assertTrue((fails, x) == (0, x))

    def test_hsla__sanity_testing_converted_should_not_raise(self):
        self.colorspaces_converted_should_not_raise("hsla")

    def test_hsva__sanity_testing_converted_should_not_raise(self):
        self.colorspaces_converted_should_not_raise("hsva")

    def test_cmy__sanity_testing_converted_should_not_raise(self):
        self.colorspaces_converted_should_not_raise("cmy")

    def test_i1i2i3__sanity_testing_converted_should_not_raise(self):
        self.colorspaces_converted_should_not_raise("i1i2i3")

    ################################################################################

    def colorspaces_converted_should_equate_bar_rounding(self, prop):
        for c in rgba_combos_Color_generator():
            other = pygame.Color(0)

            try:
                setattr(other, prop, getattr(c, prop))
                # eg other.hsla = c.hsla

                self.assertTrue(abs(other.r - c.r) <= 1)
                self.assertTrue(abs(other.b - c.b) <= 1)
                self.assertTrue(abs(other.g - c.g) <= 1)
                # CMY and I1I2I3 do not care about the alpha
                if not prop in ("cmy", "i1i2i3"):
                    self.assertTrue(abs(other.a - c.a) <= 1)

            except ValueError:
                pass  # other tests will notify, this tests equation

    def test_hsla__sanity_testing_converted_should_equate_bar_rounding(self):
        self.colorspaces_converted_should_equate_bar_rounding("hsla")

    def test_hsva__sanity_testing_converted_should_equate_bar_rounding(self):
        self.colorspaces_converted_should_equate_bar_rounding("hsva")

    def test_cmy__sanity_testing_converted_should_equate_bar_rounding(self):
        self.colorspaces_converted_should_equate_bar_rounding("cmy")

    def test_i1i2i3__sanity_testing_converted_should_equate_bar_rounding(self):
        self.colorspaces_converted_should_equate_bar_rounding("i1i2i3")

    ################################################################################

    def test_correct_gamma__verified_against_python_implementation(self):
        "|tags:slow|"
        # gamma_correct defined at top of page

        gammas = [i / 10.0 for i in range(1, 31)]  # [0.1 ... 3.0]
        gammas_len = len(gammas)

        for i, c in enumerate(rgba_combos_Color_generator()):
            gamma = gammas[i % gammas_len]

            corrected = pygame.Color(*[gamma_correct(x, gamma) for x in tuple(c)])
            lib_corrected = c.correct_gamma(gamma)

            self.assertTrue(corrected.r == lib_corrected.r)
            self.assertTrue(corrected.g == lib_corrected.g)
            self.assertTrue(corrected.b == lib_corrected.b)
            self.assertTrue(corrected.a == lib_corrected.a)

        # TODO: test against statically defined verified _correct_ values
        # assert corrected.r == 125 etc.

    def test_pickle(self):
        import pickle

        c1 = pygame.Color(1, 2, 3, 4)
        # c2 = pygame.Color(255,254,253,252)
        pickle_string = pickle.dumps(c1)
        c1_frompickle = pickle.loads(pickle_string)
        self.assertEqual(c1, c1_frompickle)

    ################################################################################
    # only available if ctypes module is also available

    @unittest.skipIf(IS_PYPY, "PyPy has no ctypes")
    def test_arraystruct(self):
        import pygame.tests.test_utils.arrinter as ai
        import ctypes as ct

        c_byte_p = ct.POINTER(ct.c_byte)
        c = pygame.Color(5, 7, 13, 23)
        flags = ai.PAI_CONTIGUOUS | ai.PAI_FORTRAN | ai.PAI_ALIGNED | ai.PAI_NOTSWAPPED
        for i in range(1, 5):
            c.set_length(i)
            inter = ai.ArrayInterface(c)
            self.assertEqual(inter.two, 2)
            self.assertEqual(inter.nd, 1)
            self.assertEqual(inter.typekind, "u")
            self.assertEqual(inter.itemsize, 1)
            self.assertEqual(inter.flags, flags)
            self.assertEqual(inter.shape[0], i)
            self.assertEqual(inter.strides[0], 1)
            data = ct.cast(inter.data, c_byte_p)
            for j in range(i):
                self.assertEqual(data[j], c[j])

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def test_newbuf(self):
        from pygame.tests.test_utils import buftools
        from ctypes import cast, POINTER, c_uint8

        class ColorImporter(buftools.Importer):
            def __init__(self, color, flags):
                super().__init__(color, flags)
                self.items = cast(self.buf, POINTER(c_uint8))

            def __getitem__(self, index):
                if 0 <= index < 4:
                    return self.items[index]
                raise IndexError(f"valid index values are between 0 and 3: got {index}")

            def __setitem__(self, index, value):
                if 0 <= index < 4:
                    self.items[index] = value
                else:
                    raise IndexError(
                        f"valid index values are between 0 and 3: got {index}"
                    )

        c = pygame.Color(50, 100, 150, 200)
        imp = ColorImporter(c, buftools.PyBUF_SIMPLE)
        self.assertTrue(imp.obj is c)
        self.assertEqual(imp.ndim, 0)
        self.assertEqual(imp.itemsize, 1)
        self.assertEqual(imp.len, 4)
        self.assertTrue(imp.readonly)
        self.assertTrue(imp.format is None)
        self.assertTrue(imp.shape is None)
        self.assertTrue(imp.strides is None)
        self.assertTrue(imp.suboffsets is None)
        for i in range(4):
            self.assertEqual(c[i], imp[i])
        imp[0] = 60
        self.assertEqual(c.r, 60)
        imp[1] = 110
        self.assertEqual(c.g, 110)
        imp[2] = 160
        self.assertEqual(c.b, 160)
        imp[3] = 210
        self.assertEqual(c.a, 210)
        imp = ColorImporter(c, buftools.PyBUF_FORMAT)
        self.assertEqual(imp.ndim, 0)
        self.assertEqual(imp.itemsize, 1)
        self.assertEqual(imp.len, 4)
        self.assertEqual(imp.format, "B")
        self.assertEqual(imp.ndim, 0)
        self.assertEqual(imp.itemsize, 1)
        self.assertEqual(imp.len, 4)
        imp = ColorImporter(c, buftools.PyBUF_ND)
        self.assertEqual(imp.ndim, 1)
        self.assertEqual(imp.itemsize, 1)
        self.assertEqual(imp.len, 4)
        self.assertTrue(imp.format is None)
        self.assertEqual(imp.shape, (4,))
        self.assertEqual(imp.strides, None)
        imp = ColorImporter(c, buftools.PyBUF_STRIDES)
        self.assertEqual(imp.ndim, 1)
        self.assertTrue(imp.format is None)
        self.assertEqual(imp.shape, (4,))
        self.assertEqual(imp.strides, (1,))
        imp = ColorImporter(c, buftools.PyBUF_C_CONTIGUOUS)
        self.assertEqual(imp.ndim, 1)
        imp = ColorImporter(c, buftools.PyBUF_F_CONTIGUOUS)
        self.assertEqual(imp.ndim, 1)
        imp = ColorImporter(c, buftools.PyBUF_ANY_CONTIGUOUS)
        self.assertEqual(imp.ndim, 1)
        for i in range(1, 5):
            c.set_length(i)
            imp = ColorImporter(c, buftools.PyBUF_ND)
            self.assertEqual(imp.ndim, 1)
            self.assertEqual(imp.len, i)
            self.assertEqual(imp.shape, (i,))
        self.assertRaises(BufferError, ColorImporter, c, buftools.PyBUF_WRITABLE)

    def test_color_iter(self):
        c = pygame.Color(50, 100, 150, 200)

        # call __iter__ explicitly to test that it is defined
        color_iterator = c.__iter__()
        for i, val in enumerate(color_iterator):
            self.assertEqual(c[i], val)

    def test_color_contains(self):
        c = pygame.Color(50, 60, 70)

        # call __contains__ explicitly to test that it is defined
        self.assertTrue(c.__contains__(50))
        self.assertTrue(60 in c)
        self.assertTrue(70 in c)
        self.assertFalse(100 in c)
        self.assertFalse(c.__contains__(10))

        self.assertRaises(TypeError, lambda: "string" in c)
        self.assertRaises(TypeError, lambda: 3.14159 in c)

    def test_grayscale(self):
        Color = pygame.color.Color

        color = Color(255, 0, 0, 255)
        self.assertEqual(color.grayscale(), Color(76, 76, 76, 255))
        color = Color(3, 5, 7, 255)
        self.assertEqual(color.grayscale(), Color(4, 4, 4, 255))
        color = Color(3, 5, 70, 255)
        self.assertEqual(color.grayscale(), Color(11, 11, 11, 255))
        color = Color(3, 50, 70, 255)
        self.assertEqual(color.grayscale(), Color(38, 38, 38, 255))
        color = Color(30, 50, 70, 255)
        self.assertEqual(color.grayscale(), Color(46, 46, 46, 255))

        color = Color(255, 0, 0, 144)
        self.assertEqual(color.grayscale(), Color(76, 76, 76, 144))
        color = Color(3, 5, 7, 144)
        self.assertEqual(color.grayscale(), Color(4, 4, 4, 144))
        color = Color(3, 5, 70, 144)
        self.assertEqual(color.grayscale(), Color(11, 11, 11, 144))
        color = Color(3, 50, 70, 144)
        self.assertEqual(color.grayscale(), Color(38, 38, 38, 144))
        color = Color(30, 50, 70, 144)
        self.assertEqual(color.grayscale(), Color(46, 46, 46, 144))

    def test_lerp(self):
        # setup
        Color = pygame.color.Color

        color0 = Color(0, 0, 0, 0)
        color128 = Color(128, 128, 128, 128)
        color255 = Color(255, 255, 255, 255)
        color100 = Color(100, 100, 100, 100)

        # type checking
        self.assertTrue(isinstance(color0.lerp(color128, 0.5), Color))

        # common value testing
        self.assertEqual(color0.lerp(color128, 0.5), Color(64, 64, 64, 64))
        self.assertEqual(color0.lerp(color128, 0.5), Color(64, 64, 64, 64))
        self.assertEqual(color128.lerp(color255, 0.5), Color(192, 192, 192, 192))
        self.assertEqual(color0.lerp(color255, 0.5), Color(128, 128, 128, 128))

        # testing extremes
        self.assertEqual(color0.lerp(color100, 0), color0)
        self.assertEqual(color0.lerp(color100, 0.01), Color(1, 1, 1, 1))
        self.assertEqual(color0.lerp(color100, 0.99), Color(99, 99, 99, 99))
        self.assertEqual(color0.lerp(color100, 1), color100)

        # kwarg testing
        self.assertEqual(color0.lerp(color=color100, amount=0.5), Color(50, 50, 50, 50))
        self.assertEqual(color0.lerp(amount=0.5, color=color100), Color(50, 50, 50, 50))

        # invalid input testing
        self.assertRaises(ValueError, lambda: color0.lerp(color128, 2.5))
        self.assertRaises(ValueError, lambda: color0.lerp(color128, -0.5))
        self.assertRaises(ValueError, lambda: color0.lerp((256, 0, 0, 0), 0.5))
        self.assertRaises(ValueError, lambda: color0.lerp((0, 256, 0, 0), 0.5))
        self.assertRaises(ValueError, lambda: color0.lerp((0, 0, 256, 0), 0.5))
        self.assertRaises(ValueError, lambda: color0.lerp((0, 0, 0, 256), 0.5))
        self.assertRaises(TypeError, lambda: color0.lerp(0.2, 0.5))

    def test_premul_alpha(self):
        # setup
        Color = pygame.color.Color

        color0 = Color(0, 0, 0, 0)
        alpha0 = Color(255, 255, 255, 0)
        alpha49 = Color(255, 0, 0, 49)
        alpha67 = Color(0, 255, 0, 67)
        alpha73 = Color(0, 0, 255, 73)
        alpha128 = Color(255, 255, 255, 128)
        alpha199 = Color(255, 255, 255, 199)
        alpha255 = Color(128, 128, 128, 255)

        # type checking
        self.assertTrue(isinstance(color0.premul_alpha(), Color))

        # hand crafted value testing
        self.assertEqual(alpha0.premul_alpha(), Color(0, 0, 0, 0))
        self.assertEqual(alpha49.premul_alpha(), Color(49, 0, 0, 49))
        self.assertEqual(alpha67.premul_alpha(), Color(0, 67, 0, 67))
        self.assertEqual(alpha73.premul_alpha(), Color(0, 0, 73, 73))
        self.assertEqual(alpha128.premul_alpha(), Color(128, 128, 128, 128))
        self.assertEqual(alpha199.premul_alpha(), Color(199, 199, 199, 199))
        self.assertEqual(alpha255.premul_alpha(), Color(128, 128, 128, 255))

        # full range of alpha auto sub-testing
        test_colors = [
            (200, 30, 74),
            (76, 83, 24),
            (184, 21, 6),
            (74, 4, 74),
            (76, 83, 24),
            (184, 21, 234),
            (160, 30, 74),
            (96, 147, 204),
            (198, 201, 60),
            (132, 89, 74),
            (245, 9, 224),
            (184, 112, 6),
        ]

        for r, g, b in test_colors:
            for a in range(255):
                with self.subTest(r=r, g=g, b=b, a=a):
                    alpha = a / 255.0
                    self.assertEqual(
                        Color(r, g, b, a).premul_alpha(),
                        Color(
                            ((r + 1) * a) >> 8,
                            ((g + 1) * a) >> 8,
                            ((b + 1) * a) >> 8,
                            a,
                        ),
                    )

    def test_update(self):
        c = pygame.color.Color(0, 0, 0)
        c.update(1, 2, 3, 4)

        self.assertEqual(c.r, 1)
        self.assertEqual(c.g, 2)
        self.assertEqual(c.b, 3)
        self.assertEqual(c.a, 4)

        c = pygame.color.Color(0, 0, 0)
        c.update([1, 2, 3, 4])

        self.assertEqual(c.r, 1)
        self.assertEqual(c.g, 2)
        self.assertEqual(c.b, 3)
        self.assertEqual(c.a, 4)

        c = pygame.color.Color(0, 0, 0)
        c2 = pygame.color.Color(1, 2, 3, 4)
        c.update(c2)

        self.assertEqual(c.r, 1)
        self.assertEqual(c.g, 2)
        self.assertEqual(c.b, 3)
        self.assertEqual(c.a, 4)

        c = pygame.color.Color(1, 1, 1)
        c.update("black")

        self.assertEqual(c.r, 0)
        self.assertEqual(c.g, 0)
        self.assertEqual(c.b, 0)
        self.assertEqual(c.a, 255)

        c = pygame.color.Color(0, 0, 0, 120)
        c.set_length(3)
        c.update(1, 2, 3)
        self.assertEqual(len(c), 3)
        c.set_length(4)
        self.assertEqual(c[3], 120)

        c.set_length(3)
        c.update(1, 2, 3, 4)
        self.assertEqual(len(c), 4)

    def test_collection_abc(self):
        c = pygame.Color(64, 70, 75, 255)
        self.assertTrue(isinstance(c, Collection))
        self.assertFalse(isinstance(c, Sequence))


class SubclassTest(unittest.TestCase):
    class MyColor(pygame.Color):
        def __init__(self, *args, **kwds):
            super(SubclassTest.MyColor, self).__init__(*args, **kwds)
            self.an_attribute = True

    def test_add(self):
        mc1 = self.MyColor(128, 128, 128, 255)
        self.assertTrue(mc1.an_attribute)
        c2 = pygame.Color(64, 64, 64, 255)
        mc2 = mc1 + c2
        self.assertTrue(isinstance(mc2, self.MyColor))
        self.assertRaises(AttributeError, getattr, mc2, "an_attribute")
        c3 = c2 + mc1
        self.assertTrue(type(c3) is pygame.Color)

    def test_sub(self):
        mc1 = self.MyColor(128, 128, 128, 255)
        self.assertTrue(mc1.an_attribute)
        c2 = pygame.Color(64, 64, 64, 255)
        mc2 = mc1 - c2
        self.assertTrue(isinstance(mc2, self.MyColor))
        self.assertRaises(AttributeError, getattr, mc2, "an_attribute")
        c3 = c2 - mc1
        self.assertTrue(type(c3) is pygame.Color)

    def test_mul(self):
        mc1 = self.MyColor(128, 128, 128, 255)
        self.assertTrue(mc1.an_attribute)
        c2 = pygame.Color(64, 64, 64, 255)
        mc2 = mc1 * c2
        self.assertTrue(isinstance(mc2, self.MyColor))
        self.assertRaises(AttributeError, getattr, mc2, "an_attribute")
        c3 = c2 * mc1
        self.assertTrue(type(c3) is pygame.Color)

    def test_div(self):
        mc1 = self.MyColor(128, 128, 128, 255)
        self.assertTrue(mc1.an_attribute)
        c2 = pygame.Color(64, 64, 64, 255)
        mc2 = mc1 // c2
        self.assertTrue(isinstance(mc2, self.MyColor))
        self.assertRaises(AttributeError, getattr, mc2, "an_attribute")
        c3 = c2 // mc1
        self.assertTrue(type(c3) is pygame.Color)

    def test_mod(self):
        mc1 = self.MyColor(128, 128, 128, 255)
        self.assertTrue(mc1.an_attribute)
        c2 = pygame.Color(64, 64, 64, 255)
        mc2 = mc1 % c2
        self.assertTrue(isinstance(mc2, self.MyColor))
        self.assertRaises(AttributeError, getattr, mc2, "an_attribute")
        c3 = c2 % mc1
        self.assertTrue(type(c3) is pygame.Color)

    def test_inv(self):
        mc1 = self.MyColor(64, 64, 64, 64)
        self.assertTrue(mc1.an_attribute)
        mc2 = ~mc1
        self.assertTrue(isinstance(mc2, self.MyColor))
        self.assertRaises(AttributeError, getattr, mc2, "an_attribute")

    def test_correct_gamma(self):
        mc1 = self.MyColor(64, 70, 75, 255)
        self.assertTrue(mc1.an_attribute)
        mc2 = mc1.correct_gamma(0.03)
        self.assertTrue(isinstance(mc2, self.MyColor))
        self.assertRaises(AttributeError, getattr, mc2, "an_attribute")

    def test_collection_abc(self):
        mc1 = self.MyColor(64, 70, 75, 255)
        self.assertTrue(isinstance(mc1, Collection))
        self.assertFalse(isinstance(mc1, Sequence))


################################################################################

if __name__ == "__main__":
    unittest.main()
