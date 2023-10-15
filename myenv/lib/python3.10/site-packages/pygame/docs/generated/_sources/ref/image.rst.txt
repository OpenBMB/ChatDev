.. include:: common.txt

:mod:`pygame.image`
===================

.. module:: pygame.image
   :synopsis: pygame module for loading and saving images

| :sl:`pygame module for image transfer`

The image module contains functions for loading and saving pictures, as well as
transferring Surfaces to formats usable by other packages.

Note that there is no Image class; an image is loaded as a Surface object. The
Surface class allows manipulation (drawing lines, setting pixels, capturing
regions, etc.).

In the vast majority of installations, pygame is built to support extended
formats, using the SDL_Image library behind the scenes. However, some
installations may only support uncompressed ``BMP`` images. With full image
support, the :func:`pygame.image.load()` function can load the following
formats.

   * ``BMP``

   * ``GIF`` (non-animated)

   * ``JPEG``

   * ``LBM`` (and ``PBM``, ``PGM``, ``PPM``)

   * ``PCX``

   * ``PNG``
   
   * ``PNM``

   * ``SVG`` (limited support, using Nano SVG)

   * ``TGA`` (uncompressed)

   * ``TIFF``

   * ``WEBP``

   * ``XPM``
   
   
.. versionadded:: 2.0 Loading SVG, WebP, PNM

Saving images only supports a limited set of formats. You can save to the
following formats.

   * ``BMP``

   * ``JPEG``

   * ``PNG``

   * ``TGA``
   

``JPEG`` and ``JPG``, as well as ``TIF`` and ``TIFF`` refer to the same file format

.. versionadded:: 1.8 Saving PNG and JPEG files.


.. function:: load

   | :sl:`load new image from a file (or file-like object)`
   | :sg:`load(filename) -> Surface`
   | :sg:`load(fileobj, namehint="") -> Surface`

   Load an image from a file source. You can pass either a filename, a Python
   file-like object, or a pathlib.Path.

   Pygame will automatically determine the image type (e.g., ``GIF`` or bitmap)
   and create a new Surface object from the data. In some cases it will need to
   know the file extension (e.g., ``GIF`` images should end in ".gif"). If you
   pass a raw file-like object, you may also want to pass the original filename
   as the namehint argument.

   The returned Surface will contain the same color format, colorkey and alpha
   transparency as the file it came from. You will often want to call
   :func:`pygame.Surface.convert()` with no arguments, to create a copy that
   will draw more quickly on the screen.

   For alpha transparency, like in .png images, use the
   :func:`pygame.Surface.convert_alpha()` method after loading so that the
   image has per pixel transparency.

   Pygame may not always be built to support all image formats. At minimum it
   will support uncompressed ``BMP``. If :func:`pygame.image.get_extended()`
   returns ``True``, you should be able to load most images (including PNG, JPG
   and GIF).

   You should use :func:`os.path.join()` for compatibility.

   ::

     eg. asurf = pygame.image.load(os.path.join('data', 'bla.png'))

   .. ## pygame.image.load ##

.. function:: save

   | :sl:`save an image to file (or file-like object)`
   | :sg:`save(Surface, filename) -> None`
   | :sg:`save(Surface, fileobj, namehint="") -> None`

   This will save your Surface as either a ``BMP``, ``TGA``, ``PNG``, or
   ``JPEG`` image. If the filename extension is unrecognized it will default to
   ``TGA``. Both ``TGA``, and ``BMP`` file formats create uncompressed files.
   You can pass a filename, a pathlib.Path or a Python file-like object.
   For file-like object, the image is saved to ``TGA`` format unless
   a namehint with a recognizable extension is passed in.

   .. note:: When saving to a file-like object, it seems that for most formats,
             the object needs to be flushed after saving to it to make loading
             from it possible.

   .. versionchanged:: 1.8 Saving PNG and JPEG files.
   .. versionchanged:: 2.0.0
                       The ``namehint`` parameter was added to make it possible
                       to save other formats than ``TGA`` to a file-like object.
                       Saving to a file-like object with JPEG is possible.

   .. ## pygame.image.save ##

.. function:: get_sdl_image_version

   | :sl:`get version number of the SDL_Image library being used`
   | :sg:`get_sdl_image_version(linked=True) -> None`
   | :sg:`get_sdl_image_version(linked=True) -> (major, minor, patch)`

   If pygame is built with extended image formats, then this function will
   return the SDL_Image library's version number as a tuple of 3 integers
   ``(major, minor, patch)``. If not, then it will return ``None``.

   ``linked=True`` is the default behavior and the function will return the
   version of the library that Pygame is linked against, while ``linked=False``
   will return the version of the library that Pygame is compiled against.

   .. versionadded:: 2.0.0

   .. versionchanged:: 2.2.0 ``linked`` keyword argument added and default behavior changed from returning compiled version to returning linked version

   .. ## pygame.image.get_sdl_image_version ##

.. function:: get_extended

   | :sl:`test if extended image formats can be loaded`
   | :sg:`get_extended() -> bool`

   If pygame is built with extended image formats this function will return
   True. It is still not possible to determine which formats will be available,
   but generally you will be able to load them all.

   .. ## pygame.image.get_extended ##

.. function:: tostring

   | :sl:`transfer image to byte buffer`
   | :sg:`tostring(Surface, format, flipped=False) -> bytes`

   Creates a string of bytes that can be transferred with the ``fromstring``
   or ``frombytes`` methods in other Python imaging packages. Some Python
   image packages prefer their images in bottom-to-top format (PyOpenGL for
   example). If you pass ``True`` for the flipped argument, the byte buffer
   will be vertically flipped.

   The format argument is a string of one of the following values. Note that
   only 8-bit Surfaces can use the "P" format. The other formats will work for
   any Surface. Also note that other Python image packages support more formats
   than pygame.

      * ``P``, 8-bit palettized Surfaces

      * ``RGB``, 24-bit image

      * ``RGBX``, 32-bit image with unused space

      * ``RGBA``, 32-bit image with an alpha channel

      * ``ARGB``, 32-bit image with alpha channel first
      
      * ``BGRA``, 32-bit image with alpha channel, red and blue channels swapped

      * ``RGBA_PREMULT``, 32-bit image with colors scaled by alpha channel

      * ``ARGB_PREMULT``, 32-bit image with colors scaled by alpha channel, alpha channel first

   .. note:: it is preferred to use :func:`tobytes` as of pygame 2.1.3

   .. versionadded:: 2.1.3 BGRA format
   .. ## pygame.image.tostring ##

.. function:: tobytes

   | :sl:`transfer image to byte buffer`
   | :sg:`tobytes(Surface, format, flipped=False) -> bytes`

   Creates a string of bytes that can be transferred with the ``fromstring``
   or ``frombytes`` methods in other Python imaging packages. Some Python
   image packages prefer their images in bottom-to-top format (PyOpenGL for
   example). If you pass ``True`` for the flipped argument, the byte buffer
   will be vertically flipped.

   The format argument is a string of one of the following values. Note that
   only 8-bit Surfaces can use the "P" format. The other formats will work for
   any Surface. Also note that other Python image packages support more formats
   than pygame.

      * ``P``, 8-bit palettized Surfaces

      * ``RGB``, 24-bit image

      * ``RGBX``, 32-bit image with unused space

      * ``RGBA``, 32-bit image with an alpha channel

      * ``ARGB``, 32-bit image with alpha channel first
      
      * ``BGRA``, 32-bit image with alpha channel, red and blue channels swapped      

      * ``RGBA_PREMULT``, 32-bit image with colors scaled by alpha channel

      * ``ARGB_PREMULT``, 32-bit image with colors scaled by alpha channel, alpha channel first
   
   .. note:: this function is an alias for :func:`tostring`. The use of this
             function is recommended over :func:`tostring` as of pygame 2.1.3.
             This function was introduced so it matches nicely with other 
             libraries (PIL, numpy, etc), and with people's expectations.

   .. versionadded:: 2.1.3 

   .. ## pygame.image.tobytes ##


.. function:: fromstring

   | :sl:`create new Surface from a byte buffer`
   | :sg:`fromstring(bytes, size, format, flipped=False) -> Surface`

   This function takes arguments similar to :func:`pygame.image.tostring()`.
   The size argument is a pair of numbers representing the width and height.
   Once the new Surface is created it is independent from the memory of the
   bytes passed in.

   The bytes and format passed must compute to the exact size of image
   specified. Otherwise a ``ValueError`` will be raised.

   See the :func:`pygame.image.frombuffer()` method for a potentially faster
   way to transfer images into pygame.

   .. note:: it is preferred to use :func:`frombytes` as of pygame 2.1.3

   .. ## pygame.image.fromstring ##

.. function:: frombytes

   | :sl:`create new Surface from a byte buffer`
   | :sg:`frombytes(bytes, size, format, flipped=False) -> Surface`

   This function takes arguments similar to :func:`pygame.image.tobytes()`.
   The size argument is a pair of numbers representing the width and height.
   Once the new Surface is created it is independent from the memory of the
   bytes passed in.

   The bytes and format passed must compute to the exact size of image
   specified. Otherwise a ``ValueError`` will be raised.

   See the :func:`pygame.image.frombuffer()` method for a potentially faster
   way to transfer images into pygame.

   .. note:: this function is an alias for :func:`fromstring`. The use of this
             function is recommended over :func:`fromstring` as of pygame 2.1.3.
             This function was introduced so it matches nicely with other 
             libraries (PIL, numpy, etc), and with people's expectations.

   .. versionadded:: 2.1.3 

   .. ## pygame.image.frombytes ##

.. function:: frombuffer

   | :sl:`create a new Surface that shares data inside a bytes buffer`
   | :sg:`frombuffer(buffer, size, format) -> Surface`

   Create a new Surface that shares pixel data directly from a buffer. This
   buffer can be bytes, a bytearray, a memoryview, a
   :class:`pygame.BufferProxy`, or any object that supports the buffer protocol.
   This method takes similar arguments to :func:`pygame.image.fromstring()`, but
   is unable to vertically flip the source data.

   This will run much faster than :func:`pygame.image.fromstring`, since no
   pixel data must be allocated and copied.

   It accepts the following 'format' arguments:

      * ``P``, 8-bit palettized Surfaces

      * ``RGB``, 24-bit image

      * ``BGR``, 24-bit image, red and blue channels swapped.

      * ``RGBX``, 32-bit image with unused space

      * ``RGBA``, 32-bit image with an alpha channel

      * ``ARGB``, 32-bit image with alpha channel first

      * ``BGRA``, 32-bit image with alpha channel, red and blue channels swapped
  
   .. versionadded:: 2.1.3 BGRA format
   .. ## pygame.image.frombuffer ##

.. function:: load_basic

   | :sl:`load new BMP image from a file (or file-like object)`
   | :sg:`load_basic(file) -> Surface`

   Load an image from a file source. You can pass either a filename or a Python
   file-like object, or a pathlib.Path.

   This function only supports loading "basic" image format, ie ``BMP``
   format.
   This function is always available, no matter how pygame was built.

   .. ## pygame.image.load_basic ##

.. function:: load_extended

   | :sl:`load an image from a file (or file-like object)`
   | :sg:`load_extended(filename) -> Surface`
   | :sg:`load_extended(fileobj, namehint="") -> Surface`

   This function is similar to :func:`pygame.image.load()`, except that this
   function can only be used if pygame was built with extended image format
   support.

   .. versionchanged:: 2.0.1
                       This function is always available, but raises an
                       ``NotImplementedError`` if extended image formats are
                       not supported.
                       Previously, this function may or may not be
                       available, depending on the state of extended image
                       format support.

   .. ## pygame.image.load_extended ##

.. function:: save_extended

   | :sl:`save a png/jpg image to file (or file-like object)`
   | :sg:`save_extended(Surface, filename) -> None`
   | :sg:`save_extended(Surface, fileobj, namehint="") -> None`

   This will save your Surface as either a ``PNG`` or ``JPEG`` image.

   In case the image is being saved to a file-like object, this function
   uses the namehint argument to determine the format of the file being
   saved. Saves to ``JPEG`` in case the namehint was not specified while
   saving to a file-like object.

   .. versionchanged:: 2.0.1
                       This function is always available, but raises an
                       ``NotImplementedError`` if extended image formats are
                       not supported.
                       Previously, this function may or may not be
                       available, depending on the state of extended image
                       format support.

   .. ## pygame.image.save_extended ##

.. ## pygame.image ##
