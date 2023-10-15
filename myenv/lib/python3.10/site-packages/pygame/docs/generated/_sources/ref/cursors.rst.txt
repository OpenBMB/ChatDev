.. include:: common.txt

:mod:`pygame.cursors`
=====================

.. module:: pygame.cursors
   :synopsis: pygame module for cursor resources

| :sl:`pygame module for cursor resources`

Pygame offers control over the system hardware cursor. Pygame supports
black and white cursors (bitmap cursors), as well as system variant cursors and color cursors.
You control the cursor with functions inside :mod:`pygame.mouse`.

This cursors module contains functions for loading and decoding various
cursor formats. These allow you to easily store your cursors in external files
or directly as encoded python strings.

The module includes several standard cursors. The :func:`pygame.mouse.set_cursor()`
function takes several arguments. All those arguments have been stored in a
single tuple you can call like this:

::

   >>> pygame.mouse.set_cursor(*pygame.cursors.arrow)
   
The following variables can be passed to ``pygame.mouse.set_cursor`` function:

   * ``pygame.cursors.arrow``

   * ``pygame.cursors.diamond``

   * ``pygame.cursors.broken_x``

   * ``pygame.cursors.tri_left``

   * ``pygame.cursors.tri_right``

This module also contains a few cursors as formatted strings. You'll need to
pass these to ``pygame.cursors.compile()`` function before you can use them.
The example call would look like this:

::

   >>> cursor = pygame.cursors.compile(pygame.cursors.textmarker_strings)
   >>> pygame.mouse.set_cursor((8, 16), (0, 0), *cursor)

The following strings can be converted into cursor bitmaps with
``pygame.cursors.compile()`` :

   * ``pygame.cursors.thickarrow_strings``

   * ``pygame.cursors.sizer_x_strings``

   * ``pygame.cursors.sizer_y_strings``

   * ``pygame.cursors.sizer_xy_strings``
   
   * ``pygame.cursor.textmarker_strings``

.. function:: compile

   | :sl:`create binary cursor data from simple strings`
   | :sg:`compile(strings, black='X', white='.', xor='o') -> data, mask`

   A sequence of strings can be used to create binary cursor data for the
   system cursor. This returns the binary data in the form of two tuples.
   Those can be passed as the third and fourth arguments respectively of the 
   :func:`pygame.mouse.set_cursor()` function.

   If you are creating your own cursor strings, you can use any value represent
   the black and white pixels. Some system allow you to set a special toggle
   color for the system color, this is also called the xor color. If the system
   does not support xor cursors, that color will simply be black.
   
   The height must be divisible by 8. The width of the strings must all be equal 
   and be divisible by 8. If these two conditions are not met, ``ValueError`` is
   raised.
   An example set of cursor strings looks like this

   ::

       thickarrow_strings = (               #sized 24x24
         "XX                      ",
         "XXX                     ",
         "XXXX                    ",
         "XX.XX                   ",
         "XX..XX                  ",
         "XX...XX                 ",
         "XX....XX                ",
         "XX.....XX               ",
         "XX......XX              ",
         "XX.......XX             ",
         "XX........XX            ",
         "XX........XXX           ",
         "XX......XXXXX           ",
         "XX.XXX..XX              ",
         "XXXX XX..XX             ",
         "XX   XX..XX             ",
         "     XX..XX             ",
         "      XX..XX            ",
         "      XX..XX            ",
         "       XXXX             ",
         "       XX               ",
         "                        ",
         "                        ",
         "                        ")

   .. ## pygame.cursors.compile ##

.. function:: load_xbm

   | :sl:`load cursor data from an XBM file`
   | :sg:`load_xbm(cursorfile) -> cursor_args`
   | :sg:`load_xbm(cursorfile, maskfile) -> cursor_args`

   This loads cursors for a simple subset of ``XBM`` files. ``XBM`` files are
   traditionally used to store cursors on UNIX systems, they are an ASCII
   format used to represent simple images.

   Sometimes the black and white color values will be split into two separate
   ``XBM`` files. You can pass a second maskfile argument to load the two
   images into a single cursor.

   The cursorfile and maskfile arguments can either be filenames or file-like
   object with the readlines method.

   The return value cursor_args can be passed directly to the
   ``pygame.mouse.set_cursor()`` function.

   .. ## pygame.cursors.load_xbm ##



.. class:: Cursor

   | :sl:`pygame object representing a cursor`
   | :sg:`Cursor(size, hotspot, xormasks, andmasks) -> Cursor`
   | :sg:`Cursor(hotspot, surface) -> Cursor`
   | :sg:`Cursor(constant) -> Cursor`
   | :sg:`Cursor(Cursor) -> Cursor`
   | :sg:`Cursor() -> Cursor`

   In pygame 2, there are 3 types of cursors you can create to give your
   game that little bit of extra polish. There's **bitmap** type cursors,
   which existed in pygame 1.x, and are compiled from a string or load from an xbm file.
   Then there are **system** type cursors, where you choose a preset that will 
   convey the same meaning but look native across different operating systems. 
   Finally you can create a **color** cursor, which displays a pygame surface as the cursor.

   **Creating a system cursor**

   Choose a constant from this list, pass it into ``pygame.cursors.Cursor(constant)``, 
   and you're good to go. Be advised that not all systems support every system
   cursor, and you may get a substitution instead. For example, on MacOS,
   WAIT/WAITARROW should show up as an arrow, and SIZENWSE/SIZENESW/SIZEALL
   should show up as a closed hand. And on Wayland, every SIZE cursor should 
   show up as a hand.

   ::

      Pygame Cursor Constant           Description
      --------------------------------------------
      pygame.SYSTEM_CURSOR_ARROW       arrow
      pygame.SYSTEM_CURSOR_IBEAM       i-beam
      pygame.SYSTEM_CURSOR_WAIT        wait
      pygame.SYSTEM_CURSOR_CROSSHAIR   crosshair
      pygame.SYSTEM_CURSOR_WAITARROW   small wait cursor 
                                       (or wait if not available)
      pygame.SYSTEM_CURSOR_SIZENWSE    double arrow pointing 
                                       northwest and southeast
      pygame.SYSTEM_CURSOR_SIZENESW    double arrow pointing
                                       northeast and southwest
      pygame.SYSTEM_CURSOR_SIZEWE      double arrow pointing
                                       west and east
      pygame.SYSTEM_CURSOR_SIZENS      double arrow pointing 
                                       north and south
      pygame.SYSTEM_CURSOR_SIZEALL     four pointed arrow pointing
                                       north, south, east, and west
      pygame.SYSTEM_CURSOR_NO          slashed circle or crossbones
      pygame.SYSTEM_CURSOR_HAND        hand

   **Creating a cursor without passing arguments**
   
   In addition to the cursor constants available and described above,
   you can also call ``pygame.cursors.Cursor()``, and your cursor is ready (doing that is the same as
   calling ``pygame.cursors.Cursor(pygame.SYSTEM_CURSOR_ARROW)``.
   Doing one of those calls actually creates a system cursor using the default native image.

   **Creating a color cursor**

   To create a color cursor, create a ``Cursor`` from a ``hotspot`` and a ``surface``.
   ``hotspot`` is an (x,y) coordinate that determines where in the cursor the exact point is.
   The hotspot position must be within the bounds of the ``surface``.

   **Creating a bitmap cursor**

   When the mouse cursor is visible, it will be displayed as a black and white
   bitmap using the given bitmask arrays. The ``size`` is a sequence containing 
   the cursor width and height. ``hotspot`` is a sequence containing the cursor 
   hotspot position. 
   
   A cursor has a width and height, but a mouse position is represented by a 
   set of point coordinates. So the value passed into the cursor ``hotspot`` 
   variable helps pygame to actually determine at what exact point the cursor 
   is at.
   
   ``xormasks`` is a sequence of bytes containing the cursor xor data masks. 
   Lastly ``andmasks``, a sequence of bytes containing the cursor bitmask data.
   To create these variables, we can make use of the 
   :func:`pygame.cursors.compile()` function.

   Width and height must be a multiple of 8, and the mask arrays must be the 
   correct size for the given width and height. Otherwise an exception is raised.
   
   .. method:: copy

      | :sl:`copy the current cursor`
      | :sg:`copy() -> Cursor`
      
      Returns a new Cursor object with the same data and hotspot as the original.
   .. ## pygame.cursors.Cursor.copy ##
   

   .. attribute:: type
   
      | :sl:`Gets the cursor type`
      | :sg:`type -> string`

      The type will be ``"system"``, ``"bitmap"``, or ``"color"``.

   .. ## pygame.cursors.Cursor.type ##

   .. attribute:: data

      | :sl:`Gets the cursor data`
      | :sg:`data -> tuple`

      Returns the data that was used to create this cursor object, wrapped up in a tuple.

   .. ## pygame.cursors.Cursor.data ##

   .. versionadded:: 2.0.1

   .. ## pygame.cursors.Cursor ##
   
.. ## pygame.cursors ##

Example code for creating and settings cursors. (Click the mouse to switch cursor)

.. literalinclude:: code_examples/cursors_module_example.py
