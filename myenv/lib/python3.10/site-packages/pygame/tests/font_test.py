# -*- coding: utf-8 -*-
from re import T
import sys
import os
import unittest
import pathlib
import platform

import pygame
from pygame import font as pygame_font  # So font can be replaced with ftfont


FONTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "fonts")


def equal_images(s1, s2):
    size = s1.get_size()
    if s2.get_size() != size:
        return False
    w, h = size
    for x in range(w):
        for y in range(h):
            if s1.get_at((x, y)) != s2.get_at((x, y)):
                return False
    return True


IS_PYPY = "PyPy" == platform.python_implementation()


@unittest.skipIf(IS_PYPY, "pypy skip known failure")  # TODO
class FontModuleTest(unittest.TestCase):
    def setUp(self):
        pygame_font.init()

    def tearDown(self):
        pygame_font.quit()

    def test_get_sdl_ttf_version(self):
        def test_ver_tuple(ver):
            self.assertIsInstance(ver, tuple)
            self.assertEqual(len(ver), 3)
            for i in ver:
                self.assertIsInstance(i, int)

        if pygame_font.__name__ != "pygame.ftfont":
            compiled = pygame_font.get_sdl_ttf_version()
            linked = pygame_font.get_sdl_ttf_version(linked=True)

            test_ver_tuple(compiled)
            test_ver_tuple(linked)

            self.assertTrue(linked >= compiled)

    def test_SysFont(self):
        # Can only check that a font object is returned.
        fonts = pygame_font.get_fonts()
        if "arial" in fonts:
            # Try to use arial font if it is there, rather than a random font
            #  which can be different depending on installed fonts on the system.
            font_name = "arial"
        else:
            font_name = sorted(fonts)[0]
        o = pygame_font.SysFont(font_name, 20)
        self.assertTrue(isinstance(o, pygame_font.FontType))
        o = pygame_font.SysFont(font_name, 20, italic=True)
        self.assertTrue(isinstance(o, pygame_font.FontType))
        o = pygame_font.SysFont(font_name, 20, bold=True)
        self.assertTrue(isinstance(o, pygame_font.FontType))
        o = pygame_font.SysFont("thisisnotafont", 20)
        self.assertTrue(isinstance(o, pygame_font.FontType))

    def test_get_default_font(self):
        self.assertEqual(pygame_font.get_default_font(), "freesansbold.ttf")

    def test_get_fonts_returns_something(self):
        fnts = pygame_font.get_fonts()
        self.assertTrue(fnts)

    # to test if some files exist...
    # def XXtest_has_file_osx_10_5_sdk(self):
    #    import os
    #    f = "/Developer/SDKs/MacOSX10.5.sdk/usr/X11/include/ft2build.h"
    #    self.assertEqual(os.path.exists(f), True)

    # def XXtest_has_file_osx_10_4_sdk(self):
    #    import os
    #    f = "/Developer/SDKs/MacOSX10.4u.sdk/usr/X11R6/include/ft2build.h"
    #    self.assertEqual(os.path.exists(f), True)

    def test_get_fonts(self):
        fnts = pygame_font.get_fonts()

        self.assertTrue(fnts, msg=repr(fnts))

        for name in fnts:
            # note, on ubuntu 2.6 they are all unicode strings.

            self.assertTrue(isinstance(name, str), name)
            # Font names can be comprised of only numeric characters, so
            # just checking name.islower() will not work as expected here.
            self.assertFalse(any(c.isupper() for c in name))
            self.assertTrue(name.isalnum(), name)

    def test_get_init(self):
        self.assertTrue(pygame_font.get_init())
        pygame_font.quit()
        self.assertFalse(pygame_font.get_init())

    def test_init(self):
        pygame_font.init()

    def test_match_font_all_exist(self):
        fonts = pygame_font.get_fonts()

        # Ensure all listed fonts are in fact available, and the returned file
        # name is a full path.
        for font in fonts:
            path = pygame_font.match_font(font)
            self.assertFalse(path is None)
            self.assertTrue(os.path.isabs(path) and os.path.isfile(path))

    def test_match_font_name(self):
        """That match_font accepts names of various types"""
        font = pygame_font.get_fonts()[0]
        font_path = pygame_font.match_font(font)
        self.assertIsNotNone(font_path)
        font_b = font.encode()
        not_a_font = "thisisnotafont"
        not_a_font_b = b"thisisnotafont"
        good_font_names = [
            # Check single name bytes.
            font_b,
            # Check string of comma-separated names.
            ",".join([not_a_font, font, not_a_font]),
            # Check list of names.
            [not_a_font, font, not_a_font],
            # Check generator:
            (name for name in [not_a_font, font, not_a_font]),
            # Check comma-separated bytes.
            b",".join([not_a_font_b, font_b, not_a_font_b]),
            # Check list of bytes.
            [not_a_font_b, font_b, not_a_font_b],
            # Check mixed list of bytes and string.
            [font, not_a_font, font_b, not_a_font_b],
        ]
        for font_name in good_font_names:
            self.assertEqual(pygame_font.match_font(font_name), font_path, font_name)

    def test_not_match_font_name(self):
        """match_font return None when names of various types do not exist"""
        not_a_font = "thisisnotafont"
        not_a_font_b = b"thisisnotafont"
        bad_font_names = [
            not_a_font,
            ",".join([not_a_font, not_a_font, not_a_font]),
            [not_a_font, not_a_font, not_a_font],
            (name for name in [not_a_font, not_a_font, not_a_font]),
            not_a_font_b,
            b",".join([not_a_font_b, not_a_font_b, not_a_font_b]),
            [not_a_font_b, not_a_font_b, not_a_font_b],
            [not_a_font, not_a_font_b, not_a_font],
        ]
        for font_name in bad_font_names:
            self.assertIsNone(pygame_font.match_font(font_name), font_name)

    def test_match_font_bold(self):
        fonts = pygame_font.get_fonts()

        # Look for a bold font.
        self.assertTrue(any(pygame_font.match_font(font, bold=True) for font in fonts))

    def test_match_font_italic(self):
        fonts = pygame_font.get_fonts()

        # Look for an italic font.
        self.assertTrue(
            any(pygame_font.match_font(font, italic=True) for font in fonts)
        )

    def test_issue_742(self):
        """that the font background does not crash."""
        surf = pygame.Surface((320, 240))
        font = pygame_font.Font(None, 24)
        image = font.render("Test", 0, (255, 255, 255), (0, 0, 0))
        self.assertIsNone(image.get_colorkey())
        image.set_alpha(255)
        surf.blit(image, (0, 0))

        # not issue 742, but be sure to test that background color is
        # correctly issued on this mode
        self.assertEqual(surf.get_at((0, 0)), pygame.Color(0, 0, 0))

    def test_issue_font_alphablit(self):
        """Check that blitting anti-aliased text doesn't
        change the background blue"""
        pygame.display.set_mode((600, 400))

        font = pygame_font.Font(None, 24)

        (color, text, center, pos) = ((160, 200, 250), "Music", (190, 170), "midright")
        img1 = font.render(text, True, color)

        img = pygame.Surface(img1.get_size(), depth=32)
        pre_blit_corner_pixel = img.get_at((0, 0))
        img.blit(img1, (0, 0))
        post_blit_corner_pixel = img.get_at((0, 0))

        self.assertEqual(pre_blit_corner_pixel, post_blit_corner_pixel)

    def test_segfault_after_reinit(self):
        """Reinitialization of font module should not cause
        segmentation fault"""
        import gc

        font = pygame_font.Font(None, 20)
        pygame_font.quit()
        pygame_font.init()
        del font
        gc.collect()

    def test_quit(self):
        pygame_font.quit()


@unittest.skipIf(IS_PYPY, "pypy skip known failure")  # TODO
class FontTest(unittest.TestCase):
    def setUp(self):
        pygame_font.init()

    def tearDown(self):
        pygame_font.quit()

    def test_render_args(self):
        screen = pygame.display.set_mode((600, 400))
        rect = screen.get_rect()
        f = pygame_font.Font(None, 20)
        screen.fill((10, 10, 10))
        font_surface = f.render("   bar", True, (0, 0, 0), (255, 255, 255))
        font_rect = font_surface.get_rect()
        font_rect.topleft = rect.topleft
        self.assertTrue(font_surface)
        screen.blit(font_surface, font_rect, font_rect)
        pygame.display.update()
        self.assertEqual(tuple(screen.get_at((0, 0)))[:3], (255, 255, 255))
        self.assertEqual(tuple(screen.get_at(font_rect.topleft))[:3], (255, 255, 255))

        # If we don't have a real display, don't do this test.
        # Transparent background doesn't seem to work without a read video card.
        if os.environ.get("SDL_VIDEODRIVER") != "dummy":
            screen.fill((10, 10, 10))
            font_surface = f.render("   bar", True, (0, 0, 0), None)
            font_rect = font_surface.get_rect()
            font_rect.topleft = rect.topleft
            self.assertTrue(font_surface)
            screen.blit(font_surface, font_rect, font_rect)
            pygame.display.update()
            self.assertEqual(tuple(screen.get_at((0, 0)))[:3], (10, 10, 10))
            self.assertEqual(tuple(screen.get_at(font_rect.topleft))[:3], (10, 10, 10))

            screen.fill((10, 10, 10))
            font_surface = f.render("   bar", True, (0, 0, 0))
            font_rect = font_surface.get_rect()
            font_rect.topleft = rect.topleft
            self.assertTrue(font_surface)
            screen.blit(font_surface, font_rect, font_rect)
            pygame.display.update(rect)
            self.assertEqual(tuple(screen.get_at((0, 0)))[:3], (10, 10, 10))
            self.assertEqual(tuple(screen.get_at(font_rect.topleft))[:3], (10, 10, 10))


@unittest.skipIf(IS_PYPY, "pypy skip known failure")  # TODO
class FontTypeTest(unittest.TestCase):
    def setUp(self):
        pygame_font.init()

    def tearDown(self):
        pygame_font.quit()

    def test_default_parameters(self):
        f = pygame_font.Font()

    def test_get_ascent(self):
        # Ckecking ascent would need a custom test font to do properly.
        f = pygame_font.Font(None, 20)
        ascent = f.get_ascent()
        self.assertTrue(isinstance(ascent, int))
        self.assertTrue(ascent > 0)
        s = f.render("X", False, (255, 255, 255))
        self.assertTrue(s.get_size()[1] > ascent)

    def test_get_descent(self):
        # Ckecking descent would need a custom test font to do properly.
        f = pygame_font.Font(None, 20)
        descent = f.get_descent()
        self.assertTrue(isinstance(descent, int))
        self.assertTrue(descent < 0)

    def test_get_height(self):
        # Ckecking height would need a custom test font to do properly.
        f = pygame_font.Font(None, 20)
        height = f.get_height()
        self.assertTrue(isinstance(height, int))
        self.assertTrue(height > 0)
        s = f.render("X", False, (255, 255, 255))
        self.assertTrue(s.get_size()[1] == height)

    def test_get_linesize(self):
        # Ckecking linesize would need a custom test font to do properly.
        # Questions: How do linesize, height and descent relate?
        f = pygame_font.Font(None, 20)
        linesize = f.get_linesize()
        self.assertTrue(isinstance(linesize, int))
        self.assertTrue(linesize > 0)

    def test_metrics(self):
        # Ensure bytes decoding works correctly. Can only compare results
        # with unicode for now.
        f = pygame_font.Font(None, 20)
        um = f.metrics(".")
        bm = f.metrics(b".")

        self.assertEqual(len(um), 1)
        self.assertEqual(len(bm), 1)
        self.assertIsNotNone(um[0])
        self.assertEqual(um, bm)

        u = "\u212A"
        b = u.encode("UTF-16")[2:]  # Keep byte order consistent. [2:] skips BOM
        bm = f.metrics(b)

        self.assertEqual(len(bm), 2)

        try:  # FIXME why do we do this try/except ?
            um = f.metrics(u)
        except pygame.error:
            pass
        else:
            self.assertEqual(len(um), 1)
            self.assertNotEqual(bm[0], um[0])
            self.assertNotEqual(bm[1], um[0])

        u = "\U00013000"
        bm = f.metrics(u)

        self.assertEqual(len(bm), 1)
        self.assertIsNone(bm[0])

        return  # unfinished
        # The documentation is useless here. How large a list?
        # How do list positions relate to character codes?
        # What about unicode characters?

        # __doc__ (as of 2008-08-02) for pygame_font.Font.metrics:

        # Font.metrics(text): return list
        # Gets the metrics for each character in the passed string.
        #
        # The list contains tuples for each character, which contain the
        # minimum X offset, the maximum X offset, the minimum Y offset, the
        # maximum Y offset and the advance offset (bearing plus width) of the
        # character. [(minx, maxx, miny, maxy, advance), (minx, maxx, miny,
        # maxy, advance), ...]

        self.fail()

    def test_render(self):
        f = pygame_font.Font(None, 20)
        s = f.render("foo", True, [0, 0, 0], [255, 255, 255])
        s = f.render("xxx", True, [0, 0, 0], [255, 255, 255])
        s = f.render("", True, [0, 0, 0], [255, 255, 255])
        s = f.render("foo", False, [0, 0, 0], [255, 255, 255])
        s = f.render("xxx", False, [0, 0, 0], [255, 255, 255])
        s = f.render("xxx", False, [0, 0, 0])
        s = f.render("   ", False, [0, 0, 0])
        s = f.render("   ", False, [0, 0, 0], [255, 255, 255])
        # null text should be 0 pixel wide.
        s = f.render("", False, [0, 0, 0], [255, 255, 255])
        self.assertEqual(s.get_size()[0], 0)
        # None text should be 0 pixel wide.
        s = f.render(None, False, [0, 0, 0], [255, 255, 255])
        self.assertEqual(s.get_size()[0], 0)
        # Non-text should raise a TypeError.
        self.assertRaises(TypeError, f.render, [], False, [0, 0, 0], [255, 255, 255])
        self.assertRaises(TypeError, f.render, 1, False, [0, 0, 0], [255, 255, 255])
        # is background transparent for antialiasing?
        s = f.render(".", True, [255, 255, 255])
        self.assertEqual(s.get_at((0, 0))[3], 0)
        # is Unicode and bytes encoding correct?
        # Cannot really test if the correct characters are rendered, but
        # at least can assert the encodings differ.
        su = f.render(".", False, [0, 0, 0], [255, 255, 255])
        sb = f.render(b".", False, [0, 0, 0], [255, 255, 255])
        self.assertTrue(equal_images(su, sb))
        u = "\u212A"
        b = u.encode("UTF-16")[2:]  # Keep byte order consistent. [2:] skips BOM
        sb = f.render(b, False, [0, 0, 0], [255, 255, 255])
        try:  # FIXME why do we do this try/except ?
            su = f.render(u, False, [0, 0, 0], [255, 255, 255])
        except pygame.error:
            pass
        else:
            self.assertFalse(equal_images(su, sb))

        # test for internal null bytes
        self.assertRaises(ValueError, f.render, b"ab\x00cd", 0, [0, 0, 0])
        self.assertRaises(ValueError, f.render, "ab\x00cd", 0, [0, 0, 0])

    def test_render_ucs2_ucs4(self):
        """that it renders without raising if there is a new enough SDL_ttf."""
        f = pygame_font.Font(None, 20)
        # If the font module is SDL_ttf < 2.0.15 based, then it only supports UCS-2
        # it will raise an exception for an out-of-range UCS-4 code point.
        if hasattr(pygame_font, "UCS4"):
            ucs_2 = "\uFFEE"
            s = f.render(ucs_2, False, [0, 0, 0], [255, 255, 255])
            ucs_4 = "\U00010000"
            s = f.render(ucs_4, False, [0, 0, 0], [255, 255, 255])

    def test_set_bold(self):
        f = pygame_font.Font(None, 20)
        self.assertFalse(f.get_bold())
        f.set_bold(True)
        self.assertTrue(f.get_bold())
        f.set_bold(False)
        self.assertFalse(f.get_bold())

    def test_set_italic(self):
        f = pygame_font.Font(None, 20)
        self.assertFalse(f.get_italic())
        f.set_italic(True)
        self.assertTrue(f.get_italic())
        f.set_italic(False)
        self.assertFalse(f.get_italic())

    def test_set_underline(self):
        f = pygame_font.Font(None, 20)
        self.assertFalse(f.get_underline())
        f.set_underline(True)
        self.assertTrue(f.get_underline())
        f.set_underline(False)
        self.assertFalse(f.get_underline())

    def test_set_strikethrough(self):
        if pygame_font.__name__ != "pygame.ftfont":
            f = pygame_font.Font(None, 20)
            self.assertFalse(f.get_strikethrough())
            f.set_strikethrough(True)
            self.assertTrue(f.get_strikethrough())
            f.set_strikethrough(False)
            self.assertFalse(f.get_strikethrough())

    def test_bold_attr(self):
        f = pygame_font.Font(None, 20)
        self.assertFalse(f.bold)
        f.bold = True
        self.assertTrue(f.bold)
        f.bold = False
        self.assertFalse(f.bold)

    def test_set_italic_property(self):
        f = pygame_font.Font(None, 20)
        self.assertFalse(f.italic)
        f.italic = True
        self.assertTrue(f.italic)
        f.italic = False
        self.assertFalse(f.italic)

    def test_set_underline_property(self):
        f = pygame_font.Font(None, 20)
        self.assertFalse(f.underline)
        f.underline = True
        self.assertTrue(f.underline)
        f.underline = False
        self.assertFalse(f.underline)

    def test_set_strikethrough_property(self):
        if pygame_font.__name__ != "pygame.ftfont":
            f = pygame_font.Font(None, 20)
            self.assertFalse(f.strikethrough)
            f.strikethrough = True
            self.assertTrue(f.strikethrough)
            f.strikethrough = False
            self.assertFalse(f.strikethrough)

    def test_size(self):
        f = pygame_font.Font(None, 20)
        text = "Xg"
        size = f.size(text)
        w, h = size
        s = f.render(text, False, (255, 255, 255))
        btext = text.encode("ascii")

        self.assertIsInstance(w, int)
        self.assertIsInstance(h, int)
        self.assertEqual(s.get_size(), size)
        self.assertEqual(f.size(btext), size)

        text = "\u212A"
        btext = text.encode("UTF-16")[2:]  # Keep the byte order consistent.
        bsize = f.size(btext)
        size = f.size(text)

        self.assertNotEqual(size, bsize)

    def test_font_file_not_found(self):
        # A per BUG reported by Bo Jangeborg on pygame-user mailing list,
        # http://www.mail-archive.com/pygame-users@seul.org/msg11675.html

        pygame_font.init()
        self.assertRaises(
            FileNotFoundError, pygame_font.Font, "some-fictional-font.ttf", 20
        )

    def test_load_from_file(self):
        font_name = pygame_font.get_default_font()
        font_path = os.path.join(
            os.path.split(pygame.__file__)[0], pygame_font.get_default_font()
        )
        f = pygame_font.Font(font_path, 20)

    def test_load_from_file_default(self):
        font_name = pygame_font.get_default_font()
        font_path = os.path.join(
            os.path.split(pygame.__file__)[0], pygame_font.get_default_font()
        )
        f = pygame_font.Font(font_path)

    def test_load_from_pathlib(self):
        font_name = pygame_font.get_default_font()
        font_path = os.path.join(
            os.path.split(pygame.__file__)[0], pygame_font.get_default_font()
        )
        f = pygame_font.Font(pathlib.Path(font_path), 20)
        f = pygame_font.Font(pathlib.Path(font_path))

    def test_load_from_pathlib_default(self):
        font_name = pygame_font.get_default_font()
        font_path = os.path.join(
            os.path.split(pygame.__file__)[0], pygame_font.get_default_font()
        )
        f = pygame_font.Font(pathlib.Path(font_path))

    def test_load_from_file_obj(self):
        font_name = pygame_font.get_default_font()
        font_path = os.path.join(
            os.path.split(pygame.__file__)[0], pygame_font.get_default_font()
        )
        with open(font_path, "rb") as f:
            font = pygame_font.Font(f, 20)

    def test_load_from_file_obj_default(self):
        font_name = pygame_font.get_default_font()
        font_path = os.path.join(
            os.path.split(pygame.__file__)[0], pygame_font.get_default_font()
        )
        with open(font_path, "rb") as f:
            font = pygame_font.Font(f)

    def test_load_default_font_filename(self):
        # In font_init, a special case is when the filename argument is
        # identical to the default font file name.
        f = pygame_font.Font(pygame_font.get_default_font(), 20)

    def test_load_default_font_filename_default(self):
        # In font_init, a special case is when the filename argument is
        # identical to the default font file name.
        f = pygame_font.Font(pygame_font.get_default_font())

    def _load_unicode(self, path):
        import shutil

        fdir = str(FONTDIR)
        temp = os.path.join(fdir, path)
        pgfont = os.path.join(fdir, "test_sans.ttf")
        shutil.copy(pgfont, temp)
        try:
            with open(temp, "rb") as f:
                pass
        except FileNotFoundError:
            raise unittest.SkipTest("the path cannot be opened")
        try:
            pygame_font.Font(temp, 20)
        finally:
            os.remove(temp)

    def test_load_from_file_unicode_0(self):
        """ASCII string as a unicode object"""
        self._load_unicode("temp_file.ttf")

    def test_load_from_file_unicode_1(self):
        self._load_unicode("你好.ttf")

    def test_load_from_file_bytes(self):
        font_path = os.path.join(
            os.path.split(pygame.__file__)[0], pygame_font.get_default_font()
        )
        filesystem_encoding = sys.getfilesystemencoding()
        filesystem_errors = "replace" if sys.platform == "win32" else "surrogateescape"
        try:  # FIXME why do we do this try/except ?
            font_path = font_path.decode(filesystem_encoding, filesystem_errors)
        except AttributeError:
            pass
        bfont_path = font_path.encode(filesystem_encoding, filesystem_errors)
        f = pygame_font.Font(bfont_path, 20)

    def test_issue_3144(self):
        fpath = os.path.join(FONTDIR, "PlayfairDisplaySemibold.ttf")

        # issue in SDL_ttf 2.0.18 DLL on Windows
        # tested to make us aware of any regressions
        for size in (60, 40, 10, 20, 70, 45, 50, 10):
            font = pygame_font.Font(fpath, size)
            font.render("WHERE", True, "black")

    def test_font_set_script(self):
        if pygame_font.__name__ == "pygame.ftfont":
            return  # this ain't a pygame.ftfont thing!

        font = pygame_font.Font(None, 16)

        ttf_version = pygame_font.get_sdl_ttf_version()
        if ttf_version >= (2, 20, 0):
            self.assertRaises(TypeError, pygame.font.Font.set_script)
            self.assertRaises(TypeError, pygame.font.Font.set_script, font)
            self.assertRaises(TypeError, pygame.font.Font.set_script, "hey", "Deva")
            self.assertRaises(TypeError, font.set_script, 1)
            self.assertRaises(TypeError, font.set_script, ["D", "e", "v", "a"])

            self.assertRaises(ValueError, font.set_script, "too long by far")
            self.assertRaises(ValueError, font.set_script, "")
            self.assertRaises(ValueError, font.set_script, "a")

            font.set_script("Deva")
        else:
            self.assertRaises(pygame.error, font.set_script, "Deva")


@unittest.skipIf(IS_PYPY, "pypy skip known failure")  # TODO
class VisualTests(unittest.TestCase):
    __tags__ = ["interactive"]

    screen = None
    aborted = False

    def setUp(self):
        if self.screen is None:
            pygame.init()
            self.screen = pygame.display.set_mode((600, 200))
            self.screen.fill((255, 255, 255))
            pygame.display.flip()
            self.f = pygame_font.Font(None, 32)

    def abort(self):
        if self.screen is not None:
            pygame.quit()
        self.aborted = True

    def query(
        self,
        bold=False,
        italic=False,
        underline=False,
        strikethrough=False,
        antialiase=False,
    ):
        if self.aborted:
            return False
        spacing = 10
        offset = 20
        y = spacing
        f = self.f
        screen = self.screen
        screen.fill((255, 255, 255))
        pygame.display.flip()
        if not (bold or italic or underline or strikethrough or antialiase):
            text = "normal"
        else:
            modes = []
            if bold:
                modes.append("bold")
            if italic:
                modes.append("italic")
            if underline:
                modes.append("underlined")
            if strikethrough:
                modes.append("strikethrough")
            if antialiase:
                modes.append("antialiased")
            text = f"{'-'.join(modes)} (y/n):"
        f.set_bold(bold)
        f.set_italic(italic)
        f.set_underline(underline)
        if pygame_font.__name__ != "pygame.ftfont":
            f.set_strikethrough(strikethrough)
        s = f.render(text, antialiase, (0, 0, 0))
        screen.blit(s, (offset, y))
        y += s.get_size()[1] + spacing
        f.set_bold(False)
        f.set_italic(False)
        f.set_underline(False)
        if pygame_font.__name__ != "pygame.ftfont":
            f.set_strikethrough(False)
        s = f.render("(some comparison text)", False, (0, 0, 0))
        screen.blit(s, (offset, y))
        pygame.display.flip()
        while True:
            for evt in pygame.event.get():
                if evt.type == pygame.KEYDOWN:
                    if evt.key == pygame.K_ESCAPE:
                        self.abort()
                        return False
                    if evt.key == pygame.K_y:
                        return True
                    if evt.key == pygame.K_n:
                        return False
                if evt.type == pygame.QUIT:
                    self.abort()
                    return False

    def test_bold(self):
        self.assertTrue(self.query(bold=True))

    def test_italic(self):
        self.assertTrue(self.query(italic=True))

    def test_underline(self):
        self.assertTrue(self.query(underline=True))

    def test_strikethrough(self):
        if pygame_font.__name__ != "pygame.ftfont":
            self.assertTrue(self.query(strikethrough=True))

    def test_antialiase(self):
        self.assertTrue(self.query(antialiase=True))

    def test_bold_antialiase(self):
        self.assertTrue(self.query(bold=True, antialiase=True))

    def test_italic_underline(self):
        self.assertTrue(self.query(italic=True, underline=True))

    def test_bold_strikethrough(self):
        if pygame_font.__name__ != "pygame.ftfont":
            self.assertTrue(self.query(bold=True, strikethrough=True))


if __name__ == "__main__":
    unittest.main()
