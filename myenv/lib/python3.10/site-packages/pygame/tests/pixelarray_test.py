import gc
import operator
import platform
import sys
import unittest
import weakref
from functools import reduce

from pygame.tests.test_utils import SurfaceSubclass

try:
    from pygame.tests.test_utils import arrinter
except NameError:
    pass

import pygame


IS_PYPY = "PyPy" == platform.python_implementation()


class TestMixin:
    def assert_surfaces_equal(self, s1, s2, msg=None):
        """Checks if two surfaces are equal in size and color."""
        w, h = s1.get_size()

        self.assertTupleEqual((w, h), s2.get_size(), msg)

        msg = "" if msg is None else f"{msg}, "
        msg += f"size: ({w}, {h})"

        for x in range(w):
            for y in range(h):
                self.assertEqual(
                    s1.get_at((x, y)),
                    s2.get_at((x, y)),
                    f"{msg}, position: ({x}, {y})",
                )

    def assert_surface_filled(self, surface, expected_color, msg=None):
        """Checks if the surface is filled with the given color."""
        width, height = surface.get_size()

        surface.lock()  # Lock for possible speed up.
        for pos in ((x, y) for y in range(height) for x in range(width)):
            self.assertEqual(surface.get_at(pos), expected_color, msg)
        surface.unlock()


@unittest.skipIf(IS_PYPY, "pypy having issues")
class PixelArrayTypeTest(unittest.TestCase, TestMixin):
    def test_compare(self):
        # __doc__ (as of 2008-06-25) for pygame.pixelarray.PixelArray.compare:

        # PixelArray.compare (array, distance=0, weights=(0.299, 0.587, 0.114)): Return PixelArray
        # Compares the PixelArray with another one.

        w = 10
        h = 20
        size = w, h
        sf = pygame.Surface(size, 0, 32)
        ar = pygame.PixelArray(sf)
        sf2 = pygame.Surface(size, 0, 32)
        self.assertRaises(TypeError, ar.compare, sf2)
        ar2 = pygame.PixelArray(sf2)
        ar3 = ar.compare(ar2)
        self.assertTrue(isinstance(ar3, pygame.PixelArray))
        self.assertEqual(ar3.shape, size)
        sf2.fill(pygame.Color("white"))
        self.assert_surfaces_equal(sf2, ar3.surface)
        del ar3
        r = pygame.Rect(2, 5, 6, 13)
        sf.fill(pygame.Color("blue"), r)
        sf2.fill(pygame.Color("red"))
        sf2.fill(pygame.Color("blue"), r)
        ar3 = ar.compare(ar2)
        sf.fill(pygame.Color("white"), r)
        self.assert_surfaces_equal(sf, ar3.surface)

        # FINISH ME!
        # Test other bit depths, slices, and distance != 0.

    def test_compare__same_colors_within_distance(self):
        """Ensures compare works correctly with same colored surfaces."""
        size = (3, 5)
        pixelarray_result_color = pygame.Color("white")
        surface_color = (127, 127, 127, 255)

        for depth in (8, 16, 24, 32):
            expected_pixelarray_surface = pygame.Surface(size, depth=depth)
            expected_pixelarray_surface.fill(pixelarray_result_color)

            # Copy the surface to ensure same dimensions/formatting.
            surf_a = expected_pixelarray_surface.copy()
            surf_a.fill(surface_color)
            # For non-32 bit depths, the actual color can be different from what
            # was filled.
            expected_surface_color = surf_a.get_at((0, 0))

            pixelarray_a = pygame.PixelArray(surf_a)
            pixelarray_b = pygame.PixelArray(surf_a.copy())

            for distance in (0.0, 0.01, 0.1, 1.0):
                pixelarray_result = pixelarray_a.compare(
                    pixelarray_b, distance=distance
                )

                # Ensure the resulting pixelarray is correct and that the original
                # surfaces were not changed.
                self.assert_surfaces_equal(
                    pixelarray_result.surface,
                    expected_pixelarray_surface,
                    (depth, distance),
                )
                self.assert_surface_filled(
                    pixelarray_a.surface, expected_surface_color, (depth, distance)
                )
                self.assert_surface_filled(
                    pixelarray_b.surface, expected_surface_color, (depth, distance)
                )

            pixelarray_a.close()
            pixelarray_b.close()
            pixelarray_result.close()

    def test_compare__different_colors_within_distance(self):
        """Ensures compare works correctly with different colored surfaces
        and the color difference is within the given distance.
        """
        size = (3, 5)
        pixelarray_result_color = pygame.Color("white")
        surface_a_color = (127, 127, 127, 255)
        surface_b_color = (128, 127, 127, 255)

        for depth in (8, 16, 24, 32):
            expected_pixelarray_surface = pygame.Surface(size, depth=depth)
            expected_pixelarray_surface.fill(pixelarray_result_color)

            # Copy the surface to ensure same dimensions/formatting.
            surf_a = expected_pixelarray_surface.copy()
            surf_a.fill(surface_a_color)
            # For non-32 bit depths, the actual color can be different from what
            # was filled.
            expected_surface_a_color = surf_a.get_at((0, 0))
            pixelarray_a = pygame.PixelArray(surf_a)

            surf_b = expected_pixelarray_surface.copy()
            surf_b.fill(surface_b_color)
            # For non-32 bit depths, the actual color can be different from what
            # was filled.
            expected_surface_b_color = surf_b.get_at((0, 0))
            pixelarray_b = pygame.PixelArray(surf_b)

            for distance in (0.2, 0.3, 0.5, 1.0):
                pixelarray_result = pixelarray_a.compare(
                    pixelarray_b, distance=distance
                )

                # Ensure the resulting pixelarray is correct and that the original
                # surfaces were not changed.
                self.assert_surfaces_equal(
                    pixelarray_result.surface,
                    expected_pixelarray_surface,
                    (depth, distance),
                )
                self.assert_surface_filled(
                    pixelarray_a.surface, expected_surface_a_color, (depth, distance)
                )
                self.assert_surface_filled(
                    pixelarray_b.surface, expected_surface_b_color, (depth, distance)
                )

            pixelarray_a.close()
            pixelarray_b.close()
            pixelarray_result.close()

    def test_compare__different_colors_not_within_distance(self):
        """Ensures compare works correctly with different colored surfaces
        and the color difference is not within the given distance.
        """
        size = (3, 5)
        pixelarray_result_color = pygame.Color("black")
        surface_a_color = (127, 127, 127, 255)
        surface_b_color = (128, 127, 127, 255)

        for depth in (8, 16, 24, 32):
            expected_pixelarray_surface = pygame.Surface(size, depth=depth)
            expected_pixelarray_surface.fill(pixelarray_result_color)

            # Copy the surface to ensure same dimensions/formatting.
            surf_a = expected_pixelarray_surface.copy()
            surf_a.fill(surface_a_color)
            # For non-32 bit depths, the actual color can be different from what
            # was filled.
            expected_surface_a_color = surf_a.get_at((0, 0))
            pixelarray_a = pygame.PixelArray(surf_a)

            surf_b = expected_pixelarray_surface.copy()
            surf_b.fill(surface_b_color)
            # For non-32 bit depths, the actual color can be different from what
            # was filled.
            expected_surface_b_color = surf_b.get_at((0, 0))
            pixelarray_b = pygame.PixelArray(surf_b)

            for distance in (0.0, 0.00001, 0.0001, 0.001):
                pixelarray_result = pixelarray_a.compare(
                    pixelarray_b, distance=distance
                )

                # Ensure the resulting pixelarray is correct and that the original
                # surfaces were not changed.
                self.assert_surfaces_equal(
                    pixelarray_result.surface,
                    expected_pixelarray_surface,
                    (depth, distance),
                )
                self.assert_surface_filled(
                    pixelarray_a.surface, expected_surface_a_color, (depth, distance)
                )
                self.assert_surface_filled(
                    pixelarray_b.surface, expected_surface_b_color, (depth, distance)
                )

            pixelarray_a.close()
            pixelarray_b.close()
            pixelarray_result.close()

    def test_close(self):
        """does not crash when it is deleted."""
        s = pygame.Surface((10, 10))
        a = pygame.PixelArray(s)
        a.close()
        del a

    def test_close_raises(self):
        """when you try to do an operation after it is closed."""
        s = pygame.Surface((10, 10))
        a = pygame.PixelArray(s)
        a.close()

        def access_after():
            a[:]

        self.assertRaises(ValueError, access_after)

        def assign_all_after():
            a[:] = 1

        self.assertRaises(ValueError, assign_all_after)

        def make_surface_after():
            a.make_surface()

        self.assertRaises(ValueError, make_surface_after)

        def iter_after():
            for x in a:
                pass

        self.assertRaises(ValueError, iter_after)

        def close_after():
            a.close()

        self.assertRaises(ValueError, close_after)

        def surface_after():
            a.surface

        self.assertRaises(ValueError, surface_after)

        def itemsize_after():
            a.itemsize

        self.assertRaises(ValueError, itemsize_after)

        def transpose_after():
            a.transpose()

        self.assertRaises(ValueError, transpose_after)

    def test_context_manager(self):
        """closes properly."""
        s = pygame.Surface((10, 10))
        with pygame.PixelArray(s) as a:
            a[:]

        # Test pixel array write... will also catch refcount issues and
        # segfault
        with pygame.PixelArray(s) as a:
            a[:] = pygame.Color("deepskyblue")

    def test_pixel_array(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 20), 0, bpp)
            sf.fill((0, 0, 0))
            ar = pygame.PixelArray(sf)

            self.assertEqual(ar._pixels_address, sf._pixels_address)

            if sf.mustlock():
                self.assertTrue(sf.get_locked())

            self.assertEqual(len(ar), 10)

            del ar
            if sf.mustlock():
                self.assertFalse(sf.get_locked())

    def test_as_class(self):
        # Check general new-style class freatures.
        sf = pygame.Surface((2, 3), 0, 32)
        ar = pygame.PixelArray(sf)
        self.assertRaises(AttributeError, getattr, ar, "nonnative")
        ar.nonnative = "value"
        self.assertEqual(ar.nonnative, "value")
        r = weakref.ref(ar)
        self.assertTrue(r() is ar)
        del ar
        gc.collect()
        self.assertTrue(r() is None)

        class C(pygame.PixelArray):
            def __str__(self):
                return "string (%i, %i)" % self.shape

        ar = C(sf)
        self.assertEqual(str(ar), "string (2, 3)")
        r = weakref.ref(ar)
        self.assertTrue(r() is ar)
        del ar
        gc.collect()
        self.assertTrue(r() is None)

    def test_pixelarray__subclassed_surface(self):
        """Ensure the PixelArray constructor accepts subclassed surfaces."""
        surface = SurfaceSubclass((3, 5), 0, 32)
        pixelarray = pygame.PixelArray(surface)

        self.assertIsInstance(pixelarray, pygame.PixelArray)

    # Sequence interfaces
    def test_get_column(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((6, 8), 0, bpp)
            sf.fill((0, 0, 255))
            val = sf.map_rgb((0, 0, 255))
            ar = pygame.PixelArray(sf)

            ar2 = ar.__getitem__(1)
            self.assertEqual(len(ar2), 8)
            self.assertEqual(ar2.__getitem__(0), val)
            self.assertEqual(ar2.__getitem__(1), val)
            self.assertEqual(ar2.__getitem__(2), val)

            ar2 = ar.__getitem__(-1)
            self.assertEqual(len(ar2), 8)
            self.assertEqual(ar2.__getitem__(0), val)
            self.assertEqual(ar2.__getitem__(1), val)
            self.assertEqual(ar2.__getitem__(2), val)

    @unittest.skipIf(IS_PYPY, "pypy malloc abort")
    def test_get_pixel(self):
        w = 10
        h = 20
        size = w, h
        bg_color = (0, 0, 255)
        fg_color_y = (0, 0, 128)
        fg_color_x = (0, 0, 11)
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface(size, 0, bpp)
            mapped_bg_color = sf.map_rgb(bg_color)
            mapped_fg_color_y = sf.map_rgb(fg_color_y)
            mapped_fg_color_x = sf.map_rgb(fg_color_x)
            self.assertNotEqual(
                mapped_fg_color_y,
                mapped_bg_color,
                "Unusable test colors for bpp %i" % (bpp,),
            )
            self.assertNotEqual(
                mapped_fg_color_x,
                mapped_bg_color,
                "Unusable test colors for bpp %i" % (bpp,),
            )
            self.assertNotEqual(
                mapped_fg_color_y,
                mapped_fg_color_x,
                "Unusable test colors for bpp %i" % (bpp,),
            )
            sf.fill(bg_color)

            ar = pygame.PixelArray(sf)

            ar_y = ar.__getitem__(1)
            for y in range(h):
                ar2 = ar_y.__getitem__(y)
                self.assertEqual(
                    ar2,
                    mapped_bg_color,
                    "ar[1][%i] == %i, mapped_bg_color == %i"
                    % (y, ar2, mapped_bg_color),
                )

                sf.set_at((1, y), fg_color_y)
                ar2 = ar_y.__getitem__(y)
                self.assertEqual(
                    ar2,
                    mapped_fg_color_y,
                    "ar[1][%i] == %i, mapped_fg_color_y == %i"
                    % (y, ar2, mapped_fg_color_y),
                )

            sf.set_at((1, 1), bg_color)
            for x in range(w):
                ar2 = ar.__getitem__(x).__getitem__(1)
                self.assertEqual(
                    ar2,
                    mapped_bg_color,
                    "ar[%i][1] = %i, mapped_bg_color = %i" % (x, ar2, mapped_bg_color),
                )
                sf.set_at((x, 1), fg_color_x)
                ar2 = ar.__getitem__(x).__getitem__(1)
                self.assertEqual(
                    ar2,
                    mapped_fg_color_x,
                    "ar[%i][1] = %i, mapped_fg_color_x = %i"
                    % (x, ar2, mapped_fg_color_x),
                )

            ar2 = ar.__getitem__(0).__getitem__(0)
            self.assertEqual(ar2, mapped_bg_color, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(1).__getitem__(0)
            self.assertEqual(ar2, mapped_fg_color_y, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(-4).__getitem__(1)
            self.assertEqual(ar2, mapped_fg_color_x, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(-4).__getitem__(5)
            self.assertEqual(ar2, mapped_bg_color, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(-4).__getitem__(0)
            self.assertEqual(ar2, mapped_bg_color, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(-w + 1).__getitem__(0)
            self.assertEqual(ar2, mapped_fg_color_y, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(-w).__getitem__(0)
            self.assertEqual(ar2, mapped_bg_color, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(5).__getitem__(-4)
            self.assertEqual(ar2, mapped_bg_color, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(5).__getitem__(-h + 1)
            self.assertEqual(ar2, mapped_fg_color_x, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(5).__getitem__(-h)
            self.assertEqual(ar2, mapped_bg_color, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(0).__getitem__(-h + 1)
            self.assertEqual(ar2, mapped_fg_color_x, "bpp = %i" % (bpp,))

            ar2 = ar.__getitem__(0).__getitem__(-h)
            self.assertEqual(ar2, mapped_bg_color, "bpp = %i" % (bpp,))

    def test_set_pixel(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 20), 0, bpp)
            sf.fill((0, 0, 0))
            ar = pygame.PixelArray(sf)

            ar.__getitem__(0).__setitem__(0, (0, 255, 0))
            self.assertEqual(ar[0][0], sf.map_rgb((0, 255, 0)))

            ar.__getitem__(1).__setitem__(1, (128, 128, 128))
            self.assertEqual(ar[1][1], sf.map_rgb((128, 128, 128)))

            ar.__getitem__(-1).__setitem__(-1, (128, 128, 128))
            self.assertEqual(ar[9][19], sf.map_rgb((128, 128, 128)))

            ar.__getitem__(-2).__setitem__(-2, (128, 128, 128))
            self.assertEqual(ar[8][-2], sf.map_rgb((128, 128, 128)))

    def test_set_column(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((6, 8), 0, bpp)
            sf.fill((0, 0, 0))
            ar = pygame.PixelArray(sf)

            sf2 = pygame.Surface((6, 8), 0, bpp)
            sf2.fill((0, 255, 255))
            ar2 = pygame.PixelArray(sf2)

            # Test single value assignment
            ar.__setitem__(2, (128, 128, 128))
            self.assertEqual(ar[2][0], sf.map_rgb((128, 128, 128)))
            self.assertEqual(ar[2][1], sf.map_rgb((128, 128, 128)))

            ar.__setitem__(-1, (0, 255, 255))
            self.assertEqual(ar[5][0], sf.map_rgb((0, 255, 255)))
            self.assertEqual(ar[-1][1], sf.map_rgb((0, 255, 255)))

            ar.__setitem__(-2, (255, 255, 0))
            self.assertEqual(ar[4][0], sf.map_rgb((255, 255, 0)))
            self.assertEqual(ar[-2][1], sf.map_rgb((255, 255, 0)))

            # Test list assignment.
            ar.__setitem__(0, [(255, 255, 255)] * 8)
            self.assertEqual(ar[0][0], sf.map_rgb((255, 255, 255)))
            self.assertEqual(ar[0][1], sf.map_rgb((255, 255, 255)))

            # Test tuple assignment.
            # Changed in Pygame 1.9.2 - Raises an exception.
            self.assertRaises(
                ValueError,
                ar.__setitem__,
                1,
                (
                    (204, 0, 204),
                    (17, 17, 17),
                    (204, 0, 204),
                    (17, 17, 17),
                    (204, 0, 204),
                    (17, 17, 17),
                    (204, 0, 204),
                    (17, 17, 17),
                ),
            )

            # Test pixel array assignment.
            ar.__setitem__(1, ar2.__getitem__(3))
            self.assertEqual(ar[1][0], sf.map_rgb((0, 255, 255)))
            self.assertEqual(ar[1][1], sf.map_rgb((0, 255, 255)))

    def test_get_slice(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 20), 0, bpp)
            sf.fill((0, 0, 0))
            ar = pygame.PixelArray(sf)

            self.assertEqual(len(ar[0:2]), 2)
            self.assertEqual(len(ar[3:7][3]), 20)

            self.assertEqual(ar[0:0], None)
            self.assertEqual(ar[5:5], None)
            self.assertEqual(ar[9:9], None)

            # Has to resolve to ar[7:8]
            self.assertEqual(len(ar[-3:-2]), 1)  # 2D
            self.assertEqual(len(ar[-3:-2][0]), 20)  # 1D

            # Try assignments.

            # 2D assignment.
            ar[2:5] = (255, 255, 255)

            # 1D assignment
            ar[3][3:7] = (10, 10, 10)
            self.assertEqual(ar[3][5], sf.map_rgb((10, 10, 10)))
            self.assertEqual(ar[3][6], sf.map_rgb((10, 10, 10)))

    @unittest.skipIf(IS_PYPY, "skipping for PyPy (segfaults on mac pypy3 6.0.0)")
    def test_contains(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 20), 0, bpp)
            sf.fill((0, 0, 0))
            sf.set_at((8, 8), (255, 255, 255))

            ar = pygame.PixelArray(sf)
            self.assertTrue((0, 0, 0) in ar)
            self.assertTrue((255, 255, 255) in ar)
            self.assertFalse((255, 255, 0) in ar)
            self.assertFalse(0x0000FF in ar)

            # Test sliced array
            self.assertTrue((0, 0, 0) in ar[8])
            self.assertTrue((255, 255, 255) in ar[8])
            self.assertFalse((255, 255, 0) in ar[8])
            self.assertFalse(0x0000FF in ar[8])

    def test_get_surface(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 20), 0, bpp)
            sf.fill((0, 0, 0))
            ar = pygame.PixelArray(sf)
            self.assertTrue(ar.surface is sf)

    def test_get_surface__subclassed_surface(self):
        """Ensure the surface attribute can handle subclassed surfaces."""
        expected_surface = SurfaceSubclass((5, 3), 0, 32)
        pixelarray = pygame.PixelArray(expected_surface)

        surface = pixelarray.surface

        self.assertIs(surface, expected_surface)
        self.assertIsInstance(surface, pygame.Surface)
        self.assertIsInstance(surface, SurfaceSubclass)

    def test_set_slice(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((6, 8), 0, bpp)
            sf.fill((0, 0, 0))
            ar = pygame.PixelArray(sf)

            # Test single value assignment
            val = sf.map_rgb((128, 128, 128))
            ar[0:2] = val
            self.assertEqual(ar[0][0], val)
            self.assertEqual(ar[0][1], val)
            self.assertEqual(ar[1][0], val)
            self.assertEqual(ar[1][1], val)

            val = sf.map_rgb((0, 255, 255))
            ar[-3:-1] = val
            self.assertEqual(ar[3][0], val)
            self.assertEqual(ar[-2][1], val)

            val = sf.map_rgb((255, 255, 255))
            ar[-3:] = (255, 255, 255)
            self.assertEqual(ar[4][0], val)
            self.assertEqual(ar[-1][1], val)

            # Test array size mismatch.
            # Changed in ver. 1.9.2
            # (was "Test list assignment, this is a vertical assignment.")
            val = sf.map_rgb((0, 255, 0))
            self.assertRaises(ValueError, ar.__setitem__, slice(2, 4), [val] * 8)

            # And the horizontal assignment.
            val = sf.map_rgb((255, 0, 0))
            val2 = sf.map_rgb((128, 0, 255))
            ar[0:2] = [val, val2]
            self.assertEqual(ar[0][0], val)
            self.assertEqual(ar[1][0], val2)
            self.assertEqual(ar[0][1], val)
            self.assertEqual(ar[1][1], val2)
            self.assertEqual(ar[0][4], val)
            self.assertEqual(ar[1][4], val2)
            self.assertEqual(ar[0][5], val)
            self.assertEqual(ar[1][5], val2)

            # Test pixelarray assignment.
            ar[:] = (0, 0, 0)
            sf2 = pygame.Surface((6, 8), 0, bpp)
            sf2.fill((255, 0, 255))

            val = sf.map_rgb((255, 0, 255))
            ar2 = pygame.PixelArray(sf2)

            ar[:] = ar2[:]
            self.assertEqual(ar[0][0], val)
            self.assertEqual(ar[5][7], val)

            # Ensure p1 ... pn are freed for array[...] = [p1, ..., pn]
            # Bug fix: reference counting.
            if hasattr(sys, "getrefcount"):

                class Int(int):
                    """Unique int instances"""

                    pass

                sf = pygame.Surface((5, 2), 0, 32)
                ar = pygame.PixelArray(sf)
                pixel_list = [Int(i) for i in range(ar.shape[0])]
                refcnts_before = [sys.getrefcount(i) for i in pixel_list]
                ar[...] = pixel_list
                refcnts_after = [sys.getrefcount(i) for i in pixel_list]
                gc.collect()
                self.assertEqual(refcnts_after, refcnts_before)

    def test_subscript(self):
        # By default we do not need to work with any special __***__
        # methods as map subscripts are the first looked up by the
        # object system.
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((6, 8), 0, bpp)
            sf.set_at((1, 3), (0, 255, 0))
            sf.set_at((0, 0), (0, 255, 0))
            sf.set_at((4, 4), (0, 255, 0))
            val = sf.map_rgb((0, 255, 0))

            ar = pygame.PixelArray(sf)

            # Test single value requests.
            self.assertEqual(ar[1, 3], val)
            self.assertEqual(ar[0, 0], val)
            self.assertEqual(ar[4, 4], val)
            self.assertEqual(ar[1][3], val)
            self.assertEqual(ar[0][0], val)
            self.assertEqual(ar[4][4], val)

            # Test ellipse working.
            self.assertEqual(len(ar[..., ...]), 6)
            self.assertEqual(len(ar[1, ...]), 8)
            self.assertEqual(len(ar[..., 3]), 6)

            # Test simple slicing
            self.assertEqual(len(ar[:, :]), 6)
            self.assertEqual(
                len(ar[:,]),
                6,
            )
            self.assertEqual(len(ar[1, :]), 8)
            self.assertEqual(len(ar[:, 2]), 6)
            # Empty slices
            self.assertEqual(
                ar[4:4,],
                None,
            )
            self.assertEqual(ar[4:4, ...], None)
            self.assertEqual(ar[4:4, 2:2], None)
            self.assertEqual(ar[4:4, 1:4], None)
            self.assertEqual(
                ar[4:4:2,],
                None,
            )
            self.assertEqual(
                ar[4:4:-2,],
                None,
            )
            self.assertEqual(ar[4:4:1, ...], None)
            self.assertEqual(ar[4:4:-1, ...], None)
            self.assertEqual(ar[4:4:1, 2:2], None)
            self.assertEqual(ar[4:4:-1, 1:4], None)
            self.assertEqual(ar[..., 4:4], None)
            self.assertEqual(ar[1:4, 4:4], None)
            self.assertEqual(ar[..., 4:4:1], None)
            self.assertEqual(ar[..., 4:4:-1], None)
            self.assertEqual(ar[2:2, 4:4:1], None)
            self.assertEqual(ar[1:4, 4:4:-1], None)

            # Test advanced slicing
            ar[0] = 0
            ar[1] = 1
            ar[2] = 2
            ar[3] = 3
            ar[4] = 4
            ar[5] = 5

            # We should receive something like [0,2,4]
            self.assertEqual(ar[::2, 1][0], 0)
            self.assertEqual(ar[::2, 1][1], 2)
            self.assertEqual(ar[::2, 1][2], 4)
            # We should receive something like [2,2,2]
            self.assertEqual(ar[2, ::2][0], 2)
            self.assertEqual(ar[2, ::2][1], 2)
            self.assertEqual(ar[2, ::2][2], 2)

            # Should create a 3x3 array of [0,2,4]
            ar2 = ar[::2, ::2]
            self.assertEqual(len(ar2), 3)
            self.assertEqual(ar2[0][0], 0)
            self.assertEqual(ar2[0][1], 0)
            self.assertEqual(ar2[0][2], 0)
            self.assertEqual(ar2[2][0], 4)
            self.assertEqual(ar2[2][1], 4)
            self.assertEqual(ar2[2][2], 4)
            self.assertEqual(ar2[1][0], 2)
            self.assertEqual(ar2[2][0], 4)
            self.assertEqual(ar2[1][1], 2)

            # Should create a reversed 3x8 array over X of [1,2,3] -> [3,2,1]
            ar2 = ar[3:0:-1]
            self.assertEqual(len(ar2), 3)
            self.assertEqual(ar2[0][0], 3)
            self.assertEqual(ar2[0][1], 3)
            self.assertEqual(ar2[0][2], 3)
            self.assertEqual(ar2[0][7], 3)
            self.assertEqual(ar2[2][0], 1)
            self.assertEqual(ar2[2][1], 1)
            self.assertEqual(ar2[2][2], 1)
            self.assertEqual(ar2[2][7], 1)
            self.assertEqual(ar2[1][0], 2)
            self.assertEqual(ar2[1][1], 2)
            # Should completely reverse the array over X -> [5,4,3,2,1,0]
            ar2 = ar[::-1]
            self.assertEqual(len(ar2), 6)
            self.assertEqual(ar2[0][0], 5)
            self.assertEqual(ar2[0][1], 5)
            self.assertEqual(ar2[0][3], 5)
            self.assertEqual(ar2[0][-1], 5)
            self.assertEqual(ar2[1][0], 4)
            self.assertEqual(ar2[1][1], 4)
            self.assertEqual(ar2[1][3], 4)
            self.assertEqual(ar2[1][-1], 4)
            self.assertEqual(ar2[-1][-1], 0)
            self.assertEqual(ar2[-2][-2], 1)
            self.assertEqual(ar2[-3][-1], 2)

            # Test advanced slicing
            ar[:] = 0
            ar2 = ar[:, 1]
            ar2[:] = [99] * len(ar2)
            self.assertEqual(ar2[0], 99)
            self.assertEqual(ar2[-1], 99)
            self.assertEqual(ar2[-2], 99)
            self.assertEqual(ar2[2], 99)
            self.assertEqual(ar[0, 1], 99)
            self.assertEqual(ar[1, 1], 99)
            self.assertEqual(ar[2, 1], 99)
            self.assertEqual(ar[-1, 1], 99)
            self.assertEqual(ar[-2, 1], 99)

            # Cases where a 2d array should have a dimension of length 1.
            ar2 = ar[1:2, :]
            self.assertEqual(ar2.shape, (1, ar.shape[1]))
            ar2 = ar[:, 1:2]
            self.assertEqual(ar2.shape, (ar.shape[0], 1))
            sf2 = pygame.Surface((1, 5), 0, 32)
            ar2 = pygame.PixelArray(sf2)
            self.assertEqual(ar2.shape, sf2.get_size())
            sf2 = pygame.Surface((7, 1), 0, 32)
            ar2 = pygame.PixelArray(sf2)
            self.assertEqual(ar2.shape, sf2.get_size())

            # Array has a single ellipsis subscript: the identity operator
            ar2 = ar[...]
            self.assertTrue(ar2 is ar)

            # Ensure x and y are freed for p = array[x, y]
            # Bug fix: reference counting
            if hasattr(sys, "getrefcount"):

                class Int(int):
                    """Unique int instances"""

                    pass

                sf = pygame.Surface((2, 2), 0, 32)
                ar = pygame.PixelArray(sf)
                x, y = Int(0), Int(1)
                rx_before, ry_before = sys.getrefcount(x), sys.getrefcount(y)
                p = ar[x, y]
                rx_after, ry_after = sys.getrefcount(x), sys.getrefcount(y)
                self.assertEqual(rx_after, rx_before)
                self.assertEqual(ry_after, ry_before)

    def test_ass_subscript(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((6, 8), 0, bpp)
            sf.fill((255, 255, 255))
            ar = pygame.PixelArray(sf)

            # Test ellipse working
            ar[..., ...] = (0, 0, 0)
            self.assertEqual(ar[0, 0], 0)
            self.assertEqual(ar[1, 0], 0)
            self.assertEqual(ar[-1, -1], 0)
            ar[...,] = (0, 0, 255)
            self.assertEqual(ar[0, 0], sf.map_rgb((0, 0, 255)))
            self.assertEqual(ar[1, 0], sf.map_rgb((0, 0, 255)))
            self.assertEqual(ar[-1, -1], sf.map_rgb((0, 0, 255)))
            ar[:, ...] = (255, 0, 0)
            self.assertEqual(ar[0, 0], sf.map_rgb((255, 0, 0)))
            self.assertEqual(ar[1, 0], sf.map_rgb((255, 0, 0)))
            self.assertEqual(ar[-1, -1], sf.map_rgb((255, 0, 0)))
            ar[...] = (0, 255, 0)
            self.assertEqual(ar[0, 0], sf.map_rgb((0, 255, 0)))
            self.assertEqual(ar[1, 0], sf.map_rgb((0, 255, 0)))
            self.assertEqual(ar[-1, -1], sf.map_rgb((0, 255, 0)))

            # Ensure x and y are freed for array[x, y] = p
            # Bug fix: reference counting
            if hasattr(sys, "getrefcount"):

                class Int(int):
                    """Unique int instances"""

                    pass

                sf = pygame.Surface((2, 2), 0, 32)
                ar = pygame.PixelArray(sf)
                x, y = Int(0), Int(1)
                rx_before, ry_before = sys.getrefcount(x), sys.getrefcount(y)
                ar[x, y] = 0
                rx_after, ry_after = sys.getrefcount(x), sys.getrefcount(y)
                self.assertEqual(rx_after, rx_before)
                self.assertEqual(ry_after, ry_before)

    def test_pixels_field(self):
        for bpp in [1, 2, 3, 4]:
            sf = pygame.Surface((11, 7), 0, bpp * 8)
            ar = pygame.PixelArray(sf)
            ar2 = ar[1:, :]
            self.assertEqual(ar2._pixels_address - ar._pixels_address, ar.itemsize)
            ar2 = ar[:, 1:]
            self.assertEqual(ar2._pixels_address - ar._pixels_address, ar.strides[1])
            ar2 = ar[::-1, :]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address,
                (ar.shape[0] - 1) * ar.itemsize,
            )
            ar2 = ar[::-2, :]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address,
                (ar.shape[0] - 1) * ar.itemsize,
            )
            ar2 = ar[:, ::-1]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address,
                (ar.shape[1] - 1) * ar.strides[1],
            )
            ar3 = ar2[::-1, :]
            self.assertEqual(
                ar3._pixels_address - ar._pixels_address,
                (ar.shape[0] - 1) * ar.strides[0] + (ar.shape[1] - 1) * ar.strides[1],
            )
            ar2 = ar[:, ::-2]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address,
                (ar.shape[1] - 1) * ar.strides[1],
            )
            ar2 = ar[2::, 3::]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address,
                ar.strides[0] * 2 + ar.strides[1] * 3,
            )
            ar2 = ar[2::2, 3::4]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address,
                ar.strides[0] * 2 + ar.strides[1] * 3,
            )
            ar2 = ar[9:2:-1, :]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address, ar.strides[0] * 9
            )
            ar2 = ar[:, 5:2:-1]
            self.assertEqual(
                ar2._pixels_address - ar._pixels_address, ar.strides[1] * 5
            )
            ##? ar2 = ar[:,9:2:-1]

    def test_make_surface(self):
        bg_color = pygame.Color(255, 255, 255)
        fg_color = pygame.Color(128, 100, 0)
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 20), 0, bpp)
            bg_color_adj = sf.unmap_rgb(sf.map_rgb(bg_color))
            fg_color_adj = sf.unmap_rgb(sf.map_rgb(fg_color))
            sf.fill(bg_color_adj)
            sf.fill(fg_color_adj, (2, 5, 4, 11))
            ar = pygame.PixelArray(sf)
            newsf = ar[::2, ::2].make_surface()
            rect = newsf.get_rect()
            self.assertEqual(rect.width, 5)
            self.assertEqual(rect.height, 10)
            for p in [
                (0, 2),
                (0, 3),
                (1, 2),
                (2, 2),
                (3, 2),
                (3, 3),
                (0, 7),
                (0, 8),
                (1, 8),
                (2, 8),
                (3, 8),
                (3, 7),
            ]:
                self.assertEqual(newsf.get_at(p), bg_color_adj)
            for p in [(1, 3), (2, 3), (1, 5), (2, 5), (1, 7), (2, 7)]:
                self.assertEqual(newsf.get_at(p), fg_color_adj)

        # Bug when array width is not a multiple of the slice step.
        w = 17
        lst = list(range(w))
        w_slice = len(lst[::2])
        h = 3
        sf = pygame.Surface((w, h), 0, 32)
        ar = pygame.PixelArray(sf)
        ar2 = ar[::2, :]
        sf2 = ar2.make_surface()
        w2, h2 = sf2.get_size()
        self.assertEqual(w2, w_slice)
        self.assertEqual(h2, h)

        # Bug when array height is not a multiple of the slice step.
        # This can hang the Python interpreter.
        h = 17
        lst = list(range(h))
        h_slice = len(lst[::2])
        w = 3
        sf = pygame.Surface((w, h), 0, 32)
        ar = pygame.PixelArray(sf)
        ar2 = ar[:, ::2]
        sf2 = ar2.make_surface()  # Hangs here.
        w2, h2 = sf2.get_size()
        self.assertEqual(w2, w)
        self.assertEqual(h2, h_slice)

    def test_make_surface__subclassed_surface(self):
        """Ensure make_surface can handle subclassed surfaces."""
        expected_size = (3, 5)
        expected_flags = 0
        expected_depth = 32
        original_surface = SurfaceSubclass(
            expected_size, expected_flags, expected_depth
        )
        pixelarray = pygame.PixelArray(original_surface)

        surface = pixelarray.make_surface()

        self.assertIsNot(surface, original_surface)
        self.assertIsInstance(surface, pygame.Surface)
        self.assertNotIsInstance(surface, SurfaceSubclass)
        self.assertEqual(surface.get_size(), expected_size)
        self.assertEqual(surface.get_flags(), expected_flags)
        self.assertEqual(surface.get_bitsize(), expected_depth)

    def test_iter(self):
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((5, 10), 0, bpp)
            ar = pygame.PixelArray(sf)
            iterations = 0
            for col in ar:
                self.assertEqual(len(col), 10)
                iterations += 1
            self.assertEqual(iterations, 5)

    def test_replace(self):
        # print("replace start")
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 10), 0, bpp)
            sf.fill((255, 0, 0))
            rval = sf.map_rgb((0, 0, 255))
            oval = sf.map_rgb((255, 0, 0))
            ar = pygame.PixelArray(sf)
            ar[::2].replace((255, 0, 0), (0, 0, 255))
            self.assertEqual(ar[0][0], rval)
            self.assertEqual(ar[1][0], oval)
            self.assertEqual(ar[2][3], rval)
            self.assertEqual(ar[3][6], oval)
            self.assertEqual(ar[8][9], rval)
            self.assertEqual(ar[9][9], oval)

            ar[::2].replace((0, 0, 255), (255, 0, 0), weights=(10, 20, 50))
            self.assertEqual(ar[0][0], oval)
            self.assertEqual(ar[2][3], oval)
            self.assertEqual(ar[3][6], oval)
            self.assertEqual(ar[8][9], oval)
            self.assertEqual(ar[9][9], oval)
        # print("replace end")

    def test_extract(self):
        # print("extract start")
        for bpp in (8, 16, 24, 32):
            sf = pygame.Surface((10, 10), 0, bpp)
            sf.fill((0, 0, 255))
            sf.fill((255, 0, 0), (2, 2, 6, 6))

            white = sf.map_rgb((255, 255, 255))
            black = sf.map_rgb((0, 0, 0))

            ar = pygame.PixelArray(sf)
            newar = ar.extract((255, 0, 0))

            self.assertEqual(newar[0][0], black)
            self.assertEqual(newar[1][0], black)
            self.assertEqual(newar[2][3], white)
            self.assertEqual(newar[3][6], white)
            self.assertEqual(newar[8][9], black)
            self.assertEqual(newar[9][9], black)

            newar = ar.extract((255, 0, 0), weights=(10, 0.1, 50))
            self.assertEqual(newar[0][0], black)
            self.assertEqual(newar[1][0], black)
            self.assertEqual(newar[2][3], white)
            self.assertEqual(newar[3][6], white)
            self.assertEqual(newar[8][9], black)
            self.assertEqual(newar[9][9], black)
        # print("extract end")

    def test_2dslice_assignment(self):
        w = 2 * 5 * 8
        h = 3 * 5 * 9
        sf = pygame.Surface((w, h), 0, 32)
        ar = pygame.PixelArray(sf)
        size = (w, h)
        strides = (1, w)
        offset = 0
        self._test_assignment(sf, ar, size, strides, offset)
        xslice = slice(None, None, 2)
        yslice = slice(None, None, 3)
        ar, size, strides, offset = self._array_slice(
            ar, size, (xslice, yslice), strides, offset
        )
        self._test_assignment(sf, ar, size, strides, offset)
        xslice = slice(5, None, 5)
        yslice = slice(5, None, 5)
        ar, size, strides, offset = self._array_slice(
            ar, size, (xslice, yslice), strides, offset
        )
        self._test_assignment(sf, ar, size, strides, offset)

    def _test_assignment(self, sf, ar, ar_size, ar_strides, ar_offset):
        self.assertEqual(ar.shape, ar_size)
        ar_w, ar_h = ar_size
        ar_xstride, ar_ystride = ar_strides
        sf_w, sf_h = sf.get_size()
        black = pygame.Color("black")
        color = pygame.Color(0, 0, 12)
        pxcolor = sf.map_rgb(color)
        sf.fill(black)
        for ar_x, ar_y in [
            (0, 0),
            (0, ar_h - 4),
            (ar_w - 3, 0),
            (0, ar_h - 1),
            (ar_w - 1, 0),
            (ar_w - 1, ar_h - 1),
        ]:
            sf_offset = ar_offset + ar_x * ar_xstride + ar_y * ar_ystride
            sf_y = sf_offset // sf_w
            sf_x = sf_offset - sf_y * sf_w
            sf_posn = (sf_x, sf_y)
            sf_pix = sf.get_at(sf_posn)
            self.assertEqual(
                sf_pix,
                black,
                "at pixarr posn (%i, %i) (surf posn (%i, %i)): "
                "%s != %s" % (ar_x, ar_y, sf_x, sf_y, sf_pix, black),
            )
            ar[ar_x, ar_y] = pxcolor
            sf_pix = sf.get_at(sf_posn)
            self.assertEqual(
                sf_pix,
                color,
                "at pixarr posn (%i, %i) (surf posn (%i, %i)): "
                "%s != %s" % (ar_x, ar_y, sf_x, sf_y, sf_pix, color),
            )

    def _array_slice(self, ar, size, slices, strides, offset):
        ar = ar[slices]
        xslice, yslice = slices
        w, h = size
        xstart, xstop, xstep = xslice.indices(w)
        ystart, ystop, ystep = yslice.indices(h)
        w = (xstop - xstart + xstep - 1) // xstep
        h = (ystop - ystart + ystep - 1) // ystep
        xstride, ystride = strides
        offset += xstart * xstride + ystart * ystride
        xstride *= xstep
        ystride *= ystep
        return ar, (w, h), (xstride, ystride), offset

    def test_array_properties(self):
        # itemsize, ndim, shape, and strides.
        for bpp in [1, 2, 3, 4]:
            sf = pygame.Surface((2, 2), 0, bpp * 8)
            ar = pygame.PixelArray(sf)
            self.assertEqual(ar.itemsize, bpp)

        for shape in [(4, 16), (5, 13)]:
            w, h = shape
            sf = pygame.Surface(shape, 0, 32)
            bpp = sf.get_bytesize()
            pitch = sf.get_pitch()
            ar = pygame.PixelArray(sf)
            self.assertEqual(ar.ndim, 2)
            self.assertEqual(ar.shape, shape)
            self.assertEqual(ar.strides, (bpp, pitch))
            ar2 = ar[::2, :]
            w2 = len(([0] * w)[::2])
            self.assertEqual(ar2.ndim, 2)
            self.assertEqual(ar2.shape, (w2, h))
            self.assertEqual(ar2.strides, (2 * bpp, pitch))
            ar2 = ar[:, ::2]
            h2 = len(([0] * h)[::2])
            self.assertEqual(ar2.ndim, 2)
            self.assertEqual(ar2.shape, (w, h2))
            self.assertEqual(ar2.strides, (bpp, 2 * pitch))
            ar2 = ar[1]
            self.assertEqual(ar2.ndim, 1)
            self.assertEqual(ar2.shape, (h,))
            self.assertEqual(ar2.strides, (pitch,))
            ar2 = ar[:, 1]
            self.assertEqual(ar2.ndim, 1)
            self.assertEqual(ar2.shape, (w,))
            self.assertEqual(ar2.strides, (bpp,))

    def test_self_assign(self):
        # This differs from NumPy arrays.
        w = 10
        max_x = w - 1
        h = 20
        max_y = h - 1
        for bpp in [1, 2, 3, 4]:
            sf = pygame.Surface((w, h), 0, bpp * 8)
            ar = pygame.PixelArray(sf)
            for i in range(w * h):
                ar[i % w, i // w] = i
            ar[:, :] = ar[::-1, :]
            for i in range(w * h):
                self.assertEqual(ar[max_x - i % w, i // w], i)
            ar = pygame.PixelArray(sf)
            for i in range(w * h):
                ar[i % w, i // w] = i
            ar[:, :] = ar[:, ::-1]
            for i in range(w * h):
                self.assertEqual(ar[i % w, max_y - i // w], i)
            ar = pygame.PixelArray(sf)
            for i in range(w * h):
                ar[i % w, i // w] = i
            ar[:, :] = ar[::-1, ::-1]
            for i in range(w * h):
                self.assertEqual(ar[max_x - i % w, max_y - i // w], i)

    def test_color_value(self):
        # Confirm that a PixelArray slice assignment distinguishes between
        # pygame.Color and tuple objects as single (r, g, b[, a]) colors
        # and other sequences as sequences of colors to be treated as
        # slices.
        sf = pygame.Surface((5, 5), 0, 32)
        ar = pygame.PixelArray(sf)
        index = slice(None, None, 1)
        ar.__setitem__(index, (1, 2, 3))
        self.assertEqual(ar[0, 0], sf.map_rgb((1, 2, 3)))
        ar.__setitem__(index, pygame.Color(10, 11, 12))
        self.assertEqual(ar[0, 0], sf.map_rgb((10, 11, 12)))
        self.assertRaises(ValueError, ar.__setitem__, index, (1, 2, 3, 4, 5))
        self.assertRaises(ValueError, ar.__setitem__, (index, index), (1, 2, 3, 4, 5))
        self.assertRaises(ValueError, ar.__setitem__, index, [1, 2, 3])
        self.assertRaises(ValueError, ar.__setitem__, (index, index), [1, 2, 3])
        sf = pygame.Surface((3, 3), 0, 32)
        ar = pygame.PixelArray(sf)
        ar[:] = (20, 30, 40)
        self.assertEqual(ar[0, 0], sf.map_rgb((20, 30, 40)))
        ar[:] = [20, 30, 40]
        self.assertEqual(ar[0, 0], 20)
        self.assertEqual(ar[1, 0], 30)
        self.assertEqual(ar[2, 0], 40)

    def test_transpose(self):
        # PixelArray.transpose(): swap axis on a 2D array, add a length
        # 1 x axis to a 1D array.
        sf = pygame.Surface((3, 7), 0, 32)
        ar = pygame.PixelArray(sf)
        w, h = ar.shape
        dx, dy = ar.strides
        for i in range(w * h):
            x = i % w
            y = i // w
            ar[x, y] = i
        ar_t = ar.transpose()
        self.assertEqual(ar_t.shape, (h, w))
        self.assertEqual(ar_t.strides, (dy, dx))
        for i in range(w * h):
            x = i % w
            y = i // w
            self.assertEqual(ar_t[y, x], ar[x, y])
        ar1D = ar[0]
        ar2D = ar1D.transpose()
        self.assertEqual(ar2D.shape, (1, h))
        for y in range(h):
            self.assertEqual(ar1D[y], ar2D[0, y])
        ar1D = ar[:, 0]
        ar2D = ar1D.transpose()
        self.assertEqual(ar2D.shape, (1, w))
        for x in range(2):
            self.assertEqual(ar1D[x], ar2D[0, x])

    def test_length_1_dimension_broadcast(self):
        w = 5
        sf = pygame.Surface((w, w), 0, 32)
        ar = pygame.PixelArray(sf)
        # y-axis broadcast.
        sf_x = pygame.Surface((w, 1), 0, 32)
        ar_x = pygame.PixelArray(sf_x)
        for i in range(w):
            ar_x[i, 0] = (w + 1) * 10
        ar[...] = ar_x
        for y in range(w):
            for x in range(w):
                self.assertEqual(ar[x, y], ar_x[x, 0])
        # x-axis broadcast.
        ar[...] = 0
        sf_y = pygame.Surface((1, w), 0, 32)
        ar_y = pygame.PixelArray(sf_y)
        for i in range(w):
            ar_y[0, i] = (w + 1) * 10
        ar[...] = ar_y
        for x in range(w):
            for y in range(w):
                self.assertEqual(ar[x, y], ar_y[0, y])
        # (1, 1) array broadcast.
        ar[...] = 0
        sf_1px = pygame.Surface((1, 1), 0, 32)
        ar_1px = pygame.PixelArray(sf_1px)
        ar_1px[0, 0] = 42  # Well it had to show up somewhere.
        ar[...] = ar_1px
        for y in range(w):
            for x in range(w):
                self.assertEqual(ar[x, y], 42)

    def test_assign_size_mismatch(self):
        sf = pygame.Surface((7, 11), 0, 32)
        ar = pygame.PixelArray(sf)
        self.assertRaises(ValueError, ar.__setitem__, Ellipsis, ar[:, 0:2])
        self.assertRaises(ValueError, ar.__setitem__, Ellipsis, ar[0:2, :])

    def test_repr(self):
        # Python 3.x bug: the tp_repr slot function returned NULL instead
        # of a Unicode string, triggering an exception.
        sf = pygame.Surface((3, 1), pygame.SRCALPHA, 16)
        ar = pygame.PixelArray(sf)
        ar[...] = 42
        pixel = sf.get_at_mapped((0, 0))
        self.assertEqual(repr(ar), type(ar).__name__ + "([\n  [42, 42, 42]]\n)")


@unittest.skipIf(IS_PYPY, "pypy having issues")
class PixelArrayArrayInterfaceTest(unittest.TestCase, TestMixin):
    @unittest.skipIf(IS_PYPY, "skipping for PyPy (why?)")
    def test_basic(self):
        # Check unchanging fields.
        sf = pygame.Surface((2, 2), 0, 32)
        ar = pygame.PixelArray(sf)

        ai = arrinter.ArrayInterface(ar)
        self.assertEqual(ai.two, 2)
        self.assertEqual(ai.typekind, "u")
        self.assertEqual(ai.nd, 2)
        self.assertEqual(ai.data, ar._pixels_address)

    @unittest.skipIf(IS_PYPY, "skipping for PyPy (why?)")
    def test_shape(self):
        for shape in [[4, 16], [5, 13]]:
            w, h = shape
            sf = pygame.Surface(shape, 0, 32)
            ar = pygame.PixelArray(sf)
            ai = arrinter.ArrayInterface(ar)
            ai_shape = [ai.shape[i] for i in range(ai.nd)]
            self.assertEqual(ai_shape, shape)
            ar2 = ar[::2, :]
            ai2 = arrinter.ArrayInterface(ar2)
            w2 = len(([0] * w)[::2])
            ai_shape = [ai2.shape[i] for i in range(ai2.nd)]
            self.assertEqual(ai_shape, [w2, h])
            ar2 = ar[:, ::2]
            ai2 = arrinter.ArrayInterface(ar2)
            h2 = len(([0] * h)[::2])
            ai_shape = [ai2.shape[i] for i in range(ai2.nd)]
            self.assertEqual(ai_shape, [w, h2])

    @unittest.skipIf(IS_PYPY, "skipping for PyPy (why?)")
    def test_itemsize(self):
        for bytes_per_pixel in range(1, 5):
            bits_per_pixel = 8 * bytes_per_pixel
            sf = pygame.Surface((2, 2), 0, bits_per_pixel)
            ar = pygame.PixelArray(sf)
            ai = arrinter.ArrayInterface(ar)
            self.assertEqual(ai.itemsize, bytes_per_pixel)

    @unittest.skipIf(IS_PYPY, "skipping for PyPy (why?)")
    def test_flags(self):
        aim = arrinter
        common_flags = aim.PAI_NOTSWAPPED | aim.PAI_WRITEABLE | aim.PAI_ALIGNED
        s = pygame.Surface((10, 2), 0, 32)
        ar = pygame.PixelArray(s)
        ai = aim.ArrayInterface(ar)
        self.assertEqual(ai.flags, common_flags | aim.PAI_FORTRAN)

        ar2 = ar[::2, :]
        ai = aim.ArrayInterface(ar2)
        self.assertEqual(ai.flags, common_flags)

        s = pygame.Surface((8, 2), 0, 24)
        ar = pygame.PixelArray(s)
        ai = aim.ArrayInterface(ar)
        self.assertEqual(ai.flags, common_flags | aim.PAI_FORTRAN)

        s = pygame.Surface((7, 2), 0, 24)
        ar = pygame.PixelArray(s)
        ai = aim.ArrayInterface(ar)
        self.assertEqual(ai.flags, common_flags)

    def test_slicing(self):
        # This will implicitly test data and strides fields.
        #
        # Need an 8 bit test surfaces because pixelcopy.make_surface
        # returns an 8 bit surface for a 2d array.

        factors = [7, 3, 11]

        w = reduce(operator.mul, factors, 1)
        h = 13
        sf = pygame.Surface((w, h), 0, 8)
        color = sf.map_rgb((1, 17, 128))
        ar = pygame.PixelArray(sf)
        for f in factors[:-1]:
            w = w // f
            sf.fill((0, 0, 0))
            ar = ar[f : f + w, :]
            ar[0][0] = color
            ar[-1][-2] = color
            ar[0][-3] = color
            sf2 = ar.make_surface()
            sf3 = pygame.pixelcopy.make_surface(ar)
            self.assert_surfaces_equal(sf3, sf2)

        h = reduce(operator.mul, factors, 1)
        w = 13
        sf = pygame.Surface((w, h), 0, 8)
        color = sf.map_rgb((1, 17, 128))
        ar = pygame.PixelArray(sf)
        for f in factors[:-1]:
            h = h // f
            sf.fill((0, 0, 0))
            ar = ar[:, f : f + h]
            ar[0][0] = color
            ar[-1][-2] = color
            ar[0][-3] = color
            sf2 = ar.make_surface()
            sf3 = pygame.pixelcopy.make_surface(ar)
            self.assert_surfaces_equal(sf3, sf2)

        w = 20
        h = 10
        sf = pygame.Surface((w, h), 0, 8)
        color = sf.map_rgb((1, 17, 128))
        ar = pygame.PixelArray(sf)
        for slices in [
            (slice(w), slice(h)),
            (slice(0, w, 2), slice(h)),
            (slice(0, w, 3), slice(h)),
            (slice(w), slice(0, h, 2)),
            (slice(w), slice(0, h, 3)),
            (slice(0, w, 2), slice(0, h, 2)),
            (slice(0, w, 3), slice(0, h, 3)),
        ]:
            sf.fill((0, 0, 0))
            ar2 = ar[slices]
            ar2[0][0] = color
            ar2[-1][-2] = color
            ar2[0][-3] = color
            sf2 = ar2.make_surface()
            sf3 = pygame.pixelcopy.make_surface(ar2)
            self.assert_surfaces_equal(sf3, sf2)


@unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
@unittest.skipIf(IS_PYPY, "pypy having issues")
class PixelArrayNewBufferTest(unittest.TestCase, TestMixin):
    if pygame.HAVE_NEWBUF:
        from pygame.tests.test_utils import buftools

    bitsize_to_format = {8: "B", 16: "=H", 24: "3x", 32: "=I"}

    def test_newbuf_2D(self):
        buftools = self.buftools
        Importer = buftools.Importer

        for bit_size in [8, 16, 24, 32]:
            s = pygame.Surface((10, 2), 0, bit_size)
            ar = pygame.PixelArray(s)
            format = self.bitsize_to_format[bit_size]
            itemsize = ar.itemsize
            shape = ar.shape
            w, h = shape
            strides = ar.strides
            length = w * h * itemsize
            imp = Importer(ar, buftools.PyBUF_FULL)
            self.assertTrue(imp.obj, ar)
            self.assertEqual(imp.len, length)
            self.assertEqual(imp.ndim, 2)
            self.assertEqual(imp.itemsize, itemsize)
            self.assertEqual(imp.format, format)
            self.assertFalse(imp.readonly)
            self.assertEqual(imp.shape, shape)
            self.assertEqual(imp.strides, strides)
            self.assertTrue(imp.suboffsets is None)
            self.assertEqual(imp.buf, s._pixels_address)

        s = pygame.Surface((8, 16), 0, 32)
        ar = pygame.PixelArray(s)
        format = self.bitsize_to_format[s.get_bitsize()]
        itemsize = ar.itemsize
        shape = ar.shape
        w, h = shape
        strides = ar.strides
        length = w * h * itemsize
        imp = Importer(ar, buftools.PyBUF_SIMPLE)
        self.assertTrue(imp.obj, ar)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 0)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertTrue(imp.format is None)
        self.assertFalse(imp.readonly)
        self.assertTrue(imp.shape is None)
        self.assertTrue(imp.strides is None)
        self.assertTrue(imp.suboffsets is None)
        self.assertEqual(imp.buf, s._pixels_address)
        imp = Importer(ar, buftools.PyBUF_FORMAT)
        self.assertEqual(imp.ndim, 0)
        self.assertEqual(imp.format, format)
        imp = Importer(ar, buftools.PyBUF_WRITABLE)
        self.assertEqual(imp.ndim, 0)
        self.assertTrue(imp.format is None)
        imp = Importer(ar, buftools.PyBUF_F_CONTIGUOUS)
        self.assertEqual(imp.ndim, 2)
        self.assertTrue(imp.format is None)
        self.assertEqual(imp.shape, shape)
        self.assertEqual(imp.strides, strides)
        imp = Importer(ar, buftools.PyBUF_ANY_CONTIGUOUS)
        self.assertEqual(imp.ndim, 2)
        self.assertTrue(imp.format is None)
        self.assertEqual(imp.shape, shape)
        self.assertEqual(imp.strides, strides)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_ND)

        ar_sliced = ar[:, ::2]
        format = self.bitsize_to_format[s.get_bitsize()]
        itemsize = ar_sliced.itemsize
        shape = ar_sliced.shape
        w, h = shape
        strides = ar_sliced.strides
        length = w * h * itemsize
        imp = Importer(ar_sliced, buftools.PyBUF_STRIDED)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 2)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertTrue(imp.format is None)
        self.assertFalse(imp.readonly)
        self.assertEqual(imp.shape, shape)
        self.assertEqual(imp.strides, strides)
        self.assertEqual(imp.buf, s._pixels_address)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_SIMPLE)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_F_CONTIGUOUS)
        self.assertRaises(
            BufferError, Importer, ar_sliced, buftools.PyBUF_ANY_CONTIGUOUS
        )

        ar_sliced = ar[::2, :]
        format = self.bitsize_to_format[s.get_bitsize()]
        itemsize = ar_sliced.itemsize
        shape = ar_sliced.shape
        w, h = shape
        strides = ar_sliced.strides
        length = w * h * itemsize
        imp = Importer(ar_sliced, buftools.PyBUF_STRIDED)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 2)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertTrue(imp.format is None)
        self.assertFalse(imp.readonly)
        self.assertEqual(imp.shape, shape)
        self.assertEqual(imp.strides, strides)
        self.assertEqual(imp.buf, s._pixels_address)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_SIMPLE)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, ar_sliced, buftools.PyBUF_F_CONTIGUOUS)
        self.assertRaises(
            BufferError, Importer, ar_sliced, buftools.PyBUF_ANY_CONTIGUOUS
        )

        s2 = s.subsurface((2, 3, 5, 7))
        ar = pygame.PixelArray(s2)
        format = self.bitsize_to_format[s.get_bitsize()]
        itemsize = ar.itemsize
        shape = ar.shape
        w, h = shape
        strides = ar.strides
        length = w * h * itemsize
        imp = Importer(ar, buftools.PyBUF_STRIDES)
        self.assertTrue(imp.obj, ar)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 2)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertTrue(imp.format is None)
        self.assertFalse(imp.readonly)
        self.assertEqual(imp.shape, shape)
        self.assertEqual(imp.strides, strides)
        self.assertTrue(imp.suboffsets is None)
        self.assertEqual(imp.buf, s2._pixels_address)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_SIMPLE)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_FORMAT)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_WRITABLE)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_F_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_ANY_CONTIGUOUS)

    def test_newbuf_1D(self):
        buftools = self.buftools
        Importer = buftools.Importer

        s = pygame.Surface((2, 16), 0, 32)
        ar_2D = pygame.PixelArray(s)
        x = 0
        ar = ar_2D[x]
        format = self.bitsize_to_format[s.get_bitsize()]
        itemsize = ar.itemsize
        shape = ar.shape
        h = shape[0]
        strides = ar.strides
        length = h * itemsize
        buf = s._pixels_address + x * itemsize
        imp = Importer(ar, buftools.PyBUF_STRIDES)
        self.assertTrue(imp.obj, ar)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 1)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertTrue(imp.format is None)
        self.assertFalse(imp.readonly)
        self.assertEqual(imp.shape, shape)
        self.assertEqual(imp.strides, strides)
        self.assertTrue(imp.suboffsets is None)
        self.assertEqual(imp.buf, buf)
        imp = Importer(ar, buftools.PyBUF_FULL)
        self.assertEqual(imp.ndim, 1)
        self.assertEqual(imp.format, format)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_SIMPLE)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_FORMAT)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_WRITABLE)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_ND)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_C_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_F_CONTIGUOUS)
        self.assertRaises(BufferError, Importer, ar, buftools.PyBUF_ANY_CONTIGUOUS)
        y = 10
        ar = ar_2D[:, y]
        shape = ar.shape
        w = shape[0]
        strides = ar.strides
        length = w * itemsize
        buf = s._pixels_address + y * s.get_pitch()
        imp = Importer(ar, buftools.PyBUF_FULL)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 1)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertEqual(imp.format, format)
        self.assertFalse(imp.readonly)
        self.assertEqual(imp.shape, shape)
        self.assertEqual(imp.strides, strides)
        self.assertEqual(imp.buf, buf)
        self.assertTrue(imp.suboffsets is None)
        imp = Importer(ar, buftools.PyBUF_SIMPLE)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 0)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertTrue(imp.format is None)
        self.assertFalse(imp.readonly)
        self.assertTrue(imp.shape is None)
        self.assertTrue(imp.strides is None)
        imp = Importer(ar, buftools.PyBUF_ND)
        self.assertEqual(imp.len, length)
        self.assertEqual(imp.ndim, 1)
        self.assertEqual(imp.itemsize, itemsize)
        self.assertTrue(imp.format is None)
        self.assertFalse(imp.readonly)
        self.assertEqual(imp.shape, shape)
        self.assertTrue(imp.strides is None)
        imp = Importer(ar, buftools.PyBUF_C_CONTIGUOUS)
        self.assertEqual(imp.ndim, 1)
        imp = Importer(ar, buftools.PyBUF_F_CONTIGUOUS)
        self.assertEqual(imp.ndim, 1)
        imp = Importer(ar, buftools.PyBUF_ANY_CONTIGUOUS)
        self.assertEqual(imp.ndim, 1)


if __name__ == "__main__":
    unittest.main()
