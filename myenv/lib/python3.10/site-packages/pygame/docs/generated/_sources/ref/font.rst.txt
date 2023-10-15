.. include:: common.txt

:mod:`pygame.font`
==================

.. module:: pygame.font
   :synopsis: pygame module for loading and rendering fonts

| :sl:`pygame module for loading and rendering fonts`

The font module allows for rendering TrueType fonts into Surface objects.
This module is built on top of the SDL_ttf library, which comes with all
normal pygame installations.

Most of the work done with fonts are done by using the actual Font objects.
The module by itself only has routines to support the creation of Font objects
with :func:`pygame.font.Font`.

You can load fonts from the system by using the :func:`pygame.font.SysFont`
function. There are a few other functions to help look up the system fonts.

Pygame comes with a builtin default font, freesansbold. This can always be
accessed by passing ``None`` as the font name.

Before pygame 2.0.3, pygame.font accepts any UCS-2 / UTF-16 character
('\\u0001' to '\\uFFFF'). After 2.0.3, pygame.font built with SDL_ttf
2.0.15 accepts any valid UCS-4 / UTF-32 character 
(like emojis, if the font has them) ('\\U00000001' to '\\U0010FFFF')).
More about this in :func:`Font.render`.

Before pygame 2.0.3, this character space restriction can be avoided by
using the  :mod:`pygame.freetype` based ``pygame.ftfont`` to emulate the Font
module. This can be used by defining the environment variable PYGAME_FREETYPE
before the first import of :mod:`pygame`. Since the problem ``pygame.ftfont``
solves no longer exists, it will likely be removed in the future.

.. function:: init

   | :sl:`initialize the font module`
   | :sg:`init() -> None`

   This method is called automatically by ``pygame.init()``. It initializes the
   font module. The module must be initialized before any other functions will
   work.

   It is safe to call this function more than once.

   .. ## pygame.font.init ##

.. function:: quit

   | :sl:`uninitialize the font module`
   | :sg:`quit() -> None`

   Manually uninitialize SDL_ttf's font system. This is called automatically by
   ``pygame.quit()``.

   It is safe to call this function even if font is currently not initialized.

   .. ## pygame.font.quit ##

.. function:: get_init

   | :sl:`true if the font module is initialized`
   | :sg:`get_init() -> bool`

   Test if the font module is initialized or not.

   .. ## pygame.font.get_init ##

.. function:: get_default_font

   | :sl:`get the filename of the default font`
   | :sg:`get_default_font() -> string`

   Return the filename of the system font. This is not the full path to the
   file. This file can usually be found in the same directory as the font
   module, but it can also be bundled in separate archives.

   .. ## pygame.font.get_default_font ##

.. function:: get_sdl_ttf_version

   | :sl:`gets SDL_ttf version`
   | :sg:`get_sdl_ttf_version(linked=True) -> (major, minor, patch)`

   **Experimental:** feature still in development available for testing and feedback. It may change.
   `Please leave get_sdl_ttf_version feedback with authors <https://github.com/pygame/pygame/pull/3095>`_

   Returns a tuple of integers that identify SDL_ttf's version.
   SDL_ttf is the underlying font rendering library, written in C,
   on which pygame's font module depends. If 'linked' is True (the default), 
   the function returns the version of the linked TTF library. 
   Otherwise this function returns the version of TTF pygame was compiled with

   .. versionadded:: 2.1.3

   .. ## pygame.font.get_sdl_ttf_version ##

.. function:: get_fonts

   | :sl:`get all available fonts`
   | :sg:`get_fonts() -> list of strings`

   Returns a list of all the fonts available on the system. The names of the
   fonts will be set to lowercase with all spaces and punctuation removed. This
   works on most systems, but some will return an empty list if they cannot
   find fonts.

   .. versionchanged:: 2.1.3 Checks through user fonts instead of just global fonts for Windows.

   .. ## pygame.font.get_fonts ##

.. function:: match_font

   | :sl:`find a specific font on the system`
   | :sg:`match_font(name, bold=False, italic=False) -> path`

   Returns the full path to a font file on the system. If bold or italic are
   set to true, this will attempt to find the correct family of font.

   The font name can also be an iterable of font names, a string of
   comma-separated font names, or a bytes of comma-separated font names, in
   which case the set of names will be searched in order.
   If none of the given names are found, None is returned.

   .. versionadded:: 2.0.1 Accept an iterable of font names.

   .. versionchanged:: 2.1.3 Checks through user fonts instead of just global fonts for Windows.

   Example:

   ::

       print pygame.font.match_font('bitstreamverasans')
       # output is: /usr/share/fonts/truetype/ttf-bitstream-vera/Vera.ttf
       # (but only if you have Vera on your system)

   .. ## pygame.font.match_font ##

.. function:: SysFont

   | :sl:`create a Font object from the system fonts`
   | :sg:`SysFont(name, size, bold=False, italic=False) -> Font`

   Return a new Font object that is loaded from the system fonts. The font will
   match the requested bold and italic flags. Pygame uses a small set of common
   font aliases. If the specific font you ask for is not available, a reasonable
   alternative may be used. If a suitable system font is not found this will
   fall back on loading the default pygame font.

   The font name can also be an iterable of font names, a string of
   comma-separated font names, or a bytes of comma-separated font names, in
   which case the set of names will be searched in order.

   .. versionadded:: 2.0.1 Accept an iterable of font names.

   .. versionchanged:: 2.1.3 Checks through user fonts instead of just global fonts for Windows.

   .. ## pygame.font.SysFont ##

.. class:: Font

   | :sl:`create a new Font object from a file`
   | :sg:`Font(file_path=None, size=12) -> Font`
   | :sg:`Font(file_path, size) -> Font`
   | :sg:`Font(pathlib.Path, size) -> Font`
   | :sg:`Font(object, size) -> Font`

   Load a new font from a given filename or a python file object. The size is
   the height of the font in pixels. If the filename is ``None`` the pygame
   default font will be loaded. If a font cannot be loaded from the arguments
   given an exception will be raised. Once the font is created the size cannot
   be changed. If no arguments are given then the default font will be used and
   a font size of 12 is used.

   Font objects are mainly used to render text into new Surface objects. The
   render can emulate bold or italic features, but it is better to load from a
   font with actual italic or bold glyphs.

   .. attribute:: bold

      | :sl:`Gets or sets whether the font should be rendered in (faked) bold.`
      | :sg:`bold -> bool`

      Whether the font should be rendered in bold.

      When set to True, this enables the bold rendering of text. This
      is a fake stretching of the font that doesn't look good on many
      font types. If possible load the font from a real bold font
      file. While bold, the font will have a different width than when
      normal. This can be mixed with the italic, underline and
      strikethrough modes.

      .. versionadded:: 2.0.0

      .. ## Font.bold ##

   .. attribute:: italic

      | :sl:`Gets or sets whether the font should be rendered in (faked) italics.`
      | :sg:`italic -> bool`

      Whether the font should be rendered in italic.

      When set to True, this enables fake rendering of italic
      text. This is a fake skewing of the font that doesn't look good
      on many font types. If possible load the font from a real italic
      font file. While italic the font will have a different width
      than when normal. This can be mixed with the bold, underline and
      strikethrough modes.

      .. versionadded:: 2.0.0

      .. ## Font.italic ##

   .. attribute:: underline

      | :sl:`Gets or sets whether the font should be rendered with an underline.`
      | :sg:`underline -> bool`

      Whether the font should be rendered in underline.

      When set to True, all rendered fonts will include an
      underline. The underline is always one pixel thick, regardless
      of font size. This can be mixed with the bold, italic and
      strikethrough modes.

      .. versionadded:: 2.0.0

      .. ## Font.underline ##
   
   .. attribute:: strikethrough

      | :sl:`Gets or sets whether the font should be rendered with a strikethrough.`
      | :sg:`strikethrough -> bool`

      Whether the font should be rendered with a strikethrough.

      When set to True, all rendered fonts will include an
      strikethrough. The strikethrough is always one pixel thick,
      regardless of font size. This can be mixed with the bold,
      italic and underline modes.

      .. versionadded:: 2.1.3

      .. ## Font.strikethrough ##

   .. method:: render

      | :sl:`draw text on a new Surface`
      | :sg:`render(text, antialias, color, background=None) -> Surface`

      This creates a new Surface with the specified text rendered on it. 
      :mod:`pygame.font` provides no way to directly draw text on an existing
      Surface: instead you must use :func:`Font.render` to create an image
      (Surface) of the text, then blit this image onto another Surface.

      The text can only be a single line: newline characters are not rendered.
      Null characters ('\x00') raise a TypeError. Both Unicode and char (byte)
      strings are accepted. For Unicode strings only UCS-2 characters
      ('\\u0001' to '\\uFFFF') were previously supported and any greater
      unicode codepoint would raise a UnicodeError. Now, characters in the
      UCS-4 range are supported. For char strings a ``LATIN1`` encoding is
      assumed. The antialias argument is a boolean: if True the characters
      will have smooth edges. The color argument is the color of the text
      [e.g.: (0,0,255) for blue]. The optional background argument is a color
      to use for the text background. If no background is passed the area
      outside the text will be transparent.

      The Surface returned will be of the dimensions required to hold the text.
      (the same as those returned by :func:`Font.size`). If an empty string is passed
      for the text, a blank surface will be returned that is zero pixel wide and
      the height of the font.

      Depending on the type of background and antialiasing used, this returns
      different types of Surfaces. For performance reasons, it is good to know
      what type of image will be used. If antialiasing is not used, the return
      image will always be an 8-bit image with a two-color palette. If the
      background is transparent a colorkey will be set. Antialiased images are
      rendered to 24-bit ``RGB`` images. If the background is transparent a
      pixel alpha will be included.

      Optimization: if you know that the final destination for the text (on the
      screen) will always have a solid background, and the text is antialiased,
      you can improve performance by specifying the background color. This will
      cause the resulting image to maintain transparency information by
      colorkey rather than (much less efficient) alpha values.

      If you render '\\n' an unknown char will be rendered. Usually a
      rectangle. Instead you need to handle newlines yourself.

      Font rendering is not thread safe: only a single thread can render text
      at any time.

      .. versionchanged:: 2.0.3 Rendering UCS4 unicode works and does not
        raise an exception. Use `if hasattr(pygame.font, "UCS4"):` to see if
        pygame supports rendering UCS4 unicode including more languages and
        emoji.

      .. ## Font.render ##

   .. method:: size

      | :sl:`determine the amount of space needed to render text`
      | :sg:`size(text) -> (width, height)`

      Returns the dimensions needed to render the text. This can be used to
      help determine the positioning needed for text before it is rendered. It
      can also be used for word wrapping and other layout effects.

      Be aware that most fonts use kerning which adjusts the widths for
      specific letter pairs. For example, the width for "ae" will not always
      match the width for "a" + "e".

      .. ## Font.size ##

   .. method:: set_underline

      | :sl:`control if text is rendered with an underline`
      | :sg:`set_underline(bool) -> None`

      When enabled, all rendered fonts will include an underline. The underline
      is always one pixel thick, regardless of font size. This can be mixed
      with the bold, italic and strikethrough modes.

      .. note:: This is the same as the :attr:`underline` attribute.

      .. ## Font.set_underline ##

   .. method:: get_underline

      | :sl:`check if text will be rendered with an underline`
      | :sg:`get_underline() -> bool`

      Return True when the font underline is enabled.

       .. note:: This is the same as the :attr:`underline` attribute.

      .. ## Font.get_underline ##
   
   .. method:: set_strikethrough

      | :sl:`control if text is rendered with a strikethrough`
      | :sg:`set_strikethrough(bool) -> None`

      When enabled, all rendered fonts will include a strikethrough. The
      strikethrough is always one pixel thick, regardless of font size.
      This can be mixed with the bold, italic and underline modes.

      .. note:: This is the same as the :attr:`strikethrough` attribute.
      
      .. versionadded:: 2.1.3

      .. ## Font.set_strikethrough ##

   .. method:: get_strikethrough

      | :sl:`check if text will be rendered with a strikethrough`
      | :sg:`get_strikethrough() -> bool`

      Return True when the font strikethrough is enabled.

       .. note:: This is the same as the :attr:`strikethrough` attribute.
       
       .. versionadded:: 2.1.3

      .. ## Font.get_strikethrough ##

   .. method:: set_bold

      | :sl:`enable fake rendering of bold text`
      | :sg:`set_bold(bool) -> None`

      Enables the bold rendering of text. This is a fake stretching of the font
      that doesn't look good on many font types. If possible load the font from
      a real bold font file. While bold, the font will have a different width
      than when normal. This can be mixed with the italic, underline and
      strikethrough modes.

      .. note:: This is the same as the :attr:`bold` attribute.

      .. ## Font.set_bold ##

   .. method:: get_bold

      | :sl:`check if text will be rendered bold`
      | :sg:`get_bold() -> bool`

      Return True when the font bold rendering mode is enabled.

      .. note:: This is the same as the :attr:`bold` attribute.

      .. ## Font.get_bold ##

   .. method:: set_italic

      | :sl:`enable fake rendering of italic text`
      | :sg:`set_italic(bool) -> None`

      Enables fake rendering of italic text. This is a fake skewing of the font
      that doesn't look good on many font types. If possible load the font from
      a real italic font file. While italic the font will have a different
      width than when normal. This can be mixed with the bold, underline and
      strikethrough modes.

      .. note:: This is the same as the :attr:`italic` attribute.

      .. ## Font.set_italic ##

   .. method:: metrics

      | :sl:`gets the metrics for each character in the passed string`
      | :sg:`metrics(text) -> list`

      The list contains tuples for each character, which contain the minimum
      ``X`` offset, the maximum ``X`` offset, the minimum ``Y`` offset, the
      maximum ``Y`` offset and the advance offset (bearing plus width) of the
      character. [(minx, maxx, miny, maxy, advance), (minx, maxx, miny, maxy,
      advance), ...]. None is entered in the list for each unrecognized
      character.

      .. ## Font.metrics ##

   .. method:: get_italic

      | :sl:`check if the text will be rendered italic`
      | :sg:`get_italic() -> bool`

      Return True when the font italic rendering mode is enabled.

      .. note:: This is the same as the :attr:`italic` attribute.

      .. ## Font.get_italic ##

   .. method:: get_linesize

      | :sl:`get the line space of the font text`
      | :sg:`get_linesize() -> int`

      Return the height in pixels for a line of text with the font. When
      rendering multiple lines of text this is the recommended amount of space
      between lines.

      .. ## Font.get_linesize ##

   .. method:: get_height

      | :sl:`get the height of the font`
      | :sg:`get_height() -> int`

      Return the height in pixels of the actual rendered text. This is the
      average size for each glyph in the font.

      .. ## Font.get_height ##

   .. method:: get_ascent

      | :sl:`get the ascent of the font`
      | :sg:`get_ascent() -> int`

      Return the height in pixels for the font ascent. The ascent is the number
      of pixels from the font baseline to the top of the font.

      .. ## Font.get_ascent ##

   .. method:: get_descent

      | :sl:`get the descent of the font`
      | :sg:`get_descent() -> int`

      Return the height in pixels for the font descent. The descent is the
      number of pixels from the font baseline to the bottom of the font.

      .. ## Font.get_descent ##

   .. method:: set_script

      | :sl:`set the script code for text shaping`
      | :sg:`set_script(str) -> None`

      **Experimental:** feature still in development available for testing and feedback. It may change.
      `Please leave feedback with authors <https://github.com/pygame/pygame/pull/3330>`_

      Sets the script used by harfbuzz text shaping, taking a 4 character
      script code as input. For example, Hindi is written in the Devanagari
      script, for which the script code is `"Deva"`. See the full list of
      script codes in `ISO 15924 <https://www.unicode.org/iso15924/iso15924-codes.html>`_.

      This method requires pygame built with SDL_ttf 2.20.0 or above. Otherwise the
      method will raise a pygame.error.

      .. versionadded:: 2.2.0

      .. ## Font.set_script ## 

   .. ## pygame.font.Font ##

.. ## pygame.font ##
