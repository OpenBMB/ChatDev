import os

if os.environ.get("SDL_VIDEODRIVER") == "dummy":
    __tags__ = ("ignore", "subprocess_ignore")

import unittest
import ctypes
import weakref
import gc
import pathlib
import platform

IS_PYPY = "PyPy" == platform.python_implementation()


try:
    from pygame.tests.test_utils import arrinter
except NameError:
    pass

import pygame

try:
    import pygame.freetype as ft
except ImportError:
    ft = None


FONTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "fonts")


def nullfont():
    """return an uninitialized font instance"""
    return ft.Font.__new__(ft.Font)


max_point_size_FX6 = 0x7FFFFFFF
max_point_size = max_point_size_FX6 >> 6
max_point_size_f = max_point_size_FX6 * 0.015625


def surf_same_image(a, b):
    """Return True if a's pixel buffer is identical to b's"""

    a_sz = a.get_height() * a.get_pitch()
    b_sz = b.get_height() * b.get_pitch()
    if a_sz != b_sz:
        return False
    a_bytes = ctypes.string_at(a._pixels_address, a_sz)
    b_bytes = ctypes.string_at(b._pixels_address, b_sz)
    return a_bytes == b_bytes


class FreeTypeFontTest(unittest.TestCase):
    _fixed_path = os.path.join(FONTDIR, "test_fixed.otf")
    _sans_path = os.path.join(FONTDIR, "test_sans.ttf")
    _mono_path = os.path.join(FONTDIR, "PyGameMono.otf")
    _bmp_8_75dpi_path = os.path.join(FONTDIR, "PyGameMono-8.bdf")
    _bmp_18_75dpi_path = os.path.join(FONTDIR, "PyGameMono-18-75dpi.bdf")
    _bmp_18_100dpi_path = os.path.join(FONTDIR, "PyGameMono-18-100dpi.bdf")
    _TEST_FONTS = {}

    @classmethod
    def setUpClass(cls):
        ft.init()

        # Setup the test fonts.

        # Inconsolata is an open-source font designed by Raph Levien.
        # Licensed under the Open Font License.
        # http://www.levien.com/type/myfonts/inconsolata.html
        cls._TEST_FONTS["fixed"] = ft.Font(cls._fixed_path)

        # Liberation Sans is an open-source font designed by Steve Matteson.
        # Licensed under the GNU GPL.
        # https://fedorahosted.org/liberation-fonts/
        cls._TEST_FONTS["sans"] = ft.Font(cls._sans_path)

        # A scalable mono test font made for pygame. It contains only
        # a few glyphs: '\0', 'A', 'B', 'C', and U+13079.
        # It also contains two bitmap sizes: 8.0 X 8.0 and 19.0 X 19.0.
        cls._TEST_FONTS["mono"] = ft.Font(cls._mono_path)

        # A fixed size bitmap mono test font made for pygame.
        # It contains only a few glyphs: '\0', 'A', 'B', 'C', and U+13079.
        # The size is 8.0 X 8.0.
        cls._TEST_FONTS["bmp-8-75dpi"] = ft.Font(cls._bmp_8_75dpi_path)

        # A fixed size bitmap mono test font made for pygame.
        # It contains only a few glyphs: '\0', 'A', 'B', 'C', and U+13079.
        # The size is 8.0 X 8.0.
        cls._TEST_FONTS["bmp-18-75dpi"] = ft.Font(cls._bmp_18_75dpi_path)

        # A fixed size bitmap mono test font made for pygame.
        # It contains only a few glyphs: '\0', 'A', 'B', 'C', and U+13079.
        # The size is 8.0 X 8.0.
        cls._TEST_FONTS["bmp-18-100dpi"] = ft.Font(cls._bmp_18_100dpi_path)

    @classmethod
    def tearDownClass(cls):
        ft.quit()

    def test_freetype_defaultfont(self):
        font = ft.Font(None)
        self.assertEqual(font.name, "FreeSans")

    def test_freetype_Font_init(self):
        self.assertRaises(
            FileNotFoundError, ft.Font, os.path.join(FONTDIR, "nonexistent.ttf")
        )

        f = self._TEST_FONTS["sans"]
        self.assertIsInstance(f, ft.Font)

        f = self._TEST_FONTS["fixed"]
        self.assertIsInstance(f, ft.Font)

        # Test keyword arguments
        f = ft.Font(size=22, file=None)
        self.assertEqual(f.size, 22)
        f = ft.Font(font_index=0, file=None)
        self.assertNotEqual(ft.get_default_resolution(), 100)
        f = ft.Font(resolution=100, file=None)
        self.assertEqual(f.resolution, 100)
        f = ft.Font(ucs4=True, file=None)
        self.assertTrue(f.ucs4)
        self.assertRaises(OverflowError, ft.Font, file=None, size=(max_point_size + 1))
        self.assertRaises(OverflowError, ft.Font, file=None, size=-1)

        f = ft.Font(None, size=24)
        self.assertTrue(f.height > 0)
        self.assertRaises(
            FileNotFoundError, f.__init__, os.path.join(FONTDIR, "nonexistent.ttf")
        )

        # Test attribute preservation during reinitalization
        f = ft.Font(self._sans_path, size=24, ucs4=True)
        self.assertEqual(f.name, "Liberation Sans")
        self.assertTrue(f.scalable)
        self.assertFalse(f.fixed_width)
        self.assertTrue(f.antialiased)
        self.assertFalse(f.oblique)
        self.assertTrue(f.ucs4)
        f.antialiased = False
        f.oblique = True
        f.__init__(self._mono_path)
        self.assertEqual(f.name, "PyGameMono")
        self.assertTrue(f.scalable)
        self.assertTrue(f.fixed_width)
        self.assertFalse(f.antialiased)
        self.assertTrue(f.oblique)
        self.assertTrue(f.ucs4)

        # For a bitmap font, the size is automatically set to the first
        # size in the available sizes list.
        f = ft.Font(self._bmp_8_75dpi_path)
        sizes = f.get_sizes()
        self.assertEqual(len(sizes), 1)
        size_pt, width_px, height_px, x_ppem, y_ppem = sizes[0]
        self.assertEqual(f.size, (x_ppem, y_ppem))
        f.__init__(self._bmp_8_75dpi_path, size=12)
        self.assertEqual(f.size, 12.0)

    @unittest.skipIf(IS_PYPY, "PyPy doesn't use refcounting")
    def test_freetype_Font_dealloc(self):
        import sys

        handle = open(self._sans_path, "rb")

        def load_font():
            tempFont = ft.Font(handle)

        try:
            load_font()

            self.assertEqual(sys.getrefcount(handle), 2)
        finally:
            # Ensures file is closed even if test fails.
            handle.close()

    def test_freetype_Font_kerning(self):
        """Ensures get/set works with the kerning property."""
        ft_font = self._TEST_FONTS["sans"]

        # Test default is disabled.
        self.assertFalse(ft_font.kerning)

        # Test setting to True.
        ft_font.kerning = True

        self.assertTrue(ft_font.kerning)

        # Test setting to False.
        ft_font.kerning = False

        self.assertFalse(ft_font.kerning)

    def test_freetype_Font_kerning__enabled(self):
        """Ensures exceptions are not raised when calling freetype methods
        while kerning is enabled.

        Note: This does not test what changes occur to a rendered font by
              having kerning enabled.

        Related to issue #367.
        """
        surface = pygame.Surface((10, 10), 0, 32)
        TEST_TEXT = "Freetype Font"
        ft_font = self._TEST_FONTS["bmp-8-75dpi"]

        ft_font.kerning = True

        # Call different methods to ensure they don't raise an exception.
        metrics = ft_font.get_metrics(TEST_TEXT)
        self.assertIsInstance(metrics, list)

        rect = ft_font.get_rect(TEST_TEXT)
        self.assertIsInstance(rect, pygame.Rect)

        font_surf, rect = ft_font.render(TEST_TEXT)
        self.assertIsInstance(font_surf, pygame.Surface)
        self.assertIsInstance(rect, pygame.Rect)

        rect = ft_font.render_to(surface, (0, 0), TEST_TEXT)
        self.assertIsInstance(rect, pygame.Rect)

        buf, size = ft_font.render_raw(TEST_TEXT)
        self.assertIsInstance(buf, bytes)
        self.assertIsInstance(size, tuple)

        rect = ft_font.render_raw_to(surface.get_view("2"), TEST_TEXT)
        self.assertIsInstance(rect, pygame.Rect)

    def test_freetype_Font_scalable(self):
        f = self._TEST_FONTS["sans"]
        self.assertTrue(f.scalable)

        self.assertRaises(RuntimeError, lambda: nullfont().scalable)

    def test_freetype_Font_fixed_width(self):
        f = self._TEST_FONTS["sans"]
        self.assertFalse(f.fixed_width)

        f = self._TEST_FONTS["mono"]
        self.assertTrue(f.fixed_width)

        self.assertRaises(RuntimeError, lambda: nullfont().fixed_width)

    def test_freetype_Font_fixed_sizes(self):
        f = self._TEST_FONTS["sans"]
        self.assertEqual(f.fixed_sizes, 0)
        f = self._TEST_FONTS["bmp-8-75dpi"]
        self.assertEqual(f.fixed_sizes, 1)
        f = self._TEST_FONTS["mono"]
        self.assertEqual(f.fixed_sizes, 2)

    def test_freetype_Font_get_sizes(self):
        f = self._TEST_FONTS["sans"]
        szlist = f.get_sizes()
        self.assertIsInstance(szlist, list)
        self.assertEqual(len(szlist), 0)

        f = self._TEST_FONTS["bmp-8-75dpi"]
        szlist = f.get_sizes()
        self.assertIsInstance(szlist, list)
        self.assertEqual(len(szlist), 1)

        size8 = szlist[0]
        self.assertIsInstance(size8[0], int)
        self.assertEqual(size8[0], 8)
        self.assertIsInstance(size8[1], int)
        self.assertIsInstance(size8[2], int)
        self.assertIsInstance(size8[3], float)
        self.assertEqual(int(size8[3] * 64.0 + 0.5), 8 * 64)
        self.assertIsInstance(size8[4], float)
        self.assertEqual(int(size8[4] * 64.0 + 0.5), 8 * 64)

        f = self._TEST_FONTS["mono"]
        szlist = f.get_sizes()
        self.assertIsInstance(szlist, list)
        self.assertEqual(len(szlist), 2)

        size8 = szlist[0]
        self.assertEqual(size8[3], 8)
        self.assertEqual(int(size8[3] * 64.0 + 0.5), 8 * 64)
        self.assertEqual(int(size8[4] * 64.0 + 0.5), 8 * 64)

        size19 = szlist[1]
        self.assertEqual(size19[3], 19)
        self.assertEqual(int(size19[3] * 64.0 + 0.5), 19 * 64)
        self.assertEqual(int(size19[4] * 64.0 + 0.5), 19 * 64)

    def test_freetype_Font_use_bitmap_strikes(self):
        f = self._TEST_FONTS["mono"]
        try:
            # use_bitmap_strikes == True
            #
            self.assertTrue(f.use_bitmap_strikes)

            # bitmap compatible properties
            s_strike, sz = f.render_raw("A", size=19)
            try:
                f.vertical = True
                s_strike_vert, sz = f.render_raw("A", size=19)
            finally:
                f.vertical = False
            try:
                f.wide = True
                s_strike_wide, sz = f.render_raw("A", size=19)
            finally:
                f.wide = False
            try:
                f.underline = True
                s_strike_underline, sz = f.render_raw("A", size=19)
            finally:
                f.underline = False

            # bitmap incompatible properties
            s_strike_rot45, sz = f.render_raw("A", size=19, rotation=45)
            try:
                f.strong = True
                s_strike_strong, sz = f.render_raw("A", size=19)
            finally:
                f.strong = False
            try:
                f.oblique = True
                s_strike_oblique, sz = f.render_raw("A", size=19)
            finally:
                f.oblique = False

            # compare with use_bitmap_strikes == False
            #
            f.use_bitmap_strikes = False
            self.assertFalse(f.use_bitmap_strikes)

            # bitmap compatible properties
            s_outline, sz = f.render_raw("A", size=19)
            self.assertNotEqual(s_outline, s_strike)
            try:
                f.vertical = True
                s_outline, sz = f.render_raw("A", size=19)
                self.assertNotEqual(s_outline, s_strike_vert)
            finally:
                f.vertical = False
            try:
                f.wide = True
                s_outline, sz = f.render_raw("A", size=19)
                self.assertNotEqual(s_outline, s_strike_wide)
            finally:
                f.wide = False
            try:
                f.underline = True
                s_outline, sz = f.render_raw("A", size=19)
                self.assertNotEqual(s_outline, s_strike_underline)
            finally:
                f.underline = False

            # bitmap incompatible properties
            s_outline, sz = f.render_raw("A", size=19, rotation=45)
            self.assertEqual(s_outline, s_strike_rot45)
            try:
                f.strong = True
                s_outline, sz = f.render_raw("A", size=19)
                self.assertEqual(s_outline, s_strike_strong)
            finally:
                f.strong = False
            try:
                f.oblique = True
                s_outline, sz = f.render_raw("A", size=19)
                self.assertEqual(s_outline, s_strike_oblique)
            finally:
                f.oblique = False
        finally:
            f.use_bitmap_strikes = True

    def test_freetype_Font_bitmap_files(self):
        """Ensure bitmap file restrictions are caught"""
        f = self._TEST_FONTS["bmp-8-75dpi"]
        f_null = nullfont()
        s = pygame.Surface((10, 10), 0, 32)
        a = s.get_view("3")

        exception = AttributeError
        self.assertRaises(exception, setattr, f, "strong", True)
        self.assertRaises(exception, setattr, f, "oblique", True)
        self.assertRaises(exception, setattr, f, "style", ft.STYLE_STRONG)
        self.assertRaises(exception, setattr, f, "style", ft.STYLE_OBLIQUE)
        exception = RuntimeError
        self.assertRaises(exception, setattr, f_null, "strong", True)
        self.assertRaises(exception, setattr, f_null, "oblique", True)
        self.assertRaises(exception, setattr, f_null, "style", ft.STYLE_STRONG)
        self.assertRaises(exception, setattr, f_null, "style", ft.STYLE_OBLIQUE)
        exception = ValueError
        self.assertRaises(exception, f.render, "A", (0, 0, 0), size=8, rotation=1)
        self.assertRaises(
            exception, f.render, "A", (0, 0, 0), size=8, style=ft.STYLE_OBLIQUE
        )
        self.assertRaises(
            exception, f.render, "A", (0, 0, 0), size=8, style=ft.STYLE_STRONG
        )
        self.assertRaises(exception, f.render_raw, "A", size=8, rotation=1)
        self.assertRaises(exception, f.render_raw, "A", size=8, style=ft.STYLE_OBLIQUE)
        self.assertRaises(exception, f.render_raw, "A", size=8, style=ft.STYLE_STRONG)
        self.assertRaises(
            exception, f.render_to, s, (0, 0), "A", (0, 0, 0), size=8, rotation=1
        )
        self.assertRaises(
            exception,
            f.render_to,
            s,
            (0, 0),
            "A",
            (0, 0, 0),
            size=8,
            style=ft.STYLE_OBLIQUE,
        )
        self.assertRaises(
            exception,
            f.render_to,
            s,
            (0, 0),
            "A",
            (0, 0, 0),
            size=8,
            style=ft.STYLE_STRONG,
        )
        self.assertRaises(exception, f.render_raw_to, a, "A", size=8, rotation=1)
        self.assertRaises(
            exception, f.render_raw_to, a, "A", size=8, style=ft.STYLE_OBLIQUE
        )
        self.assertRaises(
            exception, f.render_raw_to, a, "A", size=8, style=ft.STYLE_STRONG
        )
        self.assertRaises(exception, f.get_rect, "A", size=8, rotation=1)
        self.assertRaises(exception, f.get_rect, "A", size=8, style=ft.STYLE_OBLIQUE)
        self.assertRaises(exception, f.get_rect, "A", size=8, style=ft.STYLE_STRONG)

        # Unsupported point size
        exception = pygame.error
        self.assertRaises(exception, f.get_rect, "A", size=42)
        self.assertRaises(exception, f.get_metrics, "A", size=42)
        self.assertRaises(exception, f.get_sized_ascender, 42)
        self.assertRaises(exception, f.get_sized_descender, 42)
        self.assertRaises(exception, f.get_sized_height, 42)
        self.assertRaises(exception, f.get_sized_glyph_height, 42)

    def test_freetype_Font_get_metrics(self):
        font = self._TEST_FONTS["sans"]

        metrics = font.get_metrics("ABCD", size=24)
        self.assertEqual(len(metrics), len("ABCD"))
        self.assertIsInstance(metrics, list)

        for metrics_tuple in metrics:
            self.assertIsInstance(metrics_tuple, tuple, metrics_tuple)
            self.assertEqual(len(metrics_tuple), 6)

            for m in metrics_tuple[:4]:
                self.assertIsInstance(m, int)

            for m in metrics_tuple[4:]:
                self.assertIsInstance(m, float)

        # test for empty string
        metrics = font.get_metrics("", size=24)
        self.assertEqual(metrics, [])

        # test for invalid string
        self.assertRaises(TypeError, font.get_metrics, 24, 24)

        # raises exception when uninitialized
        self.assertRaises(RuntimeError, nullfont().get_metrics, "a", size=24)

    def test_freetype_Font_get_rect(self):
        font = self._TEST_FONTS["sans"]

        def test_rect(r):
            self.assertIsInstance(r, pygame.Rect)

        rect_default = font.get_rect("ABCDabcd", size=24)
        test_rect(rect_default)
        self.assertTrue(rect_default.size > (0, 0))
        self.assertTrue(rect_default.width > rect_default.height)

        rect_bigger = font.get_rect("ABCDabcd", size=32)
        test_rect(rect_bigger)
        self.assertTrue(rect_bigger.size > rect_default.size)

        rect_strong = font.get_rect("ABCDabcd", size=24, style=ft.STYLE_STRONG)
        test_rect(rect_strong)
        self.assertTrue(rect_strong.size > rect_default.size)

        font.vertical = True
        rect_vert = font.get_rect("ABCDabcd", size=24)
        test_rect(rect_vert)
        self.assertTrue(rect_vert.width < rect_vert.height)
        font.vertical = False

        rect_oblique = font.get_rect("ABCDabcd", size=24, style=ft.STYLE_OBLIQUE)
        test_rect(rect_oblique)
        self.assertTrue(rect_oblique.width > rect_default.width)
        self.assertTrue(rect_oblique.height == rect_default.height)

        rect_under = font.get_rect("ABCDabcd", size=24, style=ft.STYLE_UNDERLINE)
        test_rect(rect_under)
        self.assertTrue(rect_under.width == rect_default.width)
        self.assertTrue(rect_under.height > rect_default.height)

        # Rect size should change if UTF surrogate pairs are treated as
        # one code point or two.
        ufont = self._TEST_FONTS["mono"]
        rect_utf32 = ufont.get_rect("\U00013079", size=24)
        rect_utf16 = ufont.get_rect("\uD80C\uDC79", size=24)
        self.assertEqual(rect_utf16, rect_utf32)
        ufont.ucs4 = True
        try:
            rect_utf16 = ufont.get_rect("\uD80C\uDC79", size=24)
        finally:
            ufont.ucs4 = False
        self.assertNotEqual(rect_utf16, rect_utf32)

        self.assertRaises(RuntimeError, nullfont().get_rect, "a", size=24)

        # text stretching
        rect12 = font.get_rect("A", size=12.0)
        rect24 = font.get_rect("A", size=24.0)
        rect_x = font.get_rect("A", size=(24.0, 12.0))
        self.assertEqual(rect_x.width, rect24.width)
        self.assertEqual(rect_x.height, rect12.height)
        rect_y = font.get_rect("A", size=(12.0, 24.0))
        self.assertEqual(rect_y.width, rect12.width)
        self.assertEqual(rect_y.height, rect24.height)

    def test_freetype_Font_height(self):
        f = self._TEST_FONTS["sans"]
        self.assertEqual(f.height, 2355)

        f = self._TEST_FONTS["fixed"]
        self.assertEqual(f.height, 1100)

        self.assertRaises(RuntimeError, lambda: nullfont().height)

    def test_freetype_Font_name(self):
        f = self._TEST_FONTS["sans"]
        self.assertEqual(f.name, "Liberation Sans")

        f = self._TEST_FONTS["fixed"]
        self.assertEqual(f.name, "Inconsolata")

        nf = nullfont()
        self.assertEqual(nf.name, repr(nf))

    def test_freetype_Font_size(self):
        f = ft.Font(None, size=12)
        self.assertEqual(f.size, 12)
        f.size = 22
        self.assertEqual(f.size, 22)
        f.size = 0
        self.assertEqual(f.size, 0)
        f.size = max_point_size
        self.assertEqual(f.size, max_point_size)
        f.size = 6.5
        self.assertEqual(f.size, 6.5)
        f.size = max_point_size_f
        self.assertEqual(f.size, max_point_size_f)
        self.assertRaises(OverflowError, setattr, f, "size", -1)
        self.assertRaises(OverflowError, setattr, f, "size", (max_point_size + 1))

        f.size = 24.0, 0
        size = f.size
        self.assertIsInstance(size, float)
        self.assertEqual(size, 24.0)

        f.size = 16, 16
        size = f.size
        self.assertIsInstance(size, tuple)
        self.assertEqual(len(size), 2)

        x, y = size
        self.assertIsInstance(x, float)
        self.assertEqual(x, 16.0)
        self.assertIsInstance(y, float)
        self.assertEqual(y, 16.0)

        f.size = 20.5, 22.25
        x, y = f.size
        self.assertEqual(x, 20.5)
        self.assertEqual(y, 22.25)

        f.size = 0, 0
        size = f.size
        self.assertIsInstance(size, float)
        self.assertEqual(size, 0.0)
        self.assertRaises(ValueError, setattr, f, "size", (0, 24.0))
        self.assertRaises(TypeError, setattr, f, "size", (24.0,))
        self.assertRaises(TypeError, setattr, f, "size", (24.0, 0, 0))
        self.assertRaises(TypeError, setattr, f, "size", (24.0j, 24.0))
        self.assertRaises(TypeError, setattr, f, "size", (24.0, 24.0j))
        self.assertRaises(OverflowError, setattr, f, "size", (-1, 16))
        self.assertRaises(OverflowError, setattr, f, "size", (max_point_size + 1, 16))
        self.assertRaises(OverflowError, setattr, f, "size", (16, -1))
        self.assertRaises(OverflowError, setattr, f, "size", (16, max_point_size + 1))

        # bitmap files with identical point size but differing ppems.
        f75 = self._TEST_FONTS["bmp-18-75dpi"]
        sizes = f75.get_sizes()
        self.assertEqual(len(sizes), 1)
        size_pt, width_px, height_px, x_ppem, y_ppem = sizes[0]
        self.assertEqual(size_pt, 18)
        self.assertEqual(x_ppem, 19.0)
        self.assertEqual(y_ppem, 19.0)
        rect = f75.get_rect("A", size=18)
        rect = f75.get_rect("A", size=19)
        rect = f75.get_rect("A", size=(19.0, 19.0))
        self.assertRaises(pygame.error, f75.get_rect, "A", size=17)
        f100 = self._TEST_FONTS["bmp-18-100dpi"]
        sizes = f100.get_sizes()
        self.assertEqual(len(sizes), 1)
        size_pt, width_px, height_px, x_ppem, y_ppem = sizes[0]
        self.assertEqual(size_pt, 18)
        self.assertEqual(x_ppem, 25.0)
        self.assertEqual(y_ppem, 25.0)
        rect = f100.get_rect("A", size=18)
        rect = f100.get_rect("A", size=25)
        rect = f100.get_rect("A", size=(25.0, 25.0))
        self.assertRaises(pygame.error, f100.get_rect, "A", size=17)

    def test_freetype_Font_rotation(self):
        test_angles = [
            (30, 30),
            (360, 0),
            (390, 30),
            (720, 0),
            (764, 44),
            (-30, 330),
            (-360, 0),
            (-390, 330),
            (-720, 0),
            (-764, 316),
        ]

        f = ft.Font(None)
        self.assertEqual(f.rotation, 0)
        for r, r_reduced in test_angles:
            f.rotation = r
            self.assertEqual(
                f.rotation,
                r_reduced,
                "for angle %d: %d != %d" % (r, f.rotation, r_reduced),
            )
        self.assertRaises(TypeError, setattr, f, "rotation", "12")

    def test_freetype_Font_render_to(self):
        # Rendering to an existing target surface is equivalent to
        # blitting a surface returned by Font.render with the target.
        font = self._TEST_FONTS["sans"]

        surf = pygame.Surface((800, 600))
        color = pygame.Color(0, 0, 0)

        rrect = font.render_to(surf, (32, 32), "FoobarBaz", color, None, size=24)
        self.assertIsInstance(rrect, pygame.Rect)
        self.assertEqual(rrect.topleft, (32, 32))
        self.assertNotEqual(rrect.bottomright, (32, 32))

        rcopy = rrect.copy()
        rcopy.topleft = (32, 32)
        self.assertTrue(surf.get_rect().contains(rcopy))

        rect = pygame.Rect(20, 20, 2, 2)
        rrect = font.render_to(surf, rect, "FoobarBax", color, None, size=24)
        self.assertEqual(rect.topleft, rrect.topleft)
        self.assertNotEqual(rrect.size, rect.size)
        rrect = font.render_to(surf, (20.1, 18.9), "FoobarBax", color, None, size=24)

        rrect = font.render_to(surf, rect, "", color, None, size=24)
        self.assertFalse(rrect)
        self.assertEqual(rrect.height, font.get_sized_height(24))

        # invalid surf test
        self.assertRaises(TypeError, font.render_to, "not a surface", "text", color)
        self.assertRaises(TypeError, font.render_to, pygame.Surface, "text", color)

        # invalid dest test
        for dest in [
            None,
            0,
            "a",
            "ab",
            (),
            (1,),
            ("a", 2),
            (1, "a"),
            (1 + 2j, 2),
            (1, 1 + 2j),
            (1, int),
            (int, 1),
        ]:
            self.assertRaises(
                TypeError, font.render_to, surf, dest, "foobar", color, size=24
            )

        # misc parameter test
        self.assertRaises(ValueError, font.render_to, surf, (0, 0), "foobar", color)
        self.assertRaises(
            TypeError, font.render_to, surf, (0, 0), "foobar", color, 2.3, size=24
        )
        self.assertRaises(
            ValueError,
            font.render_to,
            surf,
            (0, 0),
            "foobar",
            color,
            None,
            style=42,
            size=24,
        )
        self.assertRaises(
            TypeError,
            font.render_to,
            surf,
            (0, 0),
            "foobar",
            color,
            None,
            style=None,
            size=24,
        )
        self.assertRaises(
            ValueError,
            font.render_to,
            surf,
            (0, 0),
            "foobar",
            color,
            None,
            style=97,
            size=24,
        )

    def test_freetype_Font_render(self):
        font = self._TEST_FONTS["sans"]

        surf = pygame.Surface((800, 600))
        color = pygame.Color(0, 0, 0)

        rend = font.render("FoobarBaz", pygame.Color(0, 0, 0), None, size=24)
        self.assertIsInstance(rend, tuple)
        self.assertEqual(len(rend), 2)
        self.assertIsInstance(rend[0], pygame.Surface)
        self.assertIsInstance(rend[1], pygame.Rect)
        self.assertEqual(rend[0].get_rect().size, rend[1].size)

        s, r = font.render("", pygame.Color(0, 0, 0), None, size=24)
        self.assertEqual(r.width, 0)
        self.assertEqual(r.height, font.get_sized_height(24))
        self.assertEqual(s.get_size(), r.size)
        self.assertEqual(s.get_bitsize(), 32)

        # misc parameter test
        self.assertRaises(ValueError, font.render, "foobar", color)
        self.assertRaises(TypeError, font.render, "foobar", color, 2.3, size=24)
        self.assertRaises(
            ValueError, font.render, "foobar", color, None, style=42, size=24
        )
        self.assertRaises(
            TypeError, font.render, "foobar", color, None, style=None, size=24
        )
        self.assertRaises(
            ValueError, font.render, "foobar", color, None, style=97, size=24
        )

        # valid surrogate pairs
        font2 = self._TEST_FONTS["mono"]
        ucs4 = font2.ucs4
        try:
            font2.ucs4 = False
            rend1 = font2.render("\uD80C\uDC79", color, size=24)
            rend2 = font2.render("\U00013079", color, size=24)
            self.assertEqual(rend1[1], rend2[1])
            font2.ucs4 = True
            rend1 = font2.render("\uD80C\uDC79", color, size=24)
            self.assertNotEqual(rend1[1], rend2[1])
        finally:
            font2.ucs4 = ucs4

        # malformed surrogate pairs
        self.assertRaises(UnicodeEncodeError, font.render, "\uD80C", color, size=24)
        self.assertRaises(UnicodeEncodeError, font.render, "\uDCA7", color, size=24)
        self.assertRaises(
            UnicodeEncodeError, font.render, "\uD7FF\uDCA7", color, size=24
        )
        self.assertRaises(
            UnicodeEncodeError, font.render, "\uDC00\uDCA7", color, size=24
        )
        self.assertRaises(
            UnicodeEncodeError, font.render, "\uD80C\uDBFF", color, size=24
        )
        self.assertRaises(
            UnicodeEncodeError, font.render, "\uD80C\uE000", color, size=24
        )

        # raises exception when uninitialized
        self.assertRaises(RuntimeError, nullfont().render, "a", (0, 0, 0), size=24)

        # Confirm the correct glyphs are returned for a couple of
        # unicode code points, 'A' and '\U00023079'. For each code point
        # the rendered glyph is compared with an image of glyph bitmap
        # as exported by FontForge.
        path = os.path.join(FONTDIR, "A_PyGameMono-8.png")
        A = pygame.image.load(path)
        path = os.path.join(FONTDIR, "u13079_PyGameMono-8.png")
        u13079 = pygame.image.load(path)

        font = self._TEST_FONTS["mono"]
        font.ucs4 = False
        A_rendered, r = font.render("A", bgcolor=pygame.Color("white"), size=8)
        u13079_rendered, r = font.render(
            "\U00013079", bgcolor=pygame.Color("white"), size=8
        )

        # before comparing the surfaces, make sure they are the same
        # pixel format. Use 32-bit SRCALPHA to avoid row padding and
        # undefined bytes (the alpha byte will be set to 255.)
        bitmap = pygame.Surface(A.get_size(), pygame.SRCALPHA, 32)
        bitmap.blit(A, (0, 0))
        rendering = pygame.Surface(A_rendered.get_size(), pygame.SRCALPHA, 32)
        rendering.blit(A_rendered, (0, 0))
        self.assertTrue(surf_same_image(rendering, bitmap))
        bitmap = pygame.Surface(u13079.get_size(), pygame.SRCALPHA, 32)
        bitmap.blit(u13079, (0, 0))
        rendering = pygame.Surface(u13079_rendered.get_size(), pygame.SRCALPHA, 32)
        rendering.blit(u13079_rendered, (0, 0))
        self.assertTrue(surf_same_image(rendering, bitmap))

    def test_freetype_Font_render_mono(self):
        font = self._TEST_FONTS["sans"]
        color = pygame.Color("black")
        colorkey = pygame.Color("white")
        text = "."

        save_antialiased = font.antialiased
        font.antialiased = False
        try:
            surf, r = font.render(text, color, size=24)
            self.assertEqual(surf.get_bitsize(), 8)
            flags = surf.get_flags()
            self.assertTrue(flags & pygame.SRCCOLORKEY)
            self.assertFalse(flags & (pygame.SRCALPHA | pygame.HWSURFACE))
            self.assertEqual(surf.get_colorkey(), colorkey)
            self.assertIsNone(surf.get_alpha())

            translucent_color = pygame.Color(*color)
            translucent_color.a = 55
            surf, r = font.render(text, translucent_color, size=24)
            self.assertEqual(surf.get_bitsize(), 8)
            flags = surf.get_flags()
            self.assertTrue(flags & (pygame.SRCCOLORKEY | pygame.SRCALPHA))
            self.assertFalse(flags & pygame.HWSURFACE)
            self.assertEqual(surf.get_colorkey(), colorkey)
            self.assertEqual(surf.get_alpha(), translucent_color.a)

            surf, r = font.render(text, color, colorkey, size=24)
            self.assertEqual(surf.get_bitsize(), 32)
        finally:
            font.antialiased = save_antialiased

    def test_freetype_Font_render_to_mono(self):
        # Blitting is done in two stages. First the target is alpha filled
        # with the background color, if any. Second, the foreground
        # color is alpha blitted to the background.
        font = self._TEST_FONTS["sans"]
        text = " ."
        rect = font.get_rect(text, size=24)
        size = rect.size
        fg = pygame.Surface((1, 1), pygame.SRCALPHA, 32)
        bg = pygame.Surface((1, 1), pygame.SRCALPHA, 32)
        surrogate = pygame.Surface((1, 1), pygame.SRCALPHA, 32)
        surfaces = [
            pygame.Surface(size, 0, 8),
            pygame.Surface(size, 0, 16),
            pygame.Surface(size, pygame.SRCALPHA, 16),
            pygame.Surface(size, 0, 24),
            pygame.Surface(size, 0, 32),
            pygame.Surface(size, pygame.SRCALPHA, 32),
        ]
        fg_colors = [
            surfaces[0].get_palette_at(2),
            surfaces[1].unmap_rgb(surfaces[1].map_rgb((128, 64, 200))),
            surfaces[2].unmap_rgb(surfaces[2].map_rgb((99, 0, 100, 64))),
            (128, 97, 213),
            (128, 97, 213),
            (128, 97, 213, 60),
        ]
        fg_colors = [pygame.Color(*c) for c in fg_colors]
        self.assertEqual(len(surfaces), len(fg_colors))  # integrity check
        bg_colors = [
            surfaces[0].get_palette_at(4),
            surfaces[1].unmap_rgb(surfaces[1].map_rgb((220, 20, 99))),
            surfaces[2].unmap_rgb(surfaces[2].map_rgb((55, 200, 0, 86))),
            (255, 120, 13),
            (255, 120, 13),
            (255, 120, 13, 180),
        ]
        bg_colors = [pygame.Color(*c) for c in bg_colors]
        self.assertEqual(len(surfaces), len(bg_colors))  # integrity check

        save_antialiased = font.antialiased
        font.antialiased = False
        try:
            fill_color = pygame.Color("black")
            for i, surf in enumerate(surfaces):
                surf.fill(fill_color)
                fg_color = fg_colors[i]
                fg.set_at((0, 0), fg_color)
                surf.blit(fg, (0, 0))
                r_fg_color = surf.get_at((0, 0))
                surf.set_at((0, 0), fill_color)
                rrect = font.render_to(surf, (0, 0), text, fg_color, size=24)
                bottomleft = 0, rrect.height - 1
                self.assertEqual(
                    surf.get_at(bottomleft),
                    fill_color,
                    "Position: {}. Depth: {}."
                    " fg_color: {}.".format(bottomleft, surf.get_bitsize(), fg_color),
                )
                bottomright = rrect.width - 1, rrect.height - 1
                self.assertEqual(
                    surf.get_at(bottomright),
                    r_fg_color,
                    "Position: {}. Depth: {}."
                    " fg_color: {}.".format(bottomright, surf.get_bitsize(), fg_color),
                )
            for i, surf in enumerate(surfaces):
                surf.fill(fill_color)
                fg_color = fg_colors[i]
                bg_color = bg_colors[i]
                bg.set_at((0, 0), bg_color)
                fg.set_at((0, 0), fg_color)
                if surf.get_bitsize() == 24:
                    # For a 24 bit target surface test against Pygame's alpha
                    # blit as there appears to be a problem with SDL's alpha
                    # blit:
                    #
                    # self.assertEqual(surf.get_at(bottomright), r_fg_color)
                    #
                    # raises
                    #
                    # AssertionError: (128, 97, 213, 255) != (129, 98, 213, 255)
                    #
                    surrogate.set_at((0, 0), fill_color)
                    surrogate.blit(bg, (0, 0))
                    r_bg_color = surrogate.get_at((0, 0))
                    surrogate.blit(fg, (0, 0))
                    r_fg_color = surrogate.get_at((0, 0))
                else:
                    # Surface blit values for comparison.
                    surf.blit(bg, (0, 0))
                    r_bg_color = surf.get_at((0, 0))
                    surf.blit(fg, (0, 0))
                    r_fg_color = surf.get_at((0, 0))
                    surf.set_at((0, 0), fill_color)
                rrect = font.render_to(surf, (0, 0), text, fg_color, bg_color, size=24)
                bottomleft = 0, rrect.height - 1
                self.assertEqual(surf.get_at(bottomleft), r_bg_color)
                bottomright = rrect.width - 1, rrect.height - 1
                self.assertEqual(surf.get_at(bottomright), r_fg_color)
        finally:
            font.antialiased = save_antialiased

    def test_freetype_Font_render_raw(self):
        font = self._TEST_FONTS["sans"]

        text = "abc"
        size = font.get_rect(text, size=24).size
        rend = font.render_raw(text, size=24)
        self.assertIsInstance(rend, tuple)
        self.assertEqual(len(rend), 2)

        r, s = rend
        self.assertIsInstance(r, bytes)
        self.assertIsInstance(s, tuple)
        self.assertTrue(len(s), 2)

        w, h = s
        self.assertIsInstance(w, int)
        self.assertIsInstance(h, int)
        self.assertEqual(s, size)
        self.assertEqual(len(r), w * h)

        r, (w, h) = font.render_raw("", size=24)
        self.assertEqual(w, 0)
        self.assertEqual(h, font.height)
        self.assertEqual(len(r), 0)

        # bug with decenders: this would crash
        rend = font.render_raw("render_raw", size=24)

        # bug with non-printable characters: this would cause a crash
        # because the text length was not adjusted for skipped characters.
        text = "".join([chr(i) for i in range(31, 64)])
        rend = font.render_raw(text, size=10)

    def test_freetype_Font_render_raw_to(self):
        # This only checks that blits do not crash. It needs to check:
        # - int values
        # - invert option
        #

        font = self._TEST_FONTS["sans"]
        text = "abc"

        # No frills antialiased render to int1 (__render_glyph_INT)
        srect = font.get_rect(text, size=24)
        surf = pygame.Surface(srect.size, 0, 8)
        rrect = font.render_raw_to(surf.get_view("2"), text, size=24)
        self.assertEqual(rrect, srect)

        for bpp in [24, 32]:
            surf = pygame.Surface(srect.size, 0, bpp)
            rrect = font.render_raw_to(surf.get_view("r"), text, size=24)
            self.assertEqual(rrect, srect)

        # Underlining to int1 (__fill_glyph_INT)
        srect = font.get_rect(text, size=24, style=ft.STYLE_UNDERLINE)
        surf = pygame.Surface(srect.size, 0, 8)
        rrect = font.render_raw_to(
            surf.get_view("2"), text, size=24, style=ft.STYLE_UNDERLINE
        )
        self.assertEqual(rrect, srect)

        for bpp in [24, 32]:
            surf = pygame.Surface(srect.size, 0, bpp)
            rrect = font.render_raw_to(
                surf.get_view("r"), text, size=24, style=ft.STYLE_UNDERLINE
            )
            self.assertEqual(rrect, srect)

        # Unaliased (mono) rendering to int1 (__render_glyph_MONO_as_INT)
        font.antialiased = False
        try:
            srect = font.get_rect(text, size=24)
            surf = pygame.Surface(srect.size, 0, 8)
            rrect = font.render_raw_to(surf.get_view("2"), text, size=24)
            self.assertEqual(rrect, srect)

            for bpp in [24, 32]:
                surf = pygame.Surface(srect.size, 0, bpp)
                rrect = font.render_raw_to(surf.get_view("r"), text, size=24)
                self.assertEqual(rrect, srect)
        finally:
            font.antialiased = True

        # Antialiased render to ints sized greater than 1 byte
        # (__render_glyph_INT)
        srect = font.get_rect(text, size=24)

        for bpp in [16, 24, 32]:
            surf = pygame.Surface(srect.size, 0, bpp)
            rrect = font.render_raw_to(surf.get_view("2"), text, size=24)
            self.assertEqual(rrect, srect)

        # Underline render to ints sized greater than 1 byte
        # (__fill_glyph_INT)
        srect = font.get_rect(text, size=24, style=ft.STYLE_UNDERLINE)

        for bpp in [16, 24, 32]:
            surf = pygame.Surface(srect.size, 0, bpp)
            rrect = font.render_raw_to(
                surf.get_view("2"), text, size=24, style=ft.STYLE_UNDERLINE
            )
            self.assertEqual(rrect, srect)

        # Unaliased (mono) rendering to ints greater than 1 byte
        # (__render_glyph_MONO_as_INT)
        font.antialiased = False
        try:
            srect = font.get_rect(text, size=24)

            for bpp in [16, 24, 32]:
                surf = pygame.Surface(srect.size, 0, bpp)
                rrect = font.render_raw_to(surf.get_view("2"), text, size=24)
                self.assertEqual(rrect, srect)
        finally:
            font.antialiased = True

        # Invalid dest parameter test.
        srect = font.get_rect(text, size=24)
        surf_buf = pygame.Surface(srect.size, 0, 32).get_view("2")

        for dest in [
            0,
            "a",
            "ab",
            (),
            (1,),
            ("a", 2),
            (1, "a"),
            (1 + 2j, 2),
            (1, 1 + 2j),
            (1, int),
            (int, 1),
        ]:
            self.assertRaises(
                TypeError, font.render_raw_to, surf_buf, text, dest, size=24
            )

    def test_freetype_Font_text_is_None_with_arr(self):
        f = ft.Font(self._sans_path, 36)
        f.style = ft.STYLE_NORMAL
        f.rotation = 0
        text = "ABCD"

        # reference values
        get_rect = f.get_rect(text)
        f.vertical = True
        get_rect_vert = f.get_rect(text)

        self.assertTrue(get_rect_vert.width < get_rect.width)
        self.assertTrue(get_rect_vert.height > get_rect.height)
        f.vertical = False
        render_to_surf = pygame.Surface(get_rect.size, pygame.SRCALPHA, 32)

        if IS_PYPY:
            return

        arr = arrinter.Array(get_rect.size, "u", 1)
        render = f.render(text, (0, 0, 0))
        render_to = f.render_to(render_to_surf, (0, 0), text, (0, 0, 0))
        render_raw = f.render_raw(text)
        render_raw_to = f.render_raw_to(arr, text)

        # comparisons
        surf = pygame.Surface(get_rect.size, pygame.SRCALPHA, 32)
        self.assertEqual(f.get_rect(None), get_rect)
        s, r = f.render(None, (0, 0, 0))
        self.assertEqual(r, render[1])
        self.assertTrue(surf_same_image(s, render[0]))
        r = f.render_to(surf, (0, 0), None, (0, 0, 0))
        self.assertEqual(r, render_to)
        self.assertTrue(surf_same_image(surf, render_to_surf))
        px, sz = f.render_raw(None)
        self.assertEqual(sz, render_raw[1])
        self.assertEqual(px, render_raw[0])
        sz = f.render_raw_to(arr, None)
        self.assertEqual(sz, render_raw_to)

    def test_freetype_Font_text_is_None(self):
        f = ft.Font(self._sans_path, 36)
        f.style = ft.STYLE_NORMAL
        f.rotation = 0
        text = "ABCD"

        # reference values
        get_rect = f.get_rect(text)
        f.vertical = True
        get_rect_vert = f.get_rect(text)

        # vertical: trigger glyph positioning.
        f.vertical = True
        r = f.get_rect(None)
        self.assertEqual(r, get_rect_vert)
        f.vertical = False

        # wide style: trigger glyph reload
        r = f.get_rect(None, style=ft.STYLE_WIDE)
        self.assertEqual(r.height, get_rect.height)
        self.assertTrue(r.width > get_rect.width)
        r = f.get_rect(None)
        self.assertEqual(r, get_rect)

        # rotated: trigger glyph reload
        r = f.get_rect(None, rotation=90)
        self.assertEqual(r.width, get_rect.height)
        self.assertEqual(r.height, get_rect.width)

        # this method will not support None text
        self.assertRaises(TypeError, f.get_metrics, None)

    def test_freetype_Font_fgcolor(self):
        f = ft.Font(self._bmp_8_75dpi_path)
        notdef = "\0"  # the PyGameMono .notdef glyph has a pixel at (0, 0)
        f.origin = False
        f.pad = False
        black = pygame.Color("black")  # initial color
        green = pygame.Color("green")
        alpha128 = pygame.Color(10, 20, 30, 128)

        c = f.fgcolor
        self.assertIsInstance(c, pygame.Color)
        self.assertEqual(c, black)

        s, r = f.render(notdef)
        self.assertEqual(s.get_at((0, 0)), black)

        f.fgcolor = green
        self.assertEqual(f.fgcolor, green)

        s, r = f.render(notdef)
        self.assertEqual(s.get_at((0, 0)), green)

        f.fgcolor = alpha128
        s, r = f.render(notdef)
        self.assertEqual(s.get_at((0, 0)), alpha128)

        surf = pygame.Surface(f.get_rect(notdef).size, pygame.SRCALPHA, 32)
        f.render_to(surf, (0, 0), None)
        self.assertEqual(surf.get_at((0, 0)), alpha128)

        self.assertRaises(AttributeError, setattr, f, "fgcolor", None)

    def test_freetype_Font_bgcolor(self):
        f = ft.Font(None, 32)
        zero = "0"  # the default font 0 glyph does not have a pixel at (0, 0)
        f.origin = False
        f.pad = False

        transparent_black = pygame.Color(0, 0, 0, 0)  # initial color
        green = pygame.Color("green")
        alpha128 = pygame.Color(10, 20, 30, 128)

        c = f.bgcolor
        self.assertIsInstance(c, pygame.Color)
        self.assertEqual(c, transparent_black)

        s, r = f.render(zero, pygame.Color(255, 255, 255))
        self.assertEqual(s.get_at((0, 0)), transparent_black)

        f.bgcolor = green
        self.assertEqual(f.bgcolor, green)

        s, r = f.render(zero)
        self.assertEqual(s.get_at((0, 0)), green)

        f.bgcolor = alpha128
        s, r = f.render(zero)
        self.assertEqual(s.get_at((0, 0)), alpha128)

        surf = pygame.Surface(f.get_rect(zero).size, pygame.SRCALPHA, 32)
        f.render_to(surf, (0, 0), None)
        self.assertEqual(surf.get_at((0, 0)), alpha128)

        self.assertRaises(AttributeError, setattr, f, "bgcolor", None)

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    @unittest.skipIf(IS_PYPY, "pypy no likey")
    def test_newbuf(self):
        from pygame.tests.test_utils import buftools

        Exporter = buftools.Exporter
        font = self._TEST_FONTS["sans"]
        srect = font.get_rect("Hi", size=12)
        for format in [
            "b",
            "B",
            "h",
            "H",
            "i",
            "I",
            "l",
            "L",
            "q",
            "Q",
            "x",
            "1x",
            "2x",
            "3x",
            "4x",
            "5x",
            "6x",
            "7x",
            "8x",
            "9x",
            "<h",
            ">h",
            "=h",
            "@h",
            "!h",
            "1h",
            "=1h",
        ]:
            newbuf = Exporter(srect.size, format=format)
            rrect = font.render_raw_to(newbuf, "Hi", size=12)
            self.assertEqual(rrect, srect)
        # Some unsupported formats
        for format in ["f", "d", "2h", "?", "hh"]:
            newbuf = Exporter(srect.size, format=format, itemsize=4)
            self.assertRaises(ValueError, font.render_raw_to, newbuf, "Hi", size=12)

    def test_freetype_Font_style(self):
        font = self._TEST_FONTS["sans"]

        # make sure STYLE_NORMAL is the default value
        self.assertEqual(ft.STYLE_NORMAL, font.style)

        # make sure we check for style type
        with self.assertRaises(TypeError):
            font.style = "None"
        with self.assertRaises(TypeError):
            font.style = None

        # make sure we only accept valid constants
        with self.assertRaises(ValueError):
            font.style = 112

        # make assure no assignments happened
        self.assertEqual(ft.STYLE_NORMAL, font.style)

        # test assignment
        font.style = ft.STYLE_UNDERLINE
        self.assertEqual(ft.STYLE_UNDERLINE, font.style)

        # test complex styles
        st = ft.STYLE_STRONG | ft.STYLE_UNDERLINE | ft.STYLE_OBLIQUE

        font.style = st
        self.assertEqual(st, font.style)

        # and that STYLE_DEFAULT has no effect (continued from above)
        self.assertNotEqual(st, ft.STYLE_DEFAULT)
        font.style = ft.STYLE_DEFAULT
        self.assertEqual(st, font.style)

        # revert changes
        font.style = ft.STYLE_NORMAL
        self.assertEqual(ft.STYLE_NORMAL, font.style)

    def test_freetype_Font_resolution(self):
        text = "|"  # Differs in width and height
        resolution = ft.get_default_resolution()
        new_font = ft.Font(self._sans_path, resolution=2 * resolution)
        self.assertEqual(new_font.resolution, 2 * resolution)
        size_normal = self._TEST_FONTS["sans"].get_rect(text, size=24).size
        size_scaled = new_font.get_rect(text, size=24).size
        size_by_2 = size_normal[0] * 2
        self.assertTrue(
            size_by_2 + 2 >= size_scaled[0] >= size_by_2 - 2,
            "%i not equal %i" % (size_scaled[1], size_by_2),
        )
        size_by_2 = size_normal[1] * 2
        self.assertTrue(
            size_by_2 + 2 >= size_scaled[1] >= size_by_2 - 2,
            "%i not equal %i" % (size_scaled[1], size_by_2),
        )
        new_resolution = resolution + 10
        ft.set_default_resolution(new_resolution)
        try:
            new_font = ft.Font(self._sans_path, resolution=0)
            self.assertEqual(new_font.resolution, new_resolution)
        finally:
            ft.set_default_resolution()

    def test_freetype_Font_path(self):
        self.assertEqual(self._TEST_FONTS["sans"].path, self._sans_path)
        self.assertRaises(AttributeError, getattr, nullfont(), "path")

    # This Font cache test is conditional on freetype being built by a debug
    # version of Python or with the C macro PGFT_DEBUG_CACHE defined.
    def test_freetype_Font_cache(self):
        glyphs = "abcde"
        glen = len(glyphs)
        other_glyphs = "123"
        oglen = len(other_glyphs)
        uempty = ""
        ##        many_glyphs = (uempty.join([chr(i) for i in range(32,127)] +
        ##                                   [chr(i) for i in range(161,172)] +
        ##                                   [chr(i) for i in range(174,239)]))
        many_glyphs = uempty.join([chr(i) for i in range(32, 127)])
        mglen = len(many_glyphs)

        count = 0
        access = 0
        hit = 0
        miss = 0

        f = ft.Font(None, size=24, font_index=0, resolution=72, ucs4=False)
        f.style = ft.STYLE_NORMAL
        f.antialiased = True

        # Ensure debug counters are zero
        self.assertEqual(f._debug_cache_stats, (0, 0, 0, 0, 0))
        # Load some basic glyphs
        count = access = miss = glen
        f.render_raw(glyphs)
        self.assertEqual(f._debug_cache_stats, (count, 0, access, hit, miss))
        # Vertical should not affect the cache
        access += glen
        hit += glen
        f.vertical = True
        f.render_raw(glyphs)
        f.vertical = False
        self.assertEqual(f._debug_cache_stats, (count, 0, access, hit, miss))
        # New glyphs will
        count += oglen
        access += oglen
        miss += oglen
        f.render_raw(other_glyphs)
        self.assertEqual(f._debug_cache_stats, (count, 0, access, hit, miss))
        # Point size does
        count += glen
        access += glen
        miss += glen
        f.render_raw(glyphs, size=12)
        self.assertEqual(f._debug_cache_stats, (count, 0, access, hit, miss))
        # Underline style does not
        access += oglen
        hit += oglen
        f.underline = True
        f.render_raw(other_glyphs)
        f.underline = False
        self.assertEqual(f._debug_cache_stats, (count, 0, access, hit, miss))
        # Oblique style does
        count += glen
        access += glen
        miss += glen
        f.oblique = True
        f.render_raw(glyphs)
        f.oblique = False
        self.assertEqual(f._debug_cache_stats, (count, 0, access, hit, miss))
        # Strong style does; by this point cache clears can happen
        count += glen
        access += glen
        miss += glen
        f.strong = True
        f.render_raw(glyphs)
        f.strong = False
        ccount, cdelete_count, caccess, chit, cmiss = f._debug_cache_stats
        self.assertEqual(
            (ccount + cdelete_count, caccess, chit, cmiss), (count, access, hit, miss)
        )
        # Rotation does
        count += glen
        access += glen
        miss += glen
        f.render_raw(glyphs, rotation=10)
        ccount, cdelete_count, caccess, chit, cmiss = f._debug_cache_stats
        self.assertEqual(
            (ccount + cdelete_count, caccess, chit, cmiss), (count, access, hit, miss)
        )
        # aliased (mono) glyphs do
        count += oglen
        access += oglen
        miss += oglen
        f.antialiased = False
        f.render_raw(other_glyphs)
        f.antialiased = True
        ccount, cdelete_count, caccess, chit, cmiss = f._debug_cache_stats
        self.assertEqual(
            (ccount + cdelete_count, caccess, chit, cmiss), (count, access, hit, miss)
        )
        # Trigger a cleanup for sure.
        count += 2 * mglen
        access += 2 * mglen
        miss += 2 * mglen
        f.get_metrics(many_glyphs, size=8)
        f.get_metrics(many_glyphs, size=10)
        ccount, cdelete_count, caccess, chit, cmiss = f._debug_cache_stats
        self.assertTrue(ccount < count)
        self.assertEqual(
            (ccount + cdelete_count, caccess, chit, cmiss), (count, access, hit, miss)
        )

    try:
        ft.Font._debug_cache_stats
    except AttributeError:
        del test_freetype_Font_cache

    def test_undefined_character_code(self):
        # To be consistent with pygame.font.Font, undefined codes
        # are rendered as the undefined character, and has metrics
        # of None.
        font = self._TEST_FONTS["sans"]

        img, size1 = font.render(chr(1), (0, 0, 0), size=24)
        img, size0 = font.render("", (0, 0, 0), size=24)
        self.assertTrue(size1.width > size0.width)

        metrics = font.get_metrics(chr(1) + chr(48), size=24)
        self.assertEqual(len(metrics), 2)
        self.assertIsNone(metrics[0])
        self.assertIsInstance(metrics[1], tuple)

    def test_issue_242(self):
        """Issue #242: get_rect() uses 0 as default style"""

        # Issue #242: freetype.Font.get_rect() ignores style defaults when
        #             the style argument is not given
        #
        # The text boundary rectangle returned by freetype.Font.get_rect()
        # should match the boundary of the same text rendered directly to a
        # surface. This permits accurate text positioning. To work properly,
        # get_rect() should calculate the text boundary to reflect text style,
        # such as underline. Instead, it ignores the style settings for the
        # Font object when the style argument is omitted.
        #
        # When the style argument is not given, freetype.get_rect() uses
        # unstyled text when calculating the boundary rectangle. This is
        # because _ftfont_getrect(), in _freetype.c, set the default
        # style to 0 rather than FT_STYLE_DEFAULT.
        #
        font = self._TEST_FONTS["sans"]

        # Try wide style on a wide character.
        prev_style = font.wide
        font.wide = True
        try:
            rect = font.get_rect("M", size=64)
            surf, rrect = font.render(None, size=64)
            self.assertEqual(rect, rrect)
        finally:
            font.wide = prev_style

        # Try strong style on several wide characters.
        prev_style = font.strong
        font.strong = True
        try:
            rect = font.get_rect("Mm_", size=64)
            surf, rrect = font.render(None, size=64)
            self.assertEqual(rect, rrect)
        finally:
            font.strong = prev_style

        # Try oblique style on a tall, narrow character.
        prev_style = font.oblique
        font.oblique = True
        try:
            rect = font.get_rect("|", size=64)
            surf, rrect = font.render(None, size=64)
            self.assertEqual(rect, rrect)
        finally:
            font.oblique = prev_style

        # Try underline style on a glyphless character.
        prev_style = font.underline
        font.underline = True
        try:
            rect = font.get_rect(" ", size=64)
            surf, rrect = font.render(None, size=64)
            self.assertEqual(rect, rrect)
        finally:
            font.underline = prev_style

    def test_issue_237(self):
        """Issue #237: Memory overrun when rendered with underlining"""

        # Issue #237: Memory overrun when text without descenders is rendered
        #             with underlining
        #
        # The bug crashes the Python interpreter. The bug is caught with C
        # assertions in ft_render_cb.c when the Pygame module is compiled
        # for debugging. So far it is only known to affect Times New Roman.
        #
        name = "Times New Roman"
        font = ft.SysFont(name, 19)
        if font.name != name:
            # The font is unavailable, so skip the test.
            return
        font.underline = True
        s, r = font.render("Amazon", size=19)

        # Some other checks to make sure nothing else broke.
        for adj in [-2, -1.9, -1, 0, 1.9, 2]:
            font.underline_adjustment = adj
            s, r = font.render("Amazon", size=19)

    def test_issue_243(self):
        """Issue Y: trailing space ignored in boundary calculation"""

        # Issue #243: For a string with trailing spaces, freetype ignores the
        # last space in boundary calculations
        #
        font = self._TEST_FONTS["fixed"]
        r1 = font.get_rect(" ", size=64)
        self.assertTrue(r1.width > 1)
        r2 = font.get_rect("  ", size=64)
        self.assertEqual(r2.width, 2 * r1.width)

    def test_garbage_collection(self):
        """Check reference counting on returned new references"""

        def ref_items(seq):
            return [weakref.ref(o) for o in seq]

        font = self._TEST_FONTS["bmp-8-75dpi"]
        font.size = font.get_sizes()[0][0]
        text = "A"
        rect = font.get_rect(text)
        surf = pygame.Surface(rect.size, pygame.SRCALPHA, 32)
        refs = []
        refs.extend(ref_items(font.render(text, (0, 0, 0))))
        refs.append(weakref.ref(font.render_to(surf, (0, 0), text, (0, 0, 0))))
        refs.append(weakref.ref(font.get_rect(text)))

        n = len(refs)
        self.assertTrue(n > 0)

        # for pypy we garbage collection twice.
        for i in range(2):
            gc.collect()

        for i in range(n):
            self.assertIsNone(refs[i](), "ref %d not collected" % i)

        try:
            from sys import getrefcount
        except ImportError:
            pass
        else:
            array = arrinter.Array(rect.size, "u", 1)
            o = font.render_raw(text)
            self.assertEqual(getrefcount(o), 2)
            self.assertEqual(getrefcount(o[0]), 2)
            self.assertEqual(getrefcount(o[1]), 2)
            self.assertEqual(getrefcount(font.render_raw_to(array, text)), 1)
            o = font.get_metrics("AB")
            self.assertEqual(getrefcount(o), 2)
            for i in range(len(o)):
                self.assertEqual(getrefcount(o[i]), 2, "refcount fail for item %d" % i)
            o = font.get_sizes()
            self.assertEqual(getrefcount(o), 2)
            for i in range(len(o)):
                self.assertEqual(getrefcount(o[i]), 2, "refcount fail for item %d" % i)

    def test_display_surface_quit(self):
        """Font.render_to() on a closed display surface"""

        # The Font.render_to() method checks that PySurfaceObject.surf is NULL
        # and raise a exception if it is. This fixes a bug in Pygame revision
        # 0600ea4f1cfb and earlier where Pygame segfaults instead.
        null_surface = pygame.Surface.__new__(pygame.Surface)
        f = self._TEST_FONTS["sans"]
        self.assertRaises(
            pygame.error, f.render_to, null_surface, (0, 0), "Crash!", size=12
        )

    def test_issue_565(self):
        """get_metrics supporting rotation/styles/size"""

        tests = [
            {"method": "size", "value": 36, "msg": "metrics same for size"},
            {"method": "rotation", "value": 90, "msg": "metrics same for rotation"},
            {"method": "oblique", "value": True, "msg": "metrics same for oblique"},
        ]
        text = "|"

        def run_test(method, value, msg):
            font = ft.Font(self._sans_path, size=24)
            before = font.get_metrics(text)
            font.__setattr__(method, value)
            after = font.get_metrics(text)
            self.assertNotEqual(before, after, msg)

        for test in tests:
            run_test(test["method"], test["value"], test["msg"])

    def test_freetype_SysFont_name(self):
        """that SysFont accepts names of various types"""
        fonts = pygame.font.get_fonts()
        size = 12

        # Check single name string:
        font_name = ft.SysFont(fonts[0], size).name
        self.assertFalse(font_name is None)

        # Check string of comma-separated names.
        names = ",".join(fonts)
        font_name_2 = ft.SysFont(names, size).name
        self.assertEqual(font_name_2, font_name)

        # Check list of names.
        font_name_2 = ft.SysFont(fonts, size).name
        self.assertEqual(font_name_2, font_name)

        # Check generator:
        names = (name for name in fonts)
        font_name_2 = ft.SysFont(names, size).name
        self.assertEqual(font_name_2, font_name)

        fonts_b = [f.encode() for f in fonts]

        # Check single name bytes.
        font_name_2 = ft.SysFont(fonts_b[0], size).name
        self.assertEqual(font_name_2, font_name)

        # Check comma-separated bytes.
        names = b",".join(fonts_b)
        font_name_2 = ft.SysFont(names, size).name
        self.assertEqual(font_name_2, font_name)

        # Check list of bytes.
        font_name_2 = ft.SysFont(fonts_b, size).name
        self.assertEqual(font_name_2, font_name)

        # Check mixed list of bytes and string.
        names = [fonts[0], fonts_b[1], fonts[2], fonts_b[3]]
        font_name_2 = ft.SysFont(names, size).name
        self.assertEqual(font_name_2, font_name)

    def test_pathlib(self):
        f = ft.Font(pathlib.Path(self._fixed_path), 20)


class FreeTypeTest(unittest.TestCase):
    def setUp(self):
        ft.init()

    def tearDown(self):
        ft.quit()

    def test_resolution(self):
        try:
            ft.set_default_resolution()
            resolution = ft.get_default_resolution()
            self.assertEqual(resolution, 72)
            new_resolution = resolution + 10
            ft.set_default_resolution(new_resolution)
            self.assertEqual(ft.get_default_resolution(), new_resolution)
            ft.init(resolution=resolution + 20)
            self.assertEqual(ft.get_default_resolution(), new_resolution)
        finally:
            ft.set_default_resolution()

    def test_autoinit_and_autoquit(self):
        pygame.init()
        self.assertTrue(ft.get_init())
        pygame.quit()
        self.assertFalse(ft.get_init())

        # Ensure autoquit is replaced at init time
        pygame.init()
        self.assertTrue(ft.get_init())
        pygame.quit()
        self.assertFalse(ft.get_init())

    def test_init(self):
        # Test if module initialized after calling init().
        ft.quit()
        ft.init()

        self.assertTrue(ft.get_init())

    def test_init__multiple(self):
        # Test if module initialized after multiple init() calls.
        ft.init()
        ft.init()

        self.assertTrue(ft.get_init())

    def test_quit(self):
        # Test if module uninitialized after calling quit().
        ft.quit()

        self.assertFalse(ft.get_init())

    def test_quit__multiple(self):
        # Test if module initialized after multiple quit() calls.
        ft.quit()
        ft.quit()

        self.assertFalse(ft.get_init())

    def test_get_init(self):
        # Test if get_init() gets the init state.
        self.assertTrue(ft.get_init())

    def test_cache_size(self):
        DEFAULT_CACHE_SIZE = 64
        self.assertEqual(ft.get_cache_size(), DEFAULT_CACHE_SIZE)
        ft.quit()
        self.assertEqual(ft.get_cache_size(), 0)
        new_cache_size = DEFAULT_CACHE_SIZE * 2
        ft.init(cache_size=new_cache_size)
        self.assertEqual(ft.get_cache_size(), new_cache_size)

    def test_get_error(self):
        """Ensures get_error() is initially empty (None)."""
        error_msg = ft.get_error()

        self.assertIsNone(error_msg)

    def test_get_version(self):
        # Test that get_version() can be called before init()
        # Also tests get_version
        ft.quit()

        # asserting not None just to have a test case
        # there is no real fail condition other than
        # raising an exception or a segfault, so a tuple of ints
        # should be returned in all cases
        self.assertIsNotNone(ft.get_version(linked=False))
        self.assertIsNotNone(ft.get_version(linked=True))


if __name__ == "__main__":
    unittest.main()
