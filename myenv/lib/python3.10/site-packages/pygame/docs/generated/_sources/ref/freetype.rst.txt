.. include:: common.txt

:mod:`pygame.freetype`
======================

.. module:: pygame.freetype
   :synopsis: Enhanced pygame module for loading and rendering computer fonts

| :sl:`Enhanced pygame module for loading and rendering computer fonts`

The ``pygame.freetype`` module is a replacement for :mod:`pygame.font`.
It has all of the functionality of the original, plus many new features.
Yet is has absolutely no dependencies on the SDL_ttf library.
It is implemented directly on the FreeType 2 library.
The ``pygame.freetype`` module is not itself backward compatible with
:mod:`pygame.font`.
Instead, use the ``pygame.ftfont`` module as a drop-in replacement
for :mod:`pygame.font`.

All font file formats supported by FreeType can be rendered by
``pygame.freetype``, namely ``TTF``, Type1, ``CFF``, OpenType,
``SFNT``, ``PCF``, ``FNT``, ``BDF``, ``PFR`` and Type42 fonts.
All glyphs having UTF-32 code points are accessible
(see :attr:`Font.ucs4`).

Most work on fonts is done using :class:`Font` instances.
The module itself only has routines for initialization and creation
of :class:`Font` objects.
You can load fonts from the system using the :func:`SysFont` function.

Extra support of bitmap fonts is available. Available bitmap sizes can
be listed (see :meth:`Font.get_sizes`). For bitmap only fonts :class:`Font`
can set the size for you (see the :attr:`Font.size` property).

For now undefined character codes are replaced with the ``.notdef``
(not defined) character.
How undefined codes are handled may become configurable in a future release.

Pygame comes with a built-in default font. This can always be accessed by
passing None as the font name to the :class:`Font` constructor.

Extra rendering features available to :class:`pygame.freetype.Font`
are direct to surface rendering (see :meth:`Font.render_to`), character kerning
(see :attr:`Font.kerning`), vertical layout (see :attr:`Font.vertical`),
rotation of rendered text (see :attr:`Font.rotation`),
and the strong style (see :attr:`Font.strong`).
Some properties are configurable, such as
strong style strength (see :attr:`Font.strength`) and underline positioning
(see :attr:`Font.underline_adjustment`). Text can be positioned by the upper
right corner of the text box or by the text baseline (see :attr:`Font.origin`).
Finally, a font's vertical and horizontal size can be adjusted separately
(see :attr:`Font.size`).
The :any:`pygame.examples.freetype_misc <pygame.examples.freetype_misc.main>`
example shows these features in use.

The pygame package does not import ``freetype`` automatically when
loaded. This module must be imported explicitly to be used. ::

   import pygame
   import pygame.freetype

.. versionadded:: 1.9.2 :mod:`freetype`


.. function:: get_error

   | :sl:`Return the latest FreeType error`
   | :sg:`get_error() -> str`
   | :sg:`get_error() -> None`

   Return a description of the last error which occurred in the FreeType2
   library, or ``None`` if no errors have occurred.

.. function:: get_version

   | :sl:`Return the FreeType version`
   | :sg:`get_version(linked=True) -> (int, int, int)`

   Returns the version of the FreeType library in use by this module. ``linked=True``
   is the default behavior and returns the linked version of FreeType and ``linked=False``
   returns the compiled version of FreeType.

   Note that the ``freetype`` module depends on the FreeType 2 library.
   It will not compile with the original FreeType 1.0. Hence, the first element
   of the tuple will always be "2".

   .. versionchanged:: 2.2.0 ``linked`` keyword argument added and default behavior changed from returning compiled version to returning linked version

.. function:: init

   | :sl:`Initialize the underlying FreeType library.`
   | :sg:`init(cache_size=64, resolution=72) -> None`

   This function initializes the underlying FreeType library and must be
   called before trying to use any of the functionality of the ``freetype``
   module.

   However, :func:`pygame.init()` will automatically call this function
   if the ``freetype`` module is already imported. It is safe to call this
   function more than once.

   Optionally, you may specify a default *cache_size* for the Glyph cache: the
   maximum number of glyphs that will be cached at any given time by the
   module. Exceedingly small values will be automatically tuned for
   performance. Also a default pixel *resolution*, in dots per inch, can
   be given to adjust font scaling.

.. function:: quit

   | :sl:`Shut down the underlying FreeType library.`
   | :sg:`quit() -> None`

   This function closes the ``freetype`` module. After calling this
   function, you should not invoke any class, method or function related to the
   ``freetype`` module as they are likely to fail or might give unpredictable
   results. It is safe to call this function even if the module hasn't been
   initialized yet.

.. function:: get_init

   | :sl:`Returns True if the FreeType module is currently initialized.`
   | :sg:`get_init() -> bool`

   Returns ``True`` if the ``pygame.freetype`` module is currently initialized.

   .. versionadded:: 1.9.5

.. function:: was_init

   | :sl:`DEPRECATED: Use get_init() instead.`
   | :sg:`was_init() -> bool`

   DEPRECATED: Returns ``True`` if the ``pygame.freetype`` module is currently
   initialized. Use ``get_init()`` instead.

.. function:: get_cache_size

   | :sl:`Return the glyph case size`
   | :sg:`get_cache_size() -> long`

   See :func:`pygame.freetype.init()`.

.. function:: get_default_resolution

   | :sl:`Return the default pixel size in dots per inch`
   | :sg:`get_default_resolution() -> long`

   Returns the default pixel size, in dots per inch, for the module.
   The default is 72 DPI.

.. function:: set_default_resolution

   | :sl:`Set the default pixel size in dots per inch for the module`
   | :sg:`set_default_resolution([resolution])`

   Set the default pixel size, in dots per inch, for the module. If the
   optional argument is omitted or zero the resolution is reset to 72 DPI.

.. function:: SysFont

   | :sl:`create a Font object from the system fonts`
   | :sg:`SysFont(name, size, bold=False, italic=False) -> Font`

   Return a new Font object that is loaded from the system fonts. The font will
   match the requested *bold* and *italic* flags. Pygame uses a small set of
   common font aliases. If the specific font you ask for is not available, a
   reasonable alternative may be used. If a suitable system font is not found
   this will fall back on loading the default pygame font.

   The font *name* can also be an iterable of font names, a string of
   comma-separated font names, or a bytes of comma-separated font names, in
   which case the set of names will be searched in order.

   .. versionadded:: 2.0.1 Accept an iterable of font names.

.. function:: get_default_font

   | :sl:`Get the filename of the default font`
   | :sg:`get_default_font() -> string`

   Return the filename of the default pygame font. This is not the full path
   to the file. The file is usually in the same directory as the font module,
   but can also be bundled in a separate archive.

.. class:: Font

   | :sl:`Create a new Font instance from a supported font file.`
   | :sg:`Font(file, size=0, font_index=0, resolution=0, ucs4=False) -> Font`
   | :sg:`Font(pathlib.Path) -> Font`

   Argument *file* can be either a string representing the font's filename, a
   file-like object containing the font, or None; if None, a default,
   Pygame, font is used.

   .. _freetype-font-size-argument:

   Optionally, a *size* argument may be specified to set the default size in
   points, which determines the size of the rendered characters.
   The size can also be passed explicitly to each method call.
   Because of the way the caching   system works, specifying a default size on
   the constructor doesn't imply a performance gain over manually passing
   the size on each function call. If the font is bitmap and no *size*
   is given, the default size is set to the first available size for the font.

   If the font file has more than one font, the font to load can be chosen with
   the *index* argument. An exception is raised for an out-of-range font index
   value.

   The optional *resolution* argument sets the pixel size, in dots per inch,
   for use in scaling glyphs for this Font instance. If 0 then the default
   module value, set by :func:`init`, is used. The Font object's
   resolution can only be changed by re-initializing the Font instance.

   The optional *ucs4* argument, an integer, sets the default text translation
   mode: 0 (False) recognize UTF-16 surrogate pairs, any other value (True),
   to treat Unicode text as UCS-4, with no surrogate pairs. See
   :attr:`Font.ucs4`.

   .. attribute:: name

      | :sl:`Proper font name.`
      | :sg:`name -> string`

      Read only. Returns the real (long) name of the font, as
      recorded in the font file.

   .. attribute:: path

      | :sl:`Font file path`
      | :sg:`path -> unicode`

      Read only. Returns the path of the loaded font file

   .. attribute:: size

      | :sl:`The default point size used in rendering`
      | :sg:`size -> float`
      | :sg:`size -> (float, float)`

      Get or set the default size for text metrics and rendering. It can be
      a single point size, given as a Python ``int`` or ``float``, or a
      font ppem (width, height) ``tuple``. Size values are non-negative.
      A zero size or width represents an undefined size. In this case
      the size must be given as a method argument, or an exception is
      raised. A zero width but non-zero height is a ValueError.

      For a scalable font, a single number value is equivalent to a tuple
      with width equal height. A font can be stretched vertically with
      height set greater than width, or horizontally with width set
      greater than height. For embedded bitmaps, as listed by :meth:`get_sizes`,
      use the nominal width and height to select an available size.

      Font size differs for a non-scalable, bitmap, font. During a
      method call it must match one of the available sizes returned by
      method :meth:`get_sizes`. If not, an exception is raised.
      If the size is a single number, the size is first matched against the
      point size value. If no match, then the available size with the
      same nominal width and height is chosen.

   .. method:: get_rect

      | :sl:`Return the size and offset of rendered text`
      | :sg:`get_rect(text, style=STYLE_DEFAULT, rotation=0, size=0) -> rect`

      Gets the final dimensions and origin, in pixels, of *text* using the
      optional *size* in points, *style*, and *rotation*. For other
      relevant render properties, and for any optional argument not given,
      the default values set for the :class:`Font` instance are used.

      Returns a :class:`Rect <pygame.Rect>` instance containing the
      width and height of the text's bounding box and the position of the
      text's origin.
      The origin is useful in aligning separately rendered pieces of text.
      It gives the baseline position and bearing at the start of the text.
      See the :meth:`render_to` method for an example.

      If *text* is a char (byte) string, its encoding is assumed to be
      ``LATIN1``.

      Optionally, *text* can be ``None``, which will return the bounding
      rectangle for the text passed to a previous :meth:`get_rect`,
      :meth:`render`, :meth:`render_to`, :meth:`render_raw`, or
      :meth:`render_raw_to` call. See :meth:`render_to` for more
      details.

   .. method:: get_metrics

      | :sl:`Return the glyph metrics for the given text`
      | :sg:`get_metrics(text, size=0) -> [(...), ...]`

      Returns the glyph metrics for each character in *text*.

      The glyph metrics are returned as a list of tuples. Each tuple gives
      metrics of a single character glyph. The glyph metrics are:

      ::

          (min_x, max_x, min_y, max_y, horizontal_advance_x, horizontal_advance_y)

      The bounding box min_x, max_x, min_y, and max_y values are returned as
      grid-fitted pixel coordinates of type int. The advance values are
      float values.

      The calculations are done using the font's default size in points.
      Optionally you may specify another point size with the *size* argument.

      The metrics are adjusted for the current rotation, strong, and oblique
      settings.

      If text is a char (byte) string, then its encoding is assumed to be
      ``LATIN1``.

   .. attribute:: height

      | :sl:`The unscaled height of the font in font units`
      | :sg:`height -> int`

      Read only. Gets the height of the font. This is the average value of all
      glyphs in the font.

   .. attribute:: ascender

      | :sl:`The unscaled ascent of the font in font units`
      | :sg:`ascender -> int`

      Read only. Return the number of units from the font's baseline to
      the top of the bounding box.

   .. attribute:: descender

      | :sl:`The unscaled descent of the font in font units`
      | :sg:`descender -> int`

      Read only. Return the height in font units for the font descent.
      The descent is the number of units from the font's baseline to the
      bottom of the bounding box.

   .. method:: get_sized_ascender

      | :sl:`The scaled ascent of the font in pixels`
      | :sg:`get_sized_ascender(<size>=0) -> int`

      Return the number of units from the font's baseline to the top of the
      bounding box. It is not adjusted for strong or rotation.

   .. method:: get_sized_descender

      | :sl:`The scaled descent of the font in pixels`
      | :sg:`get_sized_descender(<size>=0) -> int`

      Return the number of pixels from the font's baseline to the top of the
      bounding box. It is not adjusted for strong or rotation.

   .. method:: get_sized_height

      | :sl:`The scaled height of the font in pixels`
      | :sg:`get_sized_height(<size>=0) -> int`

      Returns the height of the font. This is the average value of all
      glyphs in the font. It is not adjusted for strong or rotation.

   .. method:: get_sized_glyph_height

      | :sl:`The scaled bounding box height of the font in pixels`
      | :sg:`get_sized_glyph_height(<size>=0) -> int`

      Return the glyph bounding box height of the font in pixels.
      This is the average value of all glyphs in the font.
      It is not adjusted for strong or rotation.

   .. method:: get_sizes

      | :sl:`return the available sizes of embedded bitmaps`
      | :sg:`get_sizes() -> [(int, int, int, float, float), ...]`
      | :sg:`get_sizes() -> []`

      Returns a list of tuple records, one for each point size
      supported. Each tuple containing the point size, the height in pixels,
      width in pixels, horizontal ppem (nominal width) in fractional pixels,
      and vertical ppem (nominal height) in fractional pixels.

   .. method:: render

      | :sl:`Return rendered text as a surface`
      | :sg:`render(text, fgcolor=None, bgcolor=None, style=STYLE_DEFAULT, rotation=0, size=0) -> (Surface, Rect)`

      Returns a new :class:`Surface <pygame.Surface>`,
      with the text rendered to it
      in the color given by 'fgcolor'. If no foreground color is given,
      the default foreground color, :attr:`fgcolor <Font.fgcolor>` is used.
      If ``bgcolor`` is given, the surface
      will be filled with this color. When no background color is given,
      the surface background is transparent, zero alpha. Normally the returned
      surface has a 32 bit pixel size. However, if ``bgcolor`` is ``None``
      and anti-aliasing is disabled a monochrome 8 bit colorkey surface,
      with colorkey set for the background color, is returned.

      The return value is a tuple: the new surface and the bounding
      rectangle giving the size and origin of the rendered text.

      If an empty string is passed for text then the returned Rect is zero
      width and the height of the font.

      Optional *fgcolor*, *style*, *rotation*, and *size* arguments override
      the default values set for the :class:`Font` instance.

      If *text* is a char (byte) string, then its encoding is assumed to be
      ``LATIN1``.

      Optionally, *text* can be ``None``, which will render the text
      passed to a previous :meth:`get_rect`, :meth:`render`, :meth:`render_to`,
      :meth:`render_raw`, or :meth:`render_raw_to` call.
      See :meth:`render_to` for details.

   .. method:: render_to

      | :sl:`Render text onto an existing surface`
      | :sg:`render_to(surf, dest, text, fgcolor=None, bgcolor=None, style=STYLE_DEFAULT, rotation=0, size=0) -> Rect`

      Renders the string *text* to the :mod:`pygame.Surface` *surf*,
      at position *dest*, a (x, y) surface coordinate pair.
      If either x or y is not an integer it is converted to one if possible.
      Any sequence where the first two items are x and y positional elements
      is accepted, including a :class:`Rect <pygame.Rect>` instance.
      As with :meth:`render`,
      optional *fgcolor*, *style*, *rotation*, and *size* argument are
      available.

      If a background color *bgcolor* is given, the text bounding box is
      first filled with that color. The text is blitted next.
      Both the background fill and text rendering involve full alpha blits.
      That is, the alpha values of the foreground, background, and destination
      target surface all affect the blit.

      The return value is a rectangle giving the size and position of the
      rendered text within the surface.

      If an empty string is passed for text then the returned
      :class:`Rect <pygame.Rect>` is zero width and the height of the font.
      The rect will test False.

      Optionally, *text* can be set ``None``, which will re-render text
      passed to a previous :meth:`render_to`, :meth:`get_rect`, :meth:`render`,
      :meth:`render_raw`, or :meth:`render_raw_to` call. Primarily, this
      feature is an aid to using :meth:`render_to` in combination with
      :meth:`get_rect`. An example: ::

          def word_wrap(surf, text, font, color=(0, 0, 0)):
              font.origin = True
              words = text.split(' ')
              width, height = surf.get_size()
              line_spacing = font.get_sized_height() + 2
              x, y = 0, line_spacing
              space = font.get_rect(' ')
              for word in words:
                  bounds = font.get_rect(word)
                  if x + bounds.width + bounds.x >= width:
                      x, y = 0, y + line_spacing
                  if x + bounds.width + bounds.x >= width:
                      raise ValueError("word too wide for the surface")
                  if y + bounds.height - bounds.y >= height:
                      raise ValueError("text to long for the surface")
                  font.render_to(surf, (x, y), None, color)
                  x += bounds.width + space.width
              return x, y

      When :meth:`render_to` is called with the same
      font properties ― :attr:`size`, :attr:`style`, :attr:`strength`,
      :attr:`wide`, :attr:`antialiased`, :attr:`vertical`, :attr:`rotation`,
      :attr:`kerning`, and :attr:`use_bitmap_strikes` ― as :meth:`get_rect`,
      :meth:`render_to` will use the layout calculated by :meth:`get_rect`.
      Otherwise, :meth:`render_to` will recalculate the layout if called
      with a text string or one of the above properties has changed
      after the :meth:`get_rect` call.

      If *text* is a char (byte) string, then its encoding is assumed to be
      ``LATIN1``.

   .. method:: render_raw

      | :sl:`Return rendered text as a string of bytes`
      | :sg:`render_raw(text, style=STYLE_DEFAULT, rotation=0, size=0, invert=False) -> (bytes, (int, int))`

      Like :meth:`render` but with the pixels returned as a byte string
      of 8-bit gray-scale values. The foreground color is 255, the
      background 0, useful as an alpha mask for a foreground pattern.

   .. method:: render_raw_to

      | :sl:`Render text into an array of ints`
      | :sg:`render_raw_to(array, text, dest=None, style=STYLE_DEFAULT, rotation=0, size=0, invert=False) -> Rect`

      Render to an array object exposing an array struct interface. The array
      must be two dimensional with integer items. The default *dest* value,
      ``None``, is equivalent to position (0, 0). See :meth:`render_to`.
      As with the other render methods, *text* can be ``None`` to
      render a text string passed previously to another method.

      The return value is a :func:`pygame.Rect` giving the size and position of
      the rendered text.

   .. attribute:: style

      | :sl:`The font's style flags`
      | :sg:`style -> int`

      Gets or sets the default style of the Font. This default style will be
      used for all text rendering and size calculations unless overridden
      specifically a render or :meth:`get_rect` call.
      The style value may be a bit-wise OR of one or more of the following
      constants:

      ::

          STYLE_NORMAL
          STYLE_UNDERLINE
          STYLE_OBLIQUE
          STYLE_STRONG
          STYLE_WIDE
          STYLE_DEFAULT

      These constants may be found on the FreeType constants module.
      Optionally, the default style can be modified or obtained accessing the
      individual style attributes (underline, oblique, strong).

      The ``STYLE_OBLIQUE`` and ``STYLE_STRONG`` styles are for
      scalable fonts only. An attempt to set either for a bitmap font raises
      an AttributeError. An attempt to set either for an inactive font,
      as returned by ``Font.__new__()``, raises a RuntimeError.

      Assigning ``STYLE_DEFAULT`` to the :attr:`style` property leaves
      the property unchanged, as this property defines the default.
      The :attr:`style` property will never return ``STYLE_DEFAULT``.

   .. attribute:: underline

      | :sl:`The state of the font's underline style flag`
      | :sg:`underline -> bool`

      Gets or sets whether the font will be underlined when drawing text. This
      default style value will be used for all text rendering and size
      calculations unless overridden specifically in a render or
      :meth:`get_rect` call, via the 'style' parameter.

   .. attribute:: strong

      | :sl:`The state of the font's strong style flag`
      | :sg:`strong -> bool`

      Gets or sets whether the font will be bold when drawing text. This
      default style value will be used for all text rendering and size
      calculations unless overridden specifically in a render or
      :meth:`get_rect` call, via the 'style' parameter.

   .. attribute:: oblique

      | :sl:`The state of the font's oblique style flag`
      | :sg:`oblique -> bool`

      Gets or sets whether the font will be rendered as oblique. This
      default style value will be used for all text rendering and size
      calculations unless overridden specifically in a render or
      :meth:`get_rect` call, via the *style* parameter.

      The oblique style is only supported for scalable (outline) fonts.
      An attempt to set this style on a bitmap font will raise an
      AttributeError. If the font object is inactive, as returned by
      ``Font.__new__()``, setting this property raises a RuntimeError.

   .. attribute:: wide

      | :sl:`The state of the font's wide style flag`
      | :sg:`wide -> bool`

      Gets or sets whether the font will be stretched horizontally
      when drawing text. It produces a result similar to
      :class:`pygame.font.Font`'s bold. This style not available for
      rotated text.

   .. attribute:: strength

      | :sl:`The strength associated with the strong or wide font styles`
      | :sg:`strength -> float`

      The amount by which a font glyph's size is enlarged for the
      strong or wide transformations, as a fraction of the untransformed
      size. For the wide style only the horizontal dimension is
      increased. For strong text both the horizontal and vertical
      dimensions are enlarged. A wide style of strength 0.08333 ( 1/12 ) is
      equivalent to the :class:`pygame.font.Font` bold style.
      The default is 0.02778 ( 1/36 ).

      The strength style is only supported for scalable (outline) fonts.
      An attempt to set this property on a bitmap font will raise an
      AttributeError. If the font object is inactive, as returned by
      ``Font.__new__()``, assignment to this property raises a RuntimeError.

   .. attribute:: underline_adjustment

      | :sl:`Adjustment factor for the underline position`
      | :sg:`underline_adjustment -> float`

      Gets or sets a factor which, when positive, is multiplied with the
      font's underline offset to adjust the underline position. A negative
      value turns an underline into a strike-through or overline. It is
      multiplied with the ascender. Accepted values range between -2.0 and 2.0
      inclusive. A value of 0.5 closely matches Tango underlining. A value of
      1.0 mimics :class:`pygame.font.Font` underlining.

   .. attribute:: fixed_width

      | :sl:`Gets whether the font is fixed-width`
      | :sg:`fixed_width -> bool`

      Read only. Returns ``True`` if the font contains fixed-width
      characters (for example Courier, Bitstream Vera Sans Mono, Andale Mono).

   .. attribute:: fixed_sizes

      | :sl:`the number of available bitmap sizes for the font`
      | :sg:`fixed_sizes -> int`

      Read only. Returns the number of point sizes for which the font contains
      bitmap character images. If zero then the font is not a bitmap font.
      A scalable font may contain pre-rendered point sizes as strikes.

   .. attribute:: scalable

      | :sl:`Gets whether the font is scalable`
      | :sg:`scalable -> bool`

      Read only. Returns ``True`` if the font contains outline glyphs.
      If so, the point size is not limited to available bitmap sizes.

   .. attribute:: use_bitmap_strikes

      | :sl:`allow the use of embedded bitmaps in an outline font file`
      | :sg:`use_bitmap_strikes -> bool`

      Some scalable fonts include embedded bitmaps for particular point
      sizes. This property controls whether or not those bitmap strikes
      are used. Set it ``False`` to disable the loading of any bitmap
      strike. Set it ``True``, the default, to permit bitmap strikes
      for a non-rotated render with no style other than :attr:`wide` or
      :attr:`underline`. This property is ignored for bitmap fonts.

      See also :attr:`fixed_sizes` and :meth:`get_sizes`.

   .. attribute:: antialiased

      | :sl:`Font anti-aliasing mode`
      | :sg:`antialiased -> bool`

      Gets or sets the font's anti-aliasing mode. This defaults to
      ``True`` on all fonts, which are rendered with full 8 bit blending.

      Set to ``False`` to do monochrome rendering. This should
      provide a small speed gain and reduce cache memory size.

   .. attribute:: kerning

      | :sl:`Character kerning mode`
      | :sg:`kerning -> bool`

      Gets or sets the font's kerning mode. This defaults to ``False``
      on all fonts, which will be rendered without kerning.

      Set to ``True`` to add kerning between character pairs, if supported
      by the font, when positioning glyphs.

   .. attribute:: vertical

      | :sl:`Font vertical mode`
      | :sg:`vertical -> bool`

      Gets or sets whether the characters are laid out vertically rather
      than horizontally. May be useful when rendering Kanji or some other
      vertical script.

      Set to ``True`` to switch to a vertical text layout. The default
      is ``False``, place horizontally.

      Note that the :class:`Font` class does not automatically determine
      script orientation. Vertical layout must be selected explicitly.

      Also note that several font formats (especially bitmap based ones) don't
      contain the necessary metrics to draw glyphs vertically, so drawing in
      those cases will give unspecified results.

   .. attribute:: rotation

      | :sl:`text rotation in degrees counterclockwise`
      | :sg:`rotation -> int`

      Gets or sets the baseline angle of the rendered text. The angle is
      represented as integer degrees. The default angle is 0, with horizontal
      text rendered along the X-axis, and vertical text along the Y-axis.
      A positive value rotates these axes counterclockwise that many degrees.
      A negative angle corresponds to a clockwise rotation. The rotation
      value is normalized to a value within the range 0 to 359 inclusive
      (eg. 390 -> 390 - 360 -> 30, -45 -> 360 + -45 -> 315,
      720 -> 720 - (2 * 360) -> 0).

      Only scalable (outline) fonts can be rotated. An attempt to change
      the rotation of a bitmap font raises an AttributeError.
      An attempt to change the rotation of an inactive font instance, as
      returned by ``Font.__new__()``, raises a RuntimeError.

   .. attribute:: fgcolor

      | :sl:`default foreground color`
      | :sg:`fgcolor -> Color`

      Gets or sets the default glyph rendering color. It is initially opaque
      black ― (0, 0, 0, 255). Applies to :meth:`render` and :meth:`render_to`.

   .. attribute:: bgcolor

      | :sl:`default background color`
      | :sg:`bgcolor -> Color`

      Gets or sets the default background rendering color. Initially it is
      unset and text will render with a transparent background by default.
      Applies to :meth:`render` and :meth:`render_to`.

   .. versionadded:: 2.0.0

   .. attribute:: origin

      | :sl:`Font render to text origin mode`
      | :sg:`origin -> bool`

      If set ``True``, :meth:`render_to` and :meth:`render_raw_to` will
      take the *dest* position to be that of the text origin, as opposed to
      the top-left corner of the bounding box. See :meth:`get_rect` for
      details.

   .. attribute:: pad

      | :sl:`padded boundary mode`
      | :sg:`pad -> bool`

      If set ``True``, then the text boundary rectangle will be inflated
      to match that of :class:`font.Font <pygame.font.Font>`.
      Otherwise, the boundary rectangle is just large enough for the text.

   .. attribute:: ucs4

      | :sl:`Enable UCS-4 mode`
      | :sg:`ucs4 -> bool`

      Gets or sets the decoding of Unicode text. By default, the
      freetype module performs UTF-16 surrogate pair decoding on Unicode text.
      This allows 32-bit escape sequences ('\Uxxxxxxxx') between 0x10000 and
      0x10FFFF to represent their corresponding UTF-32 code points on Python
      interpreters built with a UCS-2 Unicode type (on Windows, for instance).
      It also means character values within the UTF-16 surrogate area (0xD800
      to 0xDFFF) are considered part of a surrogate pair. A malformed surrogate
      pair will raise a UnicodeEncodeError. Setting ucs4 ``True`` turns
      surrogate pair decoding off, allowing access the full UCS-4 character
      range to a Python interpreter built with four-byte Unicode character
      support.

   .. attribute:: resolution

      | :sl:`Pixel resolution in dots per inch`
      | :sg:`resolution -> int`

      Read only. Gets pixel size used in scaling font glyphs for this
      :class:`Font` instance.
