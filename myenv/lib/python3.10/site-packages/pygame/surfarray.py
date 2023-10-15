##    pygame - Python Game Library
##    Copyright (C) 2007 Marcus von Appen
##
##    This library is free software; you can redistribute it and/or
##    modify it under the terms of the GNU Library General Public
##    License as published by the Free Software Foundation; either
##    version 2 of the License, or (at your option) any later version.
##
##    This library is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##    Library General Public License for more details.
##
##    You should have received a copy of the GNU Library General Public
##    License along with this library; if not, write to the Free
##    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
##
##    Marcus von Appen
##    mva@sysfault.org

"""pygame module for accessing surface pixel data using array interfaces

Functions to convert between NumPy arrays and Surface objects. This module
will only be functional when pygame can use the external NumPy package.
If NumPy can't be imported, surfarray becomes a MissingModule object.

Every pixel is stored as a single integer value to represent the red,
green, and blue colors. The 8bit images use a value that looks into a
colormap. Pixels with higher depth use a bit packing process to place
three or four values into a single number.

The arrays are indexed by the X axis first, followed by the Y
axis. Arrays that treat the pixels as a single integer are referred to
as 2D arrays. This module can also separate the red, green, and blue
color values into separate indices. These types of arrays are referred
to as 3D arrays, and the last index is 0 for red, 1 for green, and 2 for
blue.
"""


from pygame.pixelcopy import (
    array_to_surface,
    surface_to_array,
    map_array as pix_map_array,
    make_surface as pix_make_surface,
)
import numpy
from numpy import (
    array as numpy_array,
    empty as numpy_empty,
    uint32 as numpy_uint32,
    ndarray as numpy_ndarray,
)

import warnings  # will be removed in the future


# float96 not available on all numpy versions.
numpy_floats = []
for type_name in "float32 float64 float96".split():
    if hasattr(numpy, type_name):
        numpy_floats.append(getattr(numpy, type_name))
# Added below due to deprecation of numpy.float. See issue #2814
numpy_floats.append(float)

# Pixel sizes corresponding to NumPy supported integer sizes, and therefore
# permissible for 2D reference arrays.
_pixel2d_bitdepths = {8, 16, 32}


__all__ = [
    "array2d",
    "array3d",
    "array_alpha",
    "array_blue",
    "array_colorkey",
    "array_green",
    "array_red",
    "array_to_surface",
    "blit_array",
    "get_arraytype",
    "get_arraytypes",
    "make_surface",
    "map_array",
    "pixels2d",
    "pixels3d",
    "pixels_alpha",
    "pixels_blue",
    "pixels_green",
    "pixels_red",
    "surface_to_array",
    "use_arraytype",
]


def blit_array(surface, array):
    """pygame.surfarray.blit_array(Surface, array): return None

    Blit directly from a array values.

    Directly copy values from an array into a Surface. This is faster than
    converting the array into a Surface and blitting. The array must be the
    same dimensions as the Surface and will completely replace all pixel
    values. Only integer, ascii character and record arrays are accepted.

    This function will temporarily lock the Surface as the new values are
    copied.
    """
    if isinstance(array, numpy_ndarray) and array.dtype in numpy_floats:
        array = array.round(0).astype(numpy_uint32)
    return array_to_surface(surface, array)


def make_surface(array):
    """pygame.surfarray.make_surface (array): return Surface

    Copy an array to a new surface.

    Create a new Surface that best resembles the data and format on the
    array. The array can be 2D or 3D with any sized integer values.
    """
    if isinstance(array, numpy_ndarray) and array.dtype in numpy_floats:
        array = array.round(0).astype(numpy_uint32)
    return pix_make_surface(array)


def array2d(surface):
    """pygame.surfarray.array2d(Surface): return array

    copy pixels into a 2d array

    Copy the pixels from a Surface into a 2D array. The bit depth of the
    surface will control the size of the integer values, and will work
    for any type of pixel format.

    This function will temporarily lock the Surface as pixels are copied
    (see the Surface.lock - lock the Surface memory for pixel access
    method).
    """
    bpp = surface.get_bytesize()
    try:
        dtype = (numpy.uint8, numpy.uint16, numpy.int32, numpy.int32)[bpp - 1]
    except IndexError:
        raise ValueError(f"unsupported bit depth {bpp * 8} for 2D array")
    size = surface.get_size()
    array = numpy.empty(size, dtype)
    surface_to_array(array, surface)
    return array


def pixels2d(surface):
    """pygame.surfarray.pixels2d(Surface): return array

    reference pixels into a 2d array

    Create a new 2D array that directly references the pixel values in a
    Surface. Any changes to the array will affect the pixels in the
    Surface. This is a fast operation since no data is copied.

    Pixels from a 24-bit Surface cannot be referenced, but all other
    Surface bit depths can.

    The Surface this references will remain locked for the lifetime of
    the array (see the Surface.lock - lock the Surface memory for pixel
    access method).
    """
    if surface.get_bitsize() not in _pixel2d_bitdepths:
        raise ValueError("unsupported bit depth for 2D reference array")
    try:
        return numpy_array(surface.get_view("2"), copy=False)
    except (ValueError, TypeError):
        raise ValueError(
            f"bit depth {surface.get_bitsize()} unsupported for 2D reference array"
        )


def array3d(surface):
    """pygame.surfarray.array3d(Surface): return array

    copy pixels into a 3d array

    Copy the pixels from a Surface into a 3D array. The bit depth of the
    surface will control the size of the integer values, and will work
    for any type of pixel format.

    This function will temporarily lock the Surface as pixels are copied
    (see the Surface.lock - lock the Surface memory for pixel access
    method).
    """
    width, height = surface.get_size()
    array = numpy.empty((width, height, 3), numpy.uint8)
    surface_to_array(array, surface)
    return array


def pixels3d(surface):
    """pygame.surfarray.pixels3d(Surface): return array

    reference pixels into a 3d array

    Create a new 3D array that directly references the pixel values in a
    Surface. Any changes to the array will affect the pixels in the
    Surface. This is a fast operation since no data is copied.

    This will only work on Surfaces that have 24-bit or 32-bit
    formats. Lower pixel formats cannot be referenced.

    The Surface this references will remain locked for the lifetime of
    the array (see the Surface.lock - lock the Surface memory for pixel
    access method).
    """
    return numpy_array(surface.get_view("3"), copy=False)


def array_alpha(surface):
    """pygame.surfarray.array_alpha(Surface): return array

    copy pixel alphas into a 2d array

    Copy the pixel alpha values (degree of transparency) from a Surface
    into a 2D array. This will work for any type of Surface
    format. Surfaces without a pixel alpha will return an array with all
    opaque values.

    This function will temporarily lock the Surface as pixels are copied
    (see the Surface.lock - lock the Surface memory for pixel access
    method).
    """
    size = surface.get_size()
    array = numpy.empty(size, numpy.uint8)
    surface_to_array(array, surface, "A")
    return array


def pixels_alpha(surface):
    """pygame.surfarray.pixels_alpha(Surface): return array

    reference pixel alphas into a 2d array

    Create a new 2D array that directly references the alpha values
    (degree of transparency) in a Surface. Any changes to the array will
    affect the pixels in the Surface. This is a fast operation since no
    data is copied.

    This can only work on 32-bit Surfaces with a per-pixel alpha value.

    The Surface this array references will remain locked for the
    lifetime of the array.
    """
    return numpy.array(surface.get_view("A"), copy=False)


def pixels_red(surface):
    """pygame.surfarray.pixels_red(Surface): return array

    Reference pixel red into a 2d array.

    Create a new 2D array that directly references the red values
    in a Surface. Any changes to the array will affect the pixels
    in the Surface. This is a fast operation since no data is copied.

    This can only work on 24-bit or 32-bit Surfaces.

    The Surface this array references will remain locked for the
    lifetime of the array.
    """
    return numpy.array(surface.get_view("R"), copy=False)


def array_red(surface):
    """pygame.surfarray.array_red(Surface): return array

    copy pixel red into a 2d array

    Copy the pixel red values from a Surface into a 2D array. This will work
    for any type of Surface format.

    This function will temporarily lock the Surface as pixels are copied
    (see the Surface.lock - lock the Surface memory for pixel access
    method).
    """
    size = surface.get_size()
    array = numpy.empty(size, numpy.uint8)
    surface_to_array(array, surface, "R")
    return array


def pixels_green(surface):
    """pygame.surfarray.pixels_green(Surface): return array

    Reference pixel green into a 2d array.

    Create a new 2D array that directly references the green values
    in a Surface. Any changes to the array will affect the pixels
    in the Surface. This is a fast operation since no data is copied.

    This can only work on 24-bit or 32-bit Surfaces.

    The Surface this array references will remain locked for the
    lifetime of the array.
    """
    return numpy.array(surface.get_view("G"), copy=False)


def array_green(surface):
    """pygame.surfarray.array_green(Surface): return array

    copy pixel green into a 2d array

    Copy the pixel green values from a Surface into a 2D array. This will work
    for any type of Surface format.

    This function will temporarily lock the Surface as pixels are copied
    (see the Surface.lock - lock the Surface memory for pixel access
    method).
    """
    size = surface.get_size()
    array = numpy.empty(size, numpy.uint8)
    surface_to_array(array, surface, "G")
    return array


def pixels_blue(surface):
    """pygame.surfarray.pixels_blue(Surface): return array

    Reference pixel blue into a 2d array.

    Create a new 2D array that directly references the blue values
    in a Surface. Any changes to the array will affect the pixels
    in the Surface. This is a fast operation since no data is copied.

    This can only work on 24-bit or 32-bit Surfaces.

    The Surface this array references will remain locked for the
    lifetime of the array.
    """
    return numpy.array(surface.get_view("B"), copy=False)


def array_blue(surface):
    """pygame.surfarray.array_blue(Surface): return array

    copy pixel blue into a 2d array

    Copy the pixel blue values from a Surface into a 2D array. This will work
    for any type of Surface format.

    This function will temporarily lock the Surface as pixels are copied
    (see the Surface.lock - lock the Surface memory for pixel access
    method).
    """
    size = surface.get_size()
    array = numpy.empty(size, numpy.uint8)
    surface_to_array(array, surface, "B")
    return array


def array_colorkey(surface):
    """pygame.surfarray.array_colorkey(Surface): return array

    copy the colorkey values into a 2d array

    Create a new array with the colorkey transparency value from each
    pixel. If the pixel matches the colorkey it will be fully
    transparent; otherwise it will be fully opaque.

    This will work on any type of Surface format. If the image has no
    colorkey a solid opaque array will be returned.

    This function will temporarily lock the Surface as pixels are
    copied.
    """
    size = surface.get_size()
    array = numpy.empty(size, numpy.uint8)
    surface_to_array(array, surface, "C")
    return array


def map_array(surface, array):
    """pygame.surfarray.map_array(Surface, array3d): return array2d

    map a 3d array into a 2d array

    Convert a 3D array into a 2D array. This will use the given Surface
    format to control the conversion.

    Note: arrays do not need to be 3D, as long as the minor axis has
    three elements giving the component colours, any array shape can be
    used (for example, a single colour can be mapped, or an array of
    colours). The array shape is limited to eleven dimensions maximum,
    including the three element minor axis.
    """
    if array.ndim == 0:
        raise ValueError("array must have at least 1 dimension")
    shape = array.shape
    if shape[-1] != 3:
        raise ValueError("array must be a 3d array of 3-value color data")
    target = numpy_empty(shape[:-1], numpy.int32)
    pix_map_array(target, array, surface)
    return target


def use_arraytype(arraytype):
    """pygame.surfarray.use_arraytype(arraytype): return None

    DEPRECATED - only numpy arrays are now supported.
    """
    warnings.warn(
        DeprecationWarning(
            "only numpy arrays are now supported, "
            "this function will be removed in a "
            "future version of the module"
        )
    )
    arraytype = arraytype.lower()
    if arraytype != "numpy":
        raise ValueError("invalid array type")


def get_arraytype():
    """pygame.surfarray.get_arraytype(): return str

    DEPRECATED - only numpy arrays are now supported.
    """
    warnings.warn(
        DeprecationWarning(
            "only numpy arrays are now supported, "
            "this function will be removed in a "
            "future version of the module"
        )
    )
    return "numpy"


def get_arraytypes():
    """pygame.surfarray.get_arraytypes(): return tuple

    DEPRECATED - only numpy arrays are now supported.
    """
    warnings.warn(
        DeprecationWarning(
            "only numpy arrays are now supported, "
            "this function will be removed in a "
            "future version of the module"
        )
    )
    return ("numpy",)
