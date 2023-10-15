import os
import unittest
from pygame.tests import test_utils
from pygame.tests.test_utils import (
    example_path,
    SurfaceSubclass,
)

try:
    from pygame.tests.test_utils.arrinter import *
except (ImportError, NameError):
    pass
import pygame
from pygame.locals import *
from pygame.bufferproxy import BufferProxy

import platform
import gc
import weakref
import ctypes

IS_PYPY = "PyPy" == platform.python_implementation()


class SurfaceTypeTest(unittest.TestCase):
    def test_surface__pixel_format_as_surface_subclass(self):
        """Ensure a subclassed surface can be used for pixel format
        when creating a new surface."""
        expected_depth = 16
        expected_flags = SRCALPHA
        expected_size = (13, 37)
        depth_surface = SurfaceSubclass((11, 21), expected_flags, expected_depth)

        surface = pygame.Surface(expected_size, expected_flags, depth_surface)

        self.assertIsNot(surface, depth_surface)
        self.assertIsInstance(surface, pygame.Surface)
        self.assertNotIsInstance(surface, SurfaceSubclass)
        self.assertEqual(surface.get_size(), expected_size)
        self.assertEqual(surface.get_flags(), expected_flags)
        self.assertEqual(surface.get_bitsize(), expected_depth)

    def test_surface_created_opaque_black(self):
        surf = pygame.Surface((20, 20))
        self.assertEqual(surf.get_at((0, 0)), (0, 0, 0, 255))

        # See https://github.com/pygame/pygame/issues/1395
        pygame.display.set_mode((500, 500))
        surf = pygame.Surface((20, 20))
        self.assertEqual(surf.get_at((0, 0)), (0, 0, 0, 255))

    def test_set_clip(self):
        """see if surface.set_clip(None) works correctly."""
        s = pygame.Surface((800, 600))
        r = pygame.Rect(10, 10, 10, 10)
        s.set_clip(r)
        r.move_ip(10, 0)
        s.set_clip(None)
        res = s.get_clip()
        # this was garbled before.
        self.assertEqual(res[0], 0)
        self.assertEqual(res[2], 800)

    def test_print(self):
        surf = pygame.Surface((70, 70), 0, 32)
        self.assertEqual(repr(surf), "<Surface(70x70x32 SW)>")

    def test_keyword_arguments(self):
        surf = pygame.Surface((70, 70), flags=SRCALPHA, depth=32)
        self.assertEqual(surf.get_flags() & SRCALPHA, SRCALPHA)
        self.assertEqual(surf.get_bitsize(), 32)

        # sanity check to make sure the check below is valid
        surf_16 = pygame.Surface((70, 70), 0, 16)
        self.assertEqual(surf_16.get_bytesize(), 2)

        # try again with an argument list
        surf_16 = pygame.Surface((70, 70), depth=16)
        self.assertEqual(surf_16.get_bytesize(), 2)

    def test_set_at(self):
        # 24bit surfaces
        s = pygame.Surface((100, 100), 0, 24)
        s.fill((0, 0, 0))

        # set it with a tuple.
        s.set_at((0, 0), (10, 10, 10, 255))
        r = s.get_at((0, 0))
        self.assertIsInstance(r, pygame.Color)
        self.assertEqual(r, (10, 10, 10, 255))

        # try setting a color with a single integer.
        s.fill((0, 0, 0, 255))
        s.set_at((10, 1), 0x0000FF)
        r = s.get_at((10, 1))
        self.assertEqual(r, (0, 0, 255, 255))

    def test_set_at__big_endian(self):
        """png files are loaded in big endian format (BGR rather than RGB)"""
        pygame.display.init()
        try:
            image = pygame.image.load(example_path(os.path.join("data", "BGR.png")))
            # Check they start red, green and blue
            self.assertEqual(image.get_at((10, 10)), pygame.Color(255, 0, 0))
            self.assertEqual(image.get_at((10, 20)), pygame.Color(0, 255, 0))
            self.assertEqual(image.get_at((10, 40)), pygame.Color(0, 0, 255))
            # Set three pixels that are already red, green, blue
            # to red, green and, blue with set_at:
            image.set_at((10, 10), pygame.Color(255, 0, 0))
            image.set_at((10, 20), pygame.Color(0, 255, 0))
            image.set_at((10, 40), pygame.Color(0, 0, 255))

            # Check they still are
            self.assertEqual(image.get_at((10, 10)), pygame.Color(255, 0, 0))
            self.assertEqual(image.get_at((10, 20)), pygame.Color(0, 255, 0))
            self.assertEqual(image.get_at((10, 40)), pygame.Color(0, 0, 255))

        finally:
            pygame.display.quit()

    def test_SRCALPHA(self):
        # has the flag been passed in ok?
        surf = pygame.Surface((70, 70), SRCALPHA, 32)
        self.assertEqual(surf.get_flags() & SRCALPHA, SRCALPHA)

        # 24bit surfaces can not have SRCALPHA.
        self.assertRaises(ValueError, pygame.Surface, (100, 100), pygame.SRCALPHA, 24)

        # if we have a 32 bit surface, the SRCALPHA should have worked too.
        surf2 = pygame.Surface((70, 70), SRCALPHA)
        if surf2.get_bitsize() == 32:
            self.assertEqual(surf2.get_flags() & SRCALPHA, SRCALPHA)

    def test_flags_default0_nodisplay(self):
        """is set to zero, and SRCALPHA is not set by default with no display initialized."""
        pygame.display.quit()
        surf = pygame.Surface((70, 70))
        self.assertEqual(surf.get_flags() & SRCALPHA, 0)

    def test_flags_default0_display(self):
        """is set to zero, and SRCALPH is not set by default even when the display is initialized."""
        pygame.display.set_mode((320, 200))
        try:
            surf = pygame.Surface((70, 70))
            self.assertEqual(surf.get_flags() & SRCALPHA, 0)
        finally:
            pygame.display.quit()

    def test_masks(self):
        def make_surf(bpp, flags, masks):
            pygame.Surface((10, 10), flags, bpp, masks)

        # With some masks SDL_CreateRGBSurface does not work properly.
        masks = (0xFF000000, 0xFF0000, 0xFF00, 0)
        self.assertEqual(make_surf(32, 0, masks), None)
        # For 24 and 32 bit surfaces Pygame assumes no losses.
        masks = (0x7F0000, 0xFF00, 0xFF, 0)
        self.assertRaises(ValueError, make_surf, 24, 0, masks)
        self.assertRaises(ValueError, make_surf, 32, 0, masks)
        # What contiguous bits in a mask.
        masks = (0x6F0000, 0xFF00, 0xFF, 0)
        self.assertRaises(ValueError, make_surf, 32, 0, masks)

    def test_get_bounding_rect(self):
        surf = pygame.Surface((70, 70), SRCALPHA, 32)
        surf.fill((0, 0, 0, 0))
        bound_rect = surf.get_bounding_rect()
        self.assertEqual(bound_rect.width, 0)
        self.assertEqual(bound_rect.height, 0)
        surf.set_at((30, 30), (255, 255, 255, 1))
        bound_rect = surf.get_bounding_rect()
        self.assertEqual(bound_rect.left, 30)
        self.assertEqual(bound_rect.top, 30)
        self.assertEqual(bound_rect.width, 1)
        self.assertEqual(bound_rect.height, 1)
        surf.set_at((29, 29), (255, 255, 255, 1))
        bound_rect = surf.get_bounding_rect()
        self.assertEqual(bound_rect.left, 29)
        self.assertEqual(bound_rect.top, 29)
        self.assertEqual(bound_rect.width, 2)
        self.assertEqual(bound_rect.height, 2)

        surf = pygame.Surface((70, 70), 0, 24)
        surf.fill((0, 0, 0))
        bound_rect = surf.get_bounding_rect()
        self.assertEqual(bound_rect.width, surf.get_width())
        self.assertEqual(bound_rect.height, surf.get_height())

        surf.set_colorkey((0, 0, 0))
        bound_rect = surf.get_bounding_rect()
        self.assertEqual(bound_rect.width, 0)
        self.assertEqual(bound_rect.height, 0)
        surf.set_at((30, 30), (255, 255, 255))
        bound_rect = surf.get_bounding_rect()
        self.assertEqual(bound_rect.left, 30)
        self.assertEqual(bound_rect.top, 30)
        self.assertEqual(bound_rect.width, 1)
        self.assertEqual(bound_rect.height, 1)
        surf.set_at((60, 60), (255, 255, 255))
        bound_rect = surf.get_bounding_rect()
        self.assertEqual(bound_rect.left, 30)
        self.assertEqual(bound_rect.top, 30)
        self.assertEqual(bound_rect.width, 31)
        self.assertEqual(bound_rect.height, 31)

        # Issue #180
        pygame.display.init()
        try:
            surf = pygame.Surface((4, 1), 0, 8)
            surf.fill((255, 255, 255))
            surf.get_bounding_rect()  # Segfault.
        finally:
            pygame.display.quit()

    def test_copy(self):
        """Ensure a surface can be copied."""
        color = (25, 25, 25, 25)
        s1 = pygame.Surface((32, 32), pygame.SRCALPHA, 32)
        s1.fill(color)

        s2 = s1.copy()

        s1rect = s1.get_rect()
        s2rect = s2.get_rect()

        self.assertEqual(s1rect.size, s2rect.size)
        self.assertEqual(s2.get_at((10, 10)), color)

    def test_fill(self):
        """Ensure a surface can be filled."""
        color = (25, 25, 25, 25)
        fill_rect = pygame.Rect(0, 0, 16, 16)
        s1 = pygame.Surface((32, 32), pygame.SRCALPHA, 32)
        s1.fill(color, fill_rect)

        for pt in test_utils.rect_area_pts(fill_rect):
            self.assertEqual(s1.get_at(pt), color)

        for pt in test_utils.rect_outer_bounds(fill_rect):
            self.assertNotEqual(s1.get_at(pt), color)

    def test_fill_rle(self):
        """Test RLEACCEL flag with fill()"""
        color = (250, 25, 25, 255)

        surf = pygame.Surface((32, 32))
        blit_surf = pygame.Surface((32, 32))

        blit_surf.set_colorkey((255, 0, 255), pygame.RLEACCEL)
        self.assertTrue(blit_surf.get_flags() & pygame.RLEACCELOK)
        surf.blit(blit_surf, (0, 0))
        blit_surf.fill(color)
        self.assertEqual(
            blit_surf.mustlock(), (blit_surf.get_flags() & pygame.RLEACCEL) != 0
        )
        self.assertTrue(blit_surf.get_flags() & pygame.RLEACCEL)

    def test_mustlock_rle(self):
        """Test RLEACCEL flag with mustlock()"""
        surf = pygame.Surface((100, 100))
        blit_surf = pygame.Surface((100, 100))
        blit_surf.set_colorkey((0, 0, 255), pygame.RLEACCEL)
        self.assertTrue(blit_surf.get_flags() & pygame.RLEACCELOK)
        surf.blit(blit_surf, (0, 0))
        self.assertTrue(blit_surf.get_flags() & pygame.RLEACCEL)
        self.assertTrue(blit_surf.mustlock())

    def test_mustlock_surf_alpha_rle(self):
        """Test RLEACCEL flag with mustlock() on a surface
        with per pixel alpha - new feature in SDL2"""
        surf = pygame.Surface((100, 100))
        blit_surf = pygame.Surface((100, 100), depth=32, flags=pygame.SRCALPHA)
        blit_surf.set_colorkey((192, 191, 192, 255), pygame.RLEACCEL)
        self.assertTrue(blit_surf.get_flags() & pygame.RLEACCELOK)
        surf.blit(blit_surf, (0, 0))
        self.assertTrue(blit_surf.get_flags() & pygame.RLEACCEL)
        self.assertTrue(blit_surf.get_flags() & pygame.SRCALPHA)
        self.assertTrue(blit_surf.mustlock())

    def test_copy_rle(self):
        """Test copying a surface set to use run length encoding"""
        s1 = pygame.Surface((32, 32), 24)
        s1.set_colorkey((255, 0, 255), pygame.RLEACCEL)
        self.assertTrue(s1.get_flags() & pygame.RLEACCELOK)

        newsurf = s1.copy()
        self.assertTrue(s1.get_flags() & pygame.RLEACCELOK)
        self.assertTrue(newsurf.get_flags() & pygame.RLEACCELOK)

    def test_subsurface_rle(self):
        """Ensure an RLE sub-surface works independently of its parent."""
        color = (250, 25, 25, 255)
        color2 = (200, 200, 250, 255)
        sub_rect = pygame.Rect(16, 16, 16, 16)
        s0 = pygame.Surface((32, 32), 24)
        s1 = pygame.Surface((32, 32), 24)
        s1.set_colorkey((255, 0, 255), pygame.RLEACCEL)
        s1.fill(color)
        s2 = s1.subsurface(sub_rect)
        s2.fill(color2)
        s0.blit(s1, (0, 0))
        self.assertTrue(s1.get_flags() & pygame.RLEACCEL)
        self.assertTrue(not s2.get_flags() & pygame.RLEACCEL)

    def test_subsurface_rle2(self):
        """Ensure an RLE sub-surface works independently of its parent."""
        color = (250, 25, 25, 255)
        color2 = (200, 200, 250, 255)
        sub_rect = pygame.Rect(16, 16, 16, 16)

        s0 = pygame.Surface((32, 32), 24)
        s1 = pygame.Surface((32, 32), 24)
        s1.set_colorkey((255, 0, 255), pygame.RLEACCEL)
        s1.fill(color)
        s2 = s1.subsurface(sub_rect)
        s2.fill(color2)
        s0.blit(s2, (0, 0))
        self.assertTrue(s1.get_flags() & pygame.RLEACCELOK)
        self.assertTrue(not s2.get_flags() & pygame.RLEACCELOK)

    def test_solarwolf_rle_usage(self):
        """Test for error/crash when calling set_colorkey() followed
        by convert twice in succession. Code originally taken
        from solarwolf."""

        def optimize(img):
            clear = img.get_colorkey()
            img.set_colorkey(clear, RLEACCEL)
            self.assertEqual(img.get_colorkey(), clear)
            return img.convert()

        pygame.display.init()
        try:
            pygame.display.set_mode((640, 480))

            image = pygame.image.load(example_path(os.path.join("data", "alien1.png")))
            image = image.convert()
            orig_colorkey = image.get_colorkey()

            image = optimize(image)
            image = optimize(image)
            self.assertTrue(image.get_flags() & pygame.RLEACCELOK)
            self.assertTrue(not image.get_flags() & pygame.RLEACCEL)
            self.assertEqual(image.get_colorkey(), orig_colorkey)
            self.assertTrue(isinstance(image, pygame.Surface))
        finally:
            pygame.display.quit()

    def test_solarwolf_rle_usage_2(self):
        """Test for RLE status after setting alpha"""

        pygame.display.init()
        try:
            pygame.display.set_mode((640, 480), depth=32)
            blit_to_surf = pygame.Surface((100, 100))

            image = pygame.image.load(example_path(os.path.join("data", "alien1.png")))
            image = image.convert()
            orig_colorkey = image.get_colorkey()

            # set the colorkey with RLEACCEL, should add the RLEACCELOK flag
            image.set_colorkey(orig_colorkey, RLEACCEL)
            self.assertTrue(image.get_flags() & pygame.RLEACCELOK)
            self.assertTrue(not image.get_flags() & pygame.RLEACCEL)

            # now blit the surface - should add the RLEACCEL flag
            blit_to_surf.blit(image, (0, 0))
            self.assertTrue(image.get_flags() & pygame.RLEACCELOK)
            self.assertTrue(image.get_flags() & pygame.RLEACCEL)

            # Now set the alpha, without RLE acceleration - should strip all
            # RLE flags
            image.set_alpha(90)
            self.assertTrue(not image.get_flags() & pygame.RLEACCELOK)
            self.assertTrue(not image.get_flags() & pygame.RLEACCEL)

        finally:
            pygame.display.quit()

    def test_set_alpha__set_colorkey_rle(self):
        pygame.display.init()
        try:
            pygame.display.set_mode((640, 480))
            blit_to_surf = pygame.Surface((80, 71))
            blit_to_surf.fill((255, 255, 255))

            image = pygame.image.load(example_path(os.path.join("data", "alien1.png")))
            image = image.convert()
            orig_colorkey = image.get_colorkey()

            # Add the RLE flag while setting alpha for the whole surface
            image.set_alpha(90, RLEACCEL)
            blit_to_surf.blit(image, (0, 0))
            sample_pixel_rle = blit_to_surf.get_at((50, 50))

            # Now reset the colorkey to the original value with RLE
            self.assertEqual(image.get_colorkey(), orig_colorkey)
            image.set_colorkey(orig_colorkey, RLEACCEL)
            blit_to_surf.fill((255, 255, 255))
            blit_to_surf.blit(image, (0, 0))
            sample_pixel_no_rle = blit_to_surf.get_at((50, 50))

            self.assertAlmostEqual(sample_pixel_rle.r, sample_pixel_no_rle.r, delta=2)
            self.assertAlmostEqual(sample_pixel_rle.g, sample_pixel_no_rle.g, delta=2)
            self.assertAlmostEqual(sample_pixel_rle.b, sample_pixel_no_rle.b, delta=2)

        finally:
            pygame.display.quit()

    def test_fill_negative_coordinates(self):
        # negative coordinates should be clipped by fill, and not draw outside the surface.
        color = (25, 25, 25, 25)
        color2 = (20, 20, 20, 25)
        fill_rect = pygame.Rect(-10, -10, 16, 16)

        s1 = pygame.Surface((32, 32), pygame.SRCALPHA, 32)
        r1 = s1.fill(color, fill_rect)
        c = s1.get_at((0, 0))
        self.assertEqual(c, color)

        # make subsurface in the middle to test it doesn't over write.
        s2 = s1.subsurface((5, 5, 5, 5))
        r2 = s2.fill(color2, (-3, -3, 5, 5))
        c2 = s1.get_at((4, 4))
        self.assertEqual(c, color)

        # rect returns the area we actually fill.
        r3 = s2.fill(color2, (-30, -30, 5, 5))
        # since we are using negative coords, it should be an zero sized rect.
        self.assertEqual(tuple(r3), (0, 0, 0, 0))

    def test_fill_keyword_args(self):
        """Ensure fill() accepts keyword arguments."""
        color = (1, 2, 3, 255)
        area = (1, 1, 2, 2)
        s1 = pygame.Surface((4, 4), 0, 32)
        s1.fill(special_flags=pygame.BLEND_ADD, color=color, rect=area)

        self.assertEqual(s1.get_at((0, 0)), (0, 0, 0, 255))
        self.assertEqual(s1.get_at((1, 1)), color)

    ########################################################################

    def test_get_alpha(self):
        """Ensure a surface's alpha value can be retrieved."""
        s1 = pygame.Surface((32, 32), pygame.SRCALPHA, 32)

        self.assertEqual(s1.get_alpha(), 255)

        for alpha in (0, 32, 127, 255):
            s1.set_alpha(alpha)
            for t in range(4):
                s1.set_alpha(s1.get_alpha())

            self.assertEqual(s1.get_alpha(), alpha)

    ########################################################################

    def test_get_bytesize(self):
        """Ensure a surface's bit and byte sizes can be retrieved."""
        pygame.display.init()
        try:
            depth = 32
            depth_bytes = 4
            s1 = pygame.Surface((32, 32), pygame.SRCALPHA, depth)

            self.assertEqual(s1.get_bytesize(), depth_bytes)
            self.assertEqual(s1.get_bitsize(), depth)

            depth = 15
            depth_bytes = 2
            s1 = pygame.Surface((32, 32), 0, depth)

            self.assertEqual(s1.get_bytesize(), depth_bytes)
            self.assertEqual(s1.get_bitsize(), depth)

            depth = 12
            depth_bytes = 2
            s1 = pygame.Surface((32, 32), 0, depth)

            self.assertEqual(s1.get_bytesize(), depth_bytes)
            self.assertEqual(s1.get_bitsize(), depth)

            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode()
                pygame.display.quit()
                surface.get_bytesize()
        finally:
            pygame.display.quit()

    ########################################################################

    def test_get_flags(self):
        """Ensure a surface's flags can be retrieved."""
        s1 = pygame.Surface((32, 32), pygame.SRCALPHA, 32)

        self.assertEqual(s1.get_flags(), pygame.SRCALPHA)

    @unittest.skipIf(
        os.environ.get("SDL_VIDEODRIVER") == "dummy",
        'requires a non-"dummy" SDL_VIDEODRIVER',
    )
    def test_get_flags__display_surf(self):
        pygame.display.init()
        try:
            # FULLSCREEN
            screen_surf = pygame.display.set_mode((600, 400), flags=0)
            self.assertFalse(screen_surf.get_flags() & pygame.FULLSCREEN)

            screen_surf = pygame.display.set_mode((600, 400), flags=pygame.FULLSCREEN)
            self.assertTrue(screen_surf.get_flags() & pygame.FULLSCREEN)

            # NOFRAME
            screen_surf = pygame.display.set_mode((600, 400), flags=0)
            self.assertFalse(screen_surf.get_flags() & pygame.NOFRAME)

            screen_surf = pygame.display.set_mode((600, 400), flags=pygame.NOFRAME)
            self.assertTrue(screen_surf.get_flags() & pygame.NOFRAME)

            # RESIZABLE
            screen_surf = pygame.display.set_mode((600, 400), flags=0)
            self.assertFalse(screen_surf.get_flags() & pygame.RESIZABLE)

            screen_surf = pygame.display.set_mode((600, 400), flags=pygame.RESIZABLE)
            self.assertTrue(screen_surf.get_flags() & pygame.RESIZABLE)

            # OPENGL
            screen_surf = pygame.display.set_mode((600, 400), flags=0)
            # it can have an OPENGL flag by default on Macos?
            if not (screen_surf.get_flags() & pygame.OPENGL):
                self.assertFalse(screen_surf.get_flags() & pygame.OPENGL)

            try:
                pygame.display.set_mode((200, 200), pygame.OPENGL, 32)
            except pygame.error:
                pass  # If we can't create OPENGL surface don't try this test
            else:
                self.assertTrue(screen_surf.get_flags() & pygame.OPENGL)
        finally:
            pygame.display.quit()

    ########################################################################

    def test_get_parent(self):
        """Ensure a surface's parent can be retrieved."""
        pygame.display.init()
        try:
            parent = pygame.Surface((16, 16))
            child = parent.subsurface((0, 0, 5, 5))

            self.assertIs(child.get_parent(), parent)

            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode()
                pygame.display.quit()
                surface.get_parent()
        finally:
            pygame.display.quit()

    ########################################################################

    def test_get_rect(self):
        """Ensure a surface's rect can be retrieved."""
        size = (16, 16)
        surf = pygame.Surface(size)
        rect = surf.get_rect()

        self.assertEqual(rect.size, size)

    ########################################################################

    def test_get_width__size_and_height(self):
        """Ensure a surface's size, width and height can be retrieved."""
        for w in range(0, 255, 32):
            for h in range(0, 127, 15):
                s = pygame.Surface((w, h))
                self.assertEqual(s.get_width(), w)
                self.assertEqual(s.get_height(), h)
                self.assertEqual(s.get_size(), (w, h))

    def test_get_view(self):
        """Ensure a buffer view of the surface's pixels can be retrieved."""
        # Check that BufferProxys are returned when array depth is supported,
        # ValueErrors returned otherwise.
        Error = ValueError
        s = pygame.Surface((5, 7), 0, 8)
        v2 = s.get_view("2")

        self.assertRaises(Error, s.get_view, "0")
        self.assertRaises(Error, s.get_view, "1")
        self.assertIsInstance(v2, BufferProxy)
        self.assertRaises(Error, s.get_view, "3")

        s = pygame.Surface((8, 7), 0, 8)
        length = s.get_bytesize() * s.get_width() * s.get_height()
        v0 = s.get_view("0")
        v1 = s.get_view("1")

        self.assertIsInstance(v0, BufferProxy)
        self.assertEqual(v0.length, length)
        self.assertIsInstance(v1, BufferProxy)
        self.assertEqual(v1.length, length)

        s = pygame.Surface((5, 7), 0, 16)
        v2 = s.get_view("2")

        self.assertRaises(Error, s.get_view, "0")
        self.assertRaises(Error, s.get_view, "1")
        self.assertIsInstance(v2, BufferProxy)
        self.assertRaises(Error, s.get_view, "3")

        s = pygame.Surface((8, 7), 0, 16)
        length = s.get_bytesize() * s.get_width() * s.get_height()
        v0 = s.get_view("0")
        v1 = s.get_view("1")

        self.assertIsInstance(v0, BufferProxy)
        self.assertEqual(v0.length, length)
        self.assertIsInstance(v1, BufferProxy)
        self.assertEqual(v1.length, length)

        s = pygame.Surface((5, 7), pygame.SRCALPHA, 16)
        v2 = s.get_view("2")

        self.assertIsInstance(v2, BufferProxy)
        self.assertRaises(Error, s.get_view, "3")

        s = pygame.Surface((5, 7), 0, 24)
        v2 = s.get_view("2")
        v3 = s.get_view("3")

        self.assertRaises(Error, s.get_view, "0")
        self.assertRaises(Error, s.get_view, "1")
        self.assertIsInstance(v2, BufferProxy)
        self.assertIsInstance(v3, BufferProxy)

        s = pygame.Surface((8, 7), 0, 24)
        length = s.get_bytesize() * s.get_width() * s.get_height()
        v0 = s.get_view("0")
        v1 = s.get_view("1")

        self.assertIsInstance(v0, BufferProxy)
        self.assertEqual(v0.length, length)
        self.assertIsInstance(v1, BufferProxy)
        self.assertEqual(v1.length, length)

        s = pygame.Surface((5, 7), 0, 32)
        length = s.get_bytesize() * s.get_width() * s.get_height()
        v0 = s.get_view("0")
        v1 = s.get_view("1")
        v2 = s.get_view("2")
        v3 = s.get_view("3")

        self.assertIsInstance(v0, BufferProxy)
        self.assertEqual(v0.length, length)
        self.assertIsInstance(v1, BufferProxy)
        self.assertEqual(v1.length, length)
        self.assertIsInstance(v2, BufferProxy)
        self.assertIsInstance(v3, BufferProxy)

        s2 = s.subsurface((0, 0, 4, 7))

        self.assertRaises(Error, s2.get_view, "0")
        self.assertRaises(Error, s2.get_view, "1")

        s2 = None
        s = pygame.Surface((5, 7), pygame.SRCALPHA, 32)

        for kind in ("2", "3", "a", "A", "r", "R", "g", "G", "b", "B"):
            self.assertIsInstance(s.get_view(kind), BufferProxy)

        # Check default argument value: '2'
        s = pygame.Surface((2, 4), 0, 32)
        v = s.get_view()
        if not IS_PYPY:
            ai = ArrayInterface(v)
            self.assertEqual(ai.nd, 2)

        # Check locking.
        s = pygame.Surface((2, 4), 0, 32)

        self.assertFalse(s.get_locked())

        v = s.get_view("2")

        self.assertFalse(s.get_locked())

        c = v.__array_interface__

        self.assertTrue(s.get_locked())

        c = None
        gc.collect()

        self.assertTrue(s.get_locked())

        v = None
        gc.collect()

        self.assertFalse(s.get_locked())

        # Check invalid view kind values.
        s = pygame.Surface((2, 4), pygame.SRCALPHA, 32)
        self.assertRaises(TypeError, s.get_view, "")
        self.assertRaises(TypeError, s.get_view, "9")
        self.assertRaises(TypeError, s.get_view, "RGBA")
        self.assertRaises(TypeError, s.get_view, 2)

        # Both unicode and bytes strings are allowed for kind.
        s = pygame.Surface((2, 4), 0, 32)
        s.get_view("2")
        s.get_view(b"2")

        # Garbage collection
        s = pygame.Surface((2, 4), 0, 32)
        weak_s = weakref.ref(s)
        v = s.get_view("3")
        weak_v = weakref.ref(v)
        gc.collect()
        self.assertTrue(weak_s() is s)
        self.assertTrue(weak_v() is v)
        del v
        gc.collect()
        self.assertTrue(weak_s() is s)
        self.assertTrue(weak_v() is None)
        del s
        gc.collect()
        self.assertTrue(weak_s() is None)

    def test_get_buffer(self):
        # Check that get_buffer works for all pixel sizes and for a subsurface.

        # Check for all pixel sizes
        for bitsize in [8, 16, 24, 32]:
            s = pygame.Surface((5, 7), 0, bitsize)
            length = s.get_pitch() * s.get_height()
            v = s.get_buffer()

            self.assertIsInstance(v, BufferProxy)
            self.assertEqual(v.length, length)
            self.assertEqual(repr(v), f"<BufferProxy({length})>")

        # Check for a subsurface (not contiguous)
        s = pygame.Surface((7, 10), 0, 32)
        s2 = s.subsurface((1, 2, 5, 7))
        length = s2.get_pitch() * s2.get_height()
        v = s2.get_buffer()

        self.assertIsInstance(v, BufferProxy)
        self.assertEqual(v.length, length)

        # Check locking.
        s = pygame.Surface((2, 4), 0, 32)
        v = s.get_buffer()
        self.assertTrue(s.get_locked())
        v = None
        gc.collect()
        self.assertFalse(s.get_locked())

    OLDBUF = hasattr(pygame.bufferproxy, "get_segcount")

    @unittest.skipIf(not OLDBUF, "old buffer not available")
    def test_get_buffer_oldbuf(self):
        from pygame.bufferproxy import get_segcount, get_write_buffer

        s = pygame.Surface((2, 4), pygame.SRCALPHA, 32)
        v = s.get_buffer()
        segcount, buflen = get_segcount(v)
        self.assertEqual(segcount, 1)
        self.assertEqual(buflen, s.get_pitch() * s.get_height())
        seglen, segaddr = get_write_buffer(v, 0)
        self.assertEqual(segaddr, s._pixels_address)
        self.assertEqual(seglen, buflen)

    @unittest.skipIf(not OLDBUF, "old buffer not available")
    def test_get_view_oldbuf(self):
        from pygame.bufferproxy import get_segcount, get_write_buffer

        s = pygame.Surface((2, 4), pygame.SRCALPHA, 32)
        v = s.get_view("1")
        segcount, buflen = get_segcount(v)
        self.assertEqual(segcount, 8)
        self.assertEqual(buflen, s.get_pitch() * s.get_height())
        seglen, segaddr = get_write_buffer(v, 7)
        self.assertEqual(segaddr, s._pixels_address + s.get_bytesize() * 7)
        self.assertEqual(seglen, s.get_bytesize())

    def test_set_colorkey(self):
        # __doc__ (as of 2008-06-25) for pygame.surface.Surface.set_colorkey:

        # Surface.set_colorkey(Color, flags=0): return None
        # Surface.set_colorkey(None): return None
        # Set the transparent colorkey

        s = pygame.Surface((16, 16), pygame.SRCALPHA, 32)

        colorkeys = ((20, 189, 20, 255), (128, 50, 50, 255), (23, 21, 255, 255))

        for colorkey in colorkeys:
            s.set_colorkey(colorkey)

            for t in range(4):
                s.set_colorkey(s.get_colorkey())

            self.assertEqual(s.get_colorkey(), colorkey)

    def test_set_masks(self):
        s = pygame.Surface((32, 32))
        r, g, b, a = s.get_masks()
        self.assertRaises(TypeError, s.set_masks, (b, g, r, a))

    def test_set_shifts(self):
        s = pygame.Surface((32, 32))
        r, g, b, a = s.get_shifts()
        self.assertRaises(TypeError, s.set_shifts, (b, g, r, a))

    def test_blit_keyword_args(self):
        color = (1, 2, 3, 255)
        s1 = pygame.Surface((4, 4), 0, 32)
        s2 = pygame.Surface((2, 2), 0, 32)
        s2.fill((1, 2, 3))
        s1.blit(special_flags=BLEND_ADD, source=s2, dest=(1, 1), area=s2.get_rect())
        self.assertEqual(s1.get_at((0, 0)), (0, 0, 0, 255))
        self.assertEqual(s1.get_at((1, 1)), color)

    def test_blit_big_rects(self):
        """SDL2 can have more than 16 bits for x, y, width, height."""
        big_surf = pygame.Surface((100, 68000), 0, 32)
        big_surf_color = (255, 0, 0)
        big_surf.fill(big_surf_color)

        background = pygame.Surface((500, 500), 0, 32)
        background_color = (0, 255, 0)
        background.fill(background_color)

        # copy parts of the big_surf using more than 16bit parts.
        background.blit(big_surf, (100, 100), area=(0, 16000, 100, 100))
        background.blit(big_surf, (200, 200), area=(0, 32000, 100, 100))
        background.blit(big_surf, (300, 300), area=(0, 66000, 100, 100))

        # check that all three areas are drawn.
        self.assertEqual(background.get_at((101, 101)), big_surf_color)
        self.assertEqual(background.get_at((201, 201)), big_surf_color)
        self.assertEqual(background.get_at((301, 301)), big_surf_color)

        # areas outside the 3 blitted areas not covered by those blits.
        self.assertEqual(background.get_at((400, 301)), background_color)
        self.assertEqual(background.get_at((400, 201)), background_color)
        self.assertEqual(background.get_at((100, 201)), background_color)
        self.assertEqual(background.get_at((99, 99)), background_color)
        self.assertEqual(background.get_at((450, 450)), background_color)


class TestSurfaceBlit(unittest.TestCase):
    """Tests basic blitting functionality and options."""

    # __doc__ (as of 2008-08-02) for pygame.surface.Surface.blit:

    # Surface.blit(source, dest, area=None, special_flags = 0): return Rect
    # draw one image onto another
    #
    # Draws a source Surface onto this Surface. The draw can be positioned
    # with the dest argument. Dest can either be pair of coordinates
    # representing the upper left corner of the source. A Rect can also be
    # passed as the destination and the topleft corner of the rectangle
    # will be used as the position for the blit. The size of the
    # destination rectangle does not effect the blit.
    #
    # An optional area rectangle can be passed as well. This represents a
    # smaller portion of the source Surface to draw.
    #
    # An optional special flags is for passing in new in 1.8.0: BLEND_ADD,
    # BLEND_SUB, BLEND_MULT, BLEND_MIN, BLEND_MAX new in 1.8.1:
    # BLEND_RGBA_ADD, BLEND_RGBA_SUB, BLEND_RGBA_MULT, BLEND_RGBA_MIN,
    # BLEND_RGBA_MAX BLEND_RGB_ADD, BLEND_RGB_SUB, BLEND_RGB_MULT,
    # BLEND_RGB_MIN, BLEND_RGB_MAX With other special blitting flags
    # perhaps added in the future.
    #
    # The return rectangle is the area of the affected pixels, excluding
    # any pixels outside the destination Surface, or outside the clipping
    # area.
    #
    # Pixel alphas will be ignored when blitting to an 8 bit Surface.
    # special_flags new in pygame 1.8.

    def setUp(self):
        """Resets starting surfaces."""
        self.src_surface = pygame.Surface((256, 256), 32)
        self.src_surface.fill(pygame.Color(255, 255, 255))
        self.dst_surface = pygame.Surface((64, 64), 32)
        self.dst_surface.fill(pygame.Color(0, 0, 0))

    def test_blit_overflow_coord(self):
        """Full coverage w/ overflow, specified with Coordinate"""
        result = self.dst_surface.blit(self.src_surface, (0, 0))
        self.assertIsInstance(result, pygame.Rect)
        self.assertEqual(result.size, (64, 64))
        for k in [(x, x) for x in range(64)]:
            self.assertEqual(self.dst_surface.get_at(k), (255, 255, 255))

    def test_blit_overflow_rect(self):
        """Full coverage w/ overflow, specified with a Rect"""
        result = self.dst_surface.blit(self.src_surface, pygame.Rect(-1, -1, 300, 300))
        self.assertIsInstance(result, pygame.Rect)
        self.assertEqual(result.size, (64, 64))
        for k in [(x, x) for x in range(64)]:
            self.assertEqual(self.dst_surface.get_at(k), (255, 255, 255))

    def test_blit_overflow_nonorigin(self):
        """Test Rectangle Dest, with overflow but with starting rect with top-left at (1,1)"""
        result = self.dst_surface.blit(self.src_surface, dest=pygame.Rect((1, 1, 1, 1)))
        self.assertIsInstance(result, pygame.Rect)
        self.assertEqual(result.size, (63, 63))
        self.assertEqual(self.dst_surface.get_at((0, 0)), (0, 0, 0))
        self.assertEqual(self.dst_surface.get_at((63, 0)), (0, 0, 0))
        self.assertEqual(self.dst_surface.get_at((0, 63)), (0, 0, 0))
        self.assertEqual(self.dst_surface.get_at((1, 1)), (255, 255, 255))
        self.assertEqual(self.dst_surface.get_at((63, 63)), (255, 255, 255))

    def test_blit_area_contraint(self):
        """Testing area constraint"""
        result = self.dst_surface.blit(
            self.src_surface,
            dest=pygame.Rect((1, 1, 1, 1)),
            area=pygame.Rect((2, 2, 2, 2)),
        )
        self.assertIsInstance(result, pygame.Rect)
        self.assertEqual(result.size, (2, 2))
        self.assertEqual(self.dst_surface.get_at((0, 0)), (0, 0, 0))  # Corners
        self.assertEqual(self.dst_surface.get_at((63, 0)), (0, 0, 0))
        self.assertEqual(self.dst_surface.get_at((0, 63)), (0, 0, 0))
        self.assertEqual(self.dst_surface.get_at((63, 63)), (0, 0, 0))
        self.assertEqual(
            self.dst_surface.get_at((1, 1)), (255, 255, 255)
        )  # Blitted Area
        self.assertEqual(self.dst_surface.get_at((2, 2)), (255, 255, 255))
        self.assertEqual(self.dst_surface.get_at((3, 3)), (0, 0, 0))
        # Should stop short of filling in (3,3)

    def test_blit_zero_overlap(self):
        """Testing zero-overlap condition."""
        result = self.dst_surface.blit(
            self.src_surface,
            dest=pygame.Rect((-256, -256, 1, 1)),
            area=pygame.Rect((2, 2, 256, 256)),
        )
        self.assertIsInstance(result, pygame.Rect)
        self.assertEqual(result.size, (0, 0))  # No blitting expected
        for k in [(x, x) for x in range(64)]:
            self.assertEqual(self.dst_surface.get_at(k), (0, 0, 0))  # Diagonal
        self.assertEqual(
            self.dst_surface.get_at((63, 0)), (0, 0, 0)
        )  # Remaining corners
        self.assertEqual(self.dst_surface.get_at((0, 63)), (0, 0, 0))

    def test_blit__SRCALPHA_opaque_source(self):
        src = pygame.Surface((256, 256), SRCALPHA, 32)
        dst = src.copy()

        for i, j in test_utils.rect_area_pts(src.get_rect()):
            dst.set_at((i, j), (i, 0, 0, j))
            src.set_at((i, j), (0, i, 0, 255))

        dst.blit(src, (0, 0))

        for pt in test_utils.rect_area_pts(src.get_rect()):
            self.assertEqual(dst.get_at(pt)[1], src.get_at(pt)[1])

    def test_blit__blit_to_self(self):
        """Test that blit operation works on self, alpha value is
        correct, and that no RGB distortion occurs."""
        test_surface = pygame.Surface((128, 128), SRCALPHA, 32)
        area = test_surface.get_rect()

        for pt, test_color in test_utils.gradient(area.width, area.height):
            test_surface.set_at(pt, test_color)

        reference_surface = test_surface.copy()

        test_surface.blit(test_surface, (0, 0))

        for x in range(area.width):
            for y in range(area.height):
                (r, g, b, a) = reference_color = reference_surface.get_at((x, y))
                expected_color = (r, g, b, (a + (a * ((256 - a) // 256))))
                self.assertEqual(reference_color, expected_color)

        self.assertEqual(reference_surface.get_rect(), test_surface.get_rect())

    def test_blit__SRCALPHA_to_SRCALPHA_non_zero(self):
        """Tests blitting a nonzero alpha surface to another nonzero alpha surface
        both straight alpha compositing method. Test is fuzzy (+/- 1/256) to account for
        different implementations in SDL1 and SDL2.
        """

        size = (32, 32)

        def check_color_diff(color1, color2):
            """Returns True if two colors are within (1, 1, 1, 1) of each other."""
            for val in color1 - color2:
                if abs(val) > 1:
                    return False
            return True

        def high_a_onto_low(high, low):
            """Tests straight alpha case. Source is low alpha, destination is high alpha"""
            high_alpha_surface = pygame.Surface(size, pygame.SRCALPHA, 32)
            low_alpha_surface = high_alpha_surface.copy()
            high_alpha_color = Color(
                (high, high, low, high)
            )  # Injecting some RGB variance.
            low_alpha_color = Color((high, low, low, low))
            high_alpha_surface.fill(high_alpha_color)
            low_alpha_surface.fill(low_alpha_color)

            high_alpha_surface.blit(low_alpha_surface, (0, 0))

            expected_color = low_alpha_color + Color(
                tuple(
                    ((x * (255 - low_alpha_color.a)) // 255) for x in high_alpha_color
                )
            )
            self.assertTrue(
                check_color_diff(high_alpha_surface.get_at((0, 0)), expected_color)
            )

        def low_a_onto_high(high, low):
            """Tests straight alpha case. Source is high alpha, destination is low alpha"""
            high_alpha_surface = pygame.Surface(size, pygame.SRCALPHA, 32)
            low_alpha_surface = high_alpha_surface.copy()
            high_alpha_color = Color(
                (high, high, low, high)
            )  # Injecting some RGB variance.
            low_alpha_color = Color((high, low, low, low))
            high_alpha_surface.fill(high_alpha_color)
            low_alpha_surface.fill(low_alpha_color)

            low_alpha_surface.blit(high_alpha_surface, (0, 0))

            expected_color = high_alpha_color + Color(
                tuple(
                    ((x * (255 - high_alpha_color.a)) // 255) for x in low_alpha_color
                )
            )
            self.assertTrue(
                check_color_diff(low_alpha_surface.get_at((0, 0)), expected_color)
            )

        for low_a in range(0, 128):
            for high_a in range(128, 256):
                high_a_onto_low(high_a, low_a)
                low_a_onto_high(high_a, low_a)

    def test_blit__SRCALPHA32_to_8(self):
        # Bug: fatal
        # SDL_DisplayConvert segfaults when video is uninitialized.
        target = pygame.Surface((11, 8), 0, 8)
        test_color = target.get_palette_at(2)
        source = pygame.Surface((1, 1), pygame.SRCALPHA, 32)
        source.set_at((0, 0), test_color)
        target.blit(source, (0, 0))


class GeneralSurfaceTests(unittest.TestCase):
    @unittest.skipIf(
        os.environ.get("SDL_VIDEODRIVER") == "dummy",
        'requires a non-"dummy" SDL_VIDEODRIVER',
    )
    def test_image_convert_bug_131(self):
        # bug #131: Unable to Surface.convert(32) some 1-bit images.
        # https://github.com/pygame/pygame/issues/131

        pygame.display.init()
        try:
            pygame.display.set_mode((640, 480))

            im = pygame.image.load(example_path(os.path.join("data", "city.png")))
            im2 = pygame.image.load(example_path(os.path.join("data", "brick.png")))

            self.assertEqual(im.get_palette(), ((0, 0, 0, 255), (255, 255, 255, 255)))
            self.assertEqual(im2.get_palette(), ((0, 0, 0, 255), (0, 0, 0, 255)))

            self.assertEqual(repr(im.convert(32)), "<Surface(24x24x32 SW)>")
            self.assertEqual(repr(im2.convert(32)), "<Surface(469x137x32 SW)>")

            # Ensure a palette format to palette format works.
            im3 = im.convert(8)
            self.assertEqual(repr(im3), "<Surface(24x24x8 SW)>")
            self.assertEqual(im3.get_palette(), im.get_palette())

        finally:
            pygame.display.quit()

    def test_convert_init(self):
        """Ensure initialization exceptions are raised
        for surf.convert()."""
        pygame.display.quit()
        surf = pygame.Surface((1, 1))

        self.assertRaisesRegex(pygame.error, "display initialized", surf.convert)

        pygame.display.init()
        try:
            if os.environ.get("SDL_VIDEODRIVER") != "dummy":
                try:
                    surf.convert(32)
                    surf.convert(pygame.Surface((1, 1)))
                except pygame.error:
                    self.fail("convert() should not raise an exception here.")

            self.assertRaisesRegex(pygame.error, "No video mode", surf.convert)

            pygame.display.set_mode((640, 480))
            try:
                surf.convert()
            except pygame.error:
                self.fail("convert() should not raise an exception here.")
        finally:
            pygame.display.quit()

    def test_convert_alpha_init(self):
        """Ensure initialization exceptions are raised
        for surf.convert_alpha()."""
        pygame.display.quit()
        surf = pygame.Surface((1, 1))

        self.assertRaisesRegex(pygame.error, "display initialized", surf.convert_alpha)

        pygame.display.init()
        try:
            self.assertRaisesRegex(pygame.error, "No video mode", surf.convert_alpha)

            pygame.display.set_mode((640, 480))
            try:
                surf.convert_alpha()
            except pygame.error:
                self.fail("convert_alpha() should not raise an exception here.")
        finally:
            pygame.display.quit()

    def test_convert_alpha_SRCALPHA(self):
        """Ensure that the surface returned by surf.convert_alpha()
        has alpha blending enabled"""
        pygame.display.init()
        try:
            pygame.display.set_mode((640, 480))

            s1 = pygame.Surface((100, 100), 0, 32)
            # s2=pygame.Surface((100,100), pygame.SRCALPHA, 32)
            s1_alpha = s1.convert_alpha()
            self.assertEqual(s1_alpha.get_flags() & SRCALPHA, SRCALPHA)
            self.assertEqual(s1_alpha.get_alpha(), 255)
        finally:
            pygame.display.quit()

    def test_src_alpha_issue_1289(self):
        """blit should be white."""
        surf1 = pygame.Surface((1, 1), pygame.SRCALPHA, 32)
        surf1.fill((255, 255, 255, 100))

        surf2 = pygame.Surface((1, 1), pygame.SRCALPHA, 32)
        self.assertEqual(surf2.get_at((0, 0)), (0, 0, 0, 0))
        surf2.blit(surf1, (0, 0))

        self.assertEqual(surf1.get_at((0, 0)), (255, 255, 255, 100))
        self.assertEqual(surf2.get_at((0, 0)), (255, 255, 255, 100))

    def test_src_alpha_compatible(self):
        """ "What pygame 1.9.x did". Is the alpha blitter as before?"""

        # The table below was generated with the SDL1 blit.
        # def print_table():
        #     nums = [0, 1, 65, 126, 127, 199, 254, 255]
        #     results = {}
        #     for dest_r, dest_b, dest_a in zip(nums, reversed(nums), reversed(nums)):
        #         for src_r, src_b, src_a in zip(nums, reversed(nums), nums):
        #             src_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
        #             src_surf.fill((src_r, 255, src_b, src_a))
        #             dest_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
        #             dest_surf.fill((dest_r, 255, dest_b, dest_a))
        #             dest_surf.blit(src_surf, (0, 0))
        #             key = ((dest_r, dest_b, dest_a), (src_r, src_b, src_a))
        #             results[key] = dest_surf.get_at((65, 33))
        #     print("(dest_r, dest_b, dest_a), (src_r, src_b, src_a): color")
        #     pprint(results)

        results_expected = {
            ((0, 255, 255), (0, 255, 0)): (0, 255, 255, 255),
            ((0, 255, 255), (1, 254, 1)): (0, 255, 255, 255),
            ((0, 255, 255), (65, 199, 65)): (16, 255, 241, 255),
            ((0, 255, 255), (126, 127, 126)): (62, 255, 192, 255),
            ((0, 255, 255), (127, 126, 127)): (63, 255, 191, 255),
            ((0, 255, 255), (199, 65, 199)): (155, 255, 107, 255),
            ((0, 255, 255), (254, 1, 254)): (253, 255, 2, 255),
            ((0, 255, 255), (255, 0, 255)): (255, 255, 0, 255),
            ((1, 254, 254), (0, 255, 0)): (1, 255, 254, 254),
            ((1, 254, 254), (1, 254, 1)): (1, 255, 254, 255),
            ((1, 254, 254), (65, 199, 65)): (17, 255, 240, 255),
            ((1, 254, 254), (126, 127, 126)): (63, 255, 191, 255),
            ((1, 254, 254), (127, 126, 127)): (64, 255, 190, 255),
            ((1, 254, 254), (199, 65, 199)): (155, 255, 107, 255),
            ((1, 254, 254), (254, 1, 254)): (253, 255, 2, 255),
            ((1, 254, 254), (255, 0, 255)): (255, 255, 0, 255),
            ((65, 199, 199), (0, 255, 0)): (65, 255, 199, 199),
            ((65, 199, 199), (1, 254, 1)): (64, 255, 200, 200),
            ((65, 199, 199), (65, 199, 65)): (65, 255, 199, 214),
            ((65, 199, 199), (126, 127, 126)): (95, 255, 164, 227),
            ((65, 199, 199), (127, 126, 127)): (96, 255, 163, 227),
            ((65, 199, 199), (199, 65, 199)): (169, 255, 95, 243),
            ((65, 199, 199), (254, 1, 254)): (253, 255, 2, 255),
            ((65, 199, 199), (255, 0, 255)): (255, 255, 0, 255),
            ((126, 127, 127), (0, 255, 0)): (126, 255, 127, 127),
            ((126, 127, 127), (1, 254, 1)): (125, 255, 128, 128),
            ((126, 127, 127), (65, 199, 65)): (110, 255, 146, 160),
            ((126, 127, 127), (126, 127, 126)): (126, 255, 127, 191),
            ((126, 127, 127), (127, 126, 127)): (126, 255, 126, 191),
            ((126, 127, 127), (199, 65, 199)): (183, 255, 79, 227),
            ((126, 127, 127), (254, 1, 254)): (253, 255, 1, 255),
            ((126, 127, 127), (255, 0, 255)): (255, 255, 0, 255),
            ((127, 126, 126), (0, 255, 0)): (127, 255, 126, 126),
            ((127, 126, 126), (1, 254, 1)): (126, 255, 127, 127),
            ((127, 126, 126), (65, 199, 65)): (111, 255, 145, 159),
            ((127, 126, 126), (126, 127, 126)): (127, 255, 126, 190),
            ((127, 126, 126), (127, 126, 127)): (127, 255, 126, 191),
            ((127, 126, 126), (199, 65, 199)): (183, 255, 78, 227),
            ((127, 126, 126), (254, 1, 254)): (254, 255, 1, 255),
            ((127, 126, 126), (255, 0, 255)): (255, 255, 0, 255),
            ((199, 65, 65), (0, 255, 0)): (199, 255, 65, 65),
            ((199, 65, 65), (1, 254, 1)): (198, 255, 66, 66),
            ((199, 65, 65), (65, 199, 65)): (165, 255, 99, 114),
            ((199, 65, 65), (126, 127, 126)): (163, 255, 96, 159),
            ((199, 65, 65), (127, 126, 127)): (163, 255, 95, 160),
            ((199, 65, 65), (199, 65, 199)): (199, 255, 65, 214),
            ((199, 65, 65), (254, 1, 254)): (254, 255, 1, 255),
            ((199, 65, 65), (255, 0, 255)): (255, 255, 0, 255),
            ((254, 1, 1), (0, 255, 0)): (254, 255, 1, 1),
            ((254, 1, 1), (1, 254, 1)): (253, 255, 2, 2),
            ((254, 1, 1), (65, 199, 65)): (206, 255, 52, 66),
            ((254, 1, 1), (126, 127, 126)): (191, 255, 63, 127),
            ((254, 1, 1), (127, 126, 127)): (191, 255, 63, 128),
            ((254, 1, 1), (199, 65, 199)): (212, 255, 51, 200),
            ((254, 1, 1), (254, 1, 254)): (254, 255, 1, 255),
            ((254, 1, 1), (255, 0, 255)): (255, 255, 0, 255),
            ((255, 0, 0), (0, 255, 0)): (0, 255, 255, 0),
            ((255, 0, 0), (1, 254, 1)): (1, 255, 254, 1),
            ((255, 0, 0), (65, 199, 65)): (65, 255, 199, 65),
            ((255, 0, 0), (126, 127, 126)): (126, 255, 127, 126),
            ((255, 0, 0), (127, 126, 127)): (127, 255, 126, 127),
            ((255, 0, 0), (199, 65, 199)): (199, 255, 65, 199),
            ((255, 0, 0), (254, 1, 254)): (254, 255, 1, 254),
            ((255, 0, 0), (255, 0, 255)): (255, 255, 0, 255),
        }

        # chosen because they contain edge cases.
        nums = [0, 1, 65, 126, 127, 199, 254, 255]
        results = {}
        for dst_r, dst_b, dst_a in zip(nums, reversed(nums), reversed(nums)):
            for src_r, src_b, src_a in zip(nums, reversed(nums), nums):
                with self.subTest(
                    src_r=src_r,
                    src_b=src_b,
                    src_a=src_a,
                    dest_r=dst_r,
                    dest_b=dst_b,
                    dest_a=dst_a,
                ):
                    src_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
                    src_surf.fill((src_r, 255, src_b, src_a))
                    dest_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
                    dest_surf.fill((dst_r, 255, dst_b, dst_a))

                    dest_surf.blit(src_surf, (0, 0))
                    key = ((dst_r, dst_b, dst_a), (src_r, src_b, src_a))
                    results[key] = dest_surf.get_at((65, 33))
                    self.assertEqual(results[key], results_expected[key])

        self.assertEqual(results, results_expected)

    def test_src_alpha_compatible_16bit(self):
        """ "What pygame 1.9.x did". Is the alpha blitter as before?"""

        # The table below was generated with the SDL1 blit.
        # def print_table():
        #     nums = [0, 1, 65, 126, 127, 199, 254, 255]
        #     results = {}
        #     for dest_r, dest_b, dest_a in zip(nums, reversed(nums), reversed(nums)):
        #         for src_r, src_b, src_a in zip(nums, reversed(nums), nums):
        #             src_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 16)
        #             src_surf.fill((src_r, 255, src_b, src_a))
        #             dest_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 16)
        #             dest_surf.fill((dest_r, 255, dest_b, dest_a))
        #             dest_surf.blit(src_surf, (0, 0))
        #             key = ((dest_r, dest_b, dest_a), (src_r, src_b, src_a))
        #             results[key] = dest_surf.get_at((65, 33))
        #     print("(dest_r, dest_b, dest_a), (src_r, src_b, src_a): color")
        #     pprint(results)

        results_expected = {
            ((0, 255, 255), (0, 255, 0)): (0, 255, 255, 255),
            ((0, 255, 255), (1, 254, 1)): (0, 255, 255, 255),
            ((0, 255, 255), (65, 199, 65)): (17, 255, 255, 255),
            ((0, 255, 255), (126, 127, 126)): (51, 255, 204, 255),
            ((0, 255, 255), (127, 126, 127)): (51, 255, 204, 255),
            ((0, 255, 255), (199, 65, 199)): (170, 255, 102, 255),
            ((0, 255, 255), (254, 1, 254)): (255, 255, 0, 255),
            ((0, 255, 255), (255, 0, 255)): (255, 255, 0, 255),
            ((1, 254, 254), (0, 255, 0)): (0, 255, 255, 255),
            ((1, 254, 254), (1, 254, 1)): (0, 255, 255, 255),
            ((1, 254, 254), (65, 199, 65)): (17, 255, 255, 255),
            ((1, 254, 254), (126, 127, 126)): (51, 255, 204, 255),
            ((1, 254, 254), (127, 126, 127)): (51, 255, 204, 255),
            ((1, 254, 254), (199, 65, 199)): (170, 255, 102, 255),
            ((1, 254, 254), (254, 1, 254)): (255, 255, 0, 255),
            ((1, 254, 254), (255, 0, 255)): (255, 255, 0, 255),
            ((65, 199, 199), (0, 255, 0)): (68, 255, 204, 204),
            ((65, 199, 199), (1, 254, 1)): (68, 255, 204, 204),
            ((65, 199, 199), (65, 199, 65)): (68, 255, 204, 221),
            ((65, 199, 199), (126, 127, 126)): (85, 255, 170, 238),
            ((65, 199, 199), (127, 126, 127)): (85, 255, 170, 238),
            ((65, 199, 199), (199, 65, 199)): (187, 255, 85, 255),
            ((65, 199, 199), (254, 1, 254)): (255, 255, 0, 255),
            ((65, 199, 199), (255, 0, 255)): (255, 255, 0, 255),
            ((126, 127, 127), (0, 255, 0)): (119, 255, 119, 119),
            ((126, 127, 127), (1, 254, 1)): (119, 255, 119, 119),
            ((126, 127, 127), (65, 199, 65)): (102, 255, 136, 153),
            ((126, 127, 127), (126, 127, 126)): (119, 255, 119, 187),
            ((126, 127, 127), (127, 126, 127)): (119, 255, 119, 187),
            ((126, 127, 127), (199, 65, 199)): (187, 255, 68, 238),
            ((126, 127, 127), (254, 1, 254)): (255, 255, 0, 255),
            ((126, 127, 127), (255, 0, 255)): (255, 255, 0, 255),
            ((127, 126, 126), (0, 255, 0)): (119, 255, 119, 119),
            ((127, 126, 126), (1, 254, 1)): (119, 255, 119, 119),
            ((127, 126, 126), (65, 199, 65)): (102, 255, 136, 153),
            ((127, 126, 126), (126, 127, 126)): (119, 255, 119, 187),
            ((127, 126, 126), (127, 126, 127)): (119, 255, 119, 187),
            ((127, 126, 126), (199, 65, 199)): (187, 255, 68, 238),
            ((127, 126, 126), (254, 1, 254)): (255, 255, 0, 255),
            ((127, 126, 126), (255, 0, 255)): (255, 255, 0, 255),
            ((199, 65, 65), (0, 255, 0)): (204, 255, 68, 68),
            ((199, 65, 65), (1, 254, 1)): (204, 255, 68, 68),
            ((199, 65, 65), (65, 199, 65)): (170, 255, 102, 119),
            ((199, 65, 65), (126, 127, 126)): (170, 255, 85, 153),
            ((199, 65, 65), (127, 126, 127)): (170, 255, 85, 153),
            ((199, 65, 65), (199, 65, 199)): (204, 255, 68, 221),
            ((199, 65, 65), (254, 1, 254)): (255, 255, 0, 255),
            ((199, 65, 65), (255, 0, 255)): (255, 255, 0, 255),
            ((254, 1, 1), (0, 255, 0)): (0, 255, 255, 0),
            ((254, 1, 1), (1, 254, 1)): (0, 255, 255, 0),
            ((254, 1, 1), (65, 199, 65)): (68, 255, 204, 68),
            ((254, 1, 1), (126, 127, 126)): (119, 255, 119, 119),
            ((254, 1, 1), (127, 126, 127)): (119, 255, 119, 119),
            ((254, 1, 1), (199, 65, 199)): (204, 255, 68, 204),
            ((254, 1, 1), (254, 1, 254)): (255, 255, 0, 255),
            ((254, 1, 1), (255, 0, 255)): (255, 255, 0, 255),
            ((255, 0, 0), (0, 255, 0)): (0, 255, 255, 0),
            ((255, 0, 0), (1, 254, 1)): (0, 255, 255, 0),
            ((255, 0, 0), (65, 199, 65)): (68, 255, 204, 68),
            ((255, 0, 0), (126, 127, 126)): (119, 255, 119, 119),
            ((255, 0, 0), (127, 126, 127)): (119, 255, 119, 119),
            ((255, 0, 0), (199, 65, 199)): (204, 255, 68, 204),
            ((255, 0, 0), (254, 1, 254)): (255, 255, 0, 255),
            ((255, 0, 0), (255, 0, 255)): (255, 255, 0, 255),
        }

        # chosen because they contain edge cases.
        nums = [0, 1, 65, 126, 127, 199, 254, 255]
        results = {}
        for dst_r, dst_b, dst_a in zip(nums, reversed(nums), reversed(nums)):
            for src_r, src_b, src_a in zip(nums, reversed(nums), nums):
                with self.subTest(
                    src_r=src_r,
                    src_b=src_b,
                    src_a=src_a,
                    dest_r=dst_r,
                    dest_b=dst_b,
                    dest_a=dst_a,
                ):
                    src_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 16)
                    src_surf.fill((src_r, 255, src_b, src_a))
                    dest_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 16)
                    dest_surf.fill((dst_r, 255, dst_b, dst_a))

                    dest_surf.blit(src_surf, (0, 0))
                    key = ((dst_r, dst_b, dst_a), (src_r, src_b, src_a))
                    results[key] = dest_surf.get_at((65, 33))
                    self.assertEqual(results[key], results_expected[key])

        self.assertEqual(results, results_expected)

    def test_sdl1_mimic_blitter_with_set_alpha(self):
        """does the SDL 1 style blitter in pygame 2 work with set_alpha(),
        this feature only exists in pygame 2/SDL2 SDL1 did not support
        combining surface and pixel alpha"""

        results_expected = {
            ((0, 255, 255), (0, 255, 0)): (0, 255, 255, 255),
            ((0, 255, 255), (1, 254, 1)): (0, 255, 255, 255),
            ((0, 255, 255), (65, 199, 65)): (16, 255, 241, 255),
            ((0, 255, 255), (126, 127, 126)): (62, 255, 192, 255),
            ((0, 255, 255), (127, 126, 127)): (63, 255, 191, 255),
            ((0, 255, 255), (199, 65, 199)): (155, 255, 107, 255),
            ((0, 255, 255), (254, 1, 254)): (253, 255, 2, 255),
            ((0, 255, 255), (255, 0, 255)): (255, 255, 0, 255),
            ((1, 254, 254), (0, 255, 0)): (1, 255, 254, 254),
            ((1, 254, 254), (1, 254, 1)): (1, 255, 254, 255),
            ((1, 254, 254), (65, 199, 65)): (17, 255, 240, 255),
            ((1, 254, 254), (126, 127, 126)): (63, 255, 191, 255),
            ((1, 254, 254), (127, 126, 127)): (64, 255, 190, 255),
            ((1, 254, 254), (199, 65, 199)): (155, 255, 107, 255),
            ((1, 254, 254), (254, 1, 254)): (253, 255, 2, 255),
            ((1, 254, 254), (255, 0, 255)): (255, 255, 0, 255),
            ((65, 199, 199), (0, 255, 0)): (65, 255, 199, 199),
            ((65, 199, 199), (1, 254, 1)): (64, 255, 200, 200),
            ((65, 199, 199), (65, 199, 65)): (65, 255, 199, 214),
            ((65, 199, 199), (126, 127, 126)): (95, 255, 164, 227),
            ((65, 199, 199), (127, 126, 127)): (96, 255, 163, 227),
            ((65, 199, 199), (199, 65, 199)): (169, 255, 95, 243),
            ((65, 199, 199), (254, 1, 254)): (253, 255, 2, 255),
            ((65, 199, 199), (255, 0, 255)): (255, 255, 0, 255),
            ((126, 127, 127), (0, 255, 0)): (126, 255, 127, 127),
            ((126, 127, 127), (1, 254, 1)): (125, 255, 128, 128),
            ((126, 127, 127), (65, 199, 65)): (110, 255, 146, 160),
            ((126, 127, 127), (126, 127, 126)): (126, 255, 127, 191),
            ((126, 127, 127), (127, 126, 127)): (126, 255, 126, 191),
            ((126, 127, 127), (199, 65, 199)): (183, 255, 79, 227),
            ((126, 127, 127), (254, 1, 254)): (253, 255, 1, 255),
            ((126, 127, 127), (255, 0, 255)): (255, 255, 0, 255),
            ((127, 126, 126), (0, 255, 0)): (127, 255, 126, 126),
            ((127, 126, 126), (1, 254, 1)): (126, 255, 127, 127),
            ((127, 126, 126), (65, 199, 65)): (111, 255, 145, 159),
            ((127, 126, 126), (126, 127, 126)): (127, 255, 126, 190),
            ((127, 126, 126), (127, 126, 127)): (127, 255, 126, 191),
            ((127, 126, 126), (199, 65, 199)): (183, 255, 78, 227),
            ((127, 126, 126), (254, 1, 254)): (254, 255, 1, 255),
            ((127, 126, 126), (255, 0, 255)): (255, 255, 0, 255),
            ((199, 65, 65), (0, 255, 0)): (199, 255, 65, 65),
            ((199, 65, 65), (1, 254, 1)): (198, 255, 66, 66),
            ((199, 65, 65), (65, 199, 65)): (165, 255, 99, 114),
            ((199, 65, 65), (126, 127, 126)): (163, 255, 96, 159),
            ((199, 65, 65), (127, 126, 127)): (163, 255, 95, 160),
            ((199, 65, 65), (199, 65, 199)): (199, 255, 65, 214),
            ((199, 65, 65), (254, 1, 254)): (254, 255, 1, 255),
            ((199, 65, 65), (255, 0, 255)): (255, 255, 0, 255),
            ((254, 1, 1), (0, 255, 0)): (254, 255, 1, 1),
            ((254, 1, 1), (1, 254, 1)): (253, 255, 2, 2),
            ((254, 1, 1), (65, 199, 65)): (206, 255, 52, 66),
            ((254, 1, 1), (126, 127, 126)): (191, 255, 63, 127),
            ((254, 1, 1), (127, 126, 127)): (191, 255, 63, 128),
            ((254, 1, 1), (199, 65, 199)): (212, 255, 51, 200),
            ((254, 1, 1), (254, 1, 254)): (254, 255, 1, 255),
            ((254, 1, 1), (255, 0, 255)): (255, 255, 0, 255),
            ((255, 0, 0), (0, 255, 0)): (0, 255, 255, 0),
            ((255, 0, 0), (1, 254, 1)): (1, 255, 254, 1),
            ((255, 0, 0), (65, 199, 65)): (65, 255, 199, 65),
            ((255, 0, 0), (126, 127, 126)): (126, 255, 127, 126),
            ((255, 0, 0), (127, 126, 127)): (127, 255, 126, 127),
            ((255, 0, 0), (199, 65, 199)): (199, 255, 65, 199),
            ((255, 0, 0), (254, 1, 254)): (254, 255, 1, 254),
            ((255, 0, 0), (255, 0, 255)): (255, 255, 0, 255),
        }

        # chosen because they contain edge cases.
        nums = [0, 1, 65, 126, 127, 199, 254, 255]
        results = {}
        for dst_r, dst_b, dst_a in zip(nums, reversed(nums), reversed(nums)):
            for src_r, src_b, src_a in zip(nums, reversed(nums), nums):
                with self.subTest(
                    src_r=src_r,
                    src_b=src_b,
                    src_a=src_a,
                    dest_r=dst_r,
                    dest_b=dst_b,
                    dest_a=dst_a,
                ):
                    src_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
                    src_surf.fill((src_r, 255, src_b, 255))
                    src_surf.set_alpha(src_a)
                    dest_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
                    dest_surf.fill((dst_r, 255, dst_b, dst_a))

                    dest_surf.blit(src_surf, (0, 0))
                    key = ((dst_r, dst_b, dst_a), (src_r, src_b, src_a))
                    results[key] = dest_surf.get_at((65, 33))
                    self.assertEqual(results[key], results_expected[key])

        self.assertEqual(results, results_expected)

    @unittest.skipIf(
        "arm" in platform.machine() or "aarch64" in platform.machine(),
        "sdl2 blitter produces different results on arm",
    )
    def test_src_alpha_sdl2_blitter(self):
        """Checking that the BLEND_ALPHA_SDL2 flag works - this feature
        only exists when using SDL2"""

        results_expected = {
            ((0, 255, 255), (0, 255, 0)): (0, 255, 255, 255),
            ((0, 255, 255), (1, 254, 1)): (0, 253, 253, 253),
            ((0, 255, 255), (65, 199, 65)): (16, 253, 239, 253),
            ((0, 255, 255), (126, 127, 126)): (62, 253, 190, 253),
            ((0, 255, 255), (127, 126, 127)): (63, 253, 189, 253),
            ((0, 255, 255), (199, 65, 199)): (154, 253, 105, 253),
            ((0, 255, 255), (254, 1, 254)): (252, 253, 0, 253),
            ((0, 255, 255), (255, 0, 255)): (255, 255, 0, 255),
            ((1, 254, 254), (0, 255, 0)): (1, 255, 254, 254),
            ((1, 254, 254), (1, 254, 1)): (0, 253, 252, 252),
            ((1, 254, 254), (65, 199, 65)): (16, 253, 238, 252),
            ((1, 254, 254), (126, 127, 126)): (62, 253, 189, 252),
            ((1, 254, 254), (127, 126, 127)): (63, 253, 189, 253),
            ((1, 254, 254), (199, 65, 199)): (154, 253, 105, 253),
            ((1, 254, 254), (254, 1, 254)): (252, 253, 0, 253),
            ((1, 254, 254), (255, 0, 255)): (255, 255, 0, 255),
            ((65, 199, 199), (0, 255, 0)): (65, 255, 199, 199),
            ((65, 199, 199), (1, 254, 1)): (64, 253, 197, 197),
            ((65, 199, 199), (65, 199, 65)): (64, 253, 197, 211),
            ((65, 199, 199), (126, 127, 126)): (94, 253, 162, 225),
            ((65, 199, 199), (127, 126, 127)): (95, 253, 161, 225),
            ((65, 199, 199), (199, 65, 199)): (168, 253, 93, 241),
            ((65, 199, 199), (254, 1, 254)): (252, 253, 0, 253),
            ((65, 199, 199), (255, 0, 255)): (255, 255, 0, 255),
            ((126, 127, 127), (0, 255, 0)): (126, 255, 127, 127),
            ((126, 127, 127), (1, 254, 1)): (125, 253, 126, 126),
            ((126, 127, 127), (65, 199, 65)): (109, 253, 144, 158),
            ((126, 127, 127), (126, 127, 126)): (125, 253, 125, 188),
            ((126, 127, 127), (127, 126, 127)): (126, 253, 125, 189),
            ((126, 127, 127), (199, 65, 199)): (181, 253, 77, 225),
            ((126, 127, 127), (254, 1, 254)): (252, 253, 0, 253),
            ((126, 127, 127), (255, 0, 255)): (255, 255, 0, 255),
            ((127, 126, 126), (0, 255, 0)): (127, 255, 126, 126),
            ((127, 126, 126), (1, 254, 1)): (126, 253, 125, 125),
            ((127, 126, 126), (65, 199, 65)): (110, 253, 143, 157),
            ((127, 126, 126), (126, 127, 126)): (125, 253, 125, 188),
            ((127, 126, 126), (127, 126, 127)): (126, 253, 125, 189),
            ((127, 126, 126), (199, 65, 199)): (181, 253, 77, 225),
            ((127, 126, 126), (254, 1, 254)): (252, 253, 0, 253),
            ((127, 126, 126), (255, 0, 255)): (255, 255, 0, 255),
            ((199, 65, 65), (0, 255, 0)): (199, 255, 65, 65),
            ((199, 65, 65), (1, 254, 1)): (197, 253, 64, 64),
            ((199, 65, 65), (65, 199, 65)): (163, 253, 98, 112),
            ((199, 65, 65), (126, 127, 126)): (162, 253, 94, 157),
            ((199, 65, 65), (127, 126, 127)): (162, 253, 94, 158),
            ((199, 65, 65), (199, 65, 199)): (197, 253, 64, 212),
            ((199, 65, 65), (254, 1, 254)): (252, 253, 0, 253),
            ((199, 65, 65), (255, 0, 255)): (255, 255, 0, 255),
            ((254, 1, 1), (0, 255, 0)): (254, 255, 1, 1),
            ((254, 1, 1), (1, 254, 1)): (252, 253, 0, 0),
            ((254, 1, 1), (65, 199, 65)): (204, 253, 50, 64),
            ((254, 1, 1), (126, 127, 126)): (189, 253, 62, 125),
            ((254, 1, 1), (127, 126, 127)): (190, 253, 62, 126),
            ((254, 1, 1), (199, 65, 199)): (209, 253, 50, 198),
            ((254, 1, 1), (254, 1, 254)): (252, 253, 0, 253),
            ((254, 1, 1), (255, 0, 255)): (255, 255, 0, 255),
            ((255, 0, 0), (0, 255, 0)): (255, 255, 0, 0),
            ((255, 0, 0), (1, 254, 1)): (253, 253, 0, 0),
            ((255, 0, 0), (65, 199, 65)): (205, 253, 50, 64),
            ((255, 0, 0), (126, 127, 126)): (190, 253, 62, 125),
            ((255, 0, 0), (127, 126, 127)): (190, 253, 62, 126),
            ((255, 0, 0), (199, 65, 199)): (209, 253, 50, 198),
            ((255, 0, 0), (254, 1, 254)): (252, 253, 0, 253),
            ((255, 0, 0), (255, 0, 255)): (255, 255, 0, 255),
        }

        # chosen because they contain edge cases.
        nums = [0, 1, 65, 126, 127, 199, 254, 255]
        results = {}
        for dst_r, dst_b, dst_a in zip(nums, reversed(nums), reversed(nums)):
            for src_r, src_b, src_a in zip(nums, reversed(nums), nums):
                with self.subTest(
                    src_r=src_r,
                    src_b=src_b,
                    src_a=src_a,
                    dest_r=dst_r,
                    dest_b=dst_b,
                    dest_a=dst_a,
                ):
                    src_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
                    src_surf.fill((src_r, 255, src_b, src_a))
                    dest_surf = pygame.Surface((66, 66), pygame.SRCALPHA, 32)
                    dest_surf.fill((dst_r, 255, dst_b, dst_a))

                    dest_surf.blit(
                        src_surf, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2
                    )
                    key = ((dst_r, dst_b, dst_a), (src_r, src_b, src_a))
                    results[key] = tuple(dest_surf.get_at((65, 33)))
                    for i in range(4):
                        self.assertAlmostEqual(
                            results[key][i], results_expected[key][i], delta=4
                        )

        # print("(dest_r, dest_b, dest_a), (src_r, src_b, src_a): color")
        # pprint(results)

    def test_opaque_destination_blit_with_set_alpha(self):
        # no set_alpha()
        src_surf = pygame.Surface((32, 32), pygame.SRCALPHA, 32)
        src_surf.fill((255, 255, 255, 200))
        dest_surf = pygame.Surface((32, 32))
        dest_surf.fill((100, 100, 100))

        dest_surf.blit(src_surf, (0, 0))

        no_surf_alpha_col = dest_surf.get_at((0, 0))

        dest_surf.fill((100, 100, 100))
        dest_surf.set_alpha(200)
        dest_surf.blit(src_surf, (0, 0))

        surf_alpha_col = dest_surf.get_at((0, 0))

        self.assertEqual(no_surf_alpha_col, surf_alpha_col)

    def todo_test_convert(self):
        self.fail()

    # Below should not use a display Surface, but create one and check it is converted
    # to the depth of the display surface.

    # def test_convert(self):
    #     """Ensure to creates a new copy of the Surface with the pixel format changed"""
    #     width = 23
    #     height = 17
    #     size = (width, height)
    #     flags = 0
    #     depth = 32
    #     pygame.display.init()

    #     try:
    #         convert_surface = pygame.display.set_mode(size)
    #         surface = pygame.surface.Surface.convert(convert_surface)
    #         self.assertIsNot(surface, convert_surface)
    #         self.assertNotEqual(surface.get_size(), size)

    #         depth_surface = pygame.display.set_mode(size, flags, depth)
    #         surface2 = pygame.surface.Surface.convert(depth_surface)
    #         self.assertIsNot(surface2, depth_surface)
    #         self.assertEqual(surface2.get_size(), size)
    #     finally:
    #         pygame.display.quit()

    def test_convert__pixel_format_as_surface_subclass(self):
        """Ensure convert accepts a Surface subclass argument."""
        expected_size = (23, 17)
        convert_surface = SurfaceSubclass(expected_size, 0, 32)
        depth_surface = SurfaceSubclass((31, 61), 0, 32)

        pygame.display.init()
        try:
            surface = convert_surface.convert(depth_surface)

            self.assertIsNot(surface, depth_surface)
            self.assertIsNot(surface, convert_surface)
            self.assertIsInstance(surface, pygame.Surface)
            self.assertIsInstance(surface, SurfaceSubclass)
            self.assertEqual(surface.get_size(), expected_size)
        finally:
            pygame.display.quit()

    def test_convert_alpha(self):
        """Ensure the surface returned by surf.convert_alpha
        has alpha values added"""
        pygame.display.init()
        try:
            pygame.display.set_mode((640, 480))

            s1 = pygame.Surface((100, 100), 0, 32)
            s1_alpha = pygame.Surface.convert_alpha(s1)

            s2 = pygame.Surface((100, 100), 0, 32)
            s2_alpha = s2.convert_alpha()

            s3 = pygame.Surface((100, 100), 0, 8)
            s3_alpha = s3.convert_alpha()

            s4 = pygame.Surface((100, 100), 0, 12)
            s4_alpha = s4.convert_alpha()

            s5 = pygame.Surface((100, 100), 0, 15)
            s5_alpha = s5.convert_alpha()

            s6 = pygame.Surface((100, 100), 0, 16)
            s6_alpha = s6.convert_alpha()

            s7 = pygame.Surface((100, 100), 0, 24)
            s7_alpha = s7.convert_alpha()

            self.assertEqual(s1_alpha.get_alpha(), 255)
            self.assertEqual(s2_alpha.get_alpha(), 255)
            self.assertEqual(s3_alpha.get_alpha(), 255)
            self.assertEqual(s4_alpha.get_alpha(), 255)
            self.assertEqual(s5_alpha.get_alpha(), 255)
            self.assertEqual(s6_alpha.get_alpha(), 255)
            self.assertEqual(s7_alpha.get_alpha(), 255)

            self.assertEqual(s1_alpha.get_bitsize(), 32)
            self.assertEqual(s2_alpha.get_bitsize(), 32)
            self.assertEqual(s3_alpha.get_bitsize(), 32)
            self.assertEqual(s4_alpha.get_bitsize(), 32)
            self.assertEqual(s5_alpha.get_bitsize(), 32)
            self.assertEqual(s6_alpha.get_bitsize(), 32)
            self.assertEqual(s6_alpha.get_bitsize(), 32)

            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode()
                pygame.display.quit()
                surface.convert_alpha()

        finally:
            pygame.display.quit()

    def test_convert_alpha__pixel_format_as_surface_subclass(self):
        """Ensure convert_alpha accepts a Surface subclass argument."""
        expected_size = (23, 17)
        convert_surface = SurfaceSubclass(expected_size, SRCALPHA, 32)
        depth_surface = SurfaceSubclass((31, 57), SRCALPHA, 32)

        pygame.display.init()
        try:
            pygame.display.set_mode((60, 60))

            # This is accepted as an argument, but its values are ignored.
            # See issue #599.
            surface = convert_surface.convert_alpha(depth_surface)

            self.assertIsNot(surface, depth_surface)
            self.assertIsNot(surface, convert_surface)
            self.assertIsInstance(surface, pygame.Surface)
            self.assertIsInstance(surface, SurfaceSubclass)
            self.assertEqual(surface.get_size(), expected_size)
        finally:
            pygame.display.quit()

    def test_get_abs_offset(self):
        pygame.display.init()
        try:
            parent = pygame.Surface((64, 64), SRCALPHA, 32)

            # Stack bunch of subsurfaces
            sub_level_1 = parent.subsurface((2, 2), (34, 37))
            sub_level_2 = sub_level_1.subsurface((0, 0), (30, 29))
            sub_level_3 = sub_level_2.subsurface((3, 7), (20, 21))
            sub_level_4 = sub_level_3.subsurface((6, 1), (14, 14))
            sub_level_5 = sub_level_4.subsurface((5, 6), (3, 4))

            # Parent is always (0, 0)
            self.assertEqual(parent.get_abs_offset(), (0, 0))
            # Total offset: (0+2, 0+2) = (2, 2)
            self.assertEqual(sub_level_1.get_abs_offset(), (2, 2))
            # Total offset: (0+2+0, 0+2+0) = (2, 2)
            self.assertEqual(sub_level_2.get_abs_offset(), (2, 2))
            # Total offset: (0+2+0+3, 0+2+0+7) = (5, 9)
            self.assertEqual(sub_level_3.get_abs_offset(), (5, 9))
            # Total offset: (0+2+0+3+6, 0+2+0+7+1) = (11, 10)
            self.assertEqual(sub_level_4.get_abs_offset(), (11, 10))
            # Total offset: (0+2+0+3+6+5, 0+2+0+7+1+6) = (16, 16)
            self.assertEqual(sub_level_5.get_abs_offset(), (16, 16))

            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode()
                pygame.display.quit()
                surface.get_abs_offset()
        finally:
            pygame.display.quit()

    def test_get_abs_parent(self):
        pygame.display.init()
        try:
            parent = pygame.Surface((32, 32), SRCALPHA, 32)

            # Stack bunch of subsurfaces
            sub_level_1 = parent.subsurface((1, 1), (15, 15))
            sub_level_2 = sub_level_1.subsurface((1, 1), (12, 12))
            sub_level_3 = sub_level_2.subsurface((1, 1), (9, 9))
            sub_level_4 = sub_level_3.subsurface((1, 1), (8, 8))
            sub_level_5 = sub_level_4.subsurface((2, 2), (3, 4))
            sub_level_6 = sub_level_5.subsurface((0, 0), (2, 1))

            # Can't have subsurfaces bigger than parents
            self.assertRaises(ValueError, parent.subsurface, (5, 5), (100, 100))
            self.assertRaises(ValueError, sub_level_3.subsurface, (0, 0), (11, 5))
            self.assertRaises(ValueError, sub_level_6.subsurface, (0, 0), (5, 5))

            # Calling get_abs_parent on parent should return itself
            self.assertEqual(parent.get_abs_parent(), parent)

            # On subclass "depth" of 1, get_abs_parent and get_parent should return the same
            self.assertEqual(sub_level_1.get_abs_parent(), sub_level_1.get_parent())
            self.assertEqual(sub_level_2.get_abs_parent(), parent)
            self.assertEqual(sub_level_3.get_abs_parent(), parent)
            self.assertEqual(sub_level_4.get_abs_parent(), parent)
            self.assertEqual(sub_level_5.get_abs_parent(), parent)
            self.assertEqual(
                sub_level_6.get_abs_parent(), sub_level_6.get_parent().get_abs_parent()
            )

            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode()
                pygame.display.quit()
                surface.get_abs_parent()
        finally:
            pygame.display.quit()

    def test_get_at(self):
        surf = pygame.Surface((2, 2), 0, 24)
        c00 = pygame.Color(1, 2, 3)
        c01 = pygame.Color(5, 10, 15)
        c10 = pygame.Color(100, 50, 0)
        c11 = pygame.Color(4, 5, 6)
        surf.set_at((0, 0), c00)
        surf.set_at((0, 1), c01)
        surf.set_at((1, 0), c10)
        surf.set_at((1, 1), c11)
        c = surf.get_at((0, 0))
        self.assertIsInstance(c, pygame.Color)
        self.assertEqual(c, c00)
        self.assertEqual(surf.get_at((0, 1)), c01)
        self.assertEqual(surf.get_at((1, 0)), c10)
        self.assertEqual(surf.get_at((1, 1)), c11)
        for p in [(-1, 0), (0, -1), (2, 0), (0, 2)]:
            self.assertRaises(IndexError, surf.get_at, p)

    def test_get_at_mapped(self):
        color = pygame.Color(10, 20, 30)
        for bitsize in [8, 16, 24, 32]:
            surf = pygame.Surface((2, 2), 0, bitsize)
            surf.fill(color)
            pixel = surf.get_at_mapped((0, 0))
            self.assertEqual(
                pixel,
                surf.map_rgb(color),
                "%i != %i, bitsize: %i" % (pixel, surf.map_rgb(color), bitsize),
            )

    def test_get_bitsize(self):
        pygame.display.init()
        try:
            expected_size = (11, 21)

            # Check that get_bitsize returns passed depth
            expected_depth = 32
            surface = pygame.Surface(expected_size, pygame.SRCALPHA, expected_depth)
            self.assertEqual(surface.get_size(), expected_size)
            self.assertEqual(surface.get_bitsize(), expected_depth)

            expected_depth = 16
            surface = pygame.Surface(expected_size, pygame.SRCALPHA, expected_depth)
            self.assertEqual(surface.get_size(), expected_size)
            self.assertEqual(surface.get_bitsize(), expected_depth)

            expected_depth = 15
            surface = pygame.Surface(expected_size, 0, expected_depth)
            self.assertEqual(surface.get_size(), expected_size)
            self.assertEqual(surface.get_bitsize(), expected_depth)
            # Check for invalid depths
            expected_depth = -1
            self.assertRaises(
                ValueError, pygame.Surface, expected_size, 0, expected_depth
            )
            expected_depth = 11
            self.assertRaises(
                ValueError, pygame.Surface, expected_size, 0, expected_depth
            )
            expected_depth = 1024
            self.assertRaises(
                ValueError, pygame.Surface, expected_size, 0, expected_depth
            )

            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode()
                pygame.display.quit()
                surface.get_bitsize()
        finally:
            pygame.display.quit()

    def test_get_clip(self):
        s = pygame.Surface((800, 600))
        rectangle = s.get_clip()
        self.assertEqual(rectangle, (0, 0, 800, 600))

    def test_get_colorkey(self):
        pygame.display.init()
        try:
            # if set_colorkey is not used
            s = pygame.Surface((800, 600), 0, 32)
            self.assertIsNone(s.get_colorkey())

            # if set_colorkey is used
            s.set_colorkey(None)
            self.assertIsNone(s.get_colorkey())

            # setting up remainder of tests...
            r, g, b, a = 20, 40, 60, 12
            colorkey = pygame.Color(r, g, b)
            s.set_colorkey(colorkey)

            # test for ideal case
            self.assertEqual(s.get_colorkey(), (r, g, b, 255))

            # test for if the color_key is set using pygame.RLEACCEL
            s.set_colorkey(colorkey, pygame.RLEACCEL)
            self.assertEqual(s.get_colorkey(), (r, g, b, 255))

            # test for if the color key is not what's expected
            s.set_colorkey(pygame.Color(r + 1, g + 1, b + 1))
            self.assertNotEqual(s.get_colorkey(), (r, g, b, 255))

            s.set_colorkey(pygame.Color(r, g, b, a))
            # regardless of whether alpha is not 255
            # colorkey returned from surface is always 255
            self.assertEqual(s.get_colorkey(), (r, g, b, 255))
        finally:
            # test for using method after display.quit() is called...
            s = pygame.display.set_mode((200, 200), 0, 32)
            pygame.display.quit()
            with self.assertRaises(pygame.error):
                s.get_colorkey()

    def test_get_height(self):
        sizes = ((1, 1), (119, 10), (10, 119), (1, 1000), (1000, 1), (1000, 1000))
        for width, height in sizes:
            surf = pygame.Surface((width, height))
            found_height = surf.get_height()
            self.assertEqual(height, found_height)

    def test_get_locked(self):
        def blit_locked_test(surface):
            newSurf = pygame.Surface((10, 10))
            try:
                newSurf.blit(surface, (0, 0))
            except pygame.error:
                return True
            else:
                return False

        surf = pygame.Surface((100, 100))

        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Unlocked
        # Surface should lock
        surf.lock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Locked
        # Surface should unlock
        surf.unlock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Unlocked

        # Check multiple locks
        surf = pygame.Surface((100, 100))
        surf.lock()
        surf.lock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Locked
        surf.unlock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Locked
        surf.unlock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Unlocked

        # Check many locks
        surf = pygame.Surface((100, 100))
        for i in range(1000):
            surf.lock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Locked
        for i in range(1000):
            surf.unlock()
        self.assertFalse(surf.get_locked())  # Unlocked

        # Unlocking an unlocked surface
        surf = pygame.Surface((100, 100))
        surf.unlock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Unlocked
        surf.unlock()
        self.assertIs(surf.get_locked(), blit_locked_test(surf))  # Unlocked

    def test_get_locks(self):
        # __doc__ (as of 2008-08-02) for pygame.surface.Surface.get_locks:

        # Surface.get_locks(): return tuple
        # Gets the locks for the Surface
        #
        # Returns the currently existing locks for the Surface.

        # test on a surface that is not initially locked
        surface = pygame.Surface((100, 100))
        self.assertEqual(surface.get_locks(), ())

        # test on the same surface after it has been locked
        surface.lock()
        self.assertEqual(surface.get_locks(), (surface,))

        # test on the same surface after it has been unlocked
        surface.unlock()
        self.assertEqual(surface.get_locks(), ())

        # test with PixelArray initialization: locks surface
        pxarray = pygame.PixelArray(surface)
        self.assertNotEqual(surface.get_locks(), ())

        # closing the PixelArray releases the surface lock
        pxarray.close()
        self.assertEqual(surface.get_locks(), ())

        # AttributeError raised when called on invalid object type (i.e. not a pygame.Surface object)
        with self.assertRaises(AttributeError):
            "DUMMY".get_locks()

        # test multiple locks and unlocks on the same surface
        surface.lock()
        surface.lock()
        surface.lock()
        self.assertEqual(surface.get_locks(), (surface, surface, surface))

        surface.unlock()
        surface.unlock()
        self.assertEqual(surface.get_locks(), (surface,))
        surface.unlock()
        self.assertEqual(surface.get_locks(), ())

    def test_get_losses(self):
        """Ensure a surface's losses can be retrieved"""
        pygame.display.init()
        try:
            # Masks for different color component configurations
            mask8 = (224, 28, 3, 0)
            mask15 = (31744, 992, 31, 0)
            mask16 = (63488, 2016, 31, 0)
            mask24 = (16711680, 65280, 255, 0)
            mask32 = (4278190080, 16711680, 65280, 255)

            # Surfaces with standard depths and masks
            display_surf = pygame.display.set_mode((100, 100))
            surf = pygame.Surface((100, 100))
            surf_8bit = pygame.Surface((100, 100), depth=8, masks=mask8)
            surf_15bit = pygame.Surface((100, 100), depth=15, masks=mask15)
            surf_16bit = pygame.Surface((100, 100), depth=16, masks=mask16)
            surf_24bit = pygame.Surface((100, 100), depth=24, masks=mask24)
            surf_32bit = pygame.Surface((100, 100), depth=32, masks=mask32)

            # Test output is correct type, length, and value range
            losses = surf.get_losses()
            self.assertIsInstance(losses, tuple)
            self.assertEqual(len(losses), 4)
            for loss in losses:
                self.assertIsInstance(loss, int)
                self.assertGreaterEqual(loss, 0)
                self.assertLessEqual(loss, 8)

            # Test each surface for correct losses
            # Display surface losses gives idea of default surface losses
            if display_surf.get_losses() == (0, 0, 0, 8):
                self.assertEqual(losses, (0, 0, 0, 8))
            elif display_surf.get_losses() == (8, 8, 8, 8):
                self.assertEqual(losses, (8, 8, 8, 8))

            self.assertEqual(surf_8bit.get_losses(), (5, 5, 6, 8))
            self.assertEqual(surf_15bit.get_losses(), (3, 3, 3, 8))
            self.assertEqual(surf_16bit.get_losses(), (3, 2, 3, 8))
            self.assertEqual(surf_24bit.get_losses(), (0, 0, 0, 8))
            self.assertEqual(surf_32bit.get_losses(), (0, 0, 0, 0))

            # Method should fail when display is not initialized
            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode((100, 100))
                pygame.display.quit()
                surface.get_losses()
        finally:
            pygame.display.quit()

    def test_get_masks__rgba(self):
        """
        Ensure that get_mask can return RGBA mask.
        """
        masks = [
            (0x0F00, 0x00F0, 0x000F, 0xF000),
            (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000),
        ]
        depths = [16, 32]
        for expected, depth in list(zip(masks, depths)):
            surface = pygame.Surface((10, 10), pygame.SRCALPHA, depth)
            self.assertEqual(expected, surface.get_masks())

    def test_get_masks__rgb(self):
        """
        Ensure that get_mask can return RGB mask.
        """
        masks = [
            (0x60, 0x1C, 0x03, 0x00),
            (0xF00, 0x0F0, 0x00F, 0x000),
            (0x7C00, 0x03E0, 0x001F, 0x0000),
            (0xF800, 0x07E0, 0x001F, 0x0000),
            (0xFF0000, 0x00FF00, 0x0000FF, 0x000000),
            (0xFF0000, 0x00FF00, 0x0000FF, 0x000000),
        ]
        depths = [8, 12, 15, 16, 24, 32]
        for expected, depth in list(zip(masks, depths)):
            surface = pygame.Surface((10, 10), 0, depth)
            if depth == 8:
                expected = (0x00, 0x00, 0x00, 0x00)
            self.assertEqual(expected, surface.get_masks())

    def test_get_masks__no_surface(self):
        """
        Ensure that after display.quit, calling get_masks raises pygame.error.
        """
        with self.assertRaises(pygame.error):
            surface = pygame.display.set_mode((10, 10))
            pygame.display.quit()
            surface.get_masks()

    def test_get_offset(self):
        """get_offset returns the (0,0) if surface is not a child
        returns the position of child subsurface inside of parent
        """
        pygame.display.init()
        try:
            surf = pygame.Surface((100, 100))
            self.assertEqual(surf.get_offset(), (0, 0))

            # subsurface offset test
            subsurf = surf.subsurface(1, 1, 10, 10)
            self.assertEqual(subsurf.get_offset(), (1, 1))

            with self.assertRaises(pygame.error):
                surface = pygame.display.set_mode()
                pygame.display.quit()
                surface.get_offset()
        finally:
            pygame.display.quit()

    def test_get_palette(self):
        palette = [Color(i, i, i) for i in range(256)]
        surf = pygame.Surface((2, 2), 0, 8)
        surf.set_palette(palette)
        palette2 = surf.get_palette()

        self.assertEqual(len(palette2), len(palette))
        for c2, c in zip(palette2, palette):
            self.assertEqual(c2, c)
        for c in palette2:
            self.assertIsInstance(c, pygame.Color)

    def test_get_palette_at(self):
        # See also test_get_palette
        surf = pygame.Surface((2, 2), 0, 8)
        color = pygame.Color(1, 2, 3, 255)
        surf.set_palette_at(0, color)
        color2 = surf.get_palette_at(0)
        self.assertIsInstance(color2, pygame.Color)
        self.assertEqual(color2, color)
        self.assertRaises(IndexError, surf.get_palette_at, -1)
        self.assertRaises(IndexError, surf.get_palette_at, 256)

    def test_get_pitch(self):
        # Test get_pitch() on several surfaces of varying size/depth
        sizes = ((2, 2), (7, 33), (33, 7), (2, 734), (734, 2), (734, 734))
        depths = [8, 24, 32]
        for width, height in sizes:
            for depth in depths:
                # Test get_pitch() on parent surface
                surf = pygame.Surface((width, height), depth=depth)
                buff = surf.get_buffer()
                pitch = buff.length / surf.get_height()
                test_pitch = surf.get_pitch()
                self.assertEqual(pitch, test_pitch)
                # Test get_pitch() on subsurface with same rect as parent
                rect1 = surf.get_rect()
                subsurf1 = surf.subsurface(rect1)
                sub_buff1 = subsurf1.get_buffer()
                sub_pitch1 = sub_buff1.length / subsurf1.get_height()
                test_sub_pitch1 = subsurf1.get_pitch()
                self.assertEqual(sub_pitch1, test_sub_pitch1)
                # Test get_pitch on subsurface with modified rect
                rect2 = rect1.inflate(-width / 2, -height / 2)
                subsurf2 = surf.subsurface(rect2)
                sub_buff2 = subsurf2.get_buffer()
                sub_pitch2 = sub_buff2.length / float(subsurf2.get_height())
                test_sub_pitch2 = subsurf2.get_pitch()
                self.assertEqual(sub_pitch2, test_sub_pitch2)

    def test_get_shifts(self):
        """
        Tests whether Surface.get_shifts returns proper
        RGBA shifts under various conditions.
        """
        # __doc__ (as of 2008-08-02) for pygame.surface.Surface.get_shifts:
        # Surface.get_shifts(): return (R, G, B, A)
        # the bit shifts needed to convert between color and mapped integer.
        # Returns the pixel shifts need to convert between each color and a
        # mapped integer.
        # This value is not needed for normal Pygame usage.

        # Test for SDL2 on surfaces with various depths and alpha on/off
        depths = [8, 24, 32]
        alpha = 128
        off = None
        for bit_depth in depths:
            surface = pygame.Surface((32, 32), depth=bit_depth)
            surface.set_alpha(alpha)
            r1, g1, b1, a1 = surface.get_shifts()
            surface.set_alpha(off)
            r2, g2, b2, a2 = surface.get_shifts()
            self.assertEqual((r1, g1, b1, a1), (r2, g2, b2, a2))

    def test_get_size(self):
        sizes = ((1, 1), (119, 10), (1000, 1000), (1, 5000), (1221, 1), (99, 999))
        for width, height in sizes:
            surf = pygame.Surface((width, height))
            found_size = surf.get_size()
            self.assertEqual((width, height), found_size)

    def test_lock(self):
        # __doc__ (as of 2008-08-02) for pygame.surface.Surface.lock:

        # Surface.lock(): return None
        # lock the Surface memory for pixel access
        #
        # Lock the pixel data of a Surface for access. On accelerated
        # Surfaces, the pixel data may be stored in volatile video memory or
        # nonlinear compressed forms. When a Surface is locked the pixel
        # memory becomes available to access by regular software. Code that
        # reads or writes pixel values will need the Surface to be locked.
        #
        # Surfaces should not remain locked for more than necessary. A locked
        # Surface can often not be displayed or managed by Pygame.
        #
        # Not all Surfaces require locking. The Surface.mustlock() method can
        # determine if it is actually required. There is no performance
        # penalty for locking and unlocking a Surface that does not need it.
        #
        # All pygame functions will automatically lock and unlock the Surface
        # data as needed. If a section of code is going to make calls that
        # will repeatedly lock and unlock the Surface many times, it can be
        # helpful to wrap the block inside a lock and unlock pair.
        #
        # It is safe to nest locking and unlocking calls. The surface will
        # only be unlocked after the final lock is released.
        #

        # Basic
        surf = pygame.Surface((100, 100))
        surf.lock()
        self.assertTrue(surf.get_locked())

        # Nested
        surf = pygame.Surface((100, 100))
        surf.lock()
        surf.lock()
        surf.unlock()
        self.assertTrue(surf.get_locked())
        surf.unlock()
        surf.lock()
        surf.lock()
        self.assertTrue(surf.get_locked())
        surf.unlock()
        self.assertTrue(surf.get_locked())
        surf.unlock()
        self.assertFalse(surf.get_locked())

        # Already Locked
        surf = pygame.Surface((100, 100))
        surf.lock()
        surf.lock()
        self.assertTrue(surf.get_locked())
        surf.unlock()
        self.assertTrue(surf.get_locked())
        surf.unlock()
        self.assertFalse(surf.get_locked())

    def test_map_rgb(self):
        color = Color(0, 128, 255, 64)
        surf = pygame.Surface((5, 5), SRCALPHA, 32)
        c = surf.map_rgb(color)
        self.assertEqual(surf.unmap_rgb(c), color)

        self.assertEqual(surf.get_at((0, 0)), (0, 0, 0, 0))
        surf.fill(c)
        self.assertEqual(surf.get_at((0, 0)), color)

        surf.fill((0, 0, 0, 0))
        self.assertEqual(surf.get_at((0, 0)), (0, 0, 0, 0))
        surf.set_at((0, 0), c)
        self.assertEqual(surf.get_at((0, 0)), color)

    def test_mustlock(self):
        # Test that subsurfaces mustlock
        surf = pygame.Surface((1024, 1024))
        subsurf = surf.subsurface((0, 0, 1024, 1024))
        self.assertTrue(subsurf.mustlock())
        self.assertFalse(surf.mustlock())
        # Tests nested subsurfaces
        rects = ((0, 0, 512, 512), (0, 0, 256, 256), (0, 0, 128, 128))
        surf_stack = []
        surf_stack.append(surf)
        surf_stack.append(subsurf)
        for rect in rects:
            surf_stack.append(surf_stack[-1].subsurface(rect))
            self.assertTrue(surf_stack[-1].mustlock())
            self.assertTrue(surf_stack[-2].mustlock())

    def test_set_alpha_none(self):
        """surf.set_alpha(None) disables blending"""
        s = pygame.Surface((1, 1), SRCALPHA, 32)
        s.fill((0, 255, 0, 128))
        s.set_alpha(None)
        self.assertEqual(None, s.get_alpha())

        s2 = pygame.Surface((1, 1), SRCALPHA, 32)
        s2.fill((255, 0, 0, 255))
        s2.blit(s, (0, 0))
        self.assertEqual(s2.get_at((0, 0))[0], 0, "the red component should be 0")

    def test_set_alpha_value(self):
        """surf.set_alpha(x), where x != None, enables blending"""
        s = pygame.Surface((1, 1), SRCALPHA, 32)
        s.fill((0, 255, 0, 128))
        s.set_alpha(255)

        s2 = pygame.Surface((1, 1), SRCALPHA, 32)
        s2.fill((255, 0, 0, 255))
        s2.blit(s, (0, 0))
        self.assertGreater(
            s2.get_at((0, 0))[0], 0, "the red component should be above 0"
        )

    def test_palette_colorkey(self):
        """test bug discovered by robertpfeiffer
        https://github.com/pygame/pygame/issues/721
        """
        surf = pygame.image.load(example_path(os.path.join("data", "alien2.png")))
        key = surf.get_colorkey()
        self.assertEqual(surf.get_palette()[surf.map_rgb(key)], key)

    def test_palette_colorkey_set_px(self):
        surf = pygame.image.load(example_path(os.path.join("data", "alien2.png")))
        key = surf.get_colorkey()
        surf.set_at((0, 0), key)
        self.assertEqual(surf.get_at((0, 0)), key)

    def test_palette_colorkey_fill(self):
        surf = pygame.image.load(example_path(os.path.join("data", "alien2.png")))
        key = surf.get_colorkey()
        surf.fill(key)
        self.assertEqual(surf.get_at((0, 0)), key)

    def test_set_palette(self):
        palette = [pygame.Color(i, i, i) for i in range(256)]
        palette[10] = tuple(palette[10])  # 4 element tuple
        palette[11] = tuple(palette[11])[0:3]  # 3 element tuple

        surf = pygame.Surface((2, 2), 0, 8)
        surf.set_palette(palette)
        for i in range(256):
            self.assertEqual(surf.map_rgb(palette[i]), i, "palette color %i" % (i,))
            c = palette[i]
            surf.fill(c)
            self.assertEqual(surf.get_at((0, 0)), c, "palette color %i" % (i,))
        for i in range(10):
            palette[i] = pygame.Color(255 - i, 0, 0)
        surf.set_palette(palette[0:10])
        for i in range(256):
            self.assertEqual(surf.map_rgb(palette[i]), i, "palette color %i" % (i,))
            c = palette[i]
            surf.fill(c)
            self.assertEqual(surf.get_at((0, 0)), c, "palette color %i" % (i,))
        self.assertRaises(ValueError, surf.set_palette, [Color(1, 2, 3, 254)])
        self.assertRaises(ValueError, surf.set_palette, (1, 2, 3, 254))

    def test_set_palette__fail(self):
        palette = 256 * [(10, 20, 30)]
        surf = pygame.Surface((2, 2), 0, 32)
        self.assertRaises(pygame.error, surf.set_palette, palette)

    def test_set_palette__set_at(self):
        surf = pygame.Surface((2, 2), depth=8)
        palette = 256 * [(10, 20, 30)]
        palette[1] = (50, 40, 30)
        surf.set_palette(palette)

        # calling set_at on a palettized surface should set the pixel to
        # the closest color in the palette.
        surf.set_at((0, 0), (60, 50, 40))
        self.assertEqual(surf.get_at((0, 0)), (50, 40, 30, 255))
        self.assertEqual(surf.get_at((1, 0)), (10, 20, 30, 255))

    def test_set_palette_at(self):
        surf = pygame.Surface((2, 2), 0, 8)
        original = surf.get_palette_at(10)
        replacement = Color(1, 1, 1, 255)
        if replacement == original:
            replacement = Color(2, 2, 2, 255)
        surf.set_palette_at(10, replacement)
        self.assertEqual(surf.get_palette_at(10), replacement)
        next = tuple(original)
        surf.set_palette_at(10, next)
        self.assertEqual(surf.get_palette_at(10), next)
        next = tuple(original)[0:3]
        surf.set_palette_at(10, next)
        self.assertEqual(surf.get_palette_at(10), next)
        self.assertRaises(IndexError, surf.set_palette_at, 256, replacement)
        self.assertRaises(IndexError, surf.set_palette_at, -1, replacement)

    def test_subsurface(self):
        # __doc__ (as of 2008-08-02) for pygame.surface.Surface.subsurface:

        # Surface.subsurface(Rect): return Surface
        # create a new surface that references its parent
        #
        # Returns a new Surface that shares its pixels with its new parent.
        # The new Surface is considered a child of the original. Modifications
        # to either Surface pixels will effect each other. Surface information
        # like clipping area and color keys are unique to each Surface.
        #
        # The new Surface will inherit the palette, color key, and alpha
        # settings from its parent.
        #
        # It is possible to have any number of subsurfaces and subsubsurfaces
        # on the parent. It is also possible to subsurface the display Surface
        # if the display mode is not hardware accelerated.
        #
        # See the Surface.get_offset(), Surface.get_parent() to learn more
        # about the state of a subsurface.
        #

        surf = pygame.Surface((16, 16))
        s = surf.subsurface(0, 0, 1, 1)
        s = surf.subsurface((0, 0, 1, 1))

        # s = surf.subsurface((0,0,1,1), 1)
        # This form is not acceptable.
        # s = surf.subsurface(0,0,10,10, 1)

        self.assertRaises(ValueError, surf.subsurface, (0, 0, 1, 1, 666))

        self.assertEqual(s.get_shifts(), surf.get_shifts())
        self.assertEqual(s.get_masks(), surf.get_masks())
        self.assertEqual(s.get_losses(), surf.get_losses())

        # Issue https://github.com/pygame/pygame/issues/2
        surf = pygame.Surface.__new__(pygame.Surface)
        self.assertRaises(pygame.error, surf.subsurface, (0, 0, 0, 0))

    def test_unlock(self):
        # Basic
        surf = pygame.Surface((100, 100))
        surf.lock()
        surf.unlock()
        self.assertFalse(surf.get_locked())

        # Nested
        surf = pygame.Surface((100, 100))
        surf.lock()
        surf.lock()
        surf.unlock()
        self.assertTrue(surf.get_locked())
        surf.unlock()
        self.assertFalse(surf.get_locked())

        # Already Unlocked
        surf = pygame.Surface((100, 100))
        surf.unlock()
        self.assertFalse(surf.get_locked())
        surf.unlock()
        self.assertFalse(surf.get_locked())

        # Surface can be relocked
        surf = pygame.Surface((100, 100))
        surf.lock()
        surf.unlock()
        self.assertFalse(surf.get_locked())
        surf.lock()
        surf.unlock()
        self.assertFalse(surf.get_locked())

    def test_unmap_rgb(self):
        # Special case, 8 bit-per-pixel surface (has a palette).
        surf = pygame.Surface((2, 2), 0, 8)
        c = (1, 1, 1)  # Unlikely to be in a default palette.
        i = 67
        surf.set_palette_at(i, c)
        unmapped_c = surf.unmap_rgb(i)
        self.assertEqual(unmapped_c, c)
        # Confirm it is a Color instance
        self.assertIsInstance(unmapped_c, pygame.Color)

        # Remaining, non-pallete, cases.
        c = (128, 64, 12, 255)
        formats = [(0, 16), (0, 24), (0, 32), (SRCALPHA, 16), (SRCALPHA, 32)]
        for flags, bitsize in formats:
            surf = pygame.Surface((2, 2), flags, bitsize)
            unmapped_c = surf.unmap_rgb(surf.map_rgb(c))
            surf.fill(c)
            comparison_c = surf.get_at((0, 0))
            self.assertEqual(
                unmapped_c,
                comparison_c,
                "%s != %s, flags: %i, bitsize: %i"
                % (unmapped_c, comparison_c, flags, bitsize),
            )
            # Confirm it is a Color instance
            self.assertIsInstance(unmapped_c, pygame.Color)

    def test_scroll(self):
        scrolls = [
            (8, 2, 3),
            (16, 2, 3),
            (24, 2, 3),
            (32, 2, 3),
            (32, -1, -3),
            (32, 0, 0),
            (32, 11, 0),
            (32, 0, 11),
            (32, -11, 0),
            (32, 0, -11),
            (32, -11, 2),
            (32, 2, -11),
        ]
        for bitsize, dx, dy in scrolls:
            surf = pygame.Surface((10, 10), 0, bitsize)
            surf.fill((255, 0, 0))
            surf.fill((0, 255, 0), (2, 2, 2, 2))
            comp = surf.copy()
            comp.blit(surf, (dx, dy))
            surf.scroll(dx, dy)
            w, h = surf.get_size()
            for x in range(w):
                for y in range(h):
                    with self.subTest(x=x, y=y):
                        self.assertEqual(
                            surf.get_at((x, y)),
                            comp.get_at((x, y)),
                            "%s != %s, bpp:, %i, x: %i, y: %i"
                            % (
                                surf.get_at((x, y)),
                                comp.get_at((x, y)),
                                bitsize,
                                dx,
                                dy,
                            ),
                        )
        # Confirm clip rect containment
        surf = pygame.Surface((20, 13), 0, 32)
        surf.fill((255, 0, 0))
        surf.fill((0, 255, 0), (7, 1, 6, 6))
        comp = surf.copy()
        clip = Rect(3, 1, 8, 14)
        surf.set_clip(clip)
        comp.set_clip(clip)
        comp.blit(surf, (clip.x + 2, clip.y + 3), surf.get_clip())
        surf.scroll(2, 3)
        w, h = surf.get_size()
        for x in range(w):
            for y in range(h):
                self.assertEqual(surf.get_at((x, y)), comp.get_at((x, y)))
        # Confirm keyword arguments and per-pixel alpha
        spot_color = (0, 255, 0, 128)
        surf = pygame.Surface((4, 4), pygame.SRCALPHA, 32)
        surf.fill((255, 0, 0, 255))
        surf.set_at((1, 1), spot_color)
        surf.scroll(dx=1)
        self.assertEqual(surf.get_at((2, 1)), spot_color)
        surf.scroll(dy=1)
        self.assertEqual(surf.get_at((2, 2)), spot_color)
        surf.scroll(dy=1, dx=1)
        self.assertEqual(surf.get_at((3, 3)), spot_color)
        surf.scroll(dx=-3, dy=-3)
        self.assertEqual(surf.get_at((0, 0)), spot_color)


class SurfaceSubtypeTest(unittest.TestCase):
    """Issue #280: Methods that return a new Surface preserve subclasses"""

    def setUp(self):
        pygame.display.init()

    def tearDown(self):
        pygame.display.quit()

    def test_copy(self):
        """Ensure method copy() preserves the surface's class

        When Surface is subclassed, the inherited copy() method will return
        instances of the subclass. Non Surface fields are uncopied, however.
        This includes instance attributes.
        """
        expected_size = (32, 32)
        ms1 = SurfaceSubclass(expected_size, SRCALPHA, 32)
        ms2 = ms1.copy()

        self.assertIsNot(ms1, ms2)
        self.assertIsInstance(ms1, pygame.Surface)
        self.assertIsInstance(ms2, pygame.Surface)
        self.assertIsInstance(ms1, SurfaceSubclass)
        self.assertIsInstance(ms2, SurfaceSubclass)
        self.assertTrue(ms1.test_attribute)
        self.assertRaises(AttributeError, getattr, ms2, "test_attribute")
        self.assertEqual(ms2.get_size(), expected_size)

    def test_convert(self):
        """Ensure method convert() preserves the surface's class

        When Surface is subclassed, the inherited convert() method will return
        instances of the subclass. Non Surface fields are omitted, however.
        This includes instance attributes.
        """
        expected_size = (32, 32)
        ms1 = SurfaceSubclass(expected_size, 0, 24)
        ms2 = ms1.convert(24)

        self.assertIsNot(ms1, ms2)
        self.assertIsInstance(ms1, pygame.Surface)
        self.assertIsInstance(ms2, pygame.Surface)
        self.assertIsInstance(ms1, SurfaceSubclass)
        self.assertIsInstance(ms2, SurfaceSubclass)
        self.assertTrue(ms1.test_attribute)
        self.assertRaises(AttributeError, getattr, ms2, "test_attribute")
        self.assertEqual(ms2.get_size(), expected_size)

    def test_convert_alpha(self):
        """Ensure method convert_alpha() preserves the surface's class

        When Surface is subclassed, the inherited convert_alpha() method will
        return instances of the subclass. Non Surface fields are omitted,
        however. This includes instance attributes.
        """
        pygame.display.set_mode((40, 40))
        expected_size = (32, 32)
        s = pygame.Surface(expected_size, SRCALPHA, 16)
        ms1 = SurfaceSubclass(expected_size, SRCALPHA, 32)
        ms2 = ms1.convert_alpha(s)

        self.assertIsNot(ms1, ms2)
        self.assertIsInstance(ms1, pygame.Surface)
        self.assertIsInstance(ms2, pygame.Surface)
        self.assertIsInstance(ms1, SurfaceSubclass)
        self.assertIsInstance(ms2, SurfaceSubclass)
        self.assertTrue(ms1.test_attribute)
        self.assertRaises(AttributeError, getattr, ms2, "test_attribute")
        self.assertEqual(ms2.get_size(), expected_size)

    def test_subsurface(self):
        """Ensure method subsurface() preserves the surface's class

        When Surface is subclassed, the inherited subsurface() method will
        return instances of the subclass. Non Surface fields are uncopied,
        however. This includes instance attributes.
        """
        expected_size = (10, 12)
        ms1 = SurfaceSubclass((32, 32), SRCALPHA, 32)
        ms2 = ms1.subsurface((4, 5), expected_size)

        self.assertIsNot(ms1, ms2)
        self.assertIsInstance(ms1, pygame.Surface)
        self.assertIsInstance(ms2, pygame.Surface)
        self.assertIsInstance(ms1, SurfaceSubclass)
        self.assertIsInstance(ms2, SurfaceSubclass)
        self.assertTrue(ms1.test_attribute)
        self.assertRaises(AttributeError, getattr, ms2, "test_attribute")
        self.assertEqual(ms2.get_size(), expected_size)


class SurfaceGetBufferTest(unittest.TestCase):
    # These tests requires ctypes. They are disabled if ctypes
    # is not installed.
    try:
        ArrayInterface
    except NameError:
        __tags__ = ("ignore", "subprocess_ignore")

    lilendian = pygame.get_sdl_byteorder() == pygame.LIL_ENDIAN

    def _check_interface_2D(self, s):
        s_w, s_h = s.get_size()
        s_bytesize = s.get_bytesize()
        s_pitch = s.get_pitch()
        s_pixels = s._pixels_address

        # check the array interface structure fields.
        v = s.get_view("2")
        if not IS_PYPY:
            flags = PAI_ALIGNED | PAI_NOTSWAPPED | PAI_WRITEABLE
            if s.get_pitch() == s_w * s_bytesize:
                flags |= PAI_FORTRAN

            inter = ArrayInterface(v)

            self.assertEqual(inter.two, 2)
            self.assertEqual(inter.nd, 2)
            self.assertEqual(inter.typekind, "u")
            self.assertEqual(inter.itemsize, s_bytesize)
            self.assertEqual(inter.shape[0], s_w)
            self.assertEqual(inter.shape[1], s_h)
            self.assertEqual(inter.strides[0], s_bytesize)
            self.assertEqual(inter.strides[1], s_pitch)
            self.assertEqual(inter.flags, flags)
            self.assertEqual(inter.data, s_pixels)

    def _check_interface_3D(self, s):
        s_w, s_h = s.get_size()
        s_bytesize = s.get_bytesize()
        s_pitch = s.get_pitch()
        s_pixels = s._pixels_address
        s_shifts = list(s.get_shifts())

        # Check for RGB or BGR surface.
        if s_shifts[0:3] == [0, 8, 16]:
            if self.lilendian:
                # RGB
                offset = 0
                step = 1
            else:
                # BGR
                offset = s_bytesize - 1
                step = -1
        elif s_shifts[0:3] == [8, 16, 24]:
            if self.lilendian:
                # xRGB
                offset = 1
                step = 1
            else:
                # BGRx
                offset = s_bytesize - 2
                step = -1
        elif s_shifts[0:3] == [16, 8, 0]:
            if self.lilendian:
                # BGR
                offset = 2
                step = -1
            else:
                # RGB
                offset = s_bytesize - 3
                step = 1
        elif s_shifts[0:3] == [24, 16, 8]:
            if self.lilendian:
                # BGRx
                offset = 2
                step = -1
            else:
                # RGBx
                offset = s_bytesize - 4
                step = -1
        else:
            return

        # check the array interface structure fields.
        v = s.get_view("3")
        if not IS_PYPY:
            inter = ArrayInterface(v)
            flags = PAI_ALIGNED | PAI_NOTSWAPPED | PAI_WRITEABLE
            self.assertEqual(inter.two, 2)
            self.assertEqual(inter.nd, 3)
            self.assertEqual(inter.typekind, "u")
            self.assertEqual(inter.itemsize, 1)
            self.assertEqual(inter.shape[0], s_w)
            self.assertEqual(inter.shape[1], s_h)
            self.assertEqual(inter.shape[2], 3)
            self.assertEqual(inter.strides[0], s_bytesize)
            self.assertEqual(inter.strides[1], s_pitch)
            self.assertEqual(inter.strides[2], step)
            self.assertEqual(inter.flags, flags)
            self.assertEqual(inter.data, s_pixels + offset)

    def _check_interface_rgba(self, s, plane):
        s_w, s_h = s.get_size()
        s_bytesize = s.get_bytesize()
        s_pitch = s.get_pitch()
        s_pixels = s._pixels_address
        s_shifts = s.get_shifts()
        s_masks = s.get_masks()

        # Find the color plane position within the pixel.
        if not s_masks[plane]:
            return
        alpha_shift = s_shifts[plane]
        offset = alpha_shift // 8
        if not self.lilendian:
            offset = s_bytesize - offset - 1

        # check the array interface structure fields.
        v = s.get_view("rgba"[plane])
        if not IS_PYPY:
            inter = ArrayInterface(v)
            flags = PAI_ALIGNED | PAI_NOTSWAPPED | PAI_WRITEABLE
            self.assertEqual(inter.two, 2)
            self.assertEqual(inter.nd, 2)
            self.assertEqual(inter.typekind, "u")
            self.assertEqual(inter.itemsize, 1)
            self.assertEqual(inter.shape[0], s_w)
            self.assertEqual(inter.shape[1], s_h)
            self.assertEqual(inter.strides[0], s_bytesize)
            self.assertEqual(inter.strides[1], s_pitch)
            self.assertEqual(inter.flags, flags)
            self.assertEqual(inter.data, s_pixels + offset)

    def test_array_interface(self):
        self._check_interface_2D(pygame.Surface((5, 7), 0, 8))
        self._check_interface_2D(pygame.Surface((5, 7), 0, 16))
        self._check_interface_2D(pygame.Surface((5, 7), pygame.SRCALPHA, 16))
        self._check_interface_3D(pygame.Surface((5, 7), 0, 24))
        self._check_interface_3D(pygame.Surface((8, 4), 0, 24))  # No gaps
        self._check_interface_2D(pygame.Surface((5, 7), 0, 32))
        self._check_interface_3D(pygame.Surface((5, 7), 0, 32))
        self._check_interface_2D(pygame.Surface((5, 7), pygame.SRCALPHA, 32))
        self._check_interface_3D(pygame.Surface((5, 7), pygame.SRCALPHA, 32))

    def test_array_interface_masks(self):
        """Test non-default color byte orders on 3D views"""

        sz = (5, 7)
        # Reversed RGB byte order
        s = pygame.Surface(sz, 0, 32)
        s_masks = list(s.get_masks())
        masks = [0xFF, 0xFF00, 0xFF0000]
        if s_masks[0:3] == masks or s_masks[0:3] == masks[::-1]:
            masks = s_masks[2::-1] + s_masks[3:4]
            self._check_interface_3D(pygame.Surface(sz, 0, 32, masks))
        s = pygame.Surface(sz, 0, 24)
        s_masks = list(s.get_masks())
        masks = [0xFF, 0xFF00, 0xFF0000]
        if s_masks[0:3] == masks or s_masks[0:3] == masks[::-1]:
            masks = s_masks[2::-1] + s_masks[3:4]
            self._check_interface_3D(pygame.Surface(sz, 0, 24, masks))

        masks = [0xFF00, 0xFF0000, 0xFF000000, 0]
        self._check_interface_3D(pygame.Surface(sz, 0, 32, masks))

    def test_array_interface_alpha(self):
        for shifts in [[0, 8, 16, 24], [8, 16, 24, 0], [24, 16, 8, 0], [16, 8, 0, 24]]:
            masks = [0xFF << s for s in shifts]
            s = pygame.Surface((4, 2), pygame.SRCALPHA, 32, masks)
            self._check_interface_rgba(s, 3)

    def test_array_interface_rgb(self):
        for shifts in [[0, 8, 16, 24], [8, 16, 24, 0], [24, 16, 8, 0], [16, 8, 0, 24]]:
            masks = [0xFF << s for s in shifts]
            masks[3] = 0
            for plane in range(3):
                s = pygame.Surface((4, 2), 0, 24)
                self._check_interface_rgba(s, plane)
                s = pygame.Surface((4, 2), 0, 32)
                self._check_interface_rgba(s, plane)

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def test_newbuf_PyBUF_flags_bytes(self):
        from pygame.tests.test_utils import buftools

        Importer = buftools.Importer
        s = pygame.Surface((10, 6), 0, 32)
        a = s.get_buffer()
        b = Importer(a, buftools.PyBUF_SIMPLE)
        self.assertEqual(b.ndim, 0)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, 1)
        self.assertTrue(b.shape is None)
        self.assertTrue(b.strides is None)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address)
        b = Importer(a, buftools.PyBUF_WRITABLE)
        self.assertEqual(b.ndim, 0)
        self.assertTrue(b.format is None)
        self.assertFalse(b.readonly)
        b = Importer(a, buftools.PyBUF_FORMAT)
        self.assertEqual(b.ndim, 0)
        self.assertEqual(b.format, "B")
        b = Importer(a, buftools.PyBUF_ND)
        self.assertEqual(b.ndim, 1)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, 1)
        self.assertEqual(b.shape, (a.length,))
        self.assertTrue(b.strides is None)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address)
        b = Importer(a, buftools.PyBUF_STRIDES)
        self.assertEqual(b.ndim, 1)
        self.assertTrue(b.format is None)
        self.assertEqual(b.strides, (1,))
        s2 = s.subsurface((1, 1, 7, 4))  # Not contiguous
        a = s2.get_buffer()
        b = Importer(a, buftools.PyBUF_SIMPLE)
        self.assertEqual(b.ndim, 0)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, 1)
        self.assertTrue(b.shape is None)
        self.assertTrue(b.strides is None)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s2._pixels_address)
        b = Importer(a, buftools.PyBUF_C_CONTIGUOUS)
        self.assertEqual(b.ndim, 1)
        self.assertEqual(b.strides, (1,))
        b = Importer(a, buftools.PyBUF_F_CONTIGUOUS)
        self.assertEqual(b.ndim, 1)
        self.assertEqual(b.strides, (1,))
        b = Importer(a, buftools.PyBUF_ANY_CONTIGUOUS)
        self.assertEqual(b.ndim, 1)
        self.assertEqual(b.strides, (1,))

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def test_newbuf_PyBUF_flags_0D(self):
        # This is the same handler as used by get_buffer(), so just
        # confirm that it succeeds for one case.
        from pygame.tests.test_utils import buftools

        Importer = buftools.Importer
        s = pygame.Surface((10, 6), 0, 32)
        a = s.get_view("0")
        b = Importer(a, buftools.PyBUF_SIMPLE)
        self.assertEqual(b.ndim, 0)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, 1)
        self.assertTrue(b.shape is None)
        self.assertTrue(b.strides is None)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address)

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def test_newbuf_PyBUF_flags_1D(self):
        from pygame.tests.test_utils import buftools

        Importer = buftools.Importer
        s = pygame.Surface((10, 6), 0, 32)
        a = s.get_view("1")
        b = Importer(a, buftools.PyBUF_SIMPLE)
        self.assertEqual(b.ndim, 0)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, s.get_bytesize())
        self.assertTrue(b.shape is None)
        self.assertTrue(b.strides is None)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address)
        b = Importer(a, buftools.PyBUF_WRITABLE)
        self.assertEqual(b.ndim, 0)
        self.assertTrue(b.format is None)
        self.assertFalse(b.readonly)
        b = Importer(a, buftools.PyBUF_FORMAT)
        self.assertEqual(b.ndim, 0)
        self.assertEqual(b.format, "=I")
        b = Importer(a, buftools.PyBUF_ND)
        self.assertEqual(b.ndim, 1)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, s.get_bytesize())
        self.assertEqual(b.shape, (s.get_width() * s.get_height(),))
        self.assertTrue(b.strides is None)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address)
        b = Importer(a, buftools.PyBUF_STRIDES)
        self.assertEqual(b.ndim, 1)
        self.assertTrue(b.format is None)
        self.assertEqual(b.strides, (s.get_bytesize(),))

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def test_newbuf_PyBUF_flags_2D(self):
        from pygame.tests.test_utils import buftools

        Importer = buftools.Importer
        s = pygame.Surface((10, 6), 0, 32)
        a = s.get_view("2")
        # Non dimensional requests, no PyDEF_ND, are handled by the
        # 1D surface buffer code, so only need to confirm a success.
        b = Importer(a, buftools.PyBUF_SIMPLE)
        self.assertEqual(b.ndim, 0)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, s.get_bytesize())
        self.assertTrue(b.shape is None)
        self.assertTrue(b.strides is None)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address)
        # Uniquely 2D
        b = Importer(a, buftools.PyBUF_STRIDES)
        self.assertEqual(b.ndim, 2)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, s.get_bytesize())
        self.assertEqual(b.shape, s.get_size())
        self.assertEqual(b.strides, (s.get_bytesize(), s.get_pitch()))
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address)
        b = Importer(a, buftools.PyBUF_RECORDS_RO)
        self.assertEqual(b.ndim, 2)
        self.assertEqual(b.format, "=I")
        self.assertEqual(b.strides, (s.get_bytesize(), s.get_pitch()))
        b = Importer(a, buftools.PyBUF_RECORDS)
        self.assertEqual(b.ndim, 2)
        self.assertEqual(b.format, "=I")
        self.assertEqual(b.strides, (s.get_bytesize(), s.get_pitch()))
        b = Importer(a, buftools.PyBUF_F_CONTIGUOUS)
        self.assertEqual(b.ndim, 2)
        self.assertEqual(b.format, None)
        self.assertEqual(b.strides, (s.get_bytesize(), s.get_pitch()))
        b = Importer(a, buftools.PyBUF_ANY_CONTIGUOUS)
        self.assertEqual(b.ndim, 2)
        self.assertEqual(b.format, None)
        self.assertEqual(b.strides, (s.get_bytesize(), s.get_pitch()))
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_C_CONTIGUOUS)
        s2 = s.subsurface((1, 1, 7, 4))  # Not contiguous
        a = s2.get_view("2")
        b = Importer(a, buftools.PyBUF_STRIDES)
        self.assertEqual(b.ndim, 2)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, s2.get_bytesize())
        self.assertEqual(b.shape, s2.get_size())
        self.assertEqual(b.strides, (s2.get_bytesize(), s.get_pitch()))
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s2._pixels_address)
        b = Importer(a, buftools.PyBUF_RECORDS)
        self.assertEqual(b.ndim, 2)
        self.assertEqual(b.format, "=I")
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_SIMPLE)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_FORMAT)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_WRITABLE)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_F_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_ANY_CONTIGUOUS)

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def test_newbuf_PyBUF_flags_3D(self):
        from pygame.tests.test_utils import buftools

        Importer = buftools.Importer
        s = pygame.Surface((12, 6), 0, 24)
        rmask, gmask, bmask, amask = s.get_masks()
        if self.lilendian:
            if rmask == 0x0000FF:
                color_step = 1
                addr_offset = 0
            else:
                color_step = -1
                addr_offset = 2
        else:
            if rmask == 0xFF0000:
                color_step = 1
                addr_offset = 0
            else:
                color_step = -1
                addr_offset = 2
        a = s.get_view("3")
        b = Importer(a, buftools.PyBUF_STRIDES)
        w, h = s.get_size()
        shape = w, h, 3
        strides = 3, s.get_pitch(), color_step
        self.assertEqual(b.ndim, 3)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, 1)
        self.assertEqual(b.shape, shape)
        self.assertEqual(b.strides, strides)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address + addr_offset)
        b = Importer(a, buftools.PyBUF_RECORDS_RO)
        self.assertEqual(b.ndim, 3)
        self.assertEqual(b.format, "B")
        self.assertEqual(b.strides, strides)
        b = Importer(a, buftools.PyBUF_RECORDS)
        self.assertEqual(b.ndim, 3)
        self.assertEqual(b.format, "B")
        self.assertEqual(b.strides, strides)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_SIMPLE)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_FORMAT)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_WRITABLE)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_F_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_ANY_CONTIGUOUS)

    @unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
    def test_newbuf_PyBUF_flags_rgba(self):
        # All color plane views are handled by the same routine,
        # so only one plane need be checked.
        from pygame.tests.test_utils import buftools

        Importer = buftools.Importer
        s = pygame.Surface((12, 6), 0, 24)
        rmask, gmask, bmask, amask = s.get_masks()
        if self.lilendian:
            if rmask == 0x0000FF:
                addr_offset = 0
            else:
                addr_offset = 2
        else:
            if rmask == 0xFF0000:
                addr_offset = 0
            else:
                addr_offset = 2
        a = s.get_view("R")
        b = Importer(a, buftools.PyBUF_STRIDES)
        w, h = s.get_size()
        shape = w, h
        strides = s.get_bytesize(), s.get_pitch()
        self.assertEqual(b.ndim, 2)
        self.assertTrue(b.format is None)
        self.assertEqual(b.len, a.length)
        self.assertEqual(b.itemsize, 1)
        self.assertEqual(b.shape, shape)
        self.assertEqual(b.strides, strides)
        self.assertTrue(b.suboffsets is None)
        self.assertFalse(b.readonly)
        self.assertEqual(b.buf, s._pixels_address + addr_offset)
        b = Importer(a, buftools.PyBUF_RECORDS_RO)
        self.assertEqual(b.ndim, 2)
        self.assertEqual(b.format, "B")
        self.assertEqual(b.strides, strides)
        b = Importer(a, buftools.PyBUF_RECORDS)
        self.assertEqual(b.ndim, 2)
        self.assertEqual(b.format, "B")
        self.assertEqual(b.strides, strides)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_SIMPLE)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_FORMAT)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_WRITABLE)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_F_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, a, buftools.PyBUF_ANY_CONTIGUOUS)


class SurfaceBlendTest(unittest.TestCase):
    def setUp(self):
        # Needed for 8 bits-per-pixel color palette surface tests.
        pygame.display.init()

    def tearDown(self):
        pygame.display.quit()

    _test_palette = [
        (0, 0, 0, 255),
        (10, 30, 60, 0),
        (25, 75, 100, 128),
        (200, 150, 100, 200),
        (0, 100, 200, 255),
    ]
    surf_size = (10, 12)
    _test_points = [
        ((0, 0), 1),
        ((4, 5), 1),
        ((9, 0), 2),
        ((5, 5), 2),
        ((0, 11), 3),
        ((4, 6), 3),
        ((9, 11), 4),
        ((5, 6), 4),
    ]

    def _make_surface(self, bitsize, srcalpha=False, palette=None):
        if palette is None:
            palette = self._test_palette
        flags = 0
        if srcalpha:
            flags |= SRCALPHA
        surf = pygame.Surface(self.surf_size, flags, bitsize)
        if bitsize == 8:
            surf.set_palette([c[:3] for c in palette])
        return surf

    def _fill_surface(self, surf, palette=None):
        if palette is None:
            palette = self._test_palette
        surf.fill(palette[1], (0, 0, 5, 6))
        surf.fill(palette[2], (5, 0, 5, 6))
        surf.fill(palette[3], (0, 6, 5, 6))
        surf.fill(palette[4], (5, 6, 5, 6))

    def _make_src_surface(self, bitsize, srcalpha=False, palette=None):
        surf = self._make_surface(bitsize, srcalpha, palette)
        self._fill_surface(surf, palette)
        return surf

    def _assert_surface(self, surf, palette=None, msg=""):
        if palette is None:
            palette = self._test_palette
        if surf.get_bitsize() == 16:
            palette = [surf.unmap_rgb(surf.map_rgb(c)) for c in palette]
        for posn, i in self._test_points:
            self.assertEqual(
                surf.get_at(posn),
                palette[i],
                "%s != %s: flags: %i, bpp: %i, posn: %s%s"
                % (
                    surf.get_at(posn),
                    palette[i],
                    surf.get_flags(),
                    surf.get_bitsize(),
                    posn,
                    msg,
                ),
            )

    def test_blit_blend(self):
        sources = [
            self._make_src_surface(8),
            self._make_src_surface(16),
            self._make_src_surface(16, srcalpha=True),
            self._make_src_surface(24),
            self._make_src_surface(32),
            self._make_src_surface(32, srcalpha=True),
        ]
        destinations = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]
        blend = [
            ("BLEND_ADD", (0, 25, 100, 255), lambda a, b: min(a + b, 255)),
            ("BLEND_SUB", (100, 25, 0, 100), lambda a, b: max(a - b, 0)),
            ("BLEND_MULT", (100, 200, 0, 0), lambda a, b: ((a * b) + 255) >> 8),
            ("BLEND_MIN", (255, 0, 0, 255), min),
            ("BLEND_MAX", (0, 255, 0, 255), max),
        ]

        for src in sources:
            src_palette = [src.unmap_rgb(src.map_rgb(c)) for c in self._test_palette]
            for dst in destinations:
                for blend_name, dst_color, op in blend:
                    dc = dst.unmap_rgb(dst.map_rgb(dst_color))
                    p = []
                    for sc in src_palette:
                        c = [op(dc[i], sc[i]) for i in range(3)]
                        if dst.get_masks()[3]:
                            c.append(dc[3])
                        else:
                            c.append(255)
                        c = dst.unmap_rgb(dst.map_rgb(c))
                        p.append(c)
                    dst.fill(dst_color)
                    dst.blit(src, (0, 0), special_flags=getattr(pygame, blend_name))
                    self._assert_surface(
                        dst,
                        p,
                        (
                            ", op: %s, src bpp: %i"
                            ", src flags: %i"
                            % (blend_name, src.get_bitsize(), src.get_flags())
                        ),
                    )

        src = self._make_src_surface(32)
        masks = src.get_masks()
        dst = pygame.Surface(
            src.get_size(), 0, 32, [masks[2], masks[1], masks[0], masks[3]]
        )
        for blend_name, dst_color, op in blend:
            p = []
            for src_color in self._test_palette:
                c = [op(dst_color[i], src_color[i]) for i in range(3)]
                c.append(255)
                p.append(tuple(c))
            dst.fill(dst_color)
            dst.blit(src, (0, 0), special_flags=getattr(pygame, blend_name))
            self._assert_surface(dst, p, f", {blend_name}")

        # Blend blits are special cased for 32 to 32 bit surfaces.
        #
        # Confirm that it works when the rgb bytes are not the
        # least significant bytes.
        pat = self._make_src_surface(32)
        masks = pat.get_masks()
        if min(masks) == 0xFF000000:
            masks = [m >> 8 for m in masks]
        else:
            masks = [m << 8 for m in masks]
        src = pygame.Surface(pat.get_size(), 0, 32, masks)
        self._fill_surface(src)
        dst = pygame.Surface(src.get_size(), 0, 32, masks)
        for blend_name, dst_color, op in blend:
            p = []
            for src_color in self._test_palette:
                c = [op(dst_color[i], src_color[i]) for i in range(3)]
                c.append(255)
                p.append(tuple(c))
            dst.fill(dst_color)
            dst.blit(src, (0, 0), special_flags=getattr(pygame, blend_name))
            self._assert_surface(dst, p, f", {blend_name}")

    def test_blit_blend_rgba(self):
        sources = [
            self._make_src_surface(8),
            self._make_src_surface(16),
            self._make_src_surface(16, srcalpha=True),
            self._make_src_surface(24),
            self._make_src_surface(32),
            self._make_src_surface(32, srcalpha=True),
        ]
        destinations = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]
        blend = [
            ("BLEND_RGBA_ADD", (0, 25, 100, 255), lambda a, b: min(a + b, 255)),
            ("BLEND_RGBA_SUB", (0, 25, 100, 255), lambda a, b: max(a - b, 0)),
            ("BLEND_RGBA_MULT", (0, 7, 100, 255), lambda a, b: ((a * b) + 255) >> 8),
            ("BLEND_RGBA_MIN", (0, 255, 0, 255), min),
            ("BLEND_RGBA_MAX", (0, 255, 0, 255), max),
        ]

        for src in sources:
            src_palette = [src.unmap_rgb(src.map_rgb(c)) for c in self._test_palette]
            for dst in destinations:
                for blend_name, dst_color, op in blend:
                    dc = dst.unmap_rgb(dst.map_rgb(dst_color))
                    p = []
                    for sc in src_palette:
                        c = [op(dc[i], sc[i]) for i in range(4)]
                        if not dst.get_masks()[3]:
                            c[3] = 255
                        c = dst.unmap_rgb(dst.map_rgb(c))
                        p.append(c)
                    dst.fill(dst_color)
                    dst.blit(src, (0, 0), special_flags=getattr(pygame, blend_name))
                    self._assert_surface(
                        dst,
                        p,
                        (
                            ", op: %s, src bpp: %i"
                            ", src flags: %i"
                            % (blend_name, src.get_bitsize(), src.get_flags())
                        ),
                    )

        # Blend blits are special cased for 32 to 32 bit surfaces
        # with per-pixel alpha.
        #
        # Confirm the general case is used instead when the formats differ.
        src = self._make_src_surface(32, srcalpha=True)
        masks = src.get_masks()
        dst = pygame.Surface(
            src.get_size(), SRCALPHA, 32, (masks[2], masks[1], masks[0], masks[3])
        )
        for blend_name, dst_color, op in blend:
            p = [
                tuple(op(dst_color[i], src_color[i]) for i in range(4))
                for src_color in self._test_palette
            ]
            dst.fill(dst_color)
            dst.blit(src, (0, 0), special_flags=getattr(pygame, blend_name))
            self._assert_surface(dst, p, f", {blend_name}")

        # Confirm this special case handles subsurfaces.
        src = pygame.Surface((8, 10), SRCALPHA, 32)
        dst = pygame.Surface((8, 10), SRCALPHA, 32)
        tst = pygame.Surface((8, 10), SRCALPHA, 32)
        src.fill((1, 2, 3, 4))
        dst.fill((40, 30, 20, 10))
        subsrc = src.subsurface((2, 3, 4, 4))
        subdst = dst.subsurface((2, 3, 4, 4))
        subdst.blit(subsrc, (0, 0), special_flags=BLEND_RGBA_ADD)
        tst.fill((40, 30, 20, 10))
        tst.fill((41, 32, 23, 14), (2, 3, 4, 4))
        for x in range(8):
            for y in range(10):
                self.assertEqual(
                    dst.get_at((x, y)),
                    tst.get_at((x, y)),
                    "%s != %s at (%i, %i)"
                    % (dst.get_at((x, y)), tst.get_at((x, y)), x, y),
                )

    def test_blit_blend_premultiplied(self):
        def test_premul_surf(
            src_col,
            dst_col,
            src_size=(16, 16),
            dst_size=(16, 16),
            src_bit_depth=32,
            dst_bit_depth=32,
            src_has_alpha=True,
            dst_has_alpha=True,
        ):
            if src_bit_depth == 8:
                src = pygame.Surface(src_size, 0, src_bit_depth)
                palette = [src_col, dst_col]
                src.set_palette(palette)
                src.fill(palette[0])
            elif src_has_alpha:
                src = pygame.Surface(src_size, SRCALPHA, src_bit_depth)
                src.fill(src_col)
            else:
                src = pygame.Surface(src_size, 0, src_bit_depth)
                src.fill(src_col)

            if dst_bit_depth == 8:
                dst = pygame.Surface(dst_size, 0, dst_bit_depth)
                palette = [src_col, dst_col]
                dst.set_palette(palette)
                dst.fill(palette[1])
            elif dst_has_alpha:
                dst = pygame.Surface(dst_size, SRCALPHA, dst_bit_depth)
                dst.fill(dst_col)
            else:
                dst = pygame.Surface(dst_size, 0, dst_bit_depth)
                dst.fill(dst_col)

            dst.blit(src, (0, 0), special_flags=BLEND_PREMULTIPLIED)

            actual_col = dst.get_at(
                (int(float(src_size[0] / 2.0)), int(float(src_size[0] / 2.0)))
            )

            # This is the blend pre-multiplied formula
            if src_col.a == 0:
                expected_col = dst_col
            elif src_col.a == 255:
                expected_col = src_col
            else:
                # sC + dC - (((dC + 1) * sA >> 8)
                expected_col = pygame.Color(
                    (src_col.r + dst_col.r - ((dst_col.r + 1) * src_col.a >> 8)),
                    (src_col.g + dst_col.g - ((dst_col.g + 1) * src_col.a >> 8)),
                    (src_col.b + dst_col.b - ((dst_col.b + 1) * src_col.a >> 8)),
                    (src_col.a + dst_col.a - ((dst_col.a + 1) * src_col.a >> 8)),
                )
            if not dst_has_alpha:
                expected_col.a = 255

            return (expected_col, actual_col)

        # # Colour Tests
        self.assertEqual(
            *test_premul_surf(pygame.Color(40, 20, 0, 51), pygame.Color(40, 20, 0, 51))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(0, 0, 0, 0), pygame.Color(40, 20, 0, 51))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(40, 20, 0, 51), pygame.Color(0, 0, 0, 0))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(0, 0, 0, 0), pygame.Color(0, 0, 0, 0))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(2, 2, 2, 2), pygame.Color(40, 20, 0, 51))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(40, 20, 0, 51), pygame.Color(2, 2, 2, 2))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(2, 2, 2, 2), pygame.Color(2, 2, 2, 2))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(9, 9, 9, 9), pygame.Color(40, 20, 0, 51))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(40, 20, 0, 51), pygame.Color(9, 9, 9, 9))
        )

        self.assertEqual(
            *test_premul_surf(pygame.Color(9, 9, 9, 9), pygame.Color(9, 9, 9, 9))
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(127, 127, 127, 127), pygame.Color(40, 20, 0, 51)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(40, 20, 0, 51), pygame.Color(127, 127, 127, 127)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(127, 127, 127, 127), pygame.Color(127, 127, 127, 127)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(200, 200, 200, 200), pygame.Color(40, 20, 0, 51)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(40, 20, 0, 51), pygame.Color(200, 200, 200, 200)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(200, 200, 200, 200), pygame.Color(200, 200, 200, 200)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(255, 255, 255, 255), pygame.Color(40, 20, 0, 51)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(40, 20, 0, 51), pygame.Color(255, 255, 255, 255)
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(255, 255, 255, 255), pygame.Color(255, 255, 255, 255)
            )
        )

        # Surface format tests
        self.assertRaises(
            IndexError,
            test_premul_surf,
            pygame.Color(255, 255, 255, 255),
            pygame.Color(255, 255, 255, 255),
            src_size=(0, 0),
            dst_size=(0, 0),
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(40, 20, 0, 51),
                pygame.Color(30, 20, 0, 51),
                src_size=(4, 4),
                dst_size=(9, 9),
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 51),
                pygame.Color(40, 20, 0, 51),
                src_size=(17, 67),
                dst_size=(69, 69),
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 51),
                src_size=(17, 67),
                dst_size=(69, 69),
                src_has_alpha=True,
            )
        )
        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 51),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                dst_has_alpha=False,
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                src_has_alpha=False,
                dst_has_alpha=False,
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                dst_bit_depth=24,
                src_has_alpha=True,
                dst_has_alpha=False,
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                src_bit_depth=24,
                src_has_alpha=False,
                dst_has_alpha=True,
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                src_bit_depth=24,
                dst_bit_depth=24,
                src_has_alpha=False,
                dst_has_alpha=False,
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                src_bit_depth=8,
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                dst_bit_depth=8,
            )
        )

        self.assertEqual(
            *test_premul_surf(
                pygame.Color(30, 20, 0, 255),
                pygame.Color(40, 20, 0, 255),
                src_size=(17, 67),
                dst_size=(69, 69),
                src_bit_depth=8,
                dst_bit_depth=8,
            )
        )

    def test_blit_blend_big_rect(self):
        """test that an oversized rect works ok."""
        color = (1, 2, 3, 255)
        area = (1, 1, 30, 30)
        s1 = pygame.Surface((4, 4), 0, 32)
        r = s1.fill(special_flags=pygame.BLEND_ADD, color=color, rect=area)

        self.assertEqual(pygame.Rect((1, 1, 3, 3)), r)
        self.assertEqual(s1.get_at((0, 0)), (0, 0, 0, 255))
        self.assertEqual(s1.get_at((1, 1)), color)

        black = pygame.Color("black")
        red = pygame.Color("red")
        self.assertNotEqual(black, red)

        surf = pygame.Surface((10, 10), 0, 32)
        surf.fill(black)
        subsurf = surf.subsurface(pygame.Rect(0, 1, 10, 8))
        self.assertEqual(surf.get_at((0, 0)), black)
        self.assertEqual(surf.get_at((0, 9)), black)

        subsurf.fill(red, (0, -1, 10, 1), pygame.BLEND_RGB_ADD)
        self.assertEqual(surf.get_at((0, 0)), black)
        self.assertEqual(surf.get_at((0, 9)), black)

        subsurf.fill(red, (0, 8, 10, 1), pygame.BLEND_RGB_ADD)
        self.assertEqual(surf.get_at((0, 0)), black)
        self.assertEqual(surf.get_at((0, 9)), black)

    def test_GET_PIXELVALS(self):
        # surface.h GET_PIXELVALS bug regarding whether of not
        # a surface has per-pixel alpha. Looking at the Amask
        # is not enough. The surface's SRCALPHA flag must also
        # be considered. Fix rev. 1923.
        src = self._make_surface(32, srcalpha=True)
        src.fill((0, 0, 0, 128))
        src.set_alpha(None)  # Clear SRCALPHA flag.
        dst = self._make_surface(32, srcalpha=True)
        dst.blit(src, (0, 0), special_flags=BLEND_RGBA_ADD)
        self.assertEqual(dst.get_at((0, 0)), (0, 0, 0, 255))

    def test_fill_blend(self):
        destinations = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]
        blend = [
            ("BLEND_ADD", (0, 25, 100, 255), lambda a, b: min(a + b, 255)),
            ("BLEND_SUB", (0, 25, 100, 255), lambda a, b: max(a - b, 0)),
            ("BLEND_MULT", (0, 7, 100, 255), lambda a, b: ((a * b) + 255) >> 8),
            ("BLEND_MIN", (0, 255, 0, 255), min),
            ("BLEND_MAX", (0, 255, 0, 255), max),
        ]

        for dst in destinations:
            dst_palette = [dst.unmap_rgb(dst.map_rgb(c)) for c in self._test_palette]
            for blend_name, fill_color, op in blend:
                fc = dst.unmap_rgb(dst.map_rgb(fill_color))
                self._fill_surface(dst)
                p = []
                for dc in dst_palette:
                    c = [op(dc[i], fc[i]) for i in range(3)]
                    if dst.get_masks()[3]:
                        c.append(dc[3])
                    else:
                        c.append(255)
                    c = dst.unmap_rgb(dst.map_rgb(c))
                    p.append(c)
                dst.fill(fill_color, special_flags=getattr(pygame, blend_name))
                self._assert_surface(dst, p, f", {blend_name}")

    def test_fill_blend_rgba(self):
        destinations = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]
        blend = [
            ("BLEND_RGBA_ADD", (0, 25, 100, 255), lambda a, b: min(a + b, 255)),
            ("BLEND_RGBA_SUB", (0, 25, 100, 255), lambda a, b: max(a - b, 0)),
            ("BLEND_RGBA_MULT", (0, 7, 100, 255), lambda a, b: ((a * b) + 255) >> 8),
            ("BLEND_RGBA_MIN", (0, 255, 0, 255), min),
            ("BLEND_RGBA_MAX", (0, 255, 0, 255), max),
        ]

        for dst in destinations:
            dst_palette = [dst.unmap_rgb(dst.map_rgb(c)) for c in self._test_palette]
            for blend_name, fill_color, op in blend:
                fc = dst.unmap_rgb(dst.map_rgb(fill_color))
                self._fill_surface(dst)
                p = []
                for dc in dst_palette:
                    c = [op(dc[i], fc[i]) for i in range(4)]
                    if not dst.get_masks()[3]:
                        c[3] = 255
                    c = dst.unmap_rgb(dst.map_rgb(c))
                    p.append(c)
                dst.fill(fill_color, special_flags=getattr(pygame, blend_name))
                self._assert_surface(dst, p, f", {blend_name}")

    def test_surface_premul_alpha(self):
        """Ensure that .premul_alpha() works correctly"""

        # basic functionality at valid bit depths - 32, 16 & 8
        s1 = pygame.Surface((100, 100), pygame.SRCALPHA, 32)
        s1.fill(pygame.Color(255, 255, 255, 100))
        s1_alpha = s1.premul_alpha()
        self.assertEqual(s1_alpha.get_at((50, 50)), pygame.Color(100, 100, 100, 100))

        # 16 bit colour has less precision
        s2 = pygame.Surface((100, 100), pygame.SRCALPHA, 16)
        s2.fill(
            pygame.Color(
                int(15 / 15 * 255),
                int(15 / 15 * 255),
                int(15 / 15 * 255),
                int(10 / 15 * 255),
            )
        )
        s2_alpha = s2.premul_alpha()
        self.assertEqual(
            s2_alpha.get_at((50, 50)),
            pygame.Color(
                int(10 / 15 * 255),
                int(10 / 15 * 255),
                int(10 / 15 * 255),
                int(10 / 15 * 255),
            ),
        )

        # invalid surface - we need alpha to pre-multiply
        invalid_surf = pygame.Surface((100, 100), 0, 32)
        invalid_surf.fill(pygame.Color(255, 255, 255, 100))
        with self.assertRaises(ValueError):
            invalid_surf.premul_alpha()

        # churn a bunch of values
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
                    surf = pygame.Surface((10, 10), pygame.SRCALPHA, 32)
                    surf.fill(pygame.Color(r, g, b, a))
                    surf = surf.premul_alpha()
                    self.assertEqual(
                        surf.get_at((5, 5)),
                        Color(
                            ((r + 1) * a) >> 8,
                            ((g + 1) * a) >> 8,
                            ((b + 1) * a) >> 8,
                            a,
                        ),
                    )


class SurfaceSelfBlitTest(unittest.TestCase):
    """Blit to self tests.

    This test case is in response to https://github.com/pygame/pygame/issues/19
    """

    def setUp(self):
        # Needed for 8 bits-per-pixel color palette surface tests.
        pygame.display.init()

    def tearDown(self):
        pygame.display.quit()

    _test_palette = [(0, 0, 0, 255), (255, 0, 0, 0), (0, 255, 0, 255)]
    surf_size = (9, 6)

    def _fill_surface(self, surf, palette=None):
        if palette is None:
            palette = self._test_palette
        surf.fill(palette[1])
        surf.fill(palette[2], (1, 2, 1, 2))

    def _make_surface(self, bitsize, srcalpha=False, palette=None):
        if palette is None:
            palette = self._test_palette
        flags = 0
        if srcalpha:
            flags |= SRCALPHA
        surf = pygame.Surface(self.surf_size, flags, bitsize)
        if bitsize == 8:
            surf.set_palette([c[:3] for c in palette])
        self._fill_surface(surf, palette)
        return surf

    def _assert_same(self, a, b):
        w, h = a.get_size()
        for x in range(w):
            for y in range(h):
                self.assertEqual(
                    a.get_at((x, y)),
                    b.get_at((x, y)),
                    (
                        "%s != %s, bpp: %i"
                        % (a.get_at((x, y)), b.get_at((x, y)), a.get_bitsize())
                    ),
                )

    def test_overlap_check(self):
        # Ensure overlapping blits are properly detected. There are two
        # places where this is done, within SoftBlitPyGame() in alphablit.c
        # and PySurface_Blit() in surface.c. SoftBlitPyGame should catch the
        # per-pixel alpha surface, PySurface_Blit the colorkey and blanket
        # alpha surface. per-pixel alpha and blanket alpha self blits are
        # not properly handled by SDL 1.2.13, so Pygame does them.
        bgc = (0, 0, 0, 255)
        rectc_left = (128, 64, 32, 255)
        rectc_right = (255, 255, 255, 255)
        colors = [(255, 255, 255, 255), (128, 64, 32, 255)]
        overlaps = [
            (0, 0, 1, 0, (50, 0)),
            (0, 0, 49, 1, (98, 2)),
            (0, 0, 49, 49, (98, 98)),
            (49, 0, 0, 1, (0, 2)),
            (49, 0, 0, 49, (0, 98)),
        ]
        surfs = [pygame.Surface((100, 100), SRCALPHA, 32)]
        surf = pygame.Surface((100, 100), 0, 32)
        surf.set_alpha(255)
        surfs.append(surf)
        surf = pygame.Surface((100, 100), 0, 32)
        surf.set_colorkey((0, 1, 0))
        surfs.append(surf)
        for surf in surfs:
            for s_x, s_y, d_x, d_y, test_posn in overlaps:
                surf.fill(bgc)
                surf.fill(rectc_right, (25, 0, 25, 50))
                surf.fill(rectc_left, (0, 0, 25, 50))
                surf.blit(surf, (d_x, d_y), (s_x, s_y, 50, 50))
                self.assertEqual(surf.get_at(test_posn), rectc_right)

    # https://github.com/pygame/pygame/issues/370#issuecomment-364625291
    @unittest.skipIf("ppc64le" in platform.uname(), "known ppc64le issue")
    def test_colorkey(self):
        # Check a workaround for an SDL 1.2.13 surface self-blit problem
        # https://github.com/pygame/pygame/issues/19
        pygame.display.set_mode((100, 50))  # Needed for 8bit surface
        bitsizes = [8, 16, 24, 32]
        for bitsize in bitsizes:
            surf = self._make_surface(bitsize)
            surf.set_colorkey(self._test_palette[1])
            surf.blit(surf, (3, 0))
            p = []
            for c in self._test_palette:
                c = surf.unmap_rgb(surf.map_rgb(c))
                p.append(c)
            p[1] = (p[1][0], p[1][1], p[1][2], 0)
            tmp = self._make_surface(32, srcalpha=True, palette=p)
            tmp.blit(tmp, (3, 0))
            tmp.set_alpha(None)
            comp = self._make_surface(bitsize)
            comp.blit(tmp, (0, 0))
            self._assert_same(surf, comp)

    # https://github.com/pygame/pygame/issues/370#issuecomment-364625291
    @unittest.skipIf("ppc64le" in platform.uname(), "known ppc64le issue")
    def test_blanket_alpha(self):
        # Check a workaround for an SDL 1.2.13 surface self-blit problem
        # https://github.com/pygame/pygame/issues/19
        pygame.display.set_mode((100, 50))  # Needed for 8bit surface
        bitsizes = [8, 16, 24, 32]
        for bitsize in bitsizes:
            surf = self._make_surface(bitsize)
            surf.set_alpha(128)
            surf.blit(surf, (3, 0))
            p = []
            for c in self._test_palette:
                c = surf.unmap_rgb(surf.map_rgb(c))
                p.append((c[0], c[1], c[2], 128))
            tmp = self._make_surface(32, srcalpha=True, palette=p)
            tmp.blit(tmp, (3, 0))
            tmp.set_alpha(None)
            comp = self._make_surface(bitsize)
            comp.blit(tmp, (0, 0))
            self._assert_same(surf, comp)

    def test_pixel_alpha(self):
        bitsizes = [16, 32]
        for bitsize in bitsizes:
            surf = self._make_surface(bitsize, srcalpha=True)
            comp = self._make_surface(bitsize, srcalpha=True)
            comp.blit(surf, (3, 0))
            surf.blit(surf, (3, 0))
            self._assert_same(surf, comp)

    def test_blend(self):
        bitsizes = [8, 16, 24, 32]
        blends = ["BLEND_ADD", "BLEND_SUB", "BLEND_MULT", "BLEND_MIN", "BLEND_MAX"]
        for bitsize in bitsizes:
            surf = self._make_surface(bitsize)
            comp = self._make_surface(bitsize)
            for blend in blends:
                self._fill_surface(surf)
                self._fill_surface(comp)
                comp.blit(surf, (3, 0), special_flags=getattr(pygame, blend))
                surf.blit(surf, (3, 0), special_flags=getattr(pygame, blend))
                self._assert_same(surf, comp)

    def test_blend_rgba(self):
        bitsizes = [16, 32]
        blends = [
            "BLEND_RGBA_ADD",
            "BLEND_RGBA_SUB",
            "BLEND_RGBA_MULT",
            "BLEND_RGBA_MIN",
            "BLEND_RGBA_MAX",
        ]
        for bitsize in bitsizes:
            surf = self._make_surface(bitsize, srcalpha=True)
            comp = self._make_surface(bitsize, srcalpha=True)
            for blend in blends:
                self._fill_surface(surf)
                self._fill_surface(comp)
                comp.blit(surf, (3, 0), special_flags=getattr(pygame, blend))
                surf.blit(surf, (3, 0), special_flags=getattr(pygame, blend))
                self._assert_same(surf, comp)

    def test_subsurface(self):
        # Blitting a surface to its subsurface is allowed.
        surf = self._make_surface(32, srcalpha=True)
        comp = surf.copy()
        comp.blit(surf, (3, 0))
        sub = surf.subsurface((3, 0, 6, 6))
        sub.blit(surf, (0, 0))
        del sub
        self._assert_same(surf, comp)

        # Blitting a subsurface to its owner is forbidden because of
        # lock conflicts. This limitation allows the overlap check
        # in PySurface_Blit of alphablit.c to be simplified.
        def do_blit(d, s):
            d.blit(s, (0, 0))

        sub = surf.subsurface((1, 1, 2, 2))
        self.assertRaises(pygame.error, do_blit, surf, sub)

    def test_copy_alpha(self):
        """issue 581: alpha of surface copy with SRCALPHA is set to 0."""
        surf = pygame.Surface((16, 16), pygame.SRCALPHA, 32)
        self.assertEqual(surf.get_alpha(), 255)
        surf2 = surf.copy()
        self.assertEqual(surf2.get_alpha(), 255)


class SurfaceFillTest(unittest.TestCase):
    def setUp(self):
        pygame.display.init()

    def tearDown(self):
        pygame.display.quit()

    def test_fill(self):
        screen = pygame.display.set_mode((640, 480))

        # Green and blue test pattern
        screen.fill((0, 255, 0), (0, 0, 320, 240))
        screen.fill((0, 255, 0), (320, 240, 320, 240))
        screen.fill((0, 0, 255), (320, 0, 320, 240))
        screen.fill((0, 0, 255), (0, 240, 320, 240))

        # Now apply a clip rect, such that only the left side of the
        # screen should be effected by blit operations.
        screen.set_clip((0, 0, 320, 480))

        # Test fills with each special flag, and additionally without any.
        screen.fill((255, 0, 0, 127), (160, 0, 320, 30), 0)
        screen.fill((255, 0, 0, 127), (160, 30, 320, 30), pygame.BLEND_ADD)
        screen.fill((0, 127, 127, 127), (160, 60, 320, 30), pygame.BLEND_SUB)
        screen.fill((0, 63, 63, 127), (160, 90, 320, 30), pygame.BLEND_MULT)
        screen.fill((0, 127, 127, 127), (160, 120, 320, 30), pygame.BLEND_MIN)
        screen.fill((127, 0, 0, 127), (160, 150, 320, 30), pygame.BLEND_MAX)
        screen.fill((255, 0, 0, 127), (160, 180, 320, 30), pygame.BLEND_RGBA_ADD)
        screen.fill((0, 127, 127, 127), (160, 210, 320, 30), pygame.BLEND_RGBA_SUB)
        screen.fill((0, 63, 63, 127), (160, 240, 320, 30), pygame.BLEND_RGBA_MULT)
        screen.fill((0, 127, 127, 127), (160, 270, 320, 30), pygame.BLEND_RGBA_MIN)
        screen.fill((127, 0, 0, 127), (160, 300, 320, 30), pygame.BLEND_RGBA_MAX)
        screen.fill((255, 0, 0, 127), (160, 330, 320, 30), pygame.BLEND_RGB_ADD)
        screen.fill((0, 127, 127, 127), (160, 360, 320, 30), pygame.BLEND_RGB_SUB)
        screen.fill((0, 63, 63, 127), (160, 390, 320, 30), pygame.BLEND_RGB_MULT)
        screen.fill((0, 127, 127, 127), (160, 420, 320, 30), pygame.BLEND_RGB_MIN)
        screen.fill((255, 0, 0, 127), (160, 450, 320, 30), pygame.BLEND_RGB_MAX)

        # Update the display so we can see the results
        pygame.display.flip()

        # Compare colors on both sides of window
        for y in range(5, 480, 10):
            self.assertEqual(screen.get_at((10, y)), screen.get_at((330, 480 - y)))


if __name__ == "__main__":
    unittest.main()
