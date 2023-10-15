.. include:: common.txt

:mod:`pygame.examples`
======================

.. module:: pygame.examples
   :synopsis: module of example programs

| :sl:`module of example programs`

These examples should help get you started with pygame. Here is a brief rundown
of what you get. The source code for these examples is in the public domain.
Feel free to use for your own projects.

There are several ways to run the examples. First they can be run as
stand-alone programs. Second they can be imported and their ``main()`` methods
called (see below). Finally, the easiest way is to use the python -m option:

::

   python -m pygame.examples.<example name> <example arguments>

eg:

::

   python -m pygame.examples.scaletest someimage.png

Resources such as images and sounds for the examples are found in the 
pygame/examples/data subdirectory.

You can find where the example files are installed by using the following
commands inside the python interpreter.

::

   >>> import pygame.examples.scaletest
   >>> pygame.examples.scaletest.__file__
   '/usr/lib/python2.6/site-packages/pygame/examples/scaletest.py'

On each OS and version of Python the location will be slightly different.
For example on Windows it might be in 'C:/Python26/Lib/site-packages/pygame/examples/'
On Mac OS X it might be in '/Library/Frameworks/Python.framework/Versions/2.6/lib/python2.6/site-packages/pygame/examples/'


You can also run the examples in the python interpreter by calling each modules main() function.

::

   >>> import pygame.examples.scaletest
   >>> pygame.examples.scaletest.main()


We're always on the lookout for more examples and/or example requests. Code
like this is probably the best way to start getting involved with python
gaming.

examples as a package is new to pygame 1.9.0. But most of the examples came with
pygame much earlier.

.. function:: aliens.main

   | :sl:`play the full aliens example`
   | :sg:`aliens.main() -> None`

   This started off as a port of the ``SDL`` demonstration, Aliens. Now it has
   evolved into something sort of resembling fun. This demonstrates a lot of
   different uses of sprites and optimized blitting. Also transparency,
   colorkeys, fonts, sound, music, joystick, and more. (PS, my high score is
   117! goodluck)

   .. ## pygame.examples.aliens.main ##

.. function:: stars.main

   | :sl:`run a simple starfield example`
   | :sg:`stars.main() -> None`

   A simple starfield example. You can change the center of perspective by
   leftclicking the mouse on the screen.

   .. ## pygame.examples.stars.main ##

.. function:: chimp.main

   | :sl:`hit the moving chimp`
   | :sg:`chimp.main() -> None`

   This simple example is derived from the line-by-line tutorial that comes
   with pygame. It is based on a 'popular' web banner. Note there are comments
   here, but for the full explanation, follow along in the tutorial.

   .. ## pygame.examples.chimp.main ##

.. function:: moveit.main

   | :sl:`display animated objects on the screen`
   | :sg:`moveit.main() -> None`

   This is the full and final example from the Pygame Tutorial, "How Do I Make
   It Move". It creates 10 objects and animates them on the screen.

   Note it's a bit scant on error checking, but it's easy to read. :]
   Fortunately, this is python, and we needn't wrestle with a pile of error
   codes.

   .. ## pygame.examples.moveit.main ##

.. function:: fonty.main

   | :sl:`run a font rendering example`
   | :sg:`fonty.main() -> None`

   Super quick, super simple application demonstrating the different ways to
   render fonts with the font module

   .. ## pygame.examples.fonty.main ##

.. function:: freetype_misc.main

   | :sl:`run a FreeType rendering example`
   | :sg:`freetype_misc.main() -> None`

   A showcase of rendering features the :class:`pygame.freetype.Font`
   class provides in addition to those available with :class:`pygame.font.Font`.
   It is a demonstration of direct to surface rendering, with vertical text
   and rotated text, opaque text and semi transparent text, horizontally
   stretched text and vertically stretched text.

   .. ## pygame.examples.fonty.main ##

.. function:: vgrade.main

   | :sl:`display a vertical gradient`
   | :sg:`vgrade.main() -> None`

   Demonstrates creating a vertical gradient with pixelcopy and NumPy python.
   The app will create a new gradient every half second and report the time
   needed to create and display the image. If you're not prepared to start
   working with the NumPy arrays, don't worry about the source for this one :]

   .. ## pygame.examples.vgrade.main ##

.. function:: eventlist.main

   | :sl:`display pygame events`
   | :sg:`eventlist.main() -> None`

   Eventlist is a sloppy style of pygame, but is a handy tool for learning
   about pygame events and input. At the top of the screen are the state of
   several device values, and a scrolling list of events are displayed on the
   bottom.

   This is not quality 'ui' code at all, but you can see how to implement very
   non-interactive status displays, or even a crude text output control.

   .. ## pygame.examples.eventlist.main ##

.. function:: arraydemo.main

   | :sl:`show various surfarray effects`
   | :sg:`arraydemo.main(arraytype=None) -> None`

   Another example filled with various surfarray effects. It requires the
   surfarray and image modules to be installed. This little demo can also make
   a good starting point for any of your own tests with surfarray

   The ``arraytype`` parameter is deprecated; passing any value besides 'numpy'
   will raise ValueError.

   .. ## pygame.examples.arraydemo.main ##

.. function:: sound.main

   | :sl:`load and play a sound`
   | :sg:`sound.main(file_path=None) -> None`

   Extremely basic testing of the mixer module. Load a sound and play it. All
   from the command shell, no graphics.

   If provided, use the audio file 'file_path', otherwise use a default file.

   ``sound.py`` optional command line argument: an audio file

   .. ## pygame.examples.sound.main ##

.. function:: sound_array_demos.main

   | :sl:`play various sndarray effects`
   | :sg:`sound_array_demos.main(arraytype=None) -> None`


   Uses sndarray and NumPy to create offset faded copies of the
   original sound. Currently it just uses hardcoded values for the number of
   echoes and the delay. Easy for you to recreate as needed.

   The ``arraytype`` parameter is deprecated; passing any value besides 'numpy'
   will raise ValueError.

   .. ## pygame.examples.sound_array_demos.main ##

.. function:: liquid.main

   | :sl:`display an animated liquid effect`
   | :sg:`liquid.main() -> None`

   This example was created in a quick comparison with the BlitzBasic gaming
   language. Nonetheless, it demonstrates a quick 8-bit setup (with colormap).

   .. ## pygame.examples.liquid.main ##

.. function:: glcube.main

   | :sl:`display an animated 3D cube using OpenGL`
   | :sg:`glcube.main() -> None`

   Using PyOpenGL and pygame, this creates a spinning 3D multicolored cube.

   .. ## pygame.examples.glcube.main ##

.. function:: scrap_clipboard.main

   | :sl:`access the clipboard`
   | :sg:`scrap_clipboard.main() -> None`

   A simple demonstration example for the clipboard support.

   .. ## pygame.examples.scrap_clipboard.main ##

.. function:: mask.main

   | :sl:`display multiple images bounce off each other using collision detection`
   | :sg:`mask.main(*args) -> None`

   Positional arguments:

   ::

       one or more image file names.

   This ``pygame.masks`` demo will display multiple moving sprites bouncing off
   each other. More than one sprite image can be provided.

   If run as a program then ``mask.py`` takes one or more image files as
   command line arguments.

   .. ## pygame.examples.mask.main ##

.. function:: testsprite.main

   | :sl:`show lots of sprites moving around`
   | :sg:`testsprite.main(update_rects = True, use_static = False, use_FastRenderGroup = False, screen_dims = [640, 480], use_alpha = False, flags = 0) -> None`

   Optional keyword arguments:

   ::

       update_rects - use the RenderUpdate sprite group class
       use_static - include non-moving images
       use_FastRenderGroup - Use the FastRenderGroup sprite group
       screen_dims - pygame window dimensions
       use_alpha - use alpha blending
       flags - additional display mode flags

   Like the ``testsprite.c`` that comes with SDL, this pygame version shows
   lots of sprites moving around.

   If run as a stand-alone program then no command line arguments are taken.

   .. ## pygame.examples.testsprite.main ##

.. function:: headless_no_windows_needed.main

   | :sl:`write an image file that is smoothscaled copy of an input file`
   | :sg:`headless_no_windows_needed.main(fin, fout, w, h) -> None`

   arguments:

   ::

       fin - name of an input image file
       fout - name of the output file to create/overwrite
       w, h - size of the rescaled image, as integer width and height

   How to use pygame with no windowing system, like on headless servers.

   Thumbnail generation with scaling is an example of what you can do with
   pygame.

   ``NOTE``: the pygame scale function uses MMX/SSE if available, and can be
   run in multiple threads.

   If ``headless_no_windows_needed.py`` is run as a program it takes the
   following command line arguments:

   ::

       -scale inputimage outputimage new_width new_height
       eg. -scale in.png outpng 50 50

   .. ## pygame.examples.headless_no_windows_needed.main ##

.. function:: joystick.main

   | :sl:`demonstrate joystick functionality`
   | :sg:`joystick.main() -> None`

   A demo showing full joystick support.

   .. versionadded:: 2.0.2

   .. ## pygame.examples.joystick.main ##

.. function:: blend_fill.main

   | :sl:`demonstrate the various surface.fill method blend options`
   | :sg:`blend_fill.main() -> None`

   A interactive demo that lets one choose which BLEND_xxx option to apply to a
   surface.

   .. ## pygame.examples.blend_fill.main ##

.. function:: blit_blends.main

   | :sl:`uses alternative additive fill to that of surface.fill`
   | :sg:`blit_blends.main() -> None`

   Fake additive blending. Using NumPy. it doesn't clamp. Press r,g,b Somewhat
   like blend_fill.

   .. ## pygame.examples.blit_blends.main ##

.. function:: cursors.main

   | :sl:`display two different custom cursors`
   | :sg:`cursors.main() -> None`

   Display an arrow or circle with crossbar cursor.

   .. ## pygame.examples.cursors.main ##

.. function:: pixelarray.main

   | :sl:`display various pixelarray generated effects`
   | :sg:`pixelarray.main() -> None`

   Display various pixelarray generated effects.

   .. ## pygame.examples.pixelarray.main ##

.. function:: scaletest.main

   | :sl:`interactively scale an image using smoothscale`
   | :sg:`scaletest.main(imagefile, convert_alpha=False, run_speed_test=True) -> None`

   arguments:

   ::

       imagefile - file name of source image (required)
       convert_alpha - use convert_alpha() on the surf (default False)
       run_speed_test - (default False)

   A smoothscale example that resized an image on the screen. Vertical and
   horizontal arrow keys are used to change the width and height of the
   displayed image. If the convert_alpha option is True then the source image
   is forced to have source alpha, whether or not the original images does. If
   run_speed_test is True then a background timing test is performed instead of
   the interactive scaler.

   If ``scaletest.py`` is run as a program then the command line options are:

   ::

       ImageFile [-t] [-convert_alpha]
       [-t] = Run Speed Test
       [-convert_alpha] = Use convert_alpha() on the surf.

   .. ## pygame.examples.scaletest.main ##

.. function:: midi.main

   | :sl:`run a midi example`
   | :sg:`midi.main(mode='output', device_id=None) -> None`

   Arguments:

   ::

       mode - if 'output' run a midi keyboard output example
                 'input' run a midi event logger input example
                 'list' list available midi devices
              (default 'output')
       device_id - midi device number; if None then use the default midi input or
                   output device for the system

   The output example shows how to translate mouse clicks or computer keyboard
   events into midi notes. It implements a rudimentary button widget and state
   machine.

   The input example shows how to translate midi input to pygame events.

   With the use of a virtual midi patch cord the output and input examples can
   be run as separate processes and connected so the keyboard output is
   displayed on a console.

   new to pygame 1.9.0

   .. ## pygame.examples.midi.main ##

.. function:: scroll.main

   | :sl:`run a Surface.scroll example that shows a magnified image`
   | :sg:`scroll.main(image_file=None) -> None`

   This example shows a scrollable image that has a zoom factor of eight. It
   uses the :meth:`Surface.scroll() <pygame.Surface.scroll>`
   function to shift the image on the display surface.
   A clip rectangle protects a margin area. If called as a function,
   the example accepts an optional image file path. If run as a program it
   takes an optional file path command line argument. If no file is provided a
   default image file is used.

   When running click on a black triangle to move one pixel in the direction
   the triangle points. Or use the arrow keys. Close the window or press
   ``ESC`` to quit.

   .. ## pygame.examples.scroll.main ##

.. function:: camera.main

   | :sl:`display video captured live from an attached camera`
   | :sg:`camera.main() -> None`

   A simple live video player, it uses the first available camera it finds on
   the system.

   .. ## pygame.examples.camera.main ##

.. function:: playmus.main

   | :sl:`play an audio file`
   | :sg:`playmus.main(file_path) -> None`

   A simple music player with window and keyboard playback control. Playback can
   be paused and rewound to the beginning.

   .. ## pygame.examples.playmus.main ##

.. ## pygame.examples ##
