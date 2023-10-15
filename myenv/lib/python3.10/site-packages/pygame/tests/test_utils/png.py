#!/usr/bin/env python

# $URL: http://pypng.googlecode.com/svn/trunk/code/png.py $
# $Rev: 228 $

# png.py - PNG encoder/decoder in pure Python
#
# Modified for Pygame in Oct., 2012 to work with Python 3.x.
#
# Copyright (C) 2006 Johann C. Rocholl <johann@browsershots.org>
# Portions Copyright (C) 2009 David Jones <drj@pobox.com>
# And probably portions Copyright (C) 2006 Nicko van Someren <nicko@nicko.org>
#
# Original concept by Johann C. Rocholl.
#
# LICENSE (The MIT License)
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Changelog (recent first):
# 2009-03-11 David: interlaced bit depth < 8 (writing).
# 2009-03-10 David: interlaced bit depth < 8 (reading).
# 2009-03-04 David: Flat and Boxed pixel formats.
# 2009-02-26 David: Palette support (writing).
# 2009-02-23 David: Bit-depths < 8; better PNM support.
# 2006-06-17 Nicko: Reworked into a class, faster interlacing.
# 2006-06-17 Johann: Very simple prototype PNG decoder.
# 2006-06-17 Nicko: Test suite with various image generators.
# 2006-06-17 Nicko: Alpha-channel, grey-scale, 16-bit/plane support.
# 2006-06-15 Johann: Scanline iterator interface for large input files.
# 2006-06-09 Johann: Very simple prototype PNG encoder.

# Incorporated into Bangai-O Development Tools by drj on 2009-02-11 from
# http://trac.browsershots.org/browser/trunk/pypng/lib/png.py?rev=2885

# Incorporated into pypng by drj on 2009-03-12 from
# //depot/prj/bangaio/master/code/png.py#67


"""
Pure Python PNG Reader/Writer

This Python module implements support for PNG images (see PNG
specification at http://www.w3.org/TR/2003/REC-PNG-20031110/ ). It reads
and writes PNG files with all allowable bit depths (1/2/4/8/16/24/32/48/64
bits per pixel) and colour combinations: greyscale (1/2/4/8/16 bit); RGB,
RGBA, LA (greyscale with alpha) with 8/16 bits per channel; colour mapped
images (1/2/4/8 bit).  Adam7 interlacing is supported for reading and
writing.  A number of optional chunks can be specified (when writing)
and understood (when reading): ``tRNS``, ``bKGD``, ``gAMA``.

For help, type ``import png; help(png)`` in your python interpreter.

A good place to start is the :class:`Reader` and :class:`Writer` classes.

This file can also be used as a command-line utility to convert
`Netpbm <http://netpbm.sourceforge.net/>`_ PNM files to PNG, and the reverse conversion from PNG to
PNM. The interface is similar to that of the ``pnmtopng`` program from
Netpbm.  Type ``python png.py --help`` at the shell prompt
for usage and a list of options.

A note on spelling and terminology
----------------------------------

Generally British English spelling is used in the documentation.  So
that's "greyscale" and "colour".  This not only matches the author's
native language, it's also used by the PNG specification.

The major colour models supported by PNG (and hence by PyPNG) are:
greyscale, RGB, greyscale--alpha, RGB--alpha.  These are sometimes
referred to using the abbreviations: L, RGB, LA, RGBA.  In this case
each letter abbreviates a single channel: *L* is for Luminance or Luma or
Lightness which is the channel used in greyscale images; *R*, *G*, *B* stand
for Red, Green, Blue, the components of a colour image; *A* stands for
Alpha, the opacity channel (used for transparency effects, but higher
values are more opaque, so it makes sense to call it opacity).

A note on formats
-----------------

When getting pixel data out of this module (reading) and presenting
data to this module (writing) there are a number of ways the data could
be represented as a Python value.  Generally this module uses one of
three formats called "flat row flat pixel", "boxed row flat pixel", and
"boxed row boxed pixel".  Basically the concern is whether each pixel
and each row comes in its own little tuple (box), or not.

Consider an image that is 3 pixels wide by 2 pixels high, and each pixel
has RGB components:

Boxed row flat pixel::

  list([R,G,B, R,G,B, R,G,B],
       [R,G,B, R,G,B, R,G,B])

Each row appears as its own list, but the pixels are flattened so that
three values for one pixel simply follow the three values for the previous
pixel.  This is the most common format used, because it provides a good
compromise between space and convenience.  PyPNG regards itself as
at liberty to replace any sequence type with any sufficiently compatible
other sequence type; in practice each row is an array (from the array
module), and the outer list is sometimes an iterator rather than an
explicit list (so that streaming is possible).

Flat row flat pixel::

  [R,G,B, R,G,B, R,G,B,
   R,G,B, R,G,B, R,G,B]

The entire image is one single giant sequence of colour values.
Generally an array will be used (to save space), not a list.

Boxed row boxed pixel::

  list([ (R,G,B), (R,G,B), (R,G,B) ],
       [ (R,G,B), (R,G,B), (R,G,B) ])

Each row appears in its own list, but each pixel also appears in its own
tuple.  A serious memory burn in Python.

In all cases the top row comes first, and for each row the pixels are
ordered from left-to-right.  Within a pixel the values appear in the
order, R-G-B-A (or L-A for greyscale--alpha).

There is a fourth format, mentioned because it is used internally,
is close to what lies inside a PNG file itself, and has some support
from the public API.  This format is called packed.  When packed,
each row is a sequence of bytes (integers from 0 to 255), just as
it is before PNG scanline filtering is applied.  When the bit depth
is 8 this is essentially the same as boxed row flat pixel; when the
bit depth is less than 8, several pixels are packed into each byte;
when the bit depth is 16 (the only value more than 8 that is supported
by the PNG image format) each pixel value is decomposed into 2 bytes
(and `packed` is a misnomer).  This format is used by the
:meth:`Writer.write_packed` method.  It isn't usually a convenient
format, but may be just right if the source data for the PNG image
comes from something that uses a similar format (for example, 1-bit
BMPs, or another PNG file).

And now, my famous members
--------------------------
"""

__version__ = "$URL: http://pypng.googlecode.com/svn/trunk/code/png.py $ $Rev: 228 $"

import io
import itertools
import math
import operator
import struct
import sys
import zlib
import warnings
from array import array
from functools import reduce

from pygame.tests.test_utils import tostring

__all__ = ["Image", "Reader", "Writer", "write_chunks", "from_array"]


# The PNG signature.
# http://www.w3.org/TR/PNG/#5PNG-file-signature
_signature = struct.pack("8B", 137, 80, 78, 71, 13, 10, 26, 10)

_adam7 = (
    (0, 0, 8, 8),
    (4, 0, 8, 8),
    (0, 4, 4, 8),
    (2, 0, 4, 4),
    (0, 2, 2, 4),
    (1, 0, 2, 2),
    (0, 1, 1, 2),
)


def group(s, n):
    # See
    # http://www.python.org/doc/2.6/library/functions.html#zip
    return zip(*[iter(s)] * n)


def isarray(x):
    """Same as ``isinstance(x, array)``."""
    return isinstance(x, array)


# Conditionally convert to bytes.  Works on Python 2 and Python 3.
try:
    bytes("", "ascii")

    def strtobytes(x):
        return bytes(x, "iso8859-1")

    def bytestostr(x):
        return str(x, "iso8859-1")

except:
    strtobytes = str
    bytestostr = str


def interleave_planes(ipixels, apixels, ipsize, apsize):
    """
    Interleave (colour) planes, e.g. RGB + A = RGBA.

    Return an array of pixels consisting of the `ipsize` elements of data
    from each pixel in `ipixels` followed by the `apsize` elements of data
    from each pixel in `apixels`.  Conventionally `ipixels` and
    `apixels` are byte arrays so the sizes are bytes, but it actually
    works with any arrays of the same type.  The returned array is the
    same type as the input arrays which should be the same type as each other.
    """

    itotal = len(ipixels)
    atotal = len(apixels)
    newtotal = itotal + atotal
    newpsize = ipsize + apsize
    # Set up the output buffer
    # See http://www.python.org/doc/2.4.4/lib/module-array.html#l2h-1356
    out = array(ipixels.typecode)
    # It's annoying that there is no cheap way to set the array size :-(
    out.extend(ipixels)
    out.extend(apixels)
    # Interleave in the pixel data
    for i in range(ipsize):
        out[i:newtotal:newpsize] = ipixels[i:itotal:ipsize]
    for i in range(apsize):
        out[i + ipsize : newtotal : newpsize] = apixels[i:atotal:apsize]
    return out


def check_palette(palette):
    """Check a palette argument (to the :class:`Writer` class) for validity.
    Returns the palette as a list if okay; raises an exception otherwise.
    """

    # None is the default and is allowed.
    if palette is None:
        return None

    p = list(palette)
    if not (0 < len(p) <= 256):
        raise ValueError("a palette must have between 1 and 256 entries")
    seen_triple = False
    for i, t in enumerate(p):
        if len(t) not in (3, 4):
            raise ValueError("palette entry %d: entries must be 3- or 4-tuples." % i)
        if len(t) == 3:
            seen_triple = True
        if seen_triple and len(t) == 4:
            raise ValueError(
                "palette entry %d: all 4-tuples must precede all 3-tuples" % i
            )
        for x in t:
            if int(x) != x or not (0 <= x <= 255):
                raise ValueError(
                    "palette entry %d: values must be integer: 0 <= x <= 255" % i
                )
    return p


class Error(Exception):
    prefix = "Error"

    def __str__(self):
        return f'{self.prefix}: {" ".join(self.args)}'


class FormatError(Error):
    """Problem with input file format.  In other words, PNG file does
    not conform to the specification in some way and is invalid.
    """

    prefix = "FormatError"


class ChunkError(FormatError):
    prefix = "ChunkError"


class Writer:
    """
    PNG encoder in pure Python.
    """

    def __init__(
        self,
        width=None,
        height=None,
        size=None,
        greyscale=False,
        alpha=False,
        bitdepth=8,
        palette=None,
        transparent=None,
        background=None,
        gamma=None,
        compression=None,
        interlace=False,
        bytes_per_sample=None,  # deprecated
        planes=None,
        colormap=None,
        maxval=None,
        chunk_limit=2**20,
    ):
        """
        Create a PNG encoder object.

        Arguments:

        width, height
          Image size in pixels, as two separate arguments.
        size
          Image size (w,h) in pixels, as single argument.
        greyscale
          Input data is greyscale, not RGB.
        alpha
          Input data has alpha channel (RGBA or LA).
        bitdepth
          Bit depth: from 1 to 16.
        palette
          Create a palette for a colour mapped image (colour type 3).
        transparent
          Specify a transparent colour (create a ``tRNS`` chunk).
        background
          Specify a default background colour (create a ``bKGD`` chunk).
        gamma
          Specify a gamma value (create a ``gAMA`` chunk).
        compression
          zlib compression level (1-9).
        interlace
          Create an interlaced image.
        chunk_limit
          Write multiple ``IDAT`` chunks to save memory.

        The image size (in pixels) can be specified either by using the
        `width` and `height` arguments, or with the single `size`
        argument.  If `size` is used it should be a pair (*width*,
        *height*).

        `greyscale` and `alpha` are booleans that specify whether
        an image is greyscale (or colour), and whether it has an
        alpha channel (or not).

        `bitdepth` specifies the bit depth of the source pixel values.
        Each source pixel value must be an integer between 0 and
        ``2**bitdepth-1``.  For example, 8-bit images have values
        between 0 and 255.  PNG only stores images with bit depths of
        1,2,4,8, or 16.  When `bitdepth` is not one of these values,
        the next highest valid bit depth is selected, and an ``sBIT``
        (significant bits) chunk is generated that specifies the original
        precision of the source image.  In this case the supplied pixel
        values will be rescaled to fit the range of the selected bit depth.

        The details of which bit depth / colour model combinations the
        PNG file format supports directly, are somewhat arcane
        (refer to the PNG specification for full details).  Briefly:
        "small" bit depths (1,2,4) are only allowed with greyscale and
        colour mapped images; colour mapped images cannot have bit depth
        16.

        For colour mapped images (in other words, when the `palette`
        argument is specified) the `bitdepth` argument must match one of
        the valid PNG bit depths: 1, 2, 4, or 8.  (It is valid to have a
        PNG image with a palette and an ``sBIT`` chunk, but the meaning
        is slightly different; it would be awkward to press the
        `bitdepth` argument into service for this.)

        The `palette` option, when specified, causes a colour mapped image
        to be created: the PNG colour type is set to 3; greyscale
        must not be set; alpha must not be set; transparent must
        not be set; the bit depth must be 1,2,4, or 8.  When a colour
        mapped image is created, the pixel values are palette indexes
        and the `bitdepth` argument specifies the size of these indexes
        (not the size of the colour values in the palette).

        The palette argument value should be a sequence of 3- or
        4-tuples.  3-tuples specify RGB palette entries; 4-tuples
        specify RGBA palette entries.  If both 4-tuples and 3-tuples
        appear in the sequence then all the 4-tuples must come
        before all the 3-tuples.  A ``PLTE`` chunk is created; if there
        are 4-tuples then a ``tRNS`` chunk is created as well.  The
        ``PLTE`` chunk will contain all the RGB triples in the same
        sequence; the ``tRNS`` chunk will contain the alpha channel for
        all the 4-tuples, in the same sequence.  Palette entries
        are always 8-bit.

        If specified, the `transparent` and `background` parameters must
        be a tuple with three integer values for red, green, blue, or
        a simple integer (or singleton tuple) for a greyscale image.

        If specified, the `gamma` parameter must be a positive number
        (generally, a float).  A ``gAMA`` chunk will be created.  Note that
        this will not change the values of the pixels as they appear in
        the PNG file, they are assumed to have already been converted
        appropriately for the gamma specified.

        The `compression` argument specifies the compression level
        to be used by the ``zlib`` module.  Higher values are likely
        to compress better, but will be slower to compress.  The
        default for this argument is ``None``; this does not mean
        no compression, rather it means that the default from the
        ``zlib`` module is used (which is generally acceptable).

        If `interlace` is true then an interlaced image is created
        (using PNG's so far only interlace method, *Adam7*).  This does not
        affect how the pixels should be presented to the encoder, rather
        it changes how they are arranged into the PNG file.  On slow
        connexions interlaced images can be partially decoded by the
        browser to give a rough view of the image that is successively
        refined as more image data appears.

        .. note ::

          Enabling the `interlace` option requires the entire image
          to be processed in working memory.

        `chunk_limit` is used to limit the amount of memory used whilst
        compressing the image.  In order to avoid using large amounts of
        memory, multiple ``IDAT`` chunks may be created.
        """

        # At the moment the `planes` argument is ignored;
        # its purpose is to act as a dummy so that
        # ``Writer(x, y, **info)`` works, where `info` is a dictionary
        # returned by Reader.read and friends.
        # Ditto for `colormap`.

        # A couple of helper functions come first.  Best skipped if you
        # are reading through.

        def isinteger(x):
            try:
                return int(x) == x
            except:
                return False

        def check_color(c, which):
            """Checks that a colour argument for transparent or
            background options is the right form.  Also "corrects" bare
            integers to 1-tuples.
            """

            if c is None:
                return c
            if greyscale:
                try:
                    l = len(c)
                except TypeError:
                    c = (c,)
                if len(c) != 1:
                    raise ValueError(f"{which} for greyscale must be 1-tuple")
                if not isinteger(c[0]):
                    raise ValueError(f"{which} colour for greyscale must be integer")
            else:
                if not (
                    len(c) == 3
                    and isinteger(c[0])
                    and isinteger(c[1])
                    and isinteger(c[2])
                ):
                    raise ValueError(f"{which} colour must be a triple of integers")
            return c

        if size:
            if len(size) != 2:
                raise ValueError("size argument should be a pair (width, height)")
            if width is not None and width != size[0]:
                raise ValueError(
                    "size[0] (%r) and width (%r) should match when both are used."
                    % (size[0], width)
                )
            if height is not None and height != size[1]:
                raise ValueError(
                    "size[1] (%r) and height (%r) should match when both are used."
                    % (size[1], height)
                )
            width, height = size
        del size

        if width <= 0 or height <= 0:
            raise ValueError("width and height must be greater than zero")
        if not isinteger(width) or not isinteger(height):
            raise ValueError("width and height must be integers")
        # http://www.w3.org/TR/PNG/#7Integers-and-byte-order
        if width > 2**32 - 1 or height > 2**32 - 1:
            raise ValueError("width and height cannot exceed 2**32-1")

        if alpha and transparent is not None:
            raise ValueError("transparent colour not allowed with alpha channel")

        if bytes_per_sample is not None:
            warnings.warn(
                "please use bitdepth instead of bytes_per_sample", DeprecationWarning
            )
            if bytes_per_sample not in (0.125, 0.25, 0.5, 1, 2):
                raise ValueError("bytes per sample must be .125, .25, .5, 1, or 2")
            bitdepth = int(8 * bytes_per_sample)
        del bytes_per_sample
        if not isinteger(bitdepth) or bitdepth < 1 or 16 < bitdepth:
            raise ValueError(
                f"bitdepth ({bitdepth!r}) must be a positive integer <= 16"
            )

        self.rescale = None
        if palette:
            if bitdepth not in (1, 2, 4, 8):
                raise ValueError("with palette, bitdepth must be 1, 2, 4, or 8")
            if transparent is not None:
                raise ValueError("transparent and palette not compatible")
            if alpha:
                raise ValueError("alpha and palette not compatible")
            if greyscale:
                raise ValueError("greyscale and palette not compatible")
        else:
            # No palette, check for sBIT chunk generation.
            if alpha or not greyscale:
                if bitdepth not in (8, 16):
                    targetbitdepth = (8, 16)[bitdepth > 8]
                    self.rescale = (bitdepth, targetbitdepth)
                    bitdepth = targetbitdepth
                    del targetbitdepth
            else:
                assert greyscale
                assert not alpha
                if bitdepth not in (1, 2, 4, 8, 16):
                    if bitdepth > 8:
                        targetbitdepth = 16
                    elif bitdepth == 3:
                        targetbitdepth = 4
                    else:
                        assert bitdepth in (5, 6, 7)
                        targetbitdepth = 8
                    self.rescale = (bitdepth, targetbitdepth)
                    bitdepth = targetbitdepth
                    del targetbitdepth

        if bitdepth < 8 and (alpha or not greyscale and not palette):
            raise ValueError("bitdepth < 8 only permitted with greyscale or palette")
        if bitdepth > 8 and palette:
            raise ValueError("bit depth must be 8 or less for images with palette")

        transparent = check_color(transparent, "transparent")
        background = check_color(background, "background")

        # It's important that the true boolean values (greyscale, alpha,
        # colormap, interlace) are converted to bool because Iverson's
        # convention is relied upon later on.
        self.width = width
        self.height = height
        self.transparent = transparent
        self.background = background
        self.gamma = gamma
        self.greyscale = bool(greyscale)
        self.alpha = bool(alpha)
        self.colormap = bool(palette)
        self.bitdepth = int(bitdepth)
        self.compression = compression
        self.chunk_limit = chunk_limit
        self.interlace = bool(interlace)
        self.palette = check_palette(palette)

        self.color_type = 4 * self.alpha + 2 * (not greyscale) + 1 * self.colormap
        assert self.color_type in (0, 2, 3, 4, 6)

        self.color_planes = (3, 1)[self.greyscale or self.colormap]
        self.planes = self.color_planes + self.alpha
        # :todo: fix for bitdepth < 8
        self.psize = (self.bitdepth / 8) * self.planes

    def make_palette(self):
        """Create the byte sequences for a ``PLTE`` and if necessary a
        ``tRNS`` chunk.  Returned as a pair (*p*, *t*).  *t* will be
        ``None`` if no ``tRNS`` chunk is necessary.
        """

        p = array("B")
        t = array("B")

        for x in self.palette:
            p.extend(x[0:3])
            if len(x) > 3:
                t.append(x[3])
        p = tostring(p)
        t = tostring(t)
        if t:
            return p, t
        return p, None

    def write(self, outfile, rows):
        """Write a PNG image to the output file.  `rows` should be
        an iterable that yields each row in boxed row flat pixel format.
        The rows should be the rows of the original image, so there
        should be ``self.height`` rows of ``self.width * self.planes`` values.
        If `interlace` is specified (when creating the instance), then
        an interlaced PNG file will be written.  Supply the rows in the
        normal image order; the interlacing is carried out internally.

        .. note ::

          Interlacing will require the entire image to be in working memory.
        """

        if self.interlace:
            fmt = "BH"[self.bitdepth > 8]
            a = array(fmt, itertools.chain(*rows))
            return self.write_array(outfile, a)
        else:
            nrows = self.write_passes(outfile, rows)
            if nrows != self.height:
                raise ValueError(
                    "rows supplied (%d) does not match height (%d)"
                    % (nrows, self.height)
                )

    def write_passes(self, outfile, rows, packed=False):
        """
        Write a PNG image to the output file.

        Most users are expected to find the :meth:`write` or
        :meth:`write_array` method more convenient.

        The rows should be given to this method in the order that
        they appear in the output file.  For straightlaced images,
        this is the usual top to bottom ordering, but for interlaced
        images the rows should have already been interlaced before
        passing them to this function.

        `rows` should be an iterable that yields each row.  When
        `packed` is ``False`` the rows should be in boxed row flat pixel
        format; when `packed` is ``True`` each row should be a packed
        sequence of bytes.

        """

        # http://www.w3.org/TR/PNG/#5PNG-file-signature
        outfile.write(_signature)

        # http://www.w3.org/TR/PNG/#11IHDR
        write_chunk(
            outfile,
            "IHDR",
            struct.pack(
                "!2I5B",
                self.width,
                self.height,
                self.bitdepth,
                self.color_type,
                0,
                0,
                self.interlace,
            ),
        )

        # See :chunk:order
        # http://www.w3.org/TR/PNG/#11gAMA
        if self.gamma is not None:
            write_chunk(
                outfile, "gAMA", struct.pack("!L", int(round(self.gamma * 1e5)))
            )

        # See :chunk:order
        # http://www.w3.org/TR/PNG/#11sBIT
        if self.rescale:
            write_chunk(
                outfile,
                "sBIT",
                struct.pack("%dB" % self.planes, *[self.rescale[0]] * self.planes),
            )

        # :chunk:order: Without a palette (PLTE chunk), ordering is
        # relatively relaxed.  With one, gAMA chunk must precede PLTE
        # chunk which must precede tRNS and bKGD.
        # See http://www.w3.org/TR/PNG/#5ChunkOrdering
        if self.palette:
            p, t = self.make_palette()
            write_chunk(outfile, "PLTE", p)
            if t:
                # tRNS chunk is optional.  Only needed if palette entries
                # have alpha.
                write_chunk(outfile, "tRNS", t)

        # http://www.w3.org/TR/PNG/#11tRNS
        if self.transparent is not None:
            if self.greyscale:
                write_chunk(outfile, "tRNS", struct.pack("!1H", *self.transparent))
            else:
                write_chunk(outfile, "tRNS", struct.pack("!3H", *self.transparent))

        # http://www.w3.org/TR/PNG/#11bKGD
        if self.background is not None:
            if self.greyscale:
                write_chunk(outfile, "bKGD", struct.pack("!1H", *self.background))
            else:
                write_chunk(outfile, "bKGD", struct.pack("!3H", *self.background))

        # http://www.w3.org/TR/PNG/#11IDAT
        if self.compression is not None:
            compressor = zlib.compressobj(self.compression)
        else:
            compressor = zlib.compressobj()

        # Choose an extend function based on the bitdepth.  The extend
        # function packs/decomposes the pixel values into bytes and
        # stuffs them onto the data array.
        data = array("B")
        if self.bitdepth == 8 or packed:
            extend = data.extend
        elif self.bitdepth == 16:
            # Decompose into bytes
            def extend(sl):
                fmt = f"!{len(sl)}H"
                data.extend(array("B", struct.pack(fmt, *sl)))

        else:
            # Pack into bytes
            assert self.bitdepth < 8
            # samples per byte
            spb = int(8 / self.bitdepth)

            def extend(sl):
                a = array("B", sl)
                # Adding padding bytes so we can group into a whole
                # number of spb-tuples.
                l = float(len(a))
                extra = math.ceil(l / float(spb)) * spb - l
                a.extend([0] * int(extra))
                # Pack into bytes
                l = group(a, spb)
                l = map(lambda e: reduce(lambda x, y: (x << self.bitdepth) + y, e), l)
                data.extend(l)

        if self.rescale:
            oldextend = extend
            factor = float(2 ** self.rescale[1] - 1) / float(2 ** self.rescale[0] - 1)

            def extend(sl):
                oldextend(map(lambda x: int(round(factor * x)), sl))

        # Build the first row, testing mostly to see if we need to
        # changed the extend function to cope with NumPy integer types
        # (they cause our ordinary definition of extend to fail, so we
        # wrap it).  See
        # http://code.google.com/p/pypng/issues/detail?id=44
        enumrows = enumerate(rows)
        del rows

        # First row's filter type.
        data.append(0)
        # :todo: Certain exceptions in the call to ``.next()`` or the
        # following try would indicate no row data supplied.
        # Should catch.
        i, row = next(enumrows)
        try:
            # If this fails...
            extend(row)
        except:
            # ... try a version that converts the values to int first.
            # Not only does this work for the (slightly broken) NumPy
            # types, there are probably lots of other, unknown, "nearly"
            # int types it works for.
            def wrapmapint(f):
                return lambda sl: f(map(int, sl))

            extend = wrapmapint(extend)
            del wrapmapint
            extend(row)

        for i, row in enumrows:
            # Add "None" filter type.  Currently, it's essential that
            # this filter type be used for every scanline as we do not
            # mark the first row of a reduced pass image; that means we
            # could accidentally compute the wrong filtered scanline if
            # we used "up", "average", or "paeth" on such a line.
            data.append(0)
            extend(row)
            if len(data) > self.chunk_limit:
                compressed = compressor.compress(tostring(data))
                if len(compressed):
                    # print(len(data), len(compressed), file= >> sys.stderr)
                    write_chunk(outfile, "IDAT", compressed)
                # Because of our very witty definition of ``extend``,
                # above, we must re-use the same ``data`` object.  Hence
                # we use ``del`` to empty this one, rather than create a
                # fresh one (which would be my natural FP instinct).
                del data[:]
        if len(data):
            compressed = compressor.compress(tostring(data))
        else:
            compressed = ""
        flushed = compressor.flush()
        if len(compressed) or len(flushed):
            # print(len(data), len(compressed), len(flushed), file=sys.stderr)
            write_chunk(outfile, "IDAT", compressed + flushed)
        # http://www.w3.org/TR/PNG/#11IEND
        write_chunk(outfile, "IEND")
        return i + 1

    def write_array(self, outfile, pixels):
        """
        Write an array in flat row flat pixel format as a PNG file on
        the output file.  See also :meth:`write` method.
        """

        if self.interlace:
            self.write_passes(outfile, self.array_scanlines_interlace(pixels))
        else:
            self.write_passes(outfile, self.array_scanlines(pixels))

    def write_packed(self, outfile, rows):
        """
        Write PNG file to `outfile`.  The pixel data comes from `rows`
        which should be in boxed row packed format.  Each row should be
        a sequence of packed bytes.

        Technically, this method does work for interlaced images but it
        is best avoided.  For interlaced images, the rows should be
        presented in the order that they appear in the file.

        This method should not be used when the source image bit depth
        is not one naturally supported by PNG; the bit depth should be
        1, 2, 4, 8, or 16.
        """

        if self.rescale:
            raise Error(
                "write_packed method not suitable for bit depth %d" % self.rescale[0]
            )
        return self.write_passes(outfile, rows, packed=True)

    def convert_pnm(self, infile, outfile):
        """
        Convert a PNM file containing raw pixel data into a PNG file
        with the parameters set in the writer object.  Works for
        (binary) PGM, PPM, and PAM formats.
        """

        if self.interlace:
            pixels = array("B")
            pixels.fromfile(
                infile,
                (self.bitdepth / 8) * self.color_planes * self.width * self.height,
            )
            self.write_passes(outfile, self.array_scanlines_interlace(pixels))
        else:
            self.write_passes(outfile, self.file_scanlines(infile))

    def convert_ppm_and_pgm(self, ppmfile, pgmfile, outfile):
        """
        Convert a PPM and PGM file containing raw pixel data into a
        PNG outfile with the parameters set in the writer object.
        """
        pixels = array("B")
        pixels.fromfile(
            ppmfile, (self.bitdepth / 8) * self.color_planes * self.width * self.height
        )
        apixels = array("B")
        apixels.fromfile(pgmfile, (self.bitdepth / 8) * self.width * self.height)
        pixels = interleave_planes(
            pixels,
            apixels,
            (self.bitdepth / 8) * self.color_planes,
            (self.bitdepth / 8),
        )
        if self.interlace:
            self.write_passes(outfile, self.array_scanlines_interlace(pixels))
        else:
            self.write_passes(outfile, self.array_scanlines(pixels))

    def file_scanlines(self, infile):
        """
        Generates boxed rows in flat pixel format, from the input file
        `infile`.  It assumes that the input file is in a "Netpbm-like"
        binary format, and is positioned at the beginning of the first
        pixel.  The number of pixels to read is taken from the image
        dimensions (`width`, `height`, `planes`) and the number of bytes
        per value is implied by the image `bitdepth`.
        """

        # Values per row
        vpr = self.width * self.planes
        row_bytes = vpr
        if self.bitdepth > 8:
            assert self.bitdepth == 16
            row_bytes *= 2
            fmt = ">%dH" % vpr

            def line():
                return array("H", struct.unpack(fmt, infile.read(row_bytes)))

        else:

            def line():
                scanline = array("B", infile.read(row_bytes))
                return scanline

        for y in range(self.height):
            yield line()

    def array_scanlines(self, pixels):
        """
        Generates boxed rows (flat pixels) from flat rows (flat pixels)
        in an array.
        """

        # Values per row
        vpr = self.width * self.planes
        stop = 0
        for y in range(self.height):
            start = stop
            stop = start + vpr
            yield pixels[start:stop]

    def array_scanlines_interlace(self, pixels):
        """
        Generator for interlaced scanlines from an array.  `pixels` is
        the full source image in flat row flat pixel format.  The
        generator yields each scanline of the reduced passes in turn, in
        boxed row flat pixel format.
        """

        # http://www.w3.org/TR/PNG/#8InterlaceMethods
        # Array type.
        fmt = "BH"[self.bitdepth > 8]
        # Value per row
        vpr = self.width * self.planes
        for xstart, ystart, xstep, ystep in _adam7:
            if xstart >= self.width:
                continue
            # Pixels per row (of reduced image)
            ppr = int(math.ceil((self.width - xstart) / float(xstep)))
            # number of values in reduced image row.
            row_len = ppr * self.planes
            for y in range(ystart, self.height, ystep):
                if xstep == 1:
                    offset = y * vpr
                    yield pixels[offset : offset + vpr]
                else:
                    row = array(fmt)
                    # There's no easier way to set the length of an array
                    row.extend(pixels[0:row_len])
                    offset = y * vpr + xstart * self.planes
                    end_offset = (y + 1) * vpr
                    skip = self.planes * xstep
                    for i in range(self.planes):
                        row[i :: self.planes] = pixels[offset + i : end_offset : skip]
                    yield row


def write_chunk(outfile, tag, data=strtobytes("")):
    """
    Write a PNG chunk to the output file, including length and
    checksum.
    """

    # http://www.w3.org/TR/PNG/#5Chunk-layout
    outfile.write(struct.pack("!I", len(data)))
    tag = strtobytes(tag)
    outfile.write(tag)
    outfile.write(data)
    checksum = zlib.crc32(tag)
    checksum = zlib.crc32(data, checksum)
    checksum &= 2**32 - 1
    outfile.write(struct.pack("!I", checksum))


def write_chunks(out, chunks):
    """Create a PNG file by writing out the chunks."""

    out.write(_signature)
    for chunk in chunks:
        write_chunk(out, *chunk)


def filter_scanline(type, line, fo, prev=None):
    """Apply a scanline filter to a scanline.  `type` specifies the
    filter type (0 to 4); `line` specifies the current (unfiltered)
    scanline as a sequence of bytes; `prev` specifies the previous
    (unfiltered) scanline as a sequence of bytes. `fo` specifies the
    filter offset; normally this is size of a pixel in bytes (the number
    of bytes per sample times the number of channels), but when this is
    < 1 (for bit depths < 8) then the filter offset is 1.
    """

    assert 0 <= type < 5

    # The output array.  Which, pathetically, we extend one-byte at a
    # time (fortunately this is linear).
    out = array("B", [type])

    def sub():
        ai = -fo
        for x in line:
            if ai >= 0:
                x = (x - line[ai]) & 0xFF
            out.append(x)
            ai += 1

    def up():
        for i, x in enumerate(line):
            x = (x - prev[i]) & 0xFF
            out.append(x)

    def average():
        ai = -fo
        for i, x in enumerate(line):
            if ai >= 0:
                x = (x - ((line[ai] + prev[i]) >> 1)) & 0xFF
            else:
                x = (x - (prev[i] >> 1)) & 0xFF
            out.append(x)
            ai += 1

    def paeth():
        # http://www.w3.org/TR/PNG/#9Filter-type-4-Paeth
        ai = -fo  # also used for ci
        for i, x in enumerate(line):
            a = 0
            b = prev[i]
            c = 0

            if ai >= 0:
                a = line[ai]
                c = prev[ai]
            p = a + b - c
            pa = abs(p - a)
            pb = abs(p - b)
            pc = abs(p - c)
            if pa <= pb and pa <= pc:
                Pr = a
            elif pb <= pc:
                Pr = b
            else:
                Pr = c

            x = (x - Pr) & 0xFF
            out.append(x)
            ai += 1

    if not prev:
        # We're on the first line.  Some of the filters can be reduced
        # to simpler cases which makes handling the line "off the top"
        # of the image simpler.  "up" becomes "none"; "paeth" becomes
        # "left" (non-trivial, but true). "average" needs to be handled
        # specially.
        if type == 2:  # "up"
            return line  # type = 0
        elif type == 3:
            prev = [0] * len(line)
        elif type == 4:  # "paeth"
            type = 1
    if type == 0:
        out.extend(line)
    elif type == 1:
        sub()
    elif type == 2:
        up()
    elif type == 3:
        average()
    else:  # type == 4
        paeth()
    return out


def from_array(a, mode=None, info={}):
    """Create a PNG :class:`Image` object from a 2- or 3-dimensional array.
    One application of this function is easy PIL-style saving:
    ``png.from_array(pixels, 'L').save('foo.png')``.

    .. note :

      The use of the term *3-dimensional* is for marketing purposes
      only.  It doesn't actually work.  Please bear with us.  Meanwhile
      enjoy the complimentary snacks (on request) and please use a
      2-dimensional array.

    Unless they are specified using the *info* parameter, the PNG's
    height and width are taken from the array size.  For a 3 dimensional
    array the first axis is the height; the second axis is the width;
    and the third axis is the channel number.  Thus an RGB image that is
    16 pixels high and 8 wide will use an array that is 16x8x3.  For 2
    dimensional arrays the first axis is the height, but the second axis
    is ``width*channels``, so an RGB image that is 16 pixels high and 8
    wide will use a 2-dimensional array that is 16x24 (each row will be
    8*3==24 sample values).

    *mode* is a string that specifies the image colour format in a
    PIL-style mode.  It can be:

    ``'L'``
      greyscale (1 channel)
    ``'LA'``
      greyscale with alpha (2 channel)
    ``'RGB'``
      colour image (3 channel)
    ``'RGBA'``
      colour image with alpha (4 channel)

    The mode string can also specify the bit depth (overriding how this
    function normally derives the bit depth, see below).  Appending
    ``';16'`` to the mode will cause the PNG to be 16 bits per channel;
    any decimal from 1 to 16 can be used to specify the bit depth.

    When a 2-dimensional array is used *mode* determines how many
    channels the image has, and so allows the width to be derived from
    the second array dimension.

    The array is expected to be a ``numpy`` array, but it can be any
    suitable Python sequence.  For example, a list of lists can be used:
    ``png.from_array([[0, 255, 0], [255, 0, 255]], 'L')``.  The exact
    rules are: ``len(a)`` gives the first dimension, height;
    ``len(a[0])`` gives the second dimension; ``len(a[0][0])`` gives the
    third dimension, unless an exception is raised in which case a
    2-dimensional array is assumed.  It's slightly more complicated than
    that because an iterator of rows can be used, and it all still
    works.  Using an iterator allows data to be streamed efficiently.

    The bit depth of the PNG is normally taken from the array element's
    datatype (but if *mode* specifies a bitdepth then that is used
    instead).  The array element's datatype is determined in a way which
    is supposed to work both for ``numpy`` arrays and for Python
    ``array.array`` objects.  A 1 byte datatype will give a bit depth of
    8, a 2 byte datatype will give a bit depth of 16.  If the datatype
    does not have an implicit size, for example it is a plain Python
    list of lists, as above, then a default of 8 is used.

    The *info* parameter is a dictionary that can be used to specify
    metadata (in the same style as the arguments to the
    :class:``png.Writer`` class).  For this function the keys that are
    useful are:

    height
      overrides the height derived from the array dimensions and allows
      *a* to be an iterable.
    width
      overrides the width derived from the array dimensions.
    bitdepth
      overrides the bit depth derived from the element datatype (but
      must match *mode* if that also specifies a bit depth).

    Generally anything specified in the
    *info* dictionary will override any implicit choices that this
    function would otherwise make, but must match any explicit ones.
    For example, if the *info* dictionary has a ``greyscale`` key then
    this must be true when mode is ``'L'`` or ``'LA'`` and false when
    mode is ``'RGB'`` or ``'RGBA'``.
    """

    # We abuse the *info* parameter by modifying it.  Take a copy here.
    # (Also typechecks *info* to some extent).
    info = dict(info)

    # Syntax check mode string.
    bitdepth = None
    try:
        mode = mode.split(";")
        if len(mode) not in (1, 2):
            raise Error()
        if mode[0] not in ("L", "LA", "RGB", "RGBA"):
            raise Error()
        if len(mode) == 2:
            try:
                bitdepth = int(mode[1])
            except:
                raise Error()
    except Error:
        raise Error("mode string should be 'RGB' or 'L;16' or similar.")
    mode = mode[0]

    # Get bitdepth from *mode* if possible.
    if bitdepth:
        if info.get("bitdepth") and bitdepth != info["bitdepth"]:
            raise Error(
                "mode bitdepth (%d) should match info bitdepth (%d)."
                % (bitdepth, info["bitdepth"])
            )
        info["bitdepth"] = bitdepth

    # Fill in and/or check entries in *info*.
    # Dimensions.
    if "size" in info:
        # Check width, height, size all match where used.
        for dimension, axis in [("width", 0), ("height", 1)]:
            if dimension in info:
                if info[dimension] != info["size"][axis]:
                    raise Error(
                        f"info[{dimension!r}] should match info['size'][{axis!r}]."
                    )
        info["width"], info["height"] = info["size"]
    if "height" not in info:
        try:
            l = len(a)
        except:
            raise Error("len(a) does not work, supply info['height'] instead.")
        info["height"] = l
    # Colour format.
    if "greyscale" in info:
        if bool(info["greyscale"]) != ("L" in mode):
            raise Error("info['greyscale'] should match mode.")
    info["greyscale"] = "L" in mode
    if "alpha" in info:
        if bool(info["alpha"]) != ("A" in mode):
            raise Error("info['alpha'] should match mode.")
    info["alpha"] = "A" in mode

    planes = len(mode)
    if "planes" in info:
        if info["planes"] != planes:
            raise Error("info['planes'] should match mode.")

    # In order to work out whether we the array is 2D or 3D we need its
    # first row, which requires that we take a copy of its iterator.
    # We may also need the first row to derive width and bitdepth.
    a, t = itertools.tee(a)
    row = next(t)
    del t
    try:
        row[0][0]
        threed = True
        testelement = row[0]
    except:
        threed = False
        testelement = row
    if "width" not in info:
        if threed:
            width = len(row)
        else:
            width = len(row) // planes
        info["width"] = width

    # Not implemented yet
    assert not threed

    if "bitdepth" not in info:
        try:
            dtype = testelement.dtype
            # goto the "else:" clause.  Sorry.
        except:
            try:
                # Try a Python array.array.
                bitdepth = 8 * testelement.itemsize
            except:
                # We can't determine it from the array element's
                # datatype, use a default of 8.
                bitdepth = 8
        else:
            # If we got here without exception, we now assume that
            # the array is a numpy array.
            if dtype.kind == "b":
                bitdepth = 1
            else:
                bitdepth = 8 * dtype.itemsize
        info["bitdepth"] = bitdepth

    for thing in "width height bitdepth greyscale alpha".split():
        assert thing in info
    return Image(a, info)


# So that refugee's from PIL feel more at home.  Not documented.
fromarray = from_array


class Image:
    """A PNG image.
    You can create an :class:`Image` object from an array of pixels by calling
    :meth:`png.from_array`.  It can be saved to disk with the
    :meth:`save` method."""

    def __init__(self, rows, info):
        """
        .. note ::

          The constructor is not public.  Please do not call it.
        """

        self.rows = rows
        self.info = info

    def save(self, file):
        """Save the image to *file*.  If *file* looks like an open file
        descriptor then it is used, otherwise it is treated as a
        filename and a fresh file is opened.

        In general, you can only call this method once; after it has
        been called the first time and the PNG image has been saved, the
        source data will have been streamed, and cannot be streamed
        again.
        """

        w = Writer(**self.info)

        try:
            file.write

            def close():
                pass

        except:
            file = open(file, "wb")

            def close():
                file.close()

        try:
            w.write(file, self.rows)
        finally:
            close()


class _readable:
    """
    A simple file-like interface for strings and arrays.
    """

    def __init__(self, buf):
        self.buf = buf
        self.offset = 0

    def read(self, n):
        r = self.buf[self.offset : self.offset + n]
        if isarray(r):
            r = tostring(r)
        self.offset += n
        return r


class Reader:
    """
    PNG decoder in pure Python.
    """

    def __init__(self, _guess=None, **kw):
        """
        Create a PNG decoder object.

        The constructor expects exactly one keyword argument. If you
        supply a positional argument instead, it will guess the input
        type. You can choose among the following keyword arguments:

        filename
          Name of input file (a PNG file).
        file
          A file-like object (object with a read() method).
        bytes
          ``array`` or ``string`` with PNG data.

        """
        if (_guess is not None and len(kw) != 0) or (_guess is None and len(kw) != 1):
            raise TypeError("Reader() takes exactly 1 argument")

        # Will be the first 8 bytes, later on.  See validate_signature.
        self.signature = None
        self.transparent = None
        # A pair of (len,type) if a chunk has been read but its data and
        # checksum have not (in other words the file position is just
        # past the 4 bytes that specify the chunk type).  See preamble
        # method for how this is used.
        self.atchunk = None

        if _guess is not None:
            if isarray(_guess):
                kw["bytes"] = _guess
            elif isinstance(_guess, str):
                kw["filename"] = _guess
            elif isinstance(_guess, io.IOBase):
                kw["file"] = _guess

        if "filename" in kw:
            self.file = open(kw["filename"], "rb")
        elif "file" in kw:
            self.file = kw["file"]
        elif "bytes" in kw:
            self.file = _readable(kw["bytes"])
        else:
            raise TypeError("expecting filename, file or bytes array")

    def chunk(self, seek=None):
        """
        Read the next PNG chunk from the input file; returns a
        (*type*,*data*) tuple.  *type* is the chunk's type as a string
        (all PNG chunk types are 4 characters long).  *data* is the
        chunk's data content, as a string.

        If the optional `seek` argument is
        specified then it will keep reading chunks until it either runs
        out of file or finds the type specified by the argument.  Note
        that in general the order of chunks in PNGs is unspecified, so
        using `seek` can cause you to miss chunks.
        """

        self.validate_signature()

        while True:
            # http://www.w3.org/TR/PNG/#5Chunk-layout
            if not self.atchunk:
                self.atchunk = self.chunklentype()
            length, type = self.atchunk
            self.atchunk = None
            data = self.file.read(length)
            if len(data) != length:
                raise ChunkError(
                    "Chunk %s too short for required %i octets." % (type, length)
                )
            checksum = self.file.read(4)
            if len(checksum) != 4:
                raise ValueError("Chunk %s too short for checksum.", checksum)
            if seek and type != seek:
                continue
            verify = zlib.crc32(strtobytes(type))
            verify = zlib.crc32(data, verify)
            # Whether the output from zlib.crc32 is signed or not varies
            # according to hideous implementation details, see
            # http://bugs.python.org/issue1202 .
            # We coerce it to be positive here (in a way which works on
            # Python 2.3 and older).
            verify &= 2**32 - 1
            verify = struct.pack("!I", verify)
            if checksum != verify:
                # print(repr(checksum))
                (a,) = struct.unpack("!I", checksum)
                (b,) = struct.unpack("!I", verify)
                raise ChunkError(
                    f"Checksum error in {type} chunk: 0x{a:08X} != 0x{b:08X}."
                )
            return type, data

    def chunks(self):
        """Return an iterator that will yield each chunk as a
        (*chunktype*, *content*) pair.
        """

        while True:
            t, v = self.chunk()
            yield t, v
            if t == "IEND":
                break

    def undo_filter(self, filter_type, scanline, previous):
        """Undo the filter for a scanline.  `scanline` is a sequence of
        bytes that does not include the initial filter type byte.
        `previous` is decoded previous scanline (for straightlaced
        images this is the previous pixel row, but for interlaced
        images, it is the previous scanline in the reduced image, which
        in general is not the previous pixel row in the final image).
        When there is no previous scanline (the first row of a
        straightlaced image, or the first row in one of the passes in an
        interlaced image), then this argument should be ``None``.

        The scanline will have the effects of filtering removed, and the
        result will be returned as a fresh sequence of bytes.
        """

        # :todo: Would it be better to update scanline in place?

        # Create the result byte array.  It seems that the best way to
        # create the array to be the right size is to copy from an
        # existing sequence.  *sigh*
        # If we fill the result with scanline, then this allows a
        # micro-optimisation in the "null" and "sub" cases.
        result = array("B", scanline)

        if filter_type == 0:
            # And here, we _rely_ on filling the result with scanline,
            # above.
            return result

        if filter_type not in (1, 2, 3, 4):
            raise FormatError(
                "Invalid PNG Filter Type."
                "  See http://www.w3.org/TR/2003/REC-PNG-20031110/#9Filters ."
            )

        # Filter unit.  The stride from one pixel to the corresponding
        # byte from the previous previous.  Normally this is the pixel
        # size in bytes, but when this is smaller than 1, the previous
        # byte is used instead.
        fu = max(1, self.psize)

        # For the first line of a pass, synthesize a dummy previous
        # line.  An alternative approach would be to observe that on the
        # first line 'up' is the same as 'null', 'paeth' is the same
        # as 'sub', with only 'average' requiring any special case.
        if not previous:
            previous = array("B", [0] * len(scanline))

        def sub():
            """Undo sub filter."""

            ai = 0
            # Loops starts at index fu.  Observe that the initial part
            # of the result is already filled in correctly with
            # scanline.
            for i in range(fu, len(result)):
                x = scanline[i]
                a = result[ai]
                result[i] = (x + a) & 0xFF
                ai += 1

        def up():
            """Undo up filter."""
            for i in range(len(result)):  # pylint: disable=consider-using-enumerate
                x = scanline[i]
                b = previous[i]
                result[i] = (x + b) & 0xFF

        def average():
            """Undo average filter."""

            ai = -fu
            for i in range(len(result)):  # pylint: disable=consider-using-enumerate
                x = scanline[i]
                if ai < 0:
                    a = 0
                else:
                    a = result[ai]
                b = previous[i]
                result[i] = (x + ((a + b) >> 1)) & 0xFF
                ai += 1

        def paeth():
            """Undo Paeth filter."""

            # Also used for ci.
            ai = -fu
            for i in range(len(result)):  # pylint: disable=consider-using-enumerate
                x = scanline[i]
                if ai < 0:
                    a = c = 0
                else:
                    a = result[ai]
                    c = previous[ai]
                b = previous[i]
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                result[i] = (x + pr) & 0xFF
                ai += 1

        # Call appropriate filter algorithm.  Note that 0 has already
        # been dealt with.
        (None, sub, up, average, paeth)[filter_type]()
        return result

    def deinterlace(self, raw):
        """
        Read raw pixel data, undo filters, deinterlace, and flatten.
        Return in flat row flat pixel format.
        """

        # print("Reading interlaced, w=%s, r=%s, planes=%s, bpp=%s"
        # % (self.width, self.height, self.planes, self.bps, file=sys.stderr))
        # Values per row (of the target image)
        vpr = self.width * self.planes

        # Make a result array, and make it big enough.  Interleaving
        # writes to the output array randomly (well, not quite), so the
        # entire output array must be in memory.
        fmt = "BH"[self.bitdepth > 8]
        a = array(fmt, [0] * vpr * self.height)
        source_offset = 0

        for xstart, ystart, xstep, ystep in _adam7:
            # print("Adam7: start=%s,%s step=%s,%s" % (
            #     xstart, ystart, xstep, ystep, file=sys.stderr))
            if xstart >= self.width:
                continue
            # The previous (reconstructed) scanline.  None at the
            # beginning of a pass to indicate that there is no previous
            # line.
            recon = None
            # Pixels per row (reduced pass image)
            ppr = int(math.ceil((self.width - xstart) / float(xstep)))
            # Row size in bytes for this pass.
            row_size = int(math.ceil(self.psize * ppr))
            for y in range(ystart, self.height, ystep):
                filter_type = raw[source_offset]
                source_offset += 1
                scanline = raw[source_offset : source_offset + row_size]
                source_offset += row_size
                recon = self.undo_filter(filter_type, scanline, recon)
                # Convert so that there is one element per pixel value
                flat = self.serialtoflat(recon, ppr)
                if xstep == 1:
                    assert xstart == 0
                    offset = y * vpr
                    a[offset : offset + vpr] = flat
                else:
                    offset = y * vpr + xstart * self.planes
                    end_offset = (y + 1) * vpr
                    skip = self.planes * xstep
                    for i in range(self.planes):
                        a[offset + i : end_offset : skip] = flat[i :: self.planes]
        return a

    def iterboxed(self, rows):
        """Iterator that yields each scanline in boxed row flat pixel
        format.  `rows` should be an iterator that yields the bytes of
        each row in turn.
        """

        def asvalues(raw):
            """Convert a row of raw bytes into a flat row.  Result may
            or may not share with argument"""

            if self.bitdepth == 8:
                return raw
            if self.bitdepth == 16:
                raw = tostring(raw)
                return array("H", struct.unpack("!%dH" % (len(raw) // 2), raw))
            assert self.bitdepth < 8
            width = self.width
            # Samples per byte
            spb = 8 // self.bitdepth
            out = array("B")
            mask = 2**self.bitdepth - 1
            shifts = map(self.bitdepth.__mul__, reversed(range(spb)))
            for o in raw:
                out.extend(map(lambda i: mask & (o >> i), shifts))
            return out[:width]

        return map(asvalues, rows)

    def serialtoflat(self, bytes, width=None):
        """Convert serial format (byte stream) pixel data to flat row
        flat pixel.
        """

        if self.bitdepth == 8:
            return bytes
        if self.bitdepth == 16:
            bytes = tostring(bytes)
            return array("H", struct.unpack("!%dH" % (len(bytes) // 2), bytes))
        assert self.bitdepth < 8
        if width is None:
            width = self.width
        # Samples per byte
        spb = 8 // self.bitdepth
        out = array("B")
        mask = 2**self.bitdepth - 1
        shifts = map(self.bitdepth.__mul__, reversed(range(spb)))
        l = width
        for o in bytes:
            out.extend([(mask & (o >> s)) for s in shifts][:l])
            l -= spb
            if l <= 0:
                l = width
        return out

    def iterstraight(self, raw):
        """Iterator that undoes the effect of filtering, and yields each
        row in serialised format (as a sequence of bytes).  Assumes input
        is straightlaced.  `raw` should be an iterable that yields the
        raw bytes in chunks of arbitrary size."""

        # length of row, in bytes
        rb = self.row_bytes
        a = array("B")
        # The previous (reconstructed) scanline.  None indicates first
        # line of image.
        recon = None
        for some in raw:
            a.extend(some)
            while len(a) >= rb + 1:
                filter_type = a[0]
                scanline = a[1 : rb + 1]
                del a[: rb + 1]
                recon = self.undo_filter(filter_type, scanline, recon)
                yield recon
        if len(a) != 0:
            # :file:format We get here with a file format error: when the
            # available bytes (after decompressing) do not pack into exact
            # rows.
            raise FormatError("Wrong size for decompressed IDAT chunk.")
        assert len(a) == 0

    def validate_signature(self):
        """If signature (header) has not been read then read and
        validate it; otherwise do nothing.
        """

        if self.signature:
            return
        self.signature = self.file.read(8)
        if self.signature != _signature:
            raise FormatError("PNG file has invalid signature.")

    def preamble(self):
        """
        Extract the image metadata by reading the initial part of the PNG
        file up to the start of the ``IDAT`` chunk.  All the chunks that
        precede the ``IDAT`` chunk are read and either processed for
        metadata or discarded.
        """

        self.validate_signature()

        while True:
            if not self.atchunk:
                self.atchunk = self.chunklentype()
                if self.atchunk is None:
                    raise FormatError("This PNG file has no IDAT chunks.")
            if self.atchunk[1] == "IDAT":
                return
            self.process_chunk()

    def chunklentype(self):
        """Reads just enough of the input to determine the next
        chunk's length and type, returned as a (*length*, *type*) pair
        where *type* is a string.  If there are no more chunks, ``None``
        is returned.
        """

        x = self.file.read(8)
        if not x:
            return None
        if len(x) != 8:
            raise FormatError("End of file whilst reading chunk length and type.")
        length, type = struct.unpack("!I4s", x)
        type = bytestostr(type)
        if length > 2**31 - 1:
            raise FormatError("Chunk %s is too large: %d." % (type, length))
        return length, type

    def process_chunk(self):
        """Process the next chunk and its data.  This only processes the
        following chunk types, all others are ignored: ``IHDR``,
        ``PLTE``, ``bKGD``, ``tRNS``, ``gAMA``, ``sBIT``.
        """

        type, data = self.chunk()
        if type == "IHDR":
            # http://www.w3.org/TR/PNG/#11IHDR
            if len(data) != 13:
                raise FormatError("IHDR chunk has incorrect length.")
            (
                self.width,
                self.height,
                self.bitdepth,
                self.color_type,
                self.compression,
                self.filter,
                self.interlace,
            ) = struct.unpack("!2I5B", data)

            # Check that the header specifies only valid combinations.
            if self.bitdepth not in (1, 2, 4, 8, 16):
                raise Error("invalid bit depth %d" % self.bitdepth)
            if self.color_type not in (0, 2, 3, 4, 6):
                raise Error("invalid colour type %d" % self.color_type)
            # Check indexed (palettized) images have 8 or fewer bits
            # per pixel; check only indexed or greyscale images have
            # fewer than 8 bits per pixel.
            if (self.color_type & 1 and self.bitdepth > 8) or (
                self.bitdepth < 8 and self.color_type not in (0, 3)
            ):
                raise FormatError(
                    "Illegal combination of bit depth (%d)"
                    " and colour type (%d)."
                    " See http://www.w3.org/TR/2003/REC-PNG-20031110/#table111 ."
                    % (self.bitdepth, self.color_type)
                )
            if self.compression != 0:
                raise Error("unknown compression method %d" % self.compression)
            if self.filter != 0:
                raise FormatError(
                    "Unknown filter method %d,"
                    " see http://www.w3.org/TR/2003/REC-PNG-20031110/#9Filters ."
                    % self.filter
                )
            if self.interlace not in (0, 1):
                raise FormatError(
                    "Unknown interlace method %d,"
                    " see http://www.w3.org/TR/2003/REC-PNG-20031110/#8InterlaceMethods ."
                    % self.interlace
                )

            # Derived values
            # http://www.w3.org/TR/PNG/#6Colour-values
            colormap = bool(self.color_type & 1)
            greyscale = not (self.color_type & 2)
            alpha = bool(self.color_type & 4)
            color_planes = (3, 1)[greyscale or colormap]
            planes = color_planes + alpha

            self.colormap = colormap
            self.greyscale = greyscale
            self.alpha = alpha
            self.color_planes = color_planes
            self.planes = planes
            self.psize = float(self.bitdepth) / float(8) * planes
            if int(self.psize) == self.psize:
                self.psize = int(self.psize)
            self.row_bytes = int(math.ceil(self.width * self.psize))
            # Stores PLTE chunk if present, and is used to check
            # chunk ordering constraints.
            self.plte = None
            # Stores tRNS chunk if present, and is used to check chunk
            # ordering constraints.
            self.trns = None
            # Stores sbit chunk if present.
            self.sbit = None
        elif type == "PLTE":
            # http://www.w3.org/TR/PNG/#11PLTE
            if self.plte:
                warnings.warn("Multiple PLTE chunks present.")
            self.plte = data
            if len(data) % 3 != 0:
                raise FormatError("PLTE chunk's length should be a multiple of 3.")
            if len(data) > (2**self.bitdepth) * 3:
                raise FormatError("PLTE chunk is too long.")
            if len(data) == 0:
                raise FormatError("Empty PLTE is not allowed.")
        elif type == "bKGD":
            try:
                if self.colormap:
                    if not self.plte:
                        warnings.warn("PLTE chunk is required before bKGD chunk.")
                    self.background = struct.unpack("B", data)
                else:
                    self.background = struct.unpack("!%dH" % self.color_planes, data)
            except struct.error:
                raise FormatError("bKGD chunk has incorrect length.")
        elif type == "tRNS":
            # http://www.w3.org/TR/PNG/#11tRNS
            self.trns = data
            if self.colormap:
                if not self.plte:
                    warnings.warn("PLTE chunk is required before tRNS chunk.")
                else:
                    if len(data) > len(self.plte) / 3:
                        # Was warning, but promoted to Error as it
                        # would otherwise cause pain later on.
                        raise FormatError("tRNS chunk is too long.")
            else:
                if self.alpha:
                    raise FormatError(
                        "tRNS chunk is not valid with colour type %d." % self.color_type
                    )
                try:
                    self.transparent = struct.unpack("!%dH" % self.color_planes, data)
                except struct.error:
                    raise FormatError("tRNS chunk has incorrect length.")
        elif type == "gAMA":
            try:
                self.gamma = struct.unpack("!L", data)[0] / 100000.0
            except struct.error:
                raise FormatError("gAMA chunk has incorrect length.")
        elif type == "sBIT":
            self.sbit = data
            if (
                self.colormap
                and len(data) != 3
                or not self.colormap
                and len(data) != self.planes
            ):
                raise FormatError("sBIT chunk has incorrect length.")

    def read(self):
        """
        Read the PNG file and decode it.  Returns (`width`, `height`,
        `pixels`, `metadata`).

        May use excessive memory.

        `pixels` are returned in boxed row flat pixel format.
        """

        def iteridat():
            """Iterator that yields all the ``IDAT`` chunks as strings."""
            while True:
                try:
                    type, data = self.chunk()
                except ValueError as e:
                    raise ChunkError(e.args[0])
                if type == "IEND":
                    # http://www.w3.org/TR/PNG/#11IEND
                    break
                if type != "IDAT":
                    continue
                # type == 'IDAT'
                # http://www.w3.org/TR/PNG/#11IDAT
                if self.colormap and not self.plte:
                    warnings.warn("PLTE chunk is required before IDAT chunk")
                yield data

        def iterdecomp(idat):
            """Iterator that yields decompressed strings.  `idat` should
            be an iterator that yields the ``IDAT`` chunk data.
            """

            # Currently, with no max_length parameter to decompress, this
            # routine will do one yield per IDAT chunk.  So not very
            # incremental.
            d = zlib.decompressobj()
            # Each IDAT chunk is passed to the decompressor, then any
            # remaining state is decompressed out.
            for data in idat:
                # :todo: add a max_length argument here to limit output
                # size.
                yield array("B", d.decompress(data))
            yield array("B", d.flush())

        self.preamble()
        raw = iterdecomp(iteridat())

        if self.interlace:
            raw = array("B", itertools.chain(*raw))
            arraycode = "BH"[self.bitdepth > 8]
            # Like :meth:`group` but producing an array.array object for
            # each row.
            pixels = map(
                lambda *row: array(arraycode, row),
                *[iter(self.deinterlace(raw))] * self.width * self.planes,
            )
        else:
            pixels = self.iterboxed(self.iterstraight(raw))
        meta = dict()
        for attr in "greyscale alpha planes bitdepth interlace".split():
            meta[attr] = getattr(self, attr)
        meta["size"] = (self.width, self.height)
        for attr in "gamma transparent background".split():
            a = getattr(self, attr, None)
            if a is not None:
                meta[attr] = a
        return self.width, self.height, pixels, meta

    def read_flat(self):
        """
        Read a PNG file and decode it into flat row flat pixel format.
        Returns (*width*, *height*, *pixels*, *metadata*).

        May use excessive memory.

        `pixels` are returned in flat row flat pixel format.

        See also the :meth:`read` method which returns pixels in the
        more stream-friendly boxed row flat pixel format.
        """

        x, y, pixel, meta = self.read()
        arraycode = "BH"[meta["bitdepth"] > 8]
        pixel = array(arraycode, itertools.chain(*pixel))
        return x, y, pixel, meta

    def palette(self, alpha="natural"):
        """Returns a palette that is a sequence of 3-tuples or 4-tuples,
        synthesizing it from the ``PLTE`` and ``tRNS`` chunks.  These
        chunks should have already been processed (for example, by
        calling the :meth:`preamble` method).  All the tuples are the
        same size: 3-tuples if there is no ``tRNS`` chunk, 4-tuples when
        there is a ``tRNS`` chunk.  Assumes that the image is colour type
        3 and therefore a ``PLTE`` chunk is required.

        If the `alpha` argument is ``'force'`` then an alpha channel is
        always added, forcing the result to be a sequence of 4-tuples.
        """

        if not self.plte:
            raise FormatError("Required PLTE chunk is missing in colour type 3 image.")
        plte = group(array("B", self.plte), 3)
        if self.trns or alpha == "force":
            trns = array("B", self.trns or "")
            trns.extend([255] * (len(plte) - len(trns)))
            plte = map(operator.add, plte, group(trns, 1))
        return plte

    def asDirect(self):
        """Returns the image data as a direct representation of an
        ``x * y * planes`` array.  This method is intended to remove the
        need for callers to deal with palettes and transparency
        themselves.  Images with a palette (colour type 3)
        are converted to RGB or RGBA; images with transparency (a
        ``tRNS`` chunk) are converted to LA or RGBA as appropriate.
        When returned in this format the pixel values represent the
        colour value directly without needing to refer to palettes or
        transparency information.

        Like the :meth:`read` method this method returns a 4-tuple:

        (*width*, *height*, *pixels*, *meta*)

        This method normally returns pixel values with the bit depth
        they have in the source image, but when the source PNG has an
        ``sBIT`` chunk it is inspected and can reduce the bit depth of
        the result pixels; pixel values will be reduced according to
        the bit depth specified in the ``sBIT`` chunk (PNG nerds should
        note a single result bit depth is used for all channels; the
        maximum of the ones specified in the ``sBIT`` chunk.  An RGB565
        image will be rescaled to 6-bit RGB666).

        The *meta* dictionary that is returned reflects the `direct`
        format and not the original source image.  For example, an RGB
        source image with a ``tRNS`` chunk to represent a transparent
        colour, will have ``planes=3`` and ``alpha=False`` for the
        source image, but the *meta* dictionary returned by this method
        will have ``planes=4`` and ``alpha=True`` because an alpha
        channel is synthesized and added.

        *pixels* is the pixel data in boxed row flat pixel format (just
        like the :meth:`read` method).

        All the other aspects of the image data are not changed.
        """

        self.preamble()

        # Simple case, no conversion necessary.
        if not self.colormap and not self.trns and not self.sbit:
            return self.read()

        x, y, pixels, meta = self.read()

        if self.colormap:
            meta["colormap"] = False
            meta["alpha"] = bool(self.trns)
            meta["bitdepth"] = 8
            meta["planes"] = 3 + bool(self.trns)
            plte = list(self.palette())

            def iterpal(pixels):
                for row in pixels:
                    row = map(plte.__getitem__, row)
                    yield array("B", itertools.chain(*row))

            pixels = iterpal(pixels)
        elif self.trns:
            # It would be nice if there was some reasonable way of doing
            # this without generating a whole load of intermediate tuples.
            # But tuples does seem like the easiest way, with no other way
            # clearly much simpler or much faster.  (Actually, the L to LA
            # conversion could perhaps go faster (all those 1-tuples!), but
            # I still wonder whether the code proliferation is worth it)
            it = self.transparent
            maxval = 2 ** meta["bitdepth"] - 1
            planes = meta["planes"]
            meta["alpha"] = True
            meta["planes"] += 1
            typecode = "BH"[meta["bitdepth"] > 8]

            def itertrns(pixels):
                for row in pixels:
                    # For each row we group it into pixels, then form a
                    # characterisation vector that says whether each pixel
                    # is opaque or not.  Then we convert True/False to
                    # 0/maxval (by multiplication), and add it as the extra
                    # channel.
                    row = group(row, planes)
                    opa = map(it.__ne__, row)
                    opa = map(maxval.__mul__, opa)
                    opa = zip(opa)  # convert to 1-tuples
                    yield array(typecode, itertools.chain(*map(operator.add, row, opa)))

            pixels = itertrns(pixels)
        targetbitdepth = None
        if self.sbit:
            sbit = struct.unpack(f"{len(self.sbit)}B", self.sbit)
            targetbitdepth = max(sbit)
            if targetbitdepth > meta["bitdepth"]:
                raise Error("sBIT chunk %r exceeds bitdepth %d" % (sbit, self.bitdepth))
            if min(sbit) <= 0:
                raise Error(f"sBIT chunk {sbit!r} has a 0-entry")
            if targetbitdepth == meta["bitdepth"]:
                targetbitdepth = None
        if targetbitdepth:
            shift = meta["bitdepth"] - targetbitdepth
            meta["bitdepth"] = targetbitdepth

            def itershift(pixels):
                for row in pixels:
                    yield map(shift.__rrshift__, row)

            pixels = itershift(pixels)
        return x, y, pixels, meta

    def asFloat(self, maxval=1.0):
        """Return image pixels as per :meth:`asDirect` method, but scale
        all pixel values to be floating point values between 0.0 and
        *maxval*.
        """

        x, y, pixels, info = self.asDirect()
        sourcemaxval = 2 ** info["bitdepth"] - 1
        del info["bitdepth"]
        info["maxval"] = float(maxval)
        factor = float(maxval) / float(sourcemaxval)

        def iterfloat():
            for row in pixels:
                yield map(factor.__mul__, row)

        return x, y, iterfloat(), info

    def _as_rescale(self, get, targetbitdepth):
        """Helper used by :meth:`asRGB8` and :meth:`asRGBA8`."""

        width, height, pixels, meta = get()
        maxval = 2 ** meta["bitdepth"] - 1
        targetmaxval = 2**targetbitdepth - 1
        factor = float(targetmaxval) / float(maxval)
        meta["bitdepth"] = targetbitdepth

        def iterscale():
            for row in pixels:
                yield map(lambda x: int(round(x * factor)), row)

        return width, height, iterscale(), meta

    def asRGB8(self):
        """Return the image data as an RGB pixels with 8-bits per
        sample.  This is like the :meth:`asRGB` method except that
        this method additionally rescales the values so that they
        are all between 0 and 255 (8-bit).  In the case where the
        source image has a bit depth < 8 the transformation preserves
        all the information; where the source image has bit depth
        > 8, then rescaling to 8-bit values loses precision.  No
        dithering is performed.  Like :meth:`asRGB`, an alpha channel
        in the source image will raise an exception.

        This function returns a 4-tuple:
        (*width*, *height*, *pixels*, *metadata*).
        *width*, *height*, *metadata* are as per the :meth:`read` method.

        *pixels* is the pixel data in boxed row flat pixel format.
        """

        return self._as_rescale(self.asRGB, 8)

    def asRGBA8(self):
        """Return the image data as RGBA pixels with 8-bits per
        sample.  This method is similar to :meth:`asRGB8` and
        :meth:`asRGBA`:  The result pixels have an alpha channel, *and*
        values are rescaled to the range 0 to 255.  The alpha channel is
        synthesized if necessary (with a small speed penalty).
        """

        return self._as_rescale(self.asRGBA, 8)

    def asRGB(self):
        """Return image as RGB pixels.  RGB colour images are passed
        through unchanged; greyscales are expanded into RGB
        triplets (there is a small speed overhead for doing this).

        An alpha channel in the source image will raise an
        exception.

        The return values are as for the :meth:`read` method
        except that the *metadata* reflect the returned pixels, not the
        source image.  In particular, for this method
        ``metadata['greyscale']`` will be ``False``.
        """

        width, height, pixels, meta = self.asDirect()
        if meta["alpha"]:
            raise Error("will not convert image with alpha channel to RGB")
        if not meta["greyscale"]:
            return width, height, pixels, meta
        meta["greyscale"] = False
        typecode = "BH"[meta["bitdepth"] > 8]

        def iterrgb():
            for row in pixels:
                a = array(typecode, [0]) * 3 * width
                for i in range(3):
                    a[i::3] = row
                yield a

        return width, height, iterrgb(), meta

    def asRGBA(self):
        """Return image as RGBA pixels.  Greyscales are expanded into
        RGB triplets; an alpha channel is synthesized if necessary.
        The return values are as for the :meth:`read` method
        except that the *metadata* reflect the returned pixels, not the
        source image.  In particular, for this method
        ``metadata['greyscale']`` will be ``False``, and
        ``metadata['alpha']`` will be ``True``.
        """

        width, height, pixels, meta = self.asDirect()
        if meta["alpha"] and not meta["greyscale"]:
            return width, height, pixels, meta
        typecode = "BH"[meta["bitdepth"] > 8]
        maxval = 2 ** meta["bitdepth"] - 1

        def newarray():
            return array(typecode, [0]) * 4 * width

        if meta["alpha"] and meta["greyscale"]:
            # LA to RGBA
            def convert():
                for row in pixels:
                    # Create a fresh target row, then copy L channel
                    # into first three target channels, and A channel
                    # into fourth channel.
                    a = newarray()
                    for i in range(3):
                        a[i::4] = row[0::2]
                    a[3::4] = row[1::2]
                    yield a

        elif meta["greyscale"]:
            # L to RGBA
            def convert():
                for row in pixels:
                    a = newarray()
                    for i in range(3):
                        a[i::4] = row
                    a[3::4] = array(typecode, [maxval]) * width
                    yield a

        else:
            assert not meta["alpha"] and not meta["greyscale"]

            # RGB to RGBA
            def convert():
                for row in pixels:
                    a = newarray()
                    for i in range(3):
                        a[i::4] = row[i::3]
                    a[3::4] = array(typecode, [maxval]) * width
                    yield a

        meta["alpha"] = True
        meta["greyscale"] = False
        return width, height, convert(), meta


# === Internal Test Support ===

# This section comprises the tests that are internally validated (as
# opposed to tests which produce output files that are externally
# validated).  Primarily they are unittests.

# Note that it is difficult to internally validate the results of
# writing a PNG file.  The only thing we can do is read it back in
# again, which merely checks consistency, not that the PNG file we
# produce is valid.

# Run the tests from the command line:
# python -c 'import png;png.test()'

# (For an in-memory binary file IO object) We use BytesIO where
# available, otherwise we use StringIO, but name it BytesIO.
try:
    from io import BytesIO
except:
    from StringIO import StringIO as BytesIO
import tempfile
import unittest


def test():
    unittest.main(__name__)


def topngbytes(name, rows, x, y, **k):
    """Convenience function for creating a PNG file "in memory" as a
    string.  Creates a :class:`Writer` instance using the keyword arguments,
    then passes `rows` to its :meth:`Writer.write` method.  The resulting
    PNG file is returned as a string.  `name` is used to identify the file for
    debugging.
    """

    import os

    print(name)
    f = BytesIO()
    w = Writer(x, y, **k)
    w.write(f, rows)
    if os.environ.get("PYPNG_TEST_TMP"):
        w = open(name, "wb")
        w.write(f.getvalue())
        w.close()
    return f.getvalue()


def testWithIO(inp, out, f):
    """Calls the function `f` with ``sys.stdin`` changed to `inp`
    and ``sys.stdout`` changed to `out`.  They are restored when `f`
    returns.  This function returns whatever `f` returns.
    """

    import os

    try:
        oldin, sys.stdin = sys.stdin, inp
        oldout, sys.stdout = sys.stdout, out
        x = f()
    finally:
        sys.stdin = oldin
        sys.stdout = oldout
    if os.environ.get("PYPNG_TEST_TMP") and hasattr(out, "getvalue"):
        name = mycallersname()
        if name:
            w = open(name + ".png", "wb")
            w.write(out.getvalue())
            w.close()
    return x


def mycallersname():
    """Returns the name of the caller of the caller of this function
    (hence the name of the caller of the function in which
    "mycallersname()" textually appears).  Returns None if this cannot
    be determined."""

    # http://docs.python.org/library/inspect.html#the-interpreter-stack
    import inspect

    frame = inspect.currentframe()
    if not frame:
        return None
    frame_, filename_, lineno_, funname, linelist_, listi_ = inspect.getouterframes(
        frame
    )[2]
    return funname


def seqtobytes(s):
    """Convert a sequence of integers to a *bytes* instance.  Good for
    plastering over Python 2 / Python 3 cracks.
    """

    return strtobytes("".join(chr(x) for x in s))


class Test(unittest.TestCase):
    # This member is used by the superclass.  If we don't define a new
    # class here then when we use self.assertRaises() and the PyPNG code
    # raises an assertion then we get no proper traceback.  I can't work
    # out why, but defining a new class here means we get a proper
    # traceback.
    class failureException(Exception):
        pass

    def helperLN(self, n):
        mask = (1 << n) - 1
        # Use small chunk_limit so that multiple chunk writing is
        # tested.  Making it a test for Issue 20.
        w = Writer(15, 17, greyscale=True, bitdepth=n, chunk_limit=99)
        f = BytesIO()
        w.write_array(f, array("B", map(mask.__and__, range(1, 256))))
        r = Reader(bytes=f.getvalue())
        x, y, pixels, meta = r.read()
        self.assertEqual(x, 15)
        self.assertEqual(y, 17)
        self.assertEqual(
            list(itertools.chain(*pixels)), map(mask.__and__, range(1, 256))
        )

    def testL8(self):
        return self.helperLN(8)

    def testL4(self):
        return self.helperLN(4)

    def testL2(self):
        "Also tests asRGB8."
        w = Writer(1, 4, greyscale=True, bitdepth=2)
        f = BytesIO()
        w.write_array(f, array("B", range(4)))
        r = Reader(bytes=f.getvalue())
        x, y, pixels, meta = r.asRGB8()
        self.assertEqual(x, 1)
        self.assertEqual(y, 4)
        for i, row in enumerate(pixels):
            self.assertEqual(len(row), 3)
            self.assertEqual(list(row), [0x55 * i] * 3)

    def testP2(self):
        "2-bit palette."
        a = (255, 255, 255)
        b = (200, 120, 120)
        c = (50, 99, 50)
        w = Writer(1, 4, bitdepth=2, palette=[a, b, c])
        f = BytesIO()
        w.write_array(f, array("B", (0, 1, 1, 2)))
        r = Reader(bytes=f.getvalue())
        x, y, pixels, meta = r.asRGB8()
        self.assertEqual(x, 1)
        self.assertEqual(y, 4)
        self.assertEqual(list(pixels), map(list, [a, b, b, c]))

    def testPtrns(self):
        "Test colour type 3 and tRNS chunk (and 4-bit palette)."
        a = (50, 99, 50, 50)
        b = (200, 120, 120, 80)
        c = (255, 255, 255)
        d = (200, 120, 120)
        e = (50, 99, 50)
        w = Writer(3, 3, bitdepth=4, palette=[a, b, c, d, e])
        f = BytesIO()
        w.write_array(f, array("B", (4, 3, 2, 3, 2, 0, 2, 0, 1)))
        r = Reader(bytes=f.getvalue())
        x, y, pixels, meta = r.asRGBA8()
        self.assertEqual(x, 3)
        self.assertEqual(y, 3)
        c = c + (255,)
        d = d + (255,)
        e = e + (255,)
        boxed = [(e, d, c), (d, c, a), (c, a, b)]
        flat = map(lambda row: itertools.chain(*row), boxed)
        self.assertEqual(map(list, pixels), map(list, flat))

    def testRGBtoRGBA(self):
        "asRGBA8() on colour type 2 source." ""
        # Test for Issue 26
        r = Reader(bytes=_pngsuite["basn2c08"])
        x, y, pixels, meta = r.asRGBA8()
        # Test the pixels at row 9 columns 0 and 1.
        row9 = list(pixels)[9]
        self.assertEqual(row9[0:8], [0xFF, 0xDF, 0xFF, 0xFF, 0xFF, 0xDE, 0xFF, 0xFF])

    def testLtoRGBA(self):
        "asRGBA() on grey source." ""
        # Test for Issue 60
        r = Reader(bytes=_pngsuite["basi0g08"])
        x, y, pixels, meta = r.asRGBA()
        row9 = list(list(pixels)[9])
        self.assertEqual(row9[0:8], [222, 222, 222, 255, 221, 221, 221, 255])

    def testCtrns(self):
        "Test colour type 2 and tRNS chunk."
        # Test for Issue 25
        r = Reader(bytes=_pngsuite["tbrn2c08"])
        x, y, pixels, meta = r.asRGBA8()
        # I just happen to know that the first pixel is transparent.
        # In particular it should be #7f7f7f00
        row0 = list(pixels)[0]
        self.assertEqual(tuple(row0[0:4]), (0x7F, 0x7F, 0x7F, 0x00))

    def testAdam7read(self):
        """Adam7 interlace reading.
        Specifically, test that for images in the PngSuite that
        have both an interlaced and straightlaced pair that both
        images from the pair produce the same array of pixels."""
        for candidate in _pngsuite:
            if not candidate.startswith("basn"):
                continue
            candi = candidate.replace("n", "i")
            if candi not in _pngsuite:
                continue
            print(f"adam7 read {candidate}")
            straight = Reader(bytes=_pngsuite[candidate])
            adam7 = Reader(bytes=_pngsuite[candi])
            # Just compare the pixels.  Ignore x,y (because they're
            # likely to be correct?); metadata is ignored because the
            # "interlace" member differs.  Lame.
            straight = straight.read()[2]
            adam7 = adam7.read()[2]
            self.assertEqual(map(list, straight), map(list, adam7))

    def testAdam7write(self):
        """Adam7 interlace writing.
        For each test image in the PngSuite, write an interlaced
        and a straightlaced version.  Decode both, and compare results.
        """
        # Not such a great test, because the only way we can check what
        # we have written is to read it back again.

        for name, bytes in _pngsuite.items():
            # Only certain colour types supported for this test.
            if name[3:5] not in ["n0", "n2", "n4", "n6"]:
                continue
            it = Reader(bytes=bytes)
            x, y, pixels, meta = it.read()
            pngi = topngbytes(
                f"adam7wn{name}.png",
                pixels,
                x=x,
                y=y,
                bitdepth=it.bitdepth,
                greyscale=it.greyscale,
                alpha=it.alpha,
                transparent=it.transparent,
                interlace=False,
            )
            x, y, ps, meta = Reader(bytes=pngi).read()
            it = Reader(bytes=bytes)
            x, y, pixels, meta = it.read()
            pngs = topngbytes(
                f"adam7wi{name}.png",
                pixels,
                x=x,
                y=y,
                bitdepth=it.bitdepth,
                greyscale=it.greyscale,
                alpha=it.alpha,
                transparent=it.transparent,
                interlace=True,
            )
            x, y, pi, meta = Reader(bytes=pngs).read()
            self.assertEqual(map(list, ps), map(list, pi))

    def testPGMin(self):
        """Test that the command line tool can read PGM files."""

        def do():
            return _main(["testPGMin"])

        s = BytesIO()
        s.write(strtobytes("P5 2 2 3\n"))
        s.write(strtobytes("\x00\x01\x02\x03"))
        s.flush()
        s.seek(0)
        o = BytesIO()
        testWithIO(s, o, do)
        r = Reader(bytes=o.getvalue())
        x, y, pixels, meta = r.read()
        self.assertTrue(r.greyscale)
        self.assertEqual(r.bitdepth, 2)

    def testPAMin(self):
        """Test that the command line tool can read PAM file."""

        def do():
            return _main(["testPAMin"])

        s = BytesIO()
        s.write(
            strtobytes(
                "P7\nWIDTH 3\nHEIGHT 1\nDEPTH 4\nMAXVAL 255\n"
                "TUPLTYPE RGB_ALPHA\nENDHDR\n"
            )
        )
        # The pixels in flat row flat pixel format
        flat = [255, 0, 0, 255, 0, 255, 0, 120, 0, 0, 255, 30]
        asbytes = seqtobytes(flat)
        s.write(asbytes)
        s.flush()
        s.seek(0)
        o = BytesIO()
        testWithIO(s, o, do)
        r = Reader(bytes=o.getvalue())
        x, y, pixels, meta = r.read()
        self.assertTrue(r.alpha)
        self.assertTrue(not r.greyscale)
        self.assertEqual(list(itertools.chain(*pixels)), flat)

    def testLA4(self):
        """Create an LA image with bitdepth 4."""
        bytes = topngbytes(
            "la4.png", [[5, 12]], 1, 1, greyscale=True, alpha=True, bitdepth=4
        )
        sbit = Reader(bytes=bytes).chunk("sBIT")[1]
        self.assertEqual(sbit, strtobytes("\x04\x04"))

    def testPNMsbit(self):
        """Test that PNM files can generates sBIT chunk."""

        def do():
            return _main(["testPNMsbit"])

        s = BytesIO()
        s.write(strtobytes("P6 8 1 1\n"))
        for pixel in range(8):
            s.write(struct.pack("<I", (0x4081 * pixel) & 0x10101)[:3])
        s.flush()
        s.seek(0)
        o = BytesIO()
        testWithIO(s, o, do)
        r = Reader(bytes=o.getvalue())
        sbit = r.chunk("sBIT")[1]
        self.assertEqual(sbit, strtobytes("\x01\x01\x01"))

    def testLtrns0(self):
        """Create greyscale image with tRNS chunk."""
        return self.helperLtrns(0)

    def testLtrns1(self):
        """Using 1-tuple for transparent arg."""
        return self.helperLtrns((0,))

    def helperLtrns(self, transparent):
        """Helper used by :meth:`testLtrns*`."""
        pixels = zip([0x00, 0x38, 0x4C, 0x54, 0x5C, 0x40, 0x38, 0x00])
        o = BytesIO()
        w = Writer(8, 8, greyscale=True, bitdepth=1, transparent=transparent)
        w.write_packed(o, pixels)
        r = Reader(bytes=o.getvalue())
        x, y, pixels, meta = r.asDirect()
        self.assertTrue(meta["alpha"])
        self.assertTrue(meta["greyscale"])
        self.assertEqual(meta["bitdepth"], 1)

    def testWinfo(self):
        """Test the dictionary returned by a `read` method can be used
        as args for :meth:`Writer`.
        """
        r = Reader(bytes=_pngsuite["basn2c16"])
        info = r.read()[3]
        w = Writer(**info)

    def testPackedIter(self):
        """Test iterator for row when using write_packed.

        Indicative for Issue 47.
        """
        w = Writer(16, 2, greyscale=True, alpha=False, bitdepth=1)
        o = BytesIO()
        w.write_packed(
            o, [itertools.chain([0x0A], [0xAA]), itertools.chain([0x0F], [0xFF])]
        )
        r = Reader(bytes=o.getvalue())
        x, y, pixels, info = r.asDirect()
        pixels = list(pixels)
        self.assertEqual(len(pixels), 2)
        self.assertEqual(len(pixels[0]), 16)

    def testInterlacedArray(self):
        """Test that reading an interlaced PNG yields each row as an
        array."""
        r = Reader(bytes=_pngsuite["basi0g08"])
        list(r.read()[2])[0].tostring

    def testTrnsArray(self):
        """Test that reading a type 2 PNG with tRNS chunk yields each
        row as an array (using asDirect)."""
        r = Reader(bytes=_pngsuite["tbrn2c08"])
        list(r.asDirect()[2])[0].tostring

    # Invalid file format tests.  These construct various badly
    # formatted PNG files, then feed them into a Reader.  When
    # everything is working properly, we should get FormatError
    # exceptions raised.
    def testEmpty(self):
        """Test empty file."""

        r = Reader(bytes="")
        self.assertRaises(FormatError, r.asDirect)

    def testSigOnly(self):
        """Test file containing just signature bytes."""

        r = Reader(bytes=_signature)
        self.assertRaises(FormatError, r.asDirect)

    def testExtraPixels(self):
        """Test file that contains too many pixels."""

        def eachchunk(chunk):
            if chunk[0] != "IDAT":
                return chunk
            data = zlib.decompress(chunk[1])
            data += strtobytes("\x00garbage")
            data = zlib.compress(data)
            chunk = (chunk[0], data)
            return chunk

        self.assertRaises(FormatError, self.helperFormat, eachchunk)

    def testNotEnoughPixels(self):
        def eachchunk(chunk):
            if chunk[0] != "IDAT":
                return chunk
            # Remove last byte.
            data = zlib.decompress(chunk[1])
            data = data[:-1]
            data = zlib.compress(data)
            return (chunk[0], data)

        self.assertRaises(FormatError, self.helperFormat, eachchunk)

    def helperFormat(self, f):
        r = Reader(bytes=_pngsuite["basn0g01"])
        o = BytesIO()

        def newchunks():
            for chunk in r.chunks():
                yield f(chunk)

        write_chunks(o, newchunks())
        r = Reader(bytes=o.getvalue())
        return list(r.asDirect()[2])

    def testBadFilter(self):
        def eachchunk(chunk):
            if chunk[0] != "IDAT":
                return chunk
            data = zlib.decompress(chunk[1])
            # Corrupt the first filter byte
            data = strtobytes("\x99") + data[1:]
            data = zlib.compress(data)
            return (chunk[0], data)

        self.assertRaises(FormatError, self.helperFormat, eachchunk)

    def testFlat(self):
        """Test read_flat."""
        import hashlib

        r = Reader(bytes=_pngsuite["basn0g02"])
        x, y, pixel, meta = r.read_flat()
        d = hashlib.md5(seqtobytes(pixel)).digest()
        self.assertEqual(_enhex(d), "255cd971ab8cd9e7275ff906e5041aa0")

    def testfromarray(self):
        img = from_array([[0, 0x33, 0x66], [0xFF, 0xCC, 0x99]], "L")
        img.save("testfromarray.png")

    def testfromarrayL16(self):
        img = from_array(group(range(2**16), 256), "L;16")
        img.save("testL16.png")

    def testfromarrayRGB(self):
        img = from_array(
            [
                [0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 1],
                [1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1],
            ],
            "RGB;1",
        )
        o = BytesIO()
        img.save(o)

    def testfromarrayIter(self):
        import itertools

        i = itertools.islice(itertools.count(10), 20)
        i = map(lambda x: [x, x, x], i)
        img = from_array(i, "RGB;5", dict(height=20))
        f = open("testiter.png", "wb")
        img.save(f)
        f.close()

    # numpy dependent tests.  These are skipped (with a message to
    # sys.stderr) if numpy cannot be imported.
    def testNumpyuint16(self):
        """numpy uint16."""

        try:
            import numpy
        except ImportError:
            sys.stderr.write("skipping numpy test\n")
            return

        rows = [map(numpy.uint16, range(0, 0x10000, 0x5555))]
        b = topngbytes(
            "numpyuint16.png", rows, 4, 1, greyscale=True, alpha=False, bitdepth=16
        )

    def testNumpyuint8(self):
        """numpy uint8."""

        try:
            import numpy
        except ImportError:
            sys.stderr.write("skipping numpy test\n")
            return

        rows = [map(numpy.uint8, range(0, 0x100, 0x55))]
        b = topngbytes(
            "numpyuint8.png", rows, 4, 1, greyscale=True, alpha=False, bitdepth=8
        )

    def testNumpybool(self):
        """numpy bool."""

        try:
            import numpy
        except ImportError:
            sys.stderr.write("skipping numpy test\n")
            return

        rows = [map(numpy.bool, [0, 1])]
        b = topngbytes(
            "numpybool.png", rows, 2, 1, greyscale=True, alpha=False, bitdepth=1
        )

    def testNumpyarray(self):
        """numpy array."""
        try:
            import numpy
        except ImportError:
            sys.stderr.write("skipping numpy test\n")
            return

        pixels = numpy.array([[0, 0x5555], [0x5555, 0xAAAA]], numpy.uint16)
        img = from_array(pixels, "L")
        img.save("testnumpyL16.png")


# === Command Line Support ===


def _dehex(s):
    """Liberally convert from hex string to binary string."""
    import re
    import binascii

    # Remove all non-hexadecimal digits
    s = re.sub(r"[^a-fA-F\d]", "", s)
    # binscii.unhexlify works in Python 2 and Python 3 (unlike
    # thing.decode('hex')).
    return binascii.unhexlify(strtobytes(s))


def _enhex(s):
    """Convert from binary string (bytes) to hex string (str)."""

    import binascii

    return bytestostr(binascii.hexlify(s))


# Copies of PngSuite test files taken
# from http://www.schaik.com/pngsuite/pngsuite_bas_png.html
# on 2009-02-19 by drj and converted to hex.
# Some of these are not actually in PngSuite (but maybe they should
# be?), they use the same naming scheme, but start with a capital
# letter.
_pngsuite = {
    "basi0g01": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000200000002001000000012c0677
cf0000000467414d41000186a031e8965f0000009049444154789c2d8d310ec2
300c45dfc682c415187a00a42e197ab81e83b127e00c5639001363a580d8582c
65c910357c4b78b0bfbfdf4f70168c19e7acb970a3f2d1ded9695ce5bf5963df
d92aaf4c9fd927ea449e6487df5b9c36e799b91bdf082b4d4bd4014fe4014b01
ab7a17aee694d28d328a2d63837a70451e1648702d9a9ff4a11d2f7a51aa21e5
a18c7ffd0094e3511d661822f20000000049454e44ae426082
"""
    ),
    "basi0g02": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000200000002002000000016ba60d
1f0000000467414d41000186a031e8965f0000005149444154789c635062e860
00e17286bb609c93c370ec189494960631366e4467b3ae675dcf10f521ea0303
90c1ca006444e11643482064114a4852c710baea3f18c31918020c30410403a6
0ac1a09239009c52804d85b6d97d0000000049454e44ae426082
"""
    ),
    "basi0g04": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000200400000001e4e6f8
bf0000000467414d41000186a031e8965f000000ae49444154789c658e5111c2
301044171c141c141c041c843a287510ea20d441c041c141c141c04191102454
03994998cecd7edcecedbb9bdbc3b2c2b6457545fbc4bac1be437347f7c66a77
3c23d60db15e88f5c5627338a5416c2e691a9b475a89cd27eda12895ae8dfdab
43d61e590764f5c83a226b40d669bec307f93247701687723abf31ff83a2284b
a5b4ae6b63ac6520ad730ca4ed7b06d20e030369bd6720ed383290360406d24e
13811f2781eba9d34d07160000000049454e44ae426082
"""
    ),
    "basi0g08": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000200800000001211615
be0000000467414d41000186a031e8965f000000b549444154789cb5905d0ac2
3010849dbac81c42c47bf843cf253e8878b0aa17110f214bdca6be240f5d21a5
94ced3e49bcd322c1624115515154998aa424822a82a5624a1aa8a8b24c58f99
999908130989a04a00d76c2c09e76cf21adcb209393a6553577da17140a2c59e
70ecbfa388dff1f03b82fb82bd07f05f7cb13f80bb07ad2fd60c011c3c588eef
f1f4e03bbec7ce832dca927aea005e431b625796345307b019c845e6bfc3bb98
769d84f9efb02ea6c00f9bb9ff45e81f9f280000000049454e44ae426082
"""
    ),
    "basi0g16": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000200000002010000000017186c9
fd0000000467414d41000186a031e8965f000000e249444154789cb5913b0ec2
301044c7490aa8f85d81c3e4301c8f53a4ca0da8902c8144b3920b4043111282
23bc4956681a6bf5fc3c5a3ba0448912d91a4de2c38dd8e380231eede4c4f7a1
4677700bec7bd9b1d344689315a3418d1a6efbe5b8305ba01f8ff4808c063e26
c60d5c81edcf6c58c535e252839e93801b15c0a70d810ae0d306b205dc32b187
272b64057e4720ff0502154034831520154034c3df81400510cdf0015c86e5cc
5c79c639fddba9dcb5456b51d7980eb52d8e7d7fa620a75120d6064641a05120
b606771a05626b401a05f1f589827cf0fe44c1f0bae0055698ee8914fffffe00
00000049454e44ae426082
"""
    ),
    "basi2c08": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000200000002008020000018b1fdd
350000000467414d41000186a031e8965f000000f249444154789cd59341aa04
210c44abc07b78133d59d37333bd89d76868b566d10cf4675af8596431a11662
7c5688919280e312257dd6a0a4cf1a01008ee312a5f3c69c37e6fcc3f47e6776
a07f8bdaf5b40feed2d33e025e2ff4fe2d4a63e1a16d91180b736d8bc45854c5
6d951863f4a7e0b66dcf09a900f3ffa2948d4091e53ca86c048a64390f662b50
4a999660ced906182b9a01a8be00a56404a6ede182b1223b4025e32c4de34304
63457680c93aada6c99b73865aab2fc094920d901a203f5ddfe1970d28456783
26cffbafeffcd30654f46d119be4793f827387fc0d189d5bc4d69a3c23d45a7f
db803146578337df4d0a3121fc3d330000000049454e44ae426082
"""
    ),
    "basi2c16": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000201002000001db8f01
760000000467414d41000186a031e8965f0000020a49444154789cd5962173e3
3010853fcf1838cc61a1818185a53e56787fa13fa130852e3b5878b4b0b03081
b97f7030070b53e6b057a0a8912bbb9163b9f109ececbc59bd7dcf2b45492409
d66f00eb1dd83cb5497d65456aeb8e1040913b3b2c04504c936dd5a9c7e2c6eb
b1b8f17a58e8d043da56f06f0f9f62e5217b6ba3a1b76f6c9e99e8696a2a72e2
c4fb1e4d452e92ec9652b807486d12b6669be00db38d9114b0c1961e375461a5
5f76682a85c367ad6f682ff53a9c2a353191764b78bb07d8ddc3c97c1950f391
6745c7b9852c73c2f212605a466a502705c8338069c8b9e84efab941eb393a97
d4c9fd63148314209f1c1d3434e847ead6380de291d6f26a25c1ebb5047f5f24
d85c49f0f22cc1d34282c72709cab90477bf25b89d49f0f351822297e0ea9704
f34c82bc94002448ede51866e5656aef5d7c6a385cb4d80e6a538ceba04e6df2
480e9aa84ddedb413bb5c97b3838456df2d4fec2c7a706983e7474d085fae820
a841776a83073838973ac0413fea2f1dc4a06e71108fda73109bdae48954ad60
bf867aac3ce44c7c1589a711cf8a81df9b219679d96d1cec3d8bbbeaa2012626
df8c7802eda201b2d2e0239b409868171fc104ba8b76f10b4da09f6817ffc609
c413ede267fd1fbab46880c90f80eccf0013185eb48b47ba03df2bdaadef3181
cb8976f18e13188768170f98c0f844bb78cb04c62ddac59d09fc3fa25dfc1da4
14deb3df1344f70000000049454e44ae426082
"""
    ),
    "basi3p08": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020080300000133a3ba
500000000467414d41000186a031e8965f00000300504c5445224400f5ffed77
ff77cbffff110a003a77002222ffff11ff110000222200ffac5566ff66ff6666
ff01ff221200dcffffccff994444ff005555220000cbcbff44440055ff55cbcb
00331a00ffecdcedffffe4ffcbffdcdc44ff446666ff330000442200ededff66
6600ffa444ffffaaeded0000cbcbfefffffdfffeffff0133ff33552a000101ff
8888ff00aaaa010100440000888800ffe4cbba5b0022ff22663200ffff99aaaa
ff550000aaaa00cb630011ff11d4ffaa773a00ff4444dc6b0066000001ff0188
4200ecffdc6bdc00ffdcba00333300ed00ed7300ffff88994a0011ffff770000
ff8301ffbabafe7b00fffeff00cb00ff999922ffff880000ffff77008888ffdc
ff1a33000000aa33ffff009900990000000001326600ffbaff44ffffffaaff00
770000fefeaa00004a9900ffff66ff22220000998bff1155ffffff0101ff88ff
005500001111fffffefffdfea4ff4466ffffff66ff003300ffff55ff77770000
88ff44ff00110077ffff006666ffffed000100fff5ed1111ffffff44ff22ffff
eded11110088ffff00007793ff2200dcdc3333fffe00febabaff99ffff333300
63cb00baba00acff55ffffdcffff337bfe00ed00ed5555ffaaffffdcdcff5555
00000066dcdc00dc00dc83ff017777fffefeffffffcbff5555777700fefe00cb
00cb0000fe010200010000122200ffff220044449bff33ffd4aa0000559999ff
999900ba00ba2a5500ffcbcbb4ff66ff9b33ffffbaaa00aa42880053aa00ffaa
aa0000ed00babaffff1100fe00000044009999990099ffcc99ba000088008800
dc00ff93220000dcfefffeaa5300770077020100cb0000000033ffedff00ba00
ff3333edffedffc488bcff7700aa00660066002222dc0000ffcbffdcffdcff8b
110000cb00010155005500880000002201ffffcbffcbed0000ff88884400445b
ba00ffbc77ff99ff006600baffba00777773ed00fe00003300330000baff77ff
004400aaffaafffefe000011220022c4ff8800eded99ff99ff55ff002200ffb4
661100110a1100ff1111dcffbabaffff88ff88010001ff33ffb98ed362000002
a249444154789c65d0695c0b001806f03711a9904a94d24dac63292949e5a810
d244588a14ca5161d1a1323973252242d62157d12ae498c8124d25ca3a11398a
16e55a3cdffab0ffe7f77d7fcff3528645349b584c3187824d9d19d4ec2e3523
9eb0ae975cf8de02f2486d502191841b42967a1ad49e5ddc4265f69a899e26b5
e9e468181baae3a71a41b95669da8df2ea3594c1b31046d7b17bfb86592e4cbe
d89b23e8db0af6304d756e60a8f4ad378bdc2552ae5948df1d35b52143141533
33bbbbababebeb3b3bc9c9c9c6c6c0c0d7b7b535323225a5aa8a02024a4bedec
0a0a2a2bcdcd7d7cf2f3a9a9c9cdcdd8b8adcdd5b5ababa828298982824a4ab2
b21212acadbdbc1414e2e24859b9a72730302f4f49292c4c57373c9c0a0b7372
8c8c1c1c3a3a92936d6dfdfd293e3e26262a4a4eaea2424b4b5fbfbc9c323278
3c0b0ba1303abaae8ecdeeed950d6669a9a7a7a141d4de9e9d5d5cdcd2229b94
c572716132f97cb1d8db9bc3110864a39795d9db6b6a26267a7a9a98d4d6a6a7
cb76090ef6f030354d4d75766e686030545464cb393a1a1ac6c68686eae8f8f9
a9aa4644c8b66d6e1689dcdd2512a994cb35330b0991ad9f9b6b659596a6addd
d8282fafae5e5323fb8f41d01f76c22fd8061be01bfc041a0323e1002c81cd30
0b9ec027a0c930014ec035580fc3e112bc069a0b53e11c0c8095f00176c163a0
e5301baec06a580677600ddc05ba0f13e120bc81a770133ec355a017300d4ec2
0c7800bbe1219c02fa08f3e13c1c85dbb00a2ec05ea0dff00a6ec15a98027360
070c047a06d7e1085c84f1b014f6c03fa0b33018b6c0211801ebe018fc00da0a
6f61113c877eb01d4ec317a085700f26c130f80efbe132bc039a0733e106fc81
f7f017f6c10aa0d1300a0ec374780943e1382c06fa0a9b60238c83473016cec0
02f80f73fefe1072afc1e50000000049454e44ae426082
"""
    ),
    "basi6a08": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000200806000001047d4a
620000000467414d41000186a031e8965f0000012049444154789cc595414ec3
3010459fa541b8bbb26641b8069b861e8b4d12c1c112c1452a710a2a65d840d5
949041fc481ec98ae27c7f3f8d27e3e4648047600fec0d1f390fbbe2633a31e2
9389e4e4ea7bfdbf3d9a6b800ab89f1bd6b553cfcbb0679e960563d72e0a9293
b7337b9f988cc67f5f0e186d20e808042f1c97054e1309da40d02d7e27f92e03
6cbfc64df0fc3117a6210a1b6ad1a00df21c1abcf2a01944c7101b0cb568a001
909c9cf9e399cf3d8d9d4660a875405d9a60d000b05e2de55e25780b7a5268e0
622118e2399aab063a815808462f1ab86890fc2e03e48bb109ded7d26ce4bf59
0db91bac0050747fec5015ce80da0e5700281be533f0ce6d5900b59bcb00ea6d
200314cf801faab200ea752803a8d7a90c503a039f824a53f4694e7342000000
0049454e44ae426082
"""
    ),
    "basn0g01": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000200000002001000000005b0147
590000000467414d41000186a031e8965f0000005b49444154789c2dccb10903
300c05d1ebd204b24a200b7a346f90153c82c18d0a61450751f1e08a2faaead2
a4846ccea9255306e753345712e211b221bf4b263d1b427325255e8bdab29e6f
6aca30692e9d29616ee96f3065f0bf1f1087492fd02f14c90000000049454e44
ae426082
"""
    ),
    "basn0g02": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000200000002002000000001ca13d
890000000467414d41000186a031e8965f0000001f49444154789c6360085df5
1f8cf1308850c20053868f0133091f6390b90700bd497f818b0989a900000000
49454e44ae426082
"""
    ),
    # A version of basn0g04 dithered down to 3 bits.
    "Basn0g03": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020040000000093e1c8
2900000001734249540371d88211000000fd49444154789c6d90d18906210c84
c356f22356b2889588604301b112112b11d94a96bb495cf7fe87f32d996f2689
44741cc658e39c0b118f883e1f63cc89dafbc04c0f619d7d898396c54b875517
83f3a2e7ac09a2074430e7f497f00f1138a5444f82839c5206b1f51053cca968
63258821e7f2b5438aac16fbecc052b646e709de45cf18996b29648508728612
952ca606a73566d44612b876845e9a347084ea4868d2907ff06be4436c4b41a3
a3e1774285614c5affb40dbd931a526619d9fa18e4c2be420858de1df0e69893
a0e3e5523461be448561001042b7d4a15309ce2c57aef2ba89d1c13794a109d7
b5880aa27744fc5c4aecb5e7bcef5fe528ec6293a930690000000049454e44ae
426082
"""
    ),
    "basn0g04": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020040000000093e1c8
290000000467414d41000186a031e8965f0000004849444154789c6360601014
545232367671090d4d4b2b2f6720430095dbd1418e002a77e64c720450b9ab56
912380caddbd9b1c0154ee9933e408a072efde25470095fbee1d1902001f14ee
01eaff41fa0000000049454e44ae426082
"""
    ),
    "basn0g08": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000200800000000561125
280000000467414d41000186a031e8965f0000004149444154789c6364602400
1408c8b30c05058c0f0829f8f71f3f6079301c1430ca11906764a2795c0c0605
8c8ff0cafeffcff887e67131181430cae0956564040050e5fe7135e2d8590000
000049454e44ae426082
"""
    ),
    "basn0g16": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000200000002010000000000681f9
6b0000000467414d41000186a031e8965f0000005e49444154789cd5d2310ac0
300c4351395bef7fc6dca093c0287b32d52a04a3d98f3f3880a7b857131363a0
3a82601d089900dd82f640ca04e816dc06422640b7a03d903201ba05b7819009
d02d680fa44c603f6f07ec4ff41938cf7f0016d84bd85fae2b9fd70000000049
454e44ae426082
"""
    ),
    "basn2c08": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000200802000000fc18ed
a30000000467414d41000186a031e8965f0000004849444154789cedd5c10900
300c024085ec91fdb772133b442bf4a1f8cee12bb40d043b800a14f81ca0ede4
7d4c784081020f4a871fc284071428f0a0743823a94081bb7077a3c00182b1f9
5e0f40cf4b0000000049454e44ae426082
"""
    ),
    "basn2c16": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000201002000000ac8831
e00000000467414d41000186a031e8965f000000e549444154789cd596c10a83
301044a7e0417fcb7eb7fdadf6961e06039286266693cc7a188645e43dd6a08f
1042003e2fe09aef6472737e183d27335fcee2f35a77b702ebce742870a23397
f3edf2705dd10160f3b2815fe8ecf2027974a6b0c03f74a6e4192843e75c6c03
35e8ec3202f5e84c0181bbe8cca967a00d9df3491bb040671f2e6087ce1c2860
8d1e05f8c7ee0f1d00b667e70df44467ef26d01fbd9bc028f42860f71d188bce
fb8d3630039dbd59601e7ab3c06cf428507f0634d039afdc80123a7bb1801e7a
b1802a7a14c89f016d74ce331bf080ce9e08f8414f04bca133bfe642fe5e07bb
c4ec0000000049454e44ae426082
"""
    ),
    "basn6a08": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000200806000000737a7a
f40000000467414d41000186a031e8965f0000006f49444154789cedd6310a80
300c46e12764684fa1f73f55048f21c4ddc545781d52e85028fc1f4d28d98a01
305e7b7e9cffba33831d75054703ca06a8f90d58a0074e351e227d805c8254e3
1bb0420f5cdc2e0079208892ffe2a00136a07b4007943c1004d900195036407f
011bf00052201a9c160fb84c0000000049454e44ae426082
"""
    ),
    "cs3n3p08": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020080300000044a48a
c60000000467414d41000186a031e8965f0000000373424954030303a392a042
00000054504c544592ff0000ff9200ffff00ff0000dbff00ff6dffb600006dff
b6ff00ff9200dbff000049ffff2400ff000024ff0049ff0000ffdb00ff4900ff
b6ffff0000ff2400b6ffffdb000092ffff6d000024ffff49006dff00df702b17
0000004b49444154789c85cac70182000000b1b3625754b0edbfa72324ef7486
184ed0177a437b680bcdd0031c0ed00ea21f74852ed00a1c9ed0086da0057487
6ed0121cd6d004bda0013a421ff803224033e177f4ae260000000049454e44ae
426082
"""
    ),
    "s09n3p02": _dehex(
        """
89504e470d0a1a0a0000000d49484452000000090000000902030000009dffee
830000000467414d41000186a031e8965f000000037342495404040477f8b5a3
0000000c504c544500ff000077ffff00ffff7700ff5600640000001f49444154
789c63600002fbff0c0c56ab19182ca381581a4283f82071200000696505c36a
437f230000000049454e44ae426082
"""
    ),
    "tbgn3p08": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020080300000044a48a
c60000000467414d41000186a031e8965f00000207504c54457f7f7fafafafab
abab110000222200737300999999510d00444400959500959595e6e600919191
8d8d8d620d00898989666600b7b700911600000000730d007373736f6f6faaaa
006b6b6b676767c41a00cccc0000f30000ef00d51e0055555567670000dd0051
515100d1004d4d4de61e0038380000b700160d0d00ab00560d00090900009500
009100008d003333332f2f2f2f2b2f2b2b000077007c7c001a05002b27000073
002b2b2b006f00bb1600272727780d002323230055004d4d00cc1e00004d00cc
1a000d00003c09006f6f00002f003811271111110d0d0d55554d090909001100
4d0900050505000d00e2e200000900000500626200a6a6a6a2a2a29e9e9e8484
00fb00fbd5d500801100800d00ea00ea555500a6a600e600e6f7f700e200e233
0500888888d900d9848484c01a007777003c3c05c8c8008080804409007c7c7c
bb00bbaa00aaa600a61e09056262629e009e9a009af322005e5e5e05050000ee
005a5a5adddd00a616008d008d00e20016050027270088110078780000c40078
00787300736f006f44444400aa00c81e004040406600663c3c3c090000550055
1a1a00343434d91e000084004d004d007c004500453c3c00ea1e00222222113c
113300331e1e1efb22001a1a1a004400afaf00270027003c001616161e001e0d
160d2f2f00808000001e00d1d1001100110d000db7b7b7090009050005b3b3b3
6d34c4230000000174524e530040e6d86600000001624b474402660b7c640000
01f249444154789c6360c0048c8c58049100575f215ee92e6161ef109cd2a15e
4b9645ce5d2c8f433aa4c24f3cbd4c98833b2314ab74a186f094b9c2c27571d2
6a2a58e4253c5cda8559057a392363854db4d9d0641973660b0b0bb76bb16656
06970997256877a07a95c75a1804b2fbcd128c80b482a0b0300f8a824276a9a8
ec6e61612b3e57ee06fbf0009619d5fac846ac5c60ed20e754921625a2daadc6
1967e29e97d2239c8aec7e61fdeca9cecebef54eb36c848517164514af16169e
866444b2b0b7b55534c815cc2ec22d89cd1353800a8473100a4485852d924a6a
412adc74e7ad1016ceed043267238c901716f633a812022998a4072267c4af02
92127005c0f811b62830054935ce017b38bf0948cc5c09955f030a24617d9d46
63371fd940b0827931cbfdf4956076ac018b592f72d45594a9b1f307f3261b1a
084bc2ad50018b1900719ba6ba4ca325d0427d3f6161449486f981144cf3100e
2a5f2a1ce8683e4ddf1b64275240c8438d98af0c729bbe07982b8a1c94201dc2
b3174c9820bcc06201585ad81b25b64a2146384e3798290c05ad280a18c0a62e
e898260c07fca80a24c076cc864b777131a00190cdfa3069035eccbc038c30e1
3e88b46d16b6acc5380d6ac202511c392f4b789aa7b0b08718765990111606c2
9e854c38e5191878fbe471e749b0112bb18902008dc473b2b2e8e72700000000
49454e44ae426082
"""
    ),
    "Tp2n3p08": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020080300000044a48a
c60000000467414d41000186a031e8965f00000300504c544502ffff80ff05ff
7f0703ff7f0180ff04ff00ffff06ff000880ff05ff7f07ffff06ff000804ff00
0180ff02ffff03ff7f02ffff80ff0503ff7f0180ffff0008ff7f0704ff00ffff
06ff000802ffffff7f0704ff0003ff7fffff0680ff050180ff04ff000180ffff
0008ffff0603ff7f80ff05ff7f0702ffffff000880ff05ffff0603ff7f02ffff
ff7f070180ff04ff00ffff06ff000880ff050180ffff7f0702ffff04ff0003ff
7fff7f0704ff0003ff7f0180ffffff06ff000880ff0502ffffffff0603ff7fff
7f0702ffff04ff000180ff80ff05ff0008ff7f07ffff0680ff0504ff00ff0008
0180ff03ff7f02ffff02ffffffff0604ff0003ff7f0180ffff000880ff05ff7f
0780ff05ff00080180ff02ffffff7f0703ff7fffff0604ff00ff7f07ff0008ff
ff0680ff0504ff0002ffff0180ff03ff7fff0008ffff0680ff0504ff000180ff
02ffff03ff7fff7f070180ff02ffff04ff00ffff06ff0008ff7f0780ff0503ff
7fffff06ff0008ff7f0780ff0502ffff03ff7f0180ff04ff0002ffffff7f07ff
ff0604ff0003ff7fff00080180ff80ff05ffff0603ff7f0180ffff000804ff00
80ff0502ffffff7f0780ff05ffff0604ff000180ffff000802ffffff7f0703ff
7fff0008ff7f070180ff03ff7f02ffff80ff05ffff0604ff00ff0008ffff0602
ffff0180ff04ff0003ff7f80ff05ff7f070180ff04ff00ff7f0780ff0502ffff
ff000803ff7fffff0602ffffff7f07ffff0680ff05ff000804ff0003ff7f0180
ff02ffff0180ffff7f0703ff7fff000804ff0080ff05ffff0602ffff04ff00ff
ff0603ff7fff7f070180ff80ff05ff000803ff7f0180ffff7f0702ffffff0008
04ff00ffff0680ff0503ff7f0180ff04ff0080ff05ffff06ff000802ffffff7f
0780ff05ff0008ff7f070180ff03ff7f04ff0002ffffffff0604ff00ff7f07ff
000880ff05ffff060180ff02ffff03ff7f80ff05ffff0602ffff0180ff03ff7f
04ff00ff7f07ff00080180ffff000880ff0502ffff04ff00ff7f0703ff7fffff
06ff0008ffff0604ff00ff7f0780ff0502ffff03ff7f0180ffdeb83387000000
f874524e53000000000000000008080808080808081010101010101010181818
1818181818202020202020202029292929292929293131313131313131393939
393939393941414141414141414a4a4a4a4a4a4a4a52525252525252525a5a5a
5a5a5a5a5a62626262626262626a6a6a6a6a6a6a6a73737373737373737b7b7b
7b7b7b7b7b83838383838383838b8b8b8b8b8b8b8b94949494949494949c9c9c
9c9c9c9c9ca4a4a4a4a4a4a4a4acacacacacacacacb4b4b4b4b4b4b4b4bdbdbd
bdbdbdbdbdc5c5c5c5c5c5c5c5cdcdcdcdcdcdcdcdd5d5d5d5d5d5d5d5dedede
dededededee6e6e6e6e6e6e6e6eeeeeeeeeeeeeeeef6f6f6f6f6f6f6f6b98ac5
ca0000012c49444154789c6360e7169150d230b475f7098d4ccc28a96ced9e32
63c1da2d7b8e9fb97af3d1fb8f3f18e8a0808953544a4dd7c4c2c9233c2621bf
b4aab17fdacce5ab36ee3a72eafaad87efbefea68702362e7159652d031b07cf
c0b8a4cce28aa68e89f316aedfb4ffd0b92bf79fbcfcfe931e0a183904e55435
8decdcbcc22292b3caaadb7b27cc5db67af3be63e72fdf78fce2d31f7a2860e5
119356d037b374f10e8a4fc92eaa6fee99347fc9caad7b0f9ebd74f7c1db2fbf
e8a180995f484645dbdccad12f38363dafbcb6a573faeca5ebb6ed3e7ce2c29d
e76fbefda38702063e0149751d537b67ff80e8d4dcc29a86bea97316add9b0e3
c0e96bf79ebdfafc971e0a587885e515f58cad5d7d43a2d2720aeadaba26cf5a
bc62fbcea3272fde7efafac37f3a28000087c0fe101bc2f85f0000000049454e
44ae426082
"""
    ),
    "tbbn1g04": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020040000000093e1c8
290000000467414d41000186a031e8965f0000000274524e530007e8f7589b00
000002624b47440000aa8d23320000013e49444154789c55d1cd4b024118c7f1
efbe6419045b6a48a72d352808b435284f9187ae9b098627a1573a19945beba5
e8129e8222af11d81e3a4545742de8ef6af6d5762e0fbf0fc33c33f36085cb76
bc4204778771b867260683ee57e13f0c922df5c719c2b3b6c6c25b2382cea4b9
9f7d4f244370746ac71f4ca88e0f173a6496749af47de8e44ba8f3bf9bdfa98a
0faf857a7dd95c7dc8d7c67c782c99727997f41eb2e3c1e554152465bb00fe8e
b692d190b718d159f4c0a45c4435915a243c58a7a4312a7a57913f05747594c6
46169866c57101e4d4ce4d511423119c419183a3530cc63db88559ae28e7342a
1e9c8122b71139b8872d6e913153224bc1f35b60e4445bd4004e20ed6682c759
1d9873b3da0fbf50137dc5c9bde84fdb2ec8bde1189e0448b63584735993c209
7a601bd2710caceba6158797285b7f2084a2f82c57c01a0000000049454e44ae
426082
"""
    ),
    "tbrn2c08": _dehex(
        """
89504e470d0a1a0a0000000d4948445200000020000000200802000000fc18ed
a30000000467414d41000186a031e8965f0000000674524e53007f007f007f8a
33334f00000006624b474400ff0000000033277cf3000004d649444154789cad
965f68537714c73fd912d640235e692f34d0406fa0c1663481045ab060065514
56660a295831607df0a1488715167060840a1614e6431e9cb34fd2c00a762c85
f6a10f816650c13b0cf40612e1822ddc4863bd628a8924d23d6464f9d3665dd9
f7e977ce3dbff3cd3939bfdfef6bb87dfb364782dbed065ebe7cd93acc78b4ec
a228debd7bb7bfbfbfbbbbfb7f261045311a8d261209405194274f9ea4d3e916
f15f1c3eb5dd6e4fa5fecce526239184a2b0b8486f6f617171b1f5ae4311381c
8e57af5e5dbd7a351088150a78bd389d44222c2f93cdfe66b7db8f4ee07038b6
b6b6bebf766d7e7e7e60a06432313b4ba984c3c1c4049a46b95c5a58583822c1
dbb76f27272733d1b9df853c3030c0f232562b9108cf9eb1b888d7cbf030abab
31abd5fa1f08dc6ef7e7cf9f1f3f7e1c8944745d4f1400c62c001313acad21cb
b8dd2c2c603271eb1640341aad4c6d331aa7e8c48913a150a861307ecc11e964
74899919bc5e14e56fffc404f1388502f178dceff7ef4bf0a5cfe7abb533998c
e5f9ea2f1dd88c180d64cb94412df3dd57e83a6b3b3c7a84c98420100c72fd3a
636348bae726379fe69e8e8d8dbd79f3a6558b0607079796965256479b918085
7b02db12712b6181950233023f3f647494ee6e2e5ea45864cce5b8a7fe3acffc
3aebb22c2bd5d20e22d0757d7b7bbbbdbd3d94a313bed1b0aa3cd069838b163a
8d4c59585f677292d0b84d9a995bd337def3fe6bbe5e6001989b9b6bfe27ea08
36373781542ab56573248b4c5bc843ac4048c7ab21aa24ca00534c25482828a3
8c9ee67475bbaaaab22cb722c8e57240a150301a8d219de94e44534d7d90e885
87acb0e2c4f9800731629b6c5ee14a35a6b9887d2a0032994cb9cf15dbe59650
ff7b46a04c9a749e7cc5112214266cc65c31354d5b5d5d3d90209bcd5616a552
a95c2e87f2a659bd9ee01c2cd73964e438f129a6aa9e582c363838b80f81d7eb
5555b56a2a8ad2d9d7affd0409f8015c208013fea00177b873831b0282c964f2
783c1e8fa7582cee5f81a669b5e6eeeeaee58e8559b0c233d8843c7c0b963a82
34e94b5cb2396d7d7d7db22c8ba258fb0afd43f0e2c58b919191ba9de9b4d425
118329b0c3323c8709d02041b52b4ea7f39de75d2a934a2693c0a953a76a93d4
5d157ebf7f6565a5542a553df97c5e10045dd731c130b86113cc300cbd489224
08422a952a140a95788fc763b1d41558d7a2d7af5f5fb870a1d6a3aaaacd6603
18802da84c59015bd2e6897b745d9765b99a1df0f97c0daf74e36deaf7fbcd66
73ad2797cb89a2c839880188a2e8743a8bc5a22ccbba5e376466b3b9bdbdbd21
6123413a9d0e0402b51e4dd3bababa788eb022b85caeb6b6364551b6b7b76942
43f7f727007a7a7a04a1ee8065b3595fde2768423299ac1ec6669c3973e65004
c0f8f878ad69341a33994ced2969c0d0d0502412f9f8f163f3a7fd654b474787
288ad53e74757535df6215b85cae60302849d2410aecc037f9f2e5cbd5b5c160
680eb0dbede170381c0e7ff8f0a185be3b906068684892a4ca7a6f6faff69328
8ad3d3d3f7efdfdfdbdbfb57e96868a14d0d0643381c96242997cbe5f3794010
84603078fcf8f1d6496bd14a3aba5c2ea7d369341a5555b5582c8140e0fcf9f3
1b1b1b87cf4eeb0a8063c78e45a3d19e9e1ebfdfdf5a831e844655d18093274f
9e3d7bf6d3a74f3b3b3b47c80efc05ff7af28fefb70d9b0000000049454e44ae
426082
"""
    ),
    "basn6a16": _dehex(
        """
89504e470d0a1a0a0000000d494844520000002000000020100600000023eaa6
b70000000467414d41000186a031e8965f00000d2249444154789cdd995f6c1c
d775c67ff38fb34b724d2ee55a8e4b04a0ac87049100cab4dbd8c6528902cb4d
10881620592e52d4325ac0905bc98a94025e71fd622cb5065ac98a0c283050c0
728a00b6e542a1d126885cd3298928891d9a0444037e904434951d4b90b84b2f
c9dde1fcebc33977a95555348f411e16dfce9d3b77ee77eebde77ce78c95a669
0ad07c17009a13edd898b87dfb1fcb7d2b4d1bff217f33df80deb1e6267df0ff
c1e6e6dfafdf1f5a7fd30f9aef66b6d546dd355bf02c40662e3307f9725a96c6
744c3031f83782f171c148dbc3bf1774f5dad1e79d6f095a3f54d4fbec5234ef
d9a2f8d73afe4f14f57ef4f42def7b44f19060f06b45bddf1c5534d77fd922be
2973a15a82e648661c6e3240aa3612ead952b604bde57458894f29deaf133bac
13d2766f5227a4a3b8cf08da7adfd6fbd6bd8a4fe9dbb43d35e3dfa3f844fbf8
9119bf4f7144094fb56333abf8a86063ca106f94b3a3b512343765e60082097f
1bb86ba72439a653519b09f5cee1ce61c897d37eedf5553580ae60f4af8af33a
b14fd400b6a0f34535c0434afc0b3a9f07147527a5fa7ca218ff56c74d74dc3f
155cfd3325fc278acf2ae1cb4a539f5f9937c457263b0bd51234c732a300cdd1
cc1840f0aaff54db0e4874ed5a9b5d6d27d4bb36746d80de72baa877ff4b275a
d7895ed1897ea4139b5143fcbb1a62560da1ed9662aaed895ec78a91c18795b8
5e07ab4af8ba128e95e682e0728bf8f2e5ae815a091a53d902ac1920d8e05f06
589de8d8d66680789f4e454fb9d9ec66cd857af796ee2d902fa73fd5bba775a2
153580ae44705ed0d37647d15697cb8f14bfa3e3e8fdf8031d47af571503357c
f30d25acedcbbf135c9a35c49766ba07ab255859e8ec03684e66860182dff8f7
0304bff6ff1c20fc81b7afdd00a71475539a536e36bb5973a19e3b923b02bde5
e4efd4003ac170eb2d13fe274157afedbd82d6fb3a9a1e85e4551d47cf7078f8
9671fe4289ebf5f2bf08d63f37c4eb4773c55a0996efeefa0ca011671d8060ca
2f0004c7fcc300e166ef0240f825efe3361f106d57d423d0723f7acacd66376b
2ed47b7a7a7a205f4ef4ac4691e0aad9aa0d41cf13741c3580a506487574ddca
61a8c403c1863ebfbcac3475168b2de28b8b3d77544bb05ce92a02aceced3c0d
d0cc65ea371b201cf1c601c24dde1c4078cedbdeb60322f50126a019bf6edc9b
39e566b39b3517eaf97c3e0fbde5e4491d45bd74537145d155b476aa0176e868
c6abebf30dbd5e525c54ac8e18e2d56abeb756827a3d970358a97416019a6f64
f60004fdfe1580d5c98e618070cc1b05887eee7e0d209a70db7d8063029889b4
c620ead78d7b33a7dc6c76b3e6427ddddbebde867c393aa7845e5403e8ca794a
d0d6fb897af5f03525fe5782f5e7046bdaef468bf88d1debc6ab25583cd17310
6079b9ab0ba059c914018245bf076075b5a303200c3c1f209a733701444fbbaf
00c4134ebb016c5d0b23614c243701cdf875e3decce9349bddacb9505fbf7dfd
76e82d87736a00f5d2b5ffd4b7dce2719a4d25ae717ee153c1abef18e257cfad
7fa45682da48ef38c052b53b0fd06864b300c151ff08c0ea431de701a287dd5f
004497dc7b01a253ee3e80b8c7f91c20f967fb6fdb7c80ada7d8683723614c24
3701cdf875e3decc29379bddacb950ef3fd47f08f2e5a61ea4aa2a3eb757cd55
13345efcfa59c12b2f19e2578ef77fb75a82854ffbee01a83f977b11a031931d
040802df07082b5e11207cc17b1e209a770700e2df0a83e409fb7580f827c230
99b06fd901fb058d6835dacd481813c94d40337eddb83773cacd66376b2ed437
bebcf165e82d2f4e4beb7f3fa6e652c2d7ee10bc78c010bfb87fe3c95a09ae9f
bd732740bd2fb700d0f865f64180e059ff044018ca0ca28a5b04883f701e0088
bfec7c0c909cb71f0448c6ec518074b375012079d9dedf66004bcfbc51eb2dd1
aadacd481813c94d40337eddb83773cacd66376b2ed487868686205fbe7c49ef
5605a73f34c4a7a787eeab96e0da81bb4e022c15ba27019a5b339300e16bf286
a8eae601e25866907cdf3e0890acb36f00245fb57f05904e59c300e92561946e
b2e600d209ab7d07f04d458dfb46ad1bd16ab49b913026929b8066fcba716fe6
949bcd6ed65ca8ef7e7cf7e3d05b7e7c8f217ee6cdddbb6a25a856f37980e0c7
fe4e80a82623c48193014846ec7180f4acf518409aca0cd28a5504e03b32c374
de1a00608a0240faaa327a4b19fe946fb6f90054dbb5f2333d022db56eb4966a
3723614c243701cdf8f556bea8a7dc6c76b3e66bd46584ddbbcebc0990cf4b0f
ff4070520c282338a7e26700ec725202b01e4bcf0258963c6f1d4d8f0030cb20
805549c520930c03584fa522b676f11600ffc03fde3e1b3489a9c9054c9aa23b
c08856a3dd8c843191dc0434e3d78d7b33a75c36fb993761f7ae5a69f72ef97f
e6ad336fed7e1c60e8bee96980bbdebbb60da07b7069062033d9dc0ae03d296f
70ab511ec071640676252902d833c916007b3e1900b0a6d2028035968e025861
ea01581369fb11488c34d18cbc95989afccca42baad65ba2d5683723614c24d7
8066fcbab8b7e96918baaf5aaa56219f975fb50a43f7c9bde90fa73f1c1a02d8
78f2e27e803b77ca08b90519315b6fe400fc1392097a9eccc0ad444500e70199
a1331f0f00d8934901c07e5d526ceb87c2d07e2579badd005a2b31a5089391b7
1253358049535a6add8856dd0146c298482e01ede27ed878b256ba7600ee3a09
c18fc1df09fe01084ec25defc1b56db0f1a4f4bd78e0e2818d2f0334e7330300
7df7c888b917e50dd9c1c60c80efcb0cbc63e1f700bce7c31700dccbd1060027
8add9b0de06c8e2f00d84962b7d7030e2a61538331b98051f92631bd253f336a
dd8856a3dd44c25c390efddfad96ae9f853b77c25201ba27c533b8bdf28b6ad0
3d084b33d2e7fa59099e9901b8f2d29597fa0f01848f78e70082117f1ca07b76
6910209b9519f895a008d031bbba05c09d8f06005c5b18b8fba25300cea6780e
c03e911c6ccf06d507b48a4fa606634a114609de929f9934c5a87511ad57cfc1
fa476aa5854fa1ef1e3910b905686e85cc24c40138198915f133d2d6dc2a7dea
7df2ccc2a752faf2cec1d577aebeb37e3b4034eeee0008dff3be0e6b923773b4
7904c0ef9119767cb4fa1500ef1361e08e452500f71561e84cc4ed3e20fab6a2
c905f40cb76a3026bf3319b91ac2e46792a6dcd801ebc6aba5da08f48ecb81c8
bd088d5f42f6417191de93908c803d0e76199292b485af41b60e8d9c3c537f0e
8211f0c7211a077707dc18b931b2ee6d80a4d7ae024491ebc24d4a708ff70680
7f25e807e8785f1878e322d6ddaf453f0770ff2dfa769b01423dbbad72a391b6
5a7c3235985629423372494cab55c8f7d64a8b27a0e7202c55a13b0f8d19c80e
4ae9ca3f015115dc3ca467c17a4c7ee95970ab10e5a54ff0ac3cd39881ee5958
1a84f03df0be0e492fd855a8d6aa35d10b4962dbb0a604a3d3ee5e80a8eee600
a24977f8660378bf0bbf00e01d0a8fb7f980f04b8aa6ce6aca8d5a7533c52753
839152c4e222f4dc512dd5eb90cbc981e8ea12cf90cd8a8bf47d89159e2741d3
7124f65b96fcd254dae258fa84a13c13043246a32129574787e49eae2b49b86d
c3e2e78b9ff7f4002415bb08907c66df0d103b4e0c104db90500ff70700c203a
ee1e82dba4c3e16e256c0acca6ceaae9afd1f612d7eb472157ac95962bd05594
7dd1598466053245088e827f44628657942a825b84e4fb601f84b4025611aca3
901e01bb024911dc0a4445f08e41f83df02b10142173149ab71baf027611ea95
7a257704201d14cd9af4d90b00f194530088cb4e09c0df1c5c0088f7393f6833
c0aa3ac156655de3bca9b34ab9716906ba07aba5e5bba1eb3358d90b9da7c533
64f6888bf47b60f521e8380fe10be03d2feac17900927560df40f4e48f805960
50328d648bf4893f9067c217a0631656b7c898c122847bc07b03a2d3e0ee85e4
33b0ef867450c4fad2ecd26cf7168074c0ba0c904cdac300c9cfec4701924df6
1cdca61e10685c6f7d52d0caba1498972f43d740adb4b2009d7d7220b20e3473
90a943d00ffe959bb6eac3e0fe42ea49ee00c45f06e76329b1dabf127d690d80
5581b408f63c2403e0cc433c00ee658836803b0fd100747c04ab5f917704fd10
d5c1cd41ec801343d207f602a403605d86e5f9e5f9ae0d00e994556833806685
c931fb709b0f08b4e869bea5c827859549e82c544b8d29c816a0390999613920
7e610d5727a16318c2003c1fa24be0de2b32caf92224e7c17e5004b6350c4c01
05601218066b0ad28224e149019c086257ca315102de2712903bde97b8144d82
3b2c6ac52d403c054e019249b087f53d0558995a99ea946c70cc927458b3c1ff
550f30050df988d4284376b4566a8e416654cc921985e037e0df0fc131f00f4b
acf0c6211c036f14a239703741740adc7da227edd7e56b833d0ae92549b4d357
25dfb49ed2ff63908e6adf27d6d0dda7638d4154d2778daca17f58e61297c129
41f233b01f5dc3740cac51688c35c6b22580f48224fee9b83502569a66b629f1
09f3713473413e2666e7fe6f6c6efefdfafda1f56f6e06f93496d9d67cb7366a
9964b6f92e64b689196ec6c604646fd3fe4771ff1bf03f65d8ecc3addbb5f300
00000049454e44ae426082
"""
    ),
}


def test_suite(options, args):
    """
    Create a PNG test image and write the file to stdout.
    """

    # Below is a big stack of test image generators.
    # They're all really tiny, so PEP 8 rules are suspended.

    def test_gradient_horizontal_lr(x, y):
        return x

    def test_gradient_horizontal_rl(x, y):
        return 1 - x

    def test_gradient_vertical_tb(x, y):
        return y

    def test_gradient_vertical_bt(x, y):
        return 1 - y

    def test_radial_tl(x, y):
        return max(1 - math.sqrt(x * x + y * y), 0.0)

    def test_radial_center(x, y):
        return test_radial_tl(x - 0.5, y - 0.5)

    def test_radial_tr(x, y):
        return test_radial_tl(1 - x, y)

    def test_radial_bl(x, y):
        return test_radial_tl(x, 1 - y)

    def test_radial_br(x, y):
        return test_radial_tl(1 - x, 1 - y)

    def test_stripe(x, n):
        return float(int(x * n) & 1)

    def test_stripe_h_2(x, y):
        return test_stripe(x, 2)

    def test_stripe_h_4(x, y):
        return test_stripe(x, 4)

    def test_stripe_h_10(x, y):
        return test_stripe(x, 10)

    def test_stripe_v_2(x, y):
        return test_stripe(y, 2)

    def test_stripe_v_4(x, y):
        return test_stripe(y, 4)

    def test_stripe_v_10(x, y):
        return test_stripe(y, 10)

    def test_stripe_lr_10(x, y):
        return test_stripe(x + y, 10)

    def test_stripe_rl_10(x, y):
        return test_stripe(1 + x - y, 10)

    def test_checker(x, y, n):
        return float((int(x * n) & 1) ^ (int(y * n) & 1))

    def test_checker_8(x, y):
        return test_checker(x, y, 8)

    def test_checker_15(x, y):
        return test_checker(x, y, 15)

    def test_zero(x, y):
        return 0

    def test_one(x, y):
        return 1

    test_patterns = {
        "GLR": test_gradient_horizontal_lr,
        "GRL": test_gradient_horizontal_rl,
        "GTB": test_gradient_vertical_tb,
        "GBT": test_gradient_vertical_bt,
        "RTL": test_radial_tl,
        "RTR": test_radial_tr,
        "RBL": test_radial_bl,
        "RBR": test_radial_br,
        "RCTR": test_radial_center,
        "HS2": test_stripe_h_2,
        "HS4": test_stripe_h_4,
        "HS10": test_stripe_h_10,
        "VS2": test_stripe_v_2,
        "VS4": test_stripe_v_4,
        "VS10": test_stripe_v_10,
        "LRS": test_stripe_lr_10,
        "RLS": test_stripe_rl_10,
        "CK8": test_checker_8,
        "CK15": test_checker_15,
        "ZERO": test_zero,
        "ONE": test_one,
    }

    def test_pattern(width, height, bitdepth, pattern):
        """Create a single plane (monochrome) test pattern.  Returns a
        flat row flat pixel array.
        """

        maxval = 2**bitdepth - 1
        if maxval > 255:
            a = array("H")
        else:
            a = array("B")
        fw = float(width)
        fh = float(height)
        pfun = test_patterns[pattern]
        for y in range(height):
            fy = float(y) / fh
            for x in range(width):
                a.append(int(round(pfun(float(x) / fw, fy) * maxval)))
        return a

    def test_rgba(size=256, bitdepth=8, red="GTB", green="GLR", blue="RTL", alpha=None):
        """
        Create a test image.  Each channel is generated from the
        specified pattern; any channel apart from red can be set to
        None, which will cause it not to be in the image.  It
        is possible to create all PNG channel types (L, RGB, LA, RGBA),
        as well as non PNG channel types (RGA, and so on).
        """

        i = test_pattern(size, size, bitdepth, red)
        psize = 1
        for channel in (green, blue, alpha):
            if channel:
                c = test_pattern(size, size, bitdepth, channel)
                i = interleave_planes(i, c, psize, 1)
                psize += 1
        return i

    def pngsuite_image(name):
        """
        Create a test image by reading an internal copy of the files
        from the PngSuite.  Returned in flat row flat pixel format.
        """

        if name not in _pngsuite:
            raise NotImplementedError(
                f"cannot find PngSuite file {name} (use -L for a list)"
            )
        r = Reader(bytes=_pngsuite[name])
        w, h, pixels, meta = r.asDirect()
        assert w == h
        # LAn for n < 8 is a special case for which we need to rescale
        # the data.
        if meta["greyscale"] and meta["alpha"] and meta["bitdepth"] < 8:
            factor = 255 // (2 ** meta["bitdepth"] - 1)

            def rescale(data):
                for row in data:
                    yield map(factor.__mul__, row)

            pixels = rescale(pixels)
            meta["bitdepth"] = 8
        arraycode = "BH"[meta["bitdepth"] > 8]
        return w, array(arraycode, itertools.chain(*pixels)), meta

    # The body of test_suite()
    size = 256
    if options.test_size:
        size = options.test_size
    options.bitdepth = options.test_depth
    options.greyscale = bool(options.test_black)

    kwargs = {}
    if options.test_red:
        kwargs["red"] = options.test_red
    if options.test_green:
        kwargs["green"] = options.test_green
    if options.test_blue:
        kwargs["blue"] = options.test_blue
    if options.test_alpha:
        kwargs["alpha"] = options.test_alpha
    if options.greyscale:
        if options.test_red or options.test_green or options.test_blue:
            raise ValueError(
                "cannot specify colours (R, G, B) when greyscale image (black channel, K) is specified"
            )
        kwargs["red"] = options.test_black
        kwargs["green"] = None
        kwargs["blue"] = None
    options.alpha = bool(options.test_alpha)
    if not args:
        pixels = test_rgba(size, options.bitdepth, **kwargs)
    else:
        size, pixels, meta = pngsuite_image(args[0])
        for k in ["bitdepth", "alpha", "greyscale"]:
            setattr(options, k, meta[k])

    writer = Writer(
        size,
        size,
        bitdepth=options.bitdepth,
        transparent=options.transparent,
        background=options.background,
        gamma=options.gamma,
        greyscale=options.greyscale,
        alpha=options.alpha,
        compression=options.compression,
        interlace=options.interlace,
    )
    writer.write_array(sys.stdout, pixels)


def read_pam_header(infile):
    """
    Read (the rest of a) PAM header.  `infile` should be positioned
    immediately after the initial 'P7' line (at the beginning of the
    second line).  Returns are as for `read_pnm_header`.
    """

    # Unlike PBM, PGM, and PPM, we can read the header a line at a time.
    header = dict()
    while True:
        l = infile.readline().strip()
        if l == strtobytes("ENDHDR"):
            break
        if not l:
            raise EOFError("PAM ended prematurely")
        if l[0] == strtobytes("#"):
            continue
        l = l.split(None, 1)
        if l[0] not in header:
            header[l[0]] = l[1]
        else:
            header[l[0]] += strtobytes(" ") + l[1]

    required = ["WIDTH", "HEIGHT", "DEPTH", "MAXVAL"]
    required = [strtobytes(x) for x in required]
    WIDTH, HEIGHT, DEPTH, MAXVAL = required
    present = [x for x in required if x in header]
    if len(present) != len(required):
        raise Error("PAM file must specify WIDTH, HEIGHT, DEPTH, and MAXVAL")
    width = int(header[WIDTH])
    height = int(header[HEIGHT])
    depth = int(header[DEPTH])
    maxval = int(header[MAXVAL])
    if width <= 0 or height <= 0 or depth <= 0 or maxval <= 0:
        raise Error("WIDTH, HEIGHT, DEPTH, MAXVAL must all be positive integers")
    return "P7", width, height, depth, maxval


def read_pnm_header(infile, supported=("P5", "P6")):
    """
    Read a PNM header, returning (format,width,height,depth,maxval).
    `width` and `height` are in pixels.  `depth` is the number of
    channels in the image; for PBM and PGM it is synthesized as 1, for
    PPM as 3; for PAM images it is read from the header.  `maxval` is
    synthesized (as 1) for PBM images.
    """

    # Generally, see http://netpbm.sourceforge.net/doc/ppm.html
    # and http://netpbm.sourceforge.net/doc/pam.html

    supported = [strtobytes(x) for x in supported]

    # Technically 'P7' must be followed by a newline, so by using
    # rstrip() we are being liberal in what we accept.  I think this
    # is acceptable.
    type = infile.read(3).rstrip()
    if type not in supported:
        raise NotImplementedError(f"file format {type} not supported")
    if type == strtobytes("P7"):
        # PAM header parsing is completely different.
        return read_pam_header(infile)
    # Expected number of tokens in header (3 for P4, 4 for P6)
    expected = 4
    pbm = ("P1", "P4")
    if type in pbm:
        expected = 3
    header = [type]

    # We have to read the rest of the header byte by byte because the
    # final whitespace character (immediately following the MAXVAL in
    # the case of P6) may not be a newline.  Of course all PNM files in
    # the wild use a newline at this point, so it's tempting to use
    # readline; but it would be wrong.
    def getc():
        c = infile.read(1)
        if not c:
            raise Error("premature EOF reading PNM header")
        return c

    c = getc()
    while True:
        # Skip whitespace that precedes a token.
        while c.isspace():
            c = getc()
        # Skip comments.
        while c == "#":
            while c not in "\n\r":
                c = getc()
        if not c.isdigit():
            raise Error(f"unexpected character {c} found in header")
        # According to the specification it is legal to have comments
        # that appear in the middle of a token.
        # This is bonkers; I've never seen it; and it's a bit awkward to
        # code good lexers in Python (no goto).  So we break on such
        # cases.
        token = strtobytes("")
        while c.isdigit():
            token += c
            c = getc()
        # Slight hack.  All "tokens" are decimal integers, so convert
        # them here.
        header.append(int(token))
        if len(header) == expected:
            break
    # Skip comments (again)
    while c == "#":
        while c not in "\n\r":
            c = getc()
    if not c.isspace():
        raise Error(f"expected header to end with whitespace, not {c}")

    if type in pbm:
        # synthesize a MAXVAL
        header.append(1)
    depth = (1, 3)[type == strtobytes("P6")]
    return header[0], header[1], header[2], depth, header[3]


def write_pnm(file, width, height, pixels, meta):
    """Write a Netpbm PNM/PAM file."""

    bitdepth = meta["bitdepth"]
    maxval = 2**bitdepth - 1
    # Rudely, the number of image planes can be used to determine
    # whether we are L (PGM), LA (PAM), RGB (PPM), or RGBA (PAM).
    planes = meta["planes"]
    # Can be an assert as long as we assume that pixels and meta came
    # from a PNG file.
    assert planes in (1, 2, 3, 4)
    if planes in (1, 3):
        if 1 == planes:
            # PGM
            # Could generate PBM if maxval is 1, but we don't (for one
            # thing, we'd have to convert the data, not just blat it
            # out).
            fmt = "P5"
        else:
            # PPM
            fmt = "P6"
        file.write("%s %d %d %d\n" % (fmt, width, height, maxval))
    if planes in (2, 4):
        # PAM
        # See http://netpbm.sourceforge.net/doc/pam.html
        if 2 == planes:
            tupltype = "GRAYSCALE_ALPHA"
        else:
            tupltype = "RGB_ALPHA"
        file.write(
            "P7\nWIDTH %d\nHEIGHT %d\nDEPTH %d\nMAXVAL %d\n"
            "TUPLTYPE %s\nENDHDR\n" % (width, height, planes, maxval, tupltype)
        )
    # Values per row
    vpr = planes * width
    # struct format
    fmt = ">%d" % vpr
    if maxval > 0xFF:
        fmt = fmt + "H"
    else:
        fmt = fmt + "B"
    for row in pixels:
        file.write(struct.pack(fmt, *row))
    file.flush()


def color_triple(color):
    """
    Convert a command line colour value to a RGB triple of integers.
    FIXME: Somewhere we need support for greyscale backgrounds etc.
    """
    if color.startswith("#") and len(color) == 4:
        return (int(color[1], 16), int(color[2], 16), int(color[3], 16))
    if color.startswith("#") and len(color) == 7:
        return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    elif color.startswith("#") and len(color) == 13:
        return (int(color[1:5], 16), int(color[5:9], 16), int(color[9:13], 16))


def _main(argv):
    """
    Run the PNG encoder with options from the command line.
    """

    # Parse command line arguments
    from optparse import OptionParser
    import re

    version = "%prog " + re.sub(r"( ?\$|URL: |Rev:)", "", __version__)
    parser = OptionParser(version=version)
    parser.set_usage("%prog [options] [imagefile]")
    parser.add_option(
        "-r",
        "--read-png",
        default=False,
        action="store_true",
        help="Read PNG, write PNM",
    )
    parser.add_option(
        "-i",
        "--interlace",
        default=False,
        action="store_true",
        help="create an interlaced PNG file (Adam7)",
    )
    parser.add_option(
        "-t",
        "--transparent",
        action="store",
        type="string",
        metavar="color",
        help="mark the specified colour (#RRGGBB) as transparent",
    )
    parser.add_option(
        "-b",
        "--background",
        action="store",
        type="string",
        metavar="color",
        help="save the specified background colour",
    )
    parser.add_option(
        "-a",
        "--alpha",
        action="store",
        type="string",
        metavar="pgmfile",
        help="alpha channel transparency (RGBA)",
    )
    parser.add_option(
        "-g",
        "--gamma",
        action="store",
        type="float",
        metavar="value",
        help="save the specified gamma value",
    )
    parser.add_option(
        "-c",
        "--compression",
        action="store",
        type="int",
        metavar="level",
        help="zlib compression level (0-9)",
    )
    parser.add_option(
        "-T",
        "--test",
        default=False,
        action="store_true",
        help="create a test image (a named PngSuite image if an argument is supplied)",
    )
    parser.add_option(
        "-L",
        "--list",
        default=False,
        action="store_true",
        help="print list of named test images",
    )
    parser.add_option(
        "-R",
        "--test-red",
        action="store",
        type="string",
        metavar="pattern",
        help="test pattern for the red image layer",
    )
    parser.add_option(
        "-G",
        "--test-green",
        action="store",
        type="string",
        metavar="pattern",
        help="test pattern for the green image layer",
    )
    parser.add_option(
        "-B",
        "--test-blue",
        action="store",
        type="string",
        metavar="pattern",
        help="test pattern for the blue image layer",
    )
    parser.add_option(
        "-A",
        "--test-alpha",
        action="store",
        type="string",
        metavar="pattern",
        help="test pattern for the alpha image layer",
    )
    parser.add_option(
        "-K",
        "--test-black",
        action="store",
        type="string",
        metavar="pattern",
        help="test pattern for greyscale image",
    )
    parser.add_option(
        "-d",
        "--test-depth",
        default=8,
        action="store",
        type="int",
        metavar="NBITS",
        help="create test PNGs that are NBITS bits per channel",
    )
    parser.add_option(
        "-S",
        "--test-size",
        action="store",
        type="int",
        metavar="size",
        help="width and height of the test image",
    )
    (options, args) = parser.parse_args(args=argv[1:])

    # Convert options
    if options.transparent is not None:
        options.transparent = color_triple(options.transparent)
    if options.background is not None:
        options.background = color_triple(options.background)

    if options.list:
        names = list(_pngsuite)
        names.sort()
        for name in names:
            print(name)
        return

    # Run regression tests
    if options.test:
        return test_suite(options, args)

    # Prepare input and output files
    if len(args) == 0:
        infilename = "-"
        infile = sys.stdin
    elif len(args) == 1:
        infilename = args[0]
        infile = open(infilename, "rb")
    else:
        parser.error("more than one input file")
    outfile = sys.stdout

    if options.read_png:
        # Encode PNG to PPM
        png = Reader(file=infile)
        width, height, pixels, meta = png.asDirect()
        write_pnm(outfile, width, height, pixels, meta)
    else:
        # Encode PNM to PNG
        format, width, height, depth, maxval = read_pnm_header(
            infile, ("P5", "P6", "P7")
        )
        # When it comes to the variety of input formats, we do something
        # rather rude.  Observe that L, LA, RGB, RGBA are the 4 colour
        # types supported by PNG and that they correspond to 1, 2, 3, 4
        # channels respectively.  So we use the number of channels in
        # the source image to determine which one we have.  We do not
        # care about TUPLTYPE.
        greyscale = depth <= 2
        pamalpha = depth in (2, 4)
        supported = map(lambda x: 2**x - 1, range(1, 17))
        try:
            mi = supported.index(maxval)
        except ValueError:
            raise NotImplementedError(
                f"your maxval ({maxval}) not in supported list {str(supported)}"
            )
        bitdepth = mi + 1
        writer = Writer(
            width,
            height,
            greyscale=greyscale,
            bitdepth=bitdepth,
            interlace=options.interlace,
            transparent=options.transparent,
            background=options.background,
            alpha=bool(pamalpha or options.alpha),
            gamma=options.gamma,
            compression=options.compression,
        )
        if options.alpha:
            pgmfile = open(options.alpha, "rb")
            format, awidth, aheight, adepth, amaxval = read_pnm_header(pgmfile, "P5")
            if amaxval != "255":
                raise NotImplementedError(
                    f"maxval {amaxval} not supported for alpha channel"
                )
            if (awidth, aheight) != (width, height):
                raise ValueError(
                    "alpha channel image size mismatch"
                    " (%s has %sx%s but %s has %sx%s)"
                    % (infilename, width, height, options.alpha, awidth, aheight)
                )
            writer.convert_ppm_and_pgm(infile, pgmfile, outfile)
        else:
            writer.convert_pnm(infile, outfile)


if __name__ == "__main__":
    try:
        _main(sys.argv)
    except Error as e:
        sys.stderr.write(f"{e}\n")
