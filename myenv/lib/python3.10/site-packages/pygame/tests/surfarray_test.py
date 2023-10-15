import unittest
import platform

from numpy import (
    uint8,
    uint16,
    uint32,
    uint64,
    zeros,
    float32,
    float64,
    alltrue,
    rint,
    arange,
)

import pygame
from pygame.locals import *

import pygame.surfarray


IS_PYPY = "PyPy" == platform.python_implementation()


@unittest.skipIf(IS_PYPY, "pypy skip known failure")  # TODO
class SurfarrayModuleTest(unittest.TestCase):
    pixels2d = {8: True, 16: True, 24: False, 32: True}
    pixels3d = {8: False, 16: False, 24: True, 32: True}
    array2d = {8: True, 16: True, 24: True, 32: True}
    array3d = {8: False, 16: False, 24: True, 32: True}

    test_palette = [
        (0, 0, 0, 255),
        (10, 30, 60, 255),
        (25, 75, 100, 255),
        (100, 150, 200, 255),
        (0, 100, 200, 255),
    ]
    surf_size = (10, 12)
    test_points = [
        ((0, 0), 1),
        ((4, 5), 1),
        ((9, 0), 2),
        ((5, 5), 2),
        ((0, 11), 3),
        ((4, 6), 3),
        ((9, 11), 4),
        ((5, 6), 4),
    ]

    @classmethod
    def setUpClass(cls):
        # Needed for 8 bits-per-pixel color palette surface tests.
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(cls):
        # This makes sure pygame is always initialized before each test (in
        # case a test calls pygame.quit()).
        if not pygame.get_init():
            pygame.init()

    def _make_surface(self, bitsize, srcalpha=False, palette=None):
        if palette is None:
            palette = self.test_palette
        flags = 0
        if srcalpha:
            flags |= SRCALPHA
        surf = pygame.Surface(self.surf_size, flags, bitsize)
        if bitsize == 8:
            surf.set_palette([c[:3] for c in palette])
        return surf

    def _fill_surface(self, surf, palette=None):
        if palette is None:
            palette = self.test_palette
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
            palette = self.test_palette
        if surf.get_bitsize() == 16:
            palette = [surf.unmap_rgb(surf.map_rgb(c)) for c in palette]
        for posn, i in self.test_points:
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

    def _make_array3d(self, dtype):
        return zeros((self.surf_size[0], self.surf_size[1], 3), dtype)

    def _fill_array2d(self, arr, surf):
        palette = self.test_palette
        arr[:5, :6] = surf.map_rgb(palette[1])
        arr[5:, :6] = surf.map_rgb(palette[2])
        arr[:5, 6:] = surf.map_rgb(palette[3])
        arr[5:, 6:] = surf.map_rgb(palette[4])

    def _fill_array3d(self, arr):
        palette = self.test_palette
        arr[:5, :6] = palette[1][:3]
        arr[5:, :6] = palette[2][:3]
        arr[:5, 6:] = palette[3][:3]
        arr[5:, 6:] = palette[4][:3]

    def _make_src_array3d(self, dtype):
        arr = self._make_array3d(dtype)
        self._fill_array3d(arr)
        return arr

    def _make_array2d(self, dtype):
        return zeros(self.surf_size, dtype)

    def test_array2d(self):
        sources = [
            self._make_src_surface(8),
            self._make_src_surface(16),
            self._make_src_surface(16, srcalpha=True),
            self._make_src_surface(24),
            self._make_src_surface(32),
            self._make_src_surface(32, srcalpha=True),
        ]
        palette = self.test_palette
        alpha_color = (0, 0, 0, 128)

        for surf in sources:
            arr = pygame.surfarray.array2d(surf)
            for posn, i in self.test_points:
                self.assertEqual(
                    arr[posn],
                    surf.get_at_mapped(posn),
                    "%s != %s: flags: %i, bpp: %i, posn: %s"
                    % (
                        arr[posn],
                        surf.get_at_mapped(posn),
                        surf.get_flags(),
                        surf.get_bitsize(),
                        posn,
                    ),
                )

            if surf.get_masks()[3]:
                surf.fill(alpha_color)
                arr = pygame.surfarray.array2d(surf)
                posn = (0, 0)
                self.assertEqual(
                    arr[posn],
                    surf.get_at_mapped(posn),
                    "%s != %s: bpp: %i"
                    % (arr[posn], surf.get_at_mapped(posn), surf.get_bitsize()),
                )

    def test_array3d(self):
        sources = [
            self._make_src_surface(16),
            self._make_src_surface(16, srcalpha=True),
            self._make_src_surface(24),
            self._make_src_surface(32),
            self._make_src_surface(32, srcalpha=True),
        ]
        palette = self.test_palette

        for surf in sources:
            arr = pygame.surfarray.array3d(surf)

            def same_color(ac, sc):
                return ac[0] == sc[0] and ac[1] == sc[1] and ac[2] == sc[2]

            for posn, i in self.test_points:
                self.assertTrue(
                    same_color(arr[posn], surf.get_at(posn)),
                    "%s != %s: flags: %i, bpp: %i, posn: %s"
                    % (
                        tuple(arr[posn]),
                        surf.get_at(posn),
                        surf.get_flags(),
                        surf.get_bitsize(),
                        posn,
                    ),
                )

    def test_array_alpha(self):
        palette = [
            (0, 0, 0, 0),
            (10, 50, 100, 255),
            (60, 120, 240, 130),
            (64, 128, 255, 0),
            (255, 128, 0, 65),
        ]
        targets = [
            self._make_src_surface(8, palette=palette),
            self._make_src_surface(16, palette=palette),
            self._make_src_surface(16, palette=palette, srcalpha=True),
            self._make_src_surface(24, palette=palette),
            self._make_src_surface(32, palette=palette),
            self._make_src_surface(32, palette=palette, srcalpha=True),
        ]

        for surf in targets:
            p = palette
            if surf.get_bitsize() == 16:
                p = [surf.unmap_rgb(surf.map_rgb(c)) for c in p]
            arr = pygame.surfarray.array_alpha(surf)
            if surf.get_masks()[3]:
                for (x, y), i in self.test_points:
                    self.assertEqual(
                        arr[x, y],
                        p[i][3],
                        (
                            "%i != %i, posn: (%i, %i), "
                            "bitsize: %i"
                            % (arr[x, y], p[i][3], x, y, surf.get_bitsize())
                        ),
                    )
            else:
                self.assertTrue(alltrue(arr == 255))

        # No per-pixel alpha when blanket alpha is None.
        for surf in targets:
            blanket_alpha = surf.get_alpha()
            surf.set_alpha(None)
            arr = pygame.surfarray.array_alpha(surf)
            self.assertTrue(
                alltrue(arr == 255),
                "All alpha values should be 255 when"
                " surf.set_alpha(None) has been set."
                " bitsize: %i, flags: %i" % (surf.get_bitsize(), surf.get_flags()),
            )
            surf.set_alpha(blanket_alpha)

        # Bug for per-pixel alpha surface when blanket alpha 0.
        for surf in targets:
            blanket_alpha = surf.get_alpha()
            surf.set_alpha(0)
            arr = pygame.surfarray.array_alpha(surf)
            if surf.get_masks()[3]:
                self.assertFalse(
                    alltrue(arr == 255),
                    "bitsize: %i, flags: %i" % (surf.get_bitsize(), surf.get_flags()),
                )
            else:
                self.assertTrue(
                    alltrue(arr == 255),
                    "bitsize: %i, flags: %i" % (surf.get_bitsize(), surf.get_flags()),
                )
            surf.set_alpha(blanket_alpha)

    def test_array_colorkey(self):
        palette = [
            (0, 0, 0, 0),
            (10, 50, 100, 255),
            (60, 120, 240, 130),
            (64, 128, 255, 0),
            (255, 128, 0, 65),
        ]
        targets = [
            self._make_src_surface(8, palette=palette),
            self._make_src_surface(16, palette=palette),
            self._make_src_surface(16, palette=palette, srcalpha=True),
            self._make_src_surface(24, palette=palette),
            self._make_src_surface(32, palette=palette),
            self._make_src_surface(32, palette=palette, srcalpha=True),
        ]

        for surf in targets:
            p = palette
            if surf.get_bitsize() == 16:
                p = [surf.unmap_rgb(surf.map_rgb(c)) for c in p]
            surf.set_colorkey(None)
            arr = pygame.surfarray.array_colorkey(surf)
            self.assertTrue(alltrue(arr == 255))

            for i in range(1, len(palette)):
                surf.set_colorkey(p[i])
                alphas = [255] * len(p)
                alphas[i] = 0
                arr = pygame.surfarray.array_colorkey(surf)
                for (x, y), j in self.test_points:
                    self.assertEqual(
                        arr[x, y],
                        alphas[j],
                        (
                            "%i != %i, posn: (%i, %i), "
                            "bitsize: %i"
                            % (arr[x, y], alphas[j], x, y, surf.get_bitsize())
                        ),
                    )

    def test_array_red(self):
        self._test_array_rgb("red", 0)

    def test_array_green(self):
        self._test_array_rgb("green", 1)

    def test_array_blue(self):
        self._test_array_rgb("blue", 2)

    def _test_array_rgb(self, operation, mask_posn):
        method_name = "array_" + operation

        array_rgb = getattr(pygame.surfarray, method_name)
        palette = [
            (0, 0, 0, 255),
            (5, 13, 23, 255),
            (29, 31, 37, 255),
            (131, 157, 167, 255),
            (179, 191, 251, 255),
        ]
        plane = [c[mask_posn] for c in palette]

        targets = [
            self._make_src_surface(24, palette=palette),
            self._make_src_surface(32, palette=palette),
            self._make_src_surface(32, palette=palette, srcalpha=True),
        ]

        for surf in targets:
            self.assertFalse(surf.get_locked())
            for (x, y), i in self.test_points:
                surf.fill(palette[i])
                arr = array_rgb(surf)
                self.assertEqual(arr[x, y], plane[i])
                surf.fill((100, 100, 100, 250))
                self.assertEqual(arr[x, y], plane[i])
                self.assertFalse(surf.get_locked())
                del arr

    def test_blit_array(self):
        s = pygame.Surface((10, 10), 0, 24)
        a = pygame.surfarray.array3d(s)
        pygame.surfarray.blit_array(s, a)

        # target surfaces
        targets = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]

        # source arrays
        arrays3d = []
        dtypes = [(8, uint8), (16, uint16), (32, uint32)]
        try:
            dtypes.append((64, uint64))
        except NameError:
            pass
        arrays3d = [(self._make_src_array3d(dtype), None) for __, dtype in dtypes]
        for bitsize in [8, 16, 24, 32]:
            palette = None
            if bitsize == 16:
                s = pygame.Surface((1, 1), 0, 16)
                palette = [s.unmap_rgb(s.map_rgb(c)) for c in self.test_palette]
            if self.pixels3d[bitsize]:
                surf = self._make_src_surface(bitsize)
                arr = pygame.surfarray.pixels3d(surf)
                arrays3d.append((arr, palette))
            if self.array3d[bitsize]:
                surf = self._make_src_surface(bitsize)
                arr = pygame.surfarray.array3d(surf)
                arrays3d.append((arr, palette))
                for sz, dtype in dtypes:
                    arrays3d.append((arr.astype(dtype), palette))

        # tests on arrays
        def do_blit(surf, arr):
            pygame.surfarray.blit_array(surf, arr)

        for surf in targets:
            bitsize = surf.get_bitsize()
            for arr, palette in arrays3d:
                surf.fill((0, 0, 0, 0))
                if bitsize == 8:
                    self.assertRaises(ValueError, do_blit, surf, arr)
                else:
                    pygame.surfarray.blit_array(surf, arr)
                    self._assert_surface(surf, palette)

            if self.pixels2d[bitsize]:
                surf.fill((0, 0, 0, 0))
                s = self._make_src_surface(bitsize, surf.get_flags() & SRCALPHA)
                arr = pygame.surfarray.pixels2d(s)
                pygame.surfarray.blit_array(surf, arr)
                self._assert_surface(surf)

            if self.array2d[bitsize]:
                s = self._make_src_surface(bitsize, surf.get_flags() & SRCALPHA)
                arr = pygame.surfarray.array2d(s)
                for sz, dtype in dtypes:
                    surf.fill((0, 0, 0, 0))
                    if sz >= bitsize:
                        pygame.surfarray.blit_array(surf, arr.astype(dtype))
                        self._assert_surface(surf)
                    else:
                        self.assertRaises(
                            ValueError, do_blit, surf, self._make_array2d(dtype)
                        )

        # Check alpha for 2D arrays
        surf = self._make_surface(16, srcalpha=True)
        arr = zeros(surf.get_size(), uint16)
        arr[...] = surf.map_rgb((0, 128, 255, 64))
        color = surf.unmap_rgb(arr[0, 0])
        pygame.surfarray.blit_array(surf, arr)
        self.assertEqual(surf.get_at((5, 5)), color)

        surf = self._make_surface(32, srcalpha=True)
        arr = zeros(surf.get_size(), uint32)
        color = (0, 111, 255, 63)
        arr[...] = surf.map_rgb(color)
        pygame.surfarray.blit_array(surf, arr)
        self.assertEqual(surf.get_at((5, 5)), color)

        # Check shifts
        arr3d = self._make_src_array3d(uint8)

        shift_tests = [
            (16, [12, 0, 8, 4], [0xF000, 0xF, 0xF00, 0xF0]),
            (24, [16, 0, 8, 0], [0xFF0000, 0xFF, 0xFF00, 0]),
            (32, [0, 16, 24, 8], [0xFF, 0xFF0000, 0xFF000000, 0xFF00]),
        ]

        for bitsize, shifts, masks in shift_tests:
            surf = self._make_surface(bitsize, srcalpha=(shifts[3] != 0))
            palette = None
            if bitsize == 16:
                palette = [surf.unmap_rgb(surf.map_rgb(c)) for c in self.test_palette]

            self.assertRaises(TypeError, surf.set_shifts, shifts)
            self.assertRaises(TypeError, surf.set_masks, masks)

        # Invalid arrays
        surf = pygame.Surface((1, 1), 0, 32)
        t = "abcd"
        self.assertRaises(ValueError, do_blit, surf, t)

        surf_size = self.surf_size
        surf = pygame.Surface(surf_size, 0, 32)
        arr = zeros([surf_size[0], surf_size[1] + 1, 3], uint32)
        self.assertRaises(ValueError, do_blit, surf, arr)
        arr = zeros([surf_size[0] + 1, surf_size[1], 3], uint32)
        self.assertRaises(ValueError, do_blit, surf, arr)

        surf = pygame.Surface((1, 4), 0, 32)
        arr = zeros((4,), uint32)
        self.assertRaises(ValueError, do_blit, surf, arr)
        arr.shape = (1, 1, 1, 4)
        self.assertRaises(ValueError, do_blit, surf, arr)

        # Issue #81: round from float to int
        try:
            rint
        except NameError:
            pass
        else:
            surf = pygame.Surface((10, 10), pygame.SRCALPHA, 32)
            w, h = surf.get_size()
            length = w * h
            for dtype in [float32, float64]:
                surf.fill((255, 255, 255, 0))
                farr = arange(0, length, dtype=dtype)
                farr.shape = w, h
                pygame.surfarray.blit_array(surf, farr)
                for x in range(w):
                    for y in range(h):
                        self.assertEqual(
                            surf.get_at_mapped((x, y)), int(rint(farr[x, y]))
                        )

    # this test should be removed soon, when the function is deleted
    def test_get_arraytype(self):
        array_type = pygame.surfarray.get_arraytype()

        self.assertEqual(array_type, "numpy", f"unknown array type {array_type}")

    # this test should be removed soon, when the function is deleted
    def test_get_arraytypes(self):
        arraytypes = pygame.surfarray.get_arraytypes()
        self.assertIn("numpy", arraytypes)

        for atype in arraytypes:
            self.assertEqual(atype, "numpy", f"unknown array type {atype}")

    def test_make_surface(self):
        # How does one properly test this with 2d arrays. It makes no sense
        # since the pixel format is not entirely dependent on element size.
        # Just make sure the surface pixel size is at least as large as the
        # array element size I guess.
        #
        for bitsize, dtype in [(8, uint8), (16, uint16), (24, uint32)]:
            ## Even this simple assertion fails for 2d arrays. Where's the problem?
            ##            surf = pygame.surfarray.make_surface(self._make_array2d(dtype))
            ##            self.assertGreaterEqual(surf.get_bitsize(), bitsize,
            ##                            "not %i >= %i)" % (surf.get_bitsize(), bitsize))
            ##
            surf = pygame.surfarray.make_surface(self._make_src_array3d(dtype))
            self._assert_surface(surf)

        # Issue #81: round from float to int
        try:
            rint
        except NameError:
            pass
        else:
            w = 9
            h = 11
            length = w * h
            for dtype in [float32, float64]:
                farr = arange(0, length, dtype=dtype)
                farr.shape = w, h
                surf = pygame.surfarray.make_surface(farr)
                for x in range(w):
                    for y in range(h):
                        self.assertEqual(
                            surf.get_at_mapped((x, y)), int(rint(farr[x, y]))
                        )

    def test_map_array(self):
        arr3d = self._make_src_array3d(uint8)
        targets = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]
        palette = self.test_palette

        for surf in targets:
            arr2d = pygame.surfarray.map_array(surf, arr3d)
            for posn, i in self.test_points:
                self.assertEqual(
                    arr2d[posn],
                    surf.map_rgb(palette[i]),
                    "%i != %i, bitsize: %i, flags: %i"
                    % (
                        arr2d[posn],
                        surf.map_rgb(palette[i]),
                        surf.get_bitsize(),
                        surf.get_flags(),
                    ),
                )

        # Exception checks
        self.assertRaises(
            ValueError,
            pygame.surfarray.map_array,
            self._make_surface(32),
            self._make_array2d(uint8),
        )

    def test_pixels2d(self):
        sources = [
            self._make_surface(8),
            self._make_surface(16, srcalpha=True),
            self._make_surface(32, srcalpha=True),
        ]

        for surf in sources:
            self.assertFalse(surf.get_locked())
            arr = pygame.surfarray.pixels2d(surf)
            self.assertTrue(surf.get_locked())
            self._fill_array2d(arr, surf)
            surf.unlock()
            self.assertTrue(surf.get_locked())
            del arr
            self.assertFalse(surf.get_locked())
            self.assertEqual(surf.get_locks(), ())
            self._assert_surface(surf)

        # Error checks
        self.assertRaises(ValueError, pygame.surfarray.pixels2d, self._make_surface(24))

    def test_pixels3d(self):
        sources = [self._make_surface(24), self._make_surface(32)]

        for surf in sources:
            self.assertFalse(surf.get_locked())
            arr = pygame.surfarray.pixels3d(surf)
            self.assertTrue(surf.get_locked())
            self._fill_array3d(arr)
            surf.unlock()
            self.assertTrue(surf.get_locked())
            del arr
            self.assertFalse(surf.get_locked())
            self.assertEqual(surf.get_locks(), ())
            self._assert_surface(surf)

        # Alpha check
        color = (1, 2, 3, 0)
        surf = self._make_surface(32, srcalpha=True)
        arr = pygame.surfarray.pixels3d(surf)
        arr[0, 0] = color[:3]
        self.assertEqual(surf.get_at((0, 0)), color)

        # Error checks
        def do_pixels3d(surf):
            pygame.surfarray.pixels3d(surf)

        self.assertRaises(ValueError, do_pixels3d, self._make_surface(8))
        self.assertRaises(ValueError, do_pixels3d, self._make_surface(16))

    def test_pixels_alpha(self):
        palette = [
            (0, 0, 0, 0),
            (127, 127, 127, 0),
            (127, 127, 127, 85),
            (127, 127, 127, 170),
            (127, 127, 127, 255),
        ]
        alphas = [0, 45, 86, 99, 180]

        surf = self._make_src_surface(32, srcalpha=True, palette=palette)

        self.assertFalse(surf.get_locked())
        arr = pygame.surfarray.pixels_alpha(surf)
        self.assertTrue(surf.get_locked())
        surf.unlock()
        self.assertTrue(surf.get_locked())

        for (x, y), i in self.test_points:
            self.assertEqual(arr[x, y], palette[i][3])

        for (x, y), i in self.test_points:
            alpha = alphas[i]
            arr[x, y] = alpha
            color = (127, 127, 127, alpha)
            self.assertEqual(surf.get_at((x, y)), color, "posn: (%i, %i)" % (x, y))

        del arr
        self.assertFalse(surf.get_locked())
        self.assertEqual(surf.get_locks(), ())

        # Check exceptions.
        def do_pixels_alpha(surf):
            pygame.surfarray.pixels_alpha(surf)

        targets = [(8, False), (16, False), (16, True), (24, False), (32, False)]

        for bitsize, srcalpha in targets:
            self.assertRaises(
                ValueError, do_pixels_alpha, self._make_surface(bitsize, srcalpha)
            )

    def test_pixels_red(self):
        self._test_pixels_rgb("red", 0)

    def test_pixels_green(self):
        self._test_pixels_rgb("green", 1)

    def test_pixels_blue(self):
        self._test_pixels_rgb("blue", 2)

    def _test_pixels_rgb(self, operation, mask_posn):
        method_name = "pixels_" + operation

        pixels_rgb = getattr(pygame.surfarray, method_name)
        palette = [
            (0, 0, 0, 255),
            (5, 13, 23, 255),
            (29, 31, 37, 255),
            (131, 157, 167, 255),
            (179, 191, 251, 255),
        ]
        plane = [c[mask_posn] for c in palette]

        surf24 = self._make_src_surface(24, srcalpha=False, palette=palette)
        surf32 = self._make_src_surface(32, srcalpha=False, palette=palette)
        surf32a = self._make_src_surface(32, srcalpha=True, palette=palette)

        for surf in [surf24, surf32, surf32a]:
            self.assertFalse(surf.get_locked())
            arr = pixels_rgb(surf)
            self.assertTrue(surf.get_locked())
            surf.unlock()
            self.assertTrue(surf.get_locked())

            for (x, y), i in self.test_points:
                self.assertEqual(arr[x, y], plane[i])

            del arr
            self.assertFalse(surf.get_locked())
            self.assertEqual(surf.get_locks(), ())

        # Check exceptions.
        targets = [(8, False), (16, False), (16, True)]

        for bitsize, srcalpha in targets:
            self.assertRaises(
                ValueError, pixels_rgb, self._make_surface(bitsize, srcalpha)
            )

    def test_use_arraytype(self):
        def do_use_arraytype(atype):
            pygame.surfarray.use_arraytype(atype)

        pygame.surfarray.use_arraytype("numpy")
        self.assertEqual(pygame.surfarray.get_arraytype(), "numpy")
        self.assertRaises(ValueError, do_use_arraytype, "not an option")

    def test_surf_lock(self):
        sf = pygame.Surface((5, 5), 0, 32)
        for atype in pygame.surfarray.get_arraytypes():
            pygame.surfarray.use_arraytype(atype)

            ar = pygame.surfarray.pixels2d(sf)
            self.assertTrue(sf.get_locked())

            sf.unlock()
            self.assertTrue(sf.get_locked())

            del ar
            self.assertFalse(sf.get_locked())
            self.assertEqual(sf.get_locks(), ())


if __name__ == "__main__":
    unittest.main()
