import unittest
from pygame.tests.test_utils import fixture_path
import pygame


class CursorsModuleTest(unittest.TestCase):
    def test_compile(self):
        # __doc__ (as of 2008-06-25) for pygame.cursors.compile:

        # pygame.cursors.compile(strings, black, white,xor) -> data, mask
        # compile cursor strings into cursor data
        #
        # This takes a set of strings with equal length and computes
        # the binary data for that cursor. The string widths must be
        # divisible by 8.
        #
        # The black and white arguments are single letter strings that
        # tells which characters will represent black pixels, and which
        # characters represent white pixels. All other characters are
        # considered clear.
        #
        # This returns a tuple containing the cursor data and cursor mask
        # data. Both these arguments are used when setting a cursor with
        # pygame.mouse.set_cursor().

        # Various types of input strings
        test_cursor1 = ("X.X.XXXX", "XXXXXX..", "  XXXX  ")

        test_cursor2 = (
            "X.X.XXXX",
            "XXXXXX..",
            "XXXXXX ",
            "XXXXXX..",
            "XXXXXX..",
            "XXXXXX",
            "XXXXXX..",
            "XXXXXX..",
        )
        test_cursor3 = (".XX.", "  ", "..  ", "X.. X")

        # Test such that total number of strings is not divisible by 8
        with self.assertRaises(ValueError):
            pygame.cursors.compile(test_cursor1)

        # Test such that size of individual string is not divisible by 8
        with self.assertRaises(ValueError):
            pygame.cursors.compile(test_cursor2)

        # Test such that neither size of individual string nor total number of strings is divisible by 8
        with self.assertRaises(ValueError):
            pygame.cursors.compile(test_cursor3)

        # Test that checks whether the byte data from compile function is equal to actual byte data
        actual_byte_data = (
            192,
            0,
            0,
            224,
            0,
            0,
            240,
            0,
            0,
            216,
            0,
            0,
            204,
            0,
            0,
            198,
            0,
            0,
            195,
            0,
            0,
            193,
            128,
            0,
            192,
            192,
            0,
            192,
            96,
            0,
            192,
            48,
            0,
            192,
            56,
            0,
            192,
            248,
            0,
            220,
            192,
            0,
            246,
            96,
            0,
            198,
            96,
            0,
            6,
            96,
            0,
            3,
            48,
            0,
            3,
            48,
            0,
            1,
            224,
            0,
            1,
            128,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ), (
            192,
            0,
            0,
            224,
            0,
            0,
            240,
            0,
            0,
            248,
            0,
            0,
            252,
            0,
            0,
            254,
            0,
            0,
            255,
            0,
            0,
            255,
            128,
            0,
            255,
            192,
            0,
            255,
            224,
            0,
            255,
            240,
            0,
            255,
            248,
            0,
            255,
            248,
            0,
            255,
            192,
            0,
            247,
            224,
            0,
            199,
            224,
            0,
            7,
            224,
            0,
            3,
            240,
            0,
            3,
            240,
            0,
            1,
            224,
            0,
            1,
            128,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )

        cursor = pygame.cursors.compile(pygame.cursors.thickarrow_strings)
        self.assertEqual(cursor, actual_byte_data)

        # Test such that cursor byte data obtained from compile function is valid in pygame.mouse.set_cursor()
        pygame.display.init()
        try:
            pygame.mouse.set_cursor((24, 24), (0, 0), *cursor)
        except pygame.error as e:
            if "not currently supported" in str(e):
                unittest.skip("skipping test as set_cursor() is not supported")
        finally:
            pygame.display.quit()

    ################################################################################

    def test_load_xbm(self):
        # __doc__ (as of 2008-06-25) for pygame.cursors.load_xbm:

        # pygame.cursors.load_xbm(cursorfile, maskfile) -> cursor_args
        # reads a pair of XBM files into set_cursor arguments
        #
        # Arguments can either be filenames or filelike objects
        # with the readlines method. Not largely tested, but
        # should work with typical XBM files.

        # Test that load_xbm will take filenames as arguments
        cursorfile = fixture_path(r"xbm_cursors/white_sizing.xbm")
        maskfile = fixture_path(r"xbm_cursors/white_sizing_mask.xbm")
        cursor = pygame.cursors.load_xbm(cursorfile, maskfile)

        # Test that load_xbm will take file objects as arguments
        with open(cursorfile) as cursor_f, open(maskfile) as mask_f:
            cursor = pygame.cursors.load_xbm(cursor_f, mask_f)

        # Can it load using pathlib.Path?
        import pathlib

        cursor = pygame.cursors.load_xbm(
            pathlib.Path(cursorfile), pathlib.Path(maskfile)
        )

        # Is it in a format that mouse.set_cursor won't blow up on?
        pygame.display.init()
        try:
            pygame.mouse.set_cursor(*cursor)
        except pygame.error as e:
            if "not currently supported" in str(e):
                unittest.skip("skipping test as set_cursor() is not supported")
        finally:
            pygame.display.quit()

    def test_Cursor(self):
        """Ensure that the cursor object parses information properly"""

        c1 = pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_CROSSHAIR)

        self.assertEqual(c1.data, (pygame.SYSTEM_CURSOR_CROSSHAIR,))
        self.assertEqual(c1.type, "system")

        c2 = pygame.cursors.Cursor(c1)

        self.assertEqual(c1, c2)

        with self.assertRaises(TypeError):
            pygame.cursors.Cursor(-34002)
        with self.assertRaises(TypeError):
            pygame.cursors.Cursor("a", "b", "c", "d")
        with self.assertRaises(TypeError):
            pygame.cursors.Cursor((2,))

        c3 = pygame.cursors.Cursor((0, 0), pygame.Surface((20, 20)))

        self.assertEqual(c3.data[0], (0, 0))
        self.assertEqual(c3.data[1].get_size(), (20, 20))
        self.assertEqual(c3.type, "color")

        xormask, andmask = pygame.cursors.compile(pygame.cursors.thickarrow_strings)
        c4 = pygame.cursors.Cursor((24, 24), (0, 0), xormask, andmask)

        self.assertEqual(c4.data, ((24, 24), (0, 0), xormask, andmask))
        self.assertEqual(c4.type, "bitmap")


################################################################################

if __name__ == "__main__":
    unittest.main()

################################################################################
