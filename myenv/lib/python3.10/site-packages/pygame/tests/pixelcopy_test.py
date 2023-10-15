import platform
import unittest

try:
    from pygame.tests.test_utils import arrinter
except NameError:
    pass
import pygame
from pygame.locals import *
from pygame.pixelcopy import surface_to_array, map_array, array_to_surface, make_surface

IS_PYPY = "PyPy" == platform.python_implementation()


def unsigned32(i):
    """cast signed 32 bit integer to an unsigned integer"""
    return i & 0xFFFFFFFF


@unittest.skipIf(IS_PYPY, "pypy having illegal instruction on mac")
class PixelcopyModuleTest(unittest.TestCase):
    bitsizes = [8, 16, 32]

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

    def __init__(self, *args, **kwds):
        pygame.display.init()
        try:
            unittest.TestCase.__init__(self, *args, **kwds)
            self.sources = [
                self._make_src_surface(8),
                self._make_src_surface(16),
                self._make_src_surface(16, srcalpha=True),
                self._make_src_surface(24),
                self._make_src_surface(32),
                self._make_src_surface(32, srcalpha=True),
            ]
        finally:
            pygame.display.quit()

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

    def setUp(self):
        pygame.display.init()

    def tearDown(self):
        pygame.display.quit()

    def test_surface_to_array_2d(self):
        alpha_color = (0, 0, 0, 128)

        for surf in self.sources:
            src_bitsize = surf.get_bitsize()
            for dst_bitsize in self.bitsizes:
                # dst in a surface standing in for a 2 dimensional array
                # of unsigned integers. The byte order is system dependent.
                dst = pygame.Surface(surf.get_size(), 0, dst_bitsize)
                dst.fill((0, 0, 0, 0))
                view = dst.get_view("2")
                self.assertFalse(surf.get_locked())
                if dst_bitsize < src_bitsize:
                    self.assertRaises(ValueError, surface_to_array, view, surf)
                    self.assertFalse(surf.get_locked())
                    continue
                surface_to_array(view, surf)
                self.assertFalse(surf.get_locked())
                for posn, i in self.test_points:
                    sp = surf.get_at_mapped(posn)
                    dp = dst.get_at_mapped(posn)
                    self.assertEqual(
                        dp,
                        sp,
                        "%s != %s: flags: %i"
                        ", bpp: %i, posn: %s"
                        % (dp, sp, surf.get_flags(), surf.get_bitsize(), posn),
                    )
                del view

                if surf.get_masks()[3]:
                    dst.fill((0, 0, 0, 0))
                    view = dst.get_view("2")
                    posn = (2, 1)
                    surf.set_at(posn, alpha_color)
                    self.assertFalse(surf.get_locked())
                    surface_to_array(view, surf)
                    self.assertFalse(surf.get_locked())
                    sp = surf.get_at_mapped(posn)
                    dp = dst.get_at_mapped(posn)
                    self.assertEqual(
                        dp, sp, "%s != %s: bpp: %i" % (dp, sp, surf.get_bitsize())
                    )

        if IS_PYPY:
            return
        # Swapped endian destination array
        pai_flags = arrinter.PAI_ALIGNED | arrinter.PAI_WRITEABLE
        for surf in self.sources:
            for itemsize in [1, 2, 4, 8]:
                if itemsize < surf.get_bytesize():
                    continue
                a = arrinter.Array(surf.get_size(), "u", itemsize, flags=pai_flags)
                surface_to_array(a, surf)
                for posn, i in self.test_points:
                    sp = unsigned32(surf.get_at_mapped(posn))
                    dp = a[posn]
                    self.assertEqual(
                        dp,
                        sp,
                        "%s != %s: itemsize: %i, flags: %i"
                        ", bpp: %i, posn: %s"
                        % (
                            dp,
                            sp,
                            itemsize,
                            surf.get_flags(),
                            surf.get_bitsize(),
                            posn,
                        ),
                    )

    def test_surface_to_array_3d(self):
        self.iter_surface_to_array_3d((0xFF, 0xFF00, 0xFF0000, 0))
        self.iter_surface_to_array_3d((0xFF0000, 0xFF00, 0xFF, 0))

    def iter_surface_to_array_3d(self, rgba_masks):
        dst = pygame.Surface(self.surf_size, 0, 24, masks=rgba_masks)

        for surf in self.sources:
            dst.fill((0, 0, 0, 0))
            src_bitsize = surf.get_bitsize()
            view = dst.get_view("3")
            self.assertFalse(surf.get_locked())
            surface_to_array(view, surf)
            self.assertFalse(surf.get_locked())
            for posn, i in self.test_points:
                sc = surf.get_at(posn)[0:3]
                dc = dst.get_at(posn)[0:3]
                self.assertEqual(
                    dc,
                    sc,
                    "%s != %s: flags: %i"
                    ", bpp: %i, posn: %s"
                    % (dc, sc, surf.get_flags(), surf.get_bitsize(), posn),
                )
            view = None

    def test_map_array(self):
        targets = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]
        source = pygame.Surface(
            self.surf_size, 0, 24, masks=[0xFF, 0xFF00, 0xFF0000, 0]
        )
        self._fill_surface(source)
        source_view = source.get_view("3")  # (w, h, 3)
        for t in targets:
            map_array(t.get_view("2"), source_view, t)
            for posn, i in self.test_points:
                sc = t.map_rgb(source.get_at(posn))
                dc = t.get_at_mapped(posn)
                self.assertEqual(
                    dc,
                    sc,
                    "%s != %s: flags: %i"
                    ", bpp: %i, posn: %s"
                    % (dc, sc, t.get_flags(), t.get_bitsize(), posn),
                )

        color = pygame.Color("salmon")
        color.set_length(3)
        for t in targets:
            map_array(t.get_view("2"), color, t)
            sc = t.map_rgb(color)
            for posn, i in self.test_points:
                dc = t.get_at_mapped(posn)
                self.assertEqual(
                    dc,
                    sc,
                    "%s != %s: flags: %i"
                    ", bpp: %i, posn: %s"
                    % (dc, sc, t.get_flags(), t.get_bitsize(), posn),
                )

        # mismatched shapes
        w, h = source.get_size()
        target = pygame.Surface((w, h + 1), 0, 32)
        self.assertRaises(ValueError, map_array, target, source, target)
        target = pygame.Surface((w - 1, h), 0, 32)
        self.assertRaises(ValueError, map_array, target, source, target)

    def test_array_to_surface_broadcasting(self):
        # target surfaces
        targets = [
            self._make_surface(8),
            self._make_surface(16),
            self._make_surface(16, srcalpha=True),
            self._make_surface(24),
            self._make_surface(32),
            self._make_surface(32, srcalpha=True),
        ]

        w, h = self.surf_size

        # broadcast column
        column = pygame.Surface((1, h), 0, 32)
        for target in targets:
            source = pygame.Surface((1, h), 0, target)
            for y in range(h):
                source.set_at((0, y), pygame.Color(y + 1, y + h + 1, y + 2 * h + 1))
            pygame.pixelcopy.surface_to_array(column.get_view("2"), source)
            pygame.pixelcopy.array_to_surface(target, column.get_view("2"))
            for x in range(w):
                for y in range(h):
                    self.assertEqual(
                        target.get_at_mapped((x, y)), column.get_at_mapped((0, y))
                    )

        # broadcast row
        row = pygame.Surface((w, 1), 0, 32)
        for target in targets:
            source = pygame.Surface((w, 1), 0, target)
            for x in range(w):
                source.set_at((x, 0), pygame.Color(x + 1, x + w + 1, x + 2 * w + 1))
            pygame.pixelcopy.surface_to_array(row.get_view("2"), source)
            pygame.pixelcopy.array_to_surface(target, row.get_view("2"))
            for x in range(w):
                for y in range(h):
                    self.assertEqual(
                        target.get_at_mapped((x, y)), row.get_at_mapped((x, 0))
                    )

        # broadcast pixel
        pixel = pygame.Surface((1, 1), 0, 32)
        for target in targets:
            source = pygame.Surface((1, 1), 0, target)
            source.set_at((0, 0), pygame.Color(13, 47, 101))
            pygame.pixelcopy.surface_to_array(pixel.get_view("2"), source)
            pygame.pixelcopy.array_to_surface(target, pixel.get_view("2"))
            p = pixel.get_at_mapped((0, 0))
            for x in range(w):
                for y in range(h):
                    self.assertEqual(target.get_at_mapped((x, y)), p)


@unittest.skipIf(IS_PYPY, "pypy having illegal instruction on mac")
class PixelCopyTestWithArrayNumpy(unittest.TestCase):
    try:
        import numpy
    except ImportError:
        __tags__ = ["ignore", "subprocess_ignore"]
    else:
        pygame.surfarray.use_arraytype("numpy")

    bitsizes = [8, 16, 32]

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

    pixels2d = {8, 16, 32}
    pixels3d = {24, 32}
    array2d = {8, 16, 24, 32}
    array3d = {24, 32}

    def __init__(self, *args, **kwds):
        import numpy

        self.dst_types = [numpy.uint8, numpy.uint16, numpy.uint32]
        try:
            self.dst_types.append(numpy.uint64)
        except AttributeError:
            pass
        pygame.display.init()
        try:
            unittest.TestCase.__init__(self, *args, **kwds)
            self.sources = [
                self._make_src_surface(8),
                self._make_src_surface(16),
                self._make_src_surface(16, srcalpha=True),
                self._make_src_surface(24),
                self._make_src_surface(32),
                self._make_src_surface(32, srcalpha=True),
            ]
        finally:
            pygame.display.quit()

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

    def setUp(self):
        pygame.display.init()

    def tearDown(self):
        pygame.display.quit()

    def test_surface_to_array_2d(self):
        try:
            from numpy import empty, dtype
        except ImportError:
            return

        palette = self.test_palette
        alpha_color = (0, 0, 0, 128)

        dst_dims = self.surf_size
        destinations = [empty(dst_dims, t) for t in self.dst_types]
        if pygame.get_sdl_byteorder() == pygame.LIL_ENDIAN:
            swapped_dst = empty(dst_dims, dtype(">u4"))
        else:
            swapped_dst = empty(dst_dims, dtype("<u4"))

        for surf in self.sources:
            src_bytesize = surf.get_bytesize()
            for dst in destinations:
                if dst.itemsize < src_bytesize:
                    self.assertRaises(ValueError, surface_to_array, dst, surf)
                    continue
                dst[...] = 0
                self.assertFalse(surf.get_locked())
                surface_to_array(dst, surf)
                self.assertFalse(surf.get_locked())
                for posn, i in self.test_points:
                    sp = unsigned32(surf.get_at_mapped(posn))
                    dp = dst[posn]
                    self.assertEqual(
                        dp,
                        sp,
                        "%s != %s: flags: %i"
                        ", bpp: %i, dtype: %s,  posn: %s"
                        % (
                            dp,
                            sp,
                            surf.get_flags(),
                            surf.get_bitsize(),
                            dst.dtype,
                            posn,
                        ),
                    )

                if surf.get_masks()[3]:
                    posn = (2, 1)
                    surf.set_at(posn, alpha_color)
                    surface_to_array(dst, surf)
                    sp = unsigned32(surf.get_at_mapped(posn))
                    dp = dst[posn]
                    self.assertEqual(
                        dp, sp, "%s != %s: bpp: %i" % (dp, sp, surf.get_bitsize())
                    )

            swapped_dst[...] = 0
            self.assertFalse(surf.get_locked())
            surface_to_array(swapped_dst, surf)
            self.assertFalse(surf.get_locked())
            for posn, i in self.test_points:
                sp = unsigned32(surf.get_at_mapped(posn))
                dp = swapped_dst[posn]
                self.assertEqual(
                    dp,
                    sp,
                    "%s != %s: flags: %i"
                    ", bpp: %i, dtype: %s,  posn: %s"
                    % (dp, sp, surf.get_flags(), surf.get_bitsize(), dst.dtype, posn),
                )

            if surf.get_masks()[3]:
                posn = (2, 1)
                surf.set_at(posn, alpha_color)
                self.assertFalse(surf.get_locked())
                surface_to_array(swapped_dst, surf)
                self.assertFalse(surf.get_locked())
                sp = unsigned32(surf.get_at_mapped(posn))
                dp = swapped_dst[posn]
                self.assertEqual(
                    dp, sp, "%s != %s: bpp: %i" % (dp, sp, surf.get_bitsize())
                )

    def test_surface_to_array_3d(self):
        try:
            from numpy import empty, dtype
        except ImportError:
            return

        palette = self.test_palette

        dst_dims = self.surf_size + (3,)
        destinations = [empty(dst_dims, t) for t in self.dst_types]
        if pygame.get_sdl_byteorder() == pygame.LIL_ENDIAN:
            swapped_dst = empty(dst_dims, dtype(">u4"))
        else:
            swapped_dst = empty(dst_dims, dtype("<u4"))

        for surf in self.sources:
            src_bitsize = surf.get_bitsize()
            for dst in destinations:
                dst[...] = 0
                self.assertFalse(surf.get_locked())
                surface_to_array(dst, surf)
                self.assertFalse(surf.get_locked())
                for posn, i in self.test_points:
                    r_surf, g_surf, b_surf, a_surf = surf.get_at(posn)
                    r_arr, g_arr, b_arr = dst[posn]
                    self.assertEqual(
                        r_arr,
                        r_surf,
                        "%i != %i, color: red, flags: %i"
                        ", bpp: %i, posn: %s"
                        % (r_arr, r_surf, surf.get_flags(), surf.get_bitsize(), posn),
                    )
                    self.assertEqual(
                        g_arr,
                        g_surf,
                        "%i != %i, color: green, flags: %i"
                        ", bpp: %i, posn: %s"
                        % (r_arr, r_surf, surf.get_flags(), surf.get_bitsize(), posn),
                    )
                    self.assertEqual(
                        b_arr,
                        b_surf,
                        "%i != %i, color: blue, flags: %i"
                        ", bpp: %i, posn: %s"
                        % (r_arr, r_surf, surf.get_flags(), surf.get_bitsize(), posn),
                    )

            swapped_dst[...] = 0
            self.assertFalse(surf.get_locked())
            surface_to_array(swapped_dst, surf)
            self.assertFalse(surf.get_locked())
            for posn, i in self.test_points:
                r_surf, g_surf, b_surf, a_surf = surf.get_at(posn)
                r_arr, g_arr, b_arr = swapped_dst[posn]
                self.assertEqual(
                    r_arr,
                    r_surf,
                    "%i != %i, color: red, flags: %i"
                    ", bpp: %i, posn: %s"
                    % (r_arr, r_surf, surf.get_flags(), surf.get_bitsize(), posn),
                )
                self.assertEqual(
                    g_arr,
                    g_surf,
                    "%i != %i, color: green, flags: %i"
                    ", bpp: %i, posn: %s"
                    % (r_arr, r_surf, surf.get_flags(), surf.get_bitsize(), posn),
                )
                self.assertEqual(
                    b_arr,
                    b_surf,
                    "%i != %i, color: blue, flags: %i"
                    ", bpp: %i, posn: %s"
                    % (r_arr, r_surf, surf.get_flags(), surf.get_bitsize(), posn),
                )

    def test_map_array(self):
        try:
            from numpy import array, zeros, uint8, int32, alltrue
        except ImportError:
            return

        surf = pygame.Surface((1, 1), 0, 32)

        # color fill
        color = array([11, 17, 59], uint8)
        target = zeros((5, 7), int32)
        map_array(target, color, surf)

        self.assertTrue(alltrue(target == surf.map_rgb(color)))

        # array column stripes
        stripe = array([[2, 5, 7], [11, 19, 23], [37, 53, 101]], uint8)
        target = zeros((4, stripe.shape[0]), int32)
        map_array(target, stripe, surf)
        target_stripe = array([surf.map_rgb(c) for c in stripe], int32)

        self.assertTrue(alltrue(target == target_stripe))

        # array row stripes
        stripe = array(
            [[[2, 5, 7]], [[11, 19, 24]], [[10, 20, 30]], [[37, 53, 101]]], uint8
        )
        target = zeros((stripe.shape[0], 3), int32)
        map_array(target, stripe, surf)
        target_stripe = array([[surf.map_rgb(c)] for c in stripe[:, 0]], int32)

        self.assertTrue(alltrue(target == target_stripe))

        # mismatched shape
        w = 4
        h = 5
        source = zeros((w, h, 3), uint8)
        target = zeros((w,), int32)
        self.assertRaises(ValueError, map_array, target, source, surf)
        source = zeros((12, w, h + 1), uint8)
        self.assertRaises(ValueError, map_array, target, source, surf)
        source = zeros((12, w - 1, 5), uint8)
        self.assertRaises(ValueError, map_array, target, source, surf)

    ## def test_array_to_surface(self):
    ##     array_to_surface gets a good workout in the surfarray module's
    ##     unit tests under the alias blit_array.

    try:
        numpy
    except NameError:
        # Ensure no methods requiring numpy are run when
        # pixelcopy_test is '__main__'.
        del __init__
        del test_surface_to_array_2d
        del test_surface_to_array_3d
        del test_map_array
    else:
        del numpy


@unittest.skipIf(not pygame.HAVE_NEWBUF, "newbuf not implemented")
@unittest.skipIf(IS_PYPY, "pypy having illegal instruction on mac")
class PixelCopyTestWithArrayNewBuf(unittest.TestCase):
    if pygame.HAVE_NEWBUF:
        from pygame.tests.test_utils import buftools

        class Array2D(buftools.Exporter):
            def __init__(self, initializer):
                from ctypes import cast, POINTER, c_uint32

                Array2D = PixelCopyTestWithArrayNewBuf.Array2D
                super().__init__((3, 5), format="=I", strides=(20, 4))
                self.content = cast(self.buf, POINTER(c_uint32))
                for i, v in enumerate(initializer):
                    self.content[i] = v

            def __getitem__(self, key):
                byte_index = key[0] * 5 + key[1]
                if not (0 <= byte_index < 15):
                    raise IndexError("%s is out of range", key)
                return self.content[byte_index]

        class Array3D(buftools.Exporter):
            def __init__(self, initializer):
                from ctypes import cast, POINTER, c_uint8

                Array3D = PixelCopyTestWithArrayNewBuf.Array3D
                super().__init__((3, 5, 3), format="B", strides=(20, 4, 1))
                self.content = cast(self.buf, POINTER(c_uint8))
                for i, v in enumerate(initializer):
                    self.content[i] = v

            def __getitem__(self, key):
                byte_index = key[0] * 20 + key[1] * 4 + key[2]
                if not (0 <= byte_index < 60):
                    raise IndexError("%s is out of range", key)
                return self.content[byte_index]

    surface = pygame.Surface((3, 5), 0, 32)

    def setUp(self):
        surf = self.surface
        for y in range(5):
            for x in range(3):
                surf.set_at((x, y), (x + 1, 0, y + 1))

    def assertCopy2D(self, surface, array):
        for x in range(0, 3):
            for y in range(0, 5):
                self.assertEqual(surface.get_at_mapped((x, y)), array[x, y])

    def test_surface_to_array_newbuf(self):
        array = self.Array2D(range(0, 15))
        self.assertNotEqual(array.content[0], self.surface.get_at_mapped((0, 0)))
        surface_to_array(array, self.surface)
        self.assertCopy2D(self.surface, array)

    def test_array_to_surface_newbuf(self):
        array = self.Array2D(range(0, 15))
        self.assertNotEqual(array.content[0], self.surface.get_at_mapped((0, 0)))
        array_to_surface(self.surface, array)
        self.assertCopy2D(self.surface, array)

    def test_map_array_newbuf(self):
        array2D = self.Array2D([0] * 15)
        elements = [i + (255 - i << 8) + (99 << 16) for i in range(0, 15)]
        array3D = self.Array3D(elements)
        map_array(array2D, array3D, self.surface)
        for x in range(0, 3):
            for y in range(0, 5):
                p = array3D[x, y, 0], array3D[x, y, 1], array3D[x, y, 2]
                self.assertEqual(self.surface.unmap_rgb(array2D[x, y]), p)

    def test_make_surface_newbuf(self):
        array = self.Array2D(range(10, 160, 10))
        surface = make_surface(array)
        self.assertCopy2D(surface, array)

    def test_format_newbuf(self):
        Exporter = self.buftools.Exporter
        surface = self.surface
        shape = surface.get_size()
        w, h = shape
        for format in [
            "=i",
            "=I",
            "=l",
            "=L",
            "=q",
            "=Q",
            "<i",
            ">i",
            "!i",
            "1i",
            "=1i",
            "@q",
            "q",
            "4x",
            "8x",
        ]:
            surface.fill((255, 254, 253))
            exp = Exporter(shape, format=format)
            exp._buf[:] = [42] * exp.buflen
            array_to_surface(surface, exp)
            for x in range(w):
                for y in range(h):
                    self.assertEqual(surface.get_at((x, y)), (42, 42, 42, 255))
        # Some unsupported formats for array_to_surface and a 32 bit surface
        for format in ["f", "d", "?", "x", "1x", "2x", "3x", "5x", "6x", "7x", "9x"]:
            exp = Exporter(shape, format=format)
            self.assertRaises(ValueError, array_to_surface, surface, exp)


if __name__ == "__main__":
    unittest.main()
