.. include:: common.txt

:mod:`pygame.gfxdraw`
=====================

.. module:: pygame.gfxdraw
   :synopsis: pygame module for drawing shapes

| :sl:`pygame module for drawing shapes`

**EXPERIMENTAL!**: This API may change or disappear in later pygame releases. If
you use this, your code may break with the next pygame release.

The pygame package does not import gfxdraw automatically when loaded, so it
must imported explicitly to be used.

::

    import pygame
    import pygame.gfxdraw

For all functions the arguments are strictly positional and integers are
accepted for coordinates and radii. The ``color`` argument can be one of the
following formats:

   - a :mod:`pygame.Color` object
   - an ``(RGB)`` triplet (tuple/list)
   - an ``(RGBA)`` quadruplet (tuple/list)

The functions :meth:`rectangle` and :meth:`box` will accept any ``(x, y, w, h)``
sequence for their ``rect`` argument, though :mod:`pygame.Rect` instances are
preferred.

To draw a filled antialiased shape, first use the antialiased (aa*) version
of the function, and then use the filled (filled_*) version.
For example:

::

   col = (255, 0, 0)
   surf.fill((255, 255, 255))
   pygame.gfxdraw.aacircle(surf, x, y, 30, col)
   pygame.gfxdraw.filled_circle(surf, x, y, 30, col)


.. note::
   For threading, each of the functions releases the GIL during the C part of
   the call.

.. note::
   See the :mod:`pygame.draw` module for alternative draw methods.
   The ``pygame.gfxdraw`` module differs from the :mod:`pygame.draw` module in
   the API it uses and the different draw functions available.
   ``pygame.gfxdraw`` wraps the primitives from the library called SDL_gfx,
   rather than using modified versions.

.. versionadded:: 1.9.0


.. function:: pixel

   | :sl:`draw a pixel`
   | :sg:`pixel(surface, x, y, color) -> None`

   Draws a single pixel, at position (x ,y), on the given surface.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the pixel
   :param int y: y coordinate of the pixel
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.pixel ##

.. function:: hline

   | :sl:`draw a horizontal line`
   | :sg:`hline(surface, x1, x2, y, color) -> None`

   Draws a straight horizontal line (``(x1, y)`` to ``(x2, y)``) on the given
   surface. There are no endcaps.

   :param Surface surface: surface to draw on
   :param int x1: x coordinate of one end of the line
   :param int x2: x coordinate of the other end of the line
   :param int y: y coordinate of the line
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.hline ##

.. function:: vline

   | :sl:`draw a vertical line`
   | :sg:`vline(surface, x, y1, y2, color) -> None`

   Draws a straight vertical line (``(x, y1)`` to ``(x, y2)``) on the given
   surface. There are no endcaps.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the line
   :param int y1: y coordinate of one end of the line
   :param int y2: y coordinate of the other end of the line
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.vline ##

.. function:: line

   | :sl:`draw a line`
   | :sg:`line(surface, x1, y1, x2, y2, color) -> None`

   Draws a straight line (``(x1, y1)`` to ``(x2, y2)``) on the given surface.
   There are no endcaps.

   :param Surface surface: surface to draw on
   :param int x1: x coordinate of one end of the line
   :param int y1: y coordinate of one end of the line
   :param int x2: x coordinate of the other end of the line
   :param int y2: y coordinate of the other end of the line
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.line ##

.. function:: rectangle

   | :sl:`draw a rectangle`
   | :sg:`rectangle(surface, rect, color) -> None`

   Draws an unfilled rectangle on the given surface. For a filled rectangle use
   :meth:`box`.

   :param Surface surface: surface to draw on
   :param Rect rect: rectangle to draw, position and dimensions
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. note::
      The ``rect.bottom`` and ``rect.right`` attributes of a :mod:`pygame.Rect`
      always lie one pixel outside of its actual border. Therefore, these
      values will not be included as part of the drawing.

   .. ## pygame.gfxdraw.rectangle ##

.. function:: box

   | :sl:`draw a filled rectangle`
   | :sg:`box(surface, rect, color) -> None`

   Draws a filled rectangle on the given surface. For an unfilled rectangle use
   :meth:`rectangle`.

   :param Surface surface: surface to draw on
   :param Rect rect: rectangle to draw, position and dimensions
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. note::
      The ``rect.bottom`` and ``rect.right`` attributes of a :mod:`pygame.Rect`
      always lie one pixel outside of its actual border. Therefore, these
      values will not be included as part of the drawing.

   .. note::
      The :func:`pygame.Surface.fill` method works just as well for drawing
      filled rectangles. In fact :func:`pygame.Surface.fill` can be hardware
      accelerated on some platforms with both software and hardware display
      modes.

   .. ## pygame.gfxdraw.box ##

.. function:: circle

   | :sl:`draw a circle`
   | :sg:`circle(surface, x, y, r, color) -> None`

   Draws an unfilled circle on the given surface. For a filled circle use
   :meth:`filled_circle`.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the circle
   :param int y: y coordinate of the center of the circle
   :param int r: radius of the circle
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.circle ##

.. function:: aacircle

   | :sl:`draw an antialiased circle`
   | :sg:`aacircle(surface, x, y, r, color) -> None`

   Draws an unfilled antialiased circle on the given surface.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the circle
   :param int y: y coordinate of the center of the circle
   :param int r: radius of the circle
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.aacircle ##

.. function:: filled_circle

   | :sl:`draw a filled circle`
   | :sg:`filled_circle(surface, x, y, r, color) -> None`

   Draws a filled circle on the given surface. For an unfilled circle use
   :meth:`circle`.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the circle
   :param int y: y coordinate of the center of the circle
   :param int r: radius of the circle
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.filled_circle ##

.. function:: ellipse

   | :sl:`draw an ellipse`
   | :sg:`ellipse(surface, x, y, rx, ry, color) -> None`

   Draws an unfilled ellipse on the given surface. For a filled ellipse use
   :meth:`filled_ellipse`.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the ellipse
   :param int y: y coordinate of the center of the ellipse
   :param int rx: horizontal radius of the ellipse
   :param int ry: vertical radius of the ellipse
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.ellipse ##

.. function:: aaellipse

   | :sl:`draw an antialiased ellipse`
   | :sg:`aaellipse(surface, x, y, rx, ry, color) -> None`

   Draws an unfilled antialiased ellipse on the given surface.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the ellipse
   :param int y: y coordinate of the center of the ellipse
   :param int rx: horizontal radius of the ellipse
   :param int ry: vertical radius of the ellipse
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.aaellipse ##

.. function:: filled_ellipse

   | :sl:`draw a filled ellipse`
   | :sg:`filled_ellipse(surface, x, y, rx, ry, color) -> None`

   Draws a filled ellipse on the given surface. For an unfilled ellipse use
   :meth:`ellipse`.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the ellipse
   :param int y: y coordinate of the center of the ellipse
   :param int rx: horizontal radius of the ellipse
   :param int ry: vertical radius of the ellipse
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.filled_ellipse ##

.. function:: arc

   | :sl:`draw an arc`
   | :sg:`arc(surface, x, y, r, start_angle, stop_angle, color) -> None`

   Draws an arc on the given surface. For an arc with its endpoints connected
   to its center use :meth:`pie`.

   The two angle arguments are given in degrees and indicate the start and stop
   positions of the arc. The arc is drawn in a clockwise direction from the
   ``start_angle`` to the ``stop_angle``. If ``start_angle == stop_angle``,
   nothing will be drawn

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the arc
   :param int y: y coordinate of the center of the arc
   :param int r: radius of the arc
   :param int start_angle: start angle in degrees
   :param int stop_angle: stop angle in degrees
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. note::
      This function uses *degrees* while the :func:`pygame.draw.arc` function
      uses *radians*.

   .. ## pygame.gfxdraw.arc ##

.. function:: pie

   | :sl:`draw a pie`
   | :sg:`pie(surface, x, y, r, start_angle, stop_angle, color) -> None`

   Draws an unfilled pie on the given surface. A pie is an :meth:`arc` with its
   endpoints connected to its center.

   The two angle arguments are given in degrees and indicate the start and stop
   positions of the pie. The pie is drawn in a clockwise direction from the
   ``start_angle`` to the ``stop_angle``. If ``start_angle == stop_angle``,
   a straight line will be drawn from the center position at the given angle,
   to a length of the radius.

   :param Surface surface: surface to draw on
   :param int x: x coordinate of the center of the pie
   :param int y: y coordinate of the center of the pie
   :param int r: radius of the pie
   :param int start_angle: start angle in degrees
   :param int stop_angle: stop angle in degrees
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.pie ##

.. function:: trigon

   | :sl:`draw a trigon/triangle`
   | :sg:`trigon(surface, x1, y1, x2, y2, x3, y3, color) -> None`

   Draws an unfilled trigon (triangle) on the given surface. For a filled
   trigon use :meth:`filled_trigon`.

   A trigon can also be drawn using :meth:`polygon` e.g.
   ``polygon(surface, ((x1, y1), (x2, y2), (x3, y3)), color)``

   :param Surface surface: surface to draw on
   :param int x1: x coordinate of the first corner of the trigon
   :param int y1: y coordinate of the first corner of the trigon
   :param int x2: x coordinate of the second corner of the trigon
   :param int y2: y coordinate of the second corner of the trigon
   :param int x3: x coordinate of the third corner of the trigon
   :param int y3: y coordinate of the third corner of the trigon
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.trigon ##

.. function:: aatrigon

   | :sl:`draw an antialiased trigon/triangle`
   | :sg:`aatrigon(surface, x1, y1, x2, y2, x3, y3, color) -> None`

   Draws an unfilled antialiased trigon (triangle) on the given surface.

   An aatrigon can also be drawn using :meth:`aapolygon` e.g.
   ``aapolygon(surface, ((x1, y1), (x2, y2), (x3, y3)), color)``

   :param Surface surface: surface to draw on
   :param int x1: x coordinate of the first corner of the trigon
   :param int y1: y coordinate of the first corner of the trigon
   :param int x2: x coordinate of the second corner of the trigon
   :param int y2: y coordinate of the second corner of the trigon
   :param int x3: x coordinate of the third corner of the trigon
   :param int y3: y coordinate of the third corner of the trigon
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.aatrigon ##

.. function:: filled_trigon

   | :sl:`draw a filled trigon/triangle`
   | :sg:`filled_trigon(surface, x1, y1, x2, y2, x3, y3, color) -> None`

   Draws a filled trigon (triangle) on the given surface. For an unfilled
   trigon use :meth:`trigon`.

   A filled_trigon can also be drawn using :meth:`filled_polygon` e.g.
   ``filled_polygon(surface, ((x1, y1), (x2, y2), (x3, y3)), color)``

   :param Surface surface: surface to draw on
   :param int x1: x coordinate of the first corner of the trigon
   :param int y1: y coordinate of the first corner of the trigon
   :param int x2: x coordinate of the second corner of the trigon
   :param int y2: y coordinate of the second corner of the trigon
   :param int x3: x coordinate of the third corner of the trigon
   :param int y3: y coordinate of the third corner of the trigon
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   .. ## pygame.gfxdraw.filled_trigon ##

.. function:: polygon

   | :sl:`draw a polygon`
   | :sg:`polygon(surface, points, color) -> None`

   Draws an unfilled polygon on the given surface. For a filled polygon use
   :meth:`filled_polygon`.

   The adjacent coordinates in the ``points`` argument, as well as the first
   and last points, will be connected by line segments.
   e.g. For the points ``[(x1, y1), (x2, y2), (x3, y3)]`` a line segment will
   be drawn from ``(x1, y1)`` to ``(x2, y2)``, from ``(x2, y2)`` to
   ``(x3, y3)``, and from ``(x3, y3)`` to ``(x1, y1)``.

   :param Surface surface: surface to draw on
   :param points: a sequence of 3 or more (x, y) coordinates, where each
      *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats (float values
      will be truncated)
   :type points: tuple(coordinate) or list(coordinate)
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   :raises ValueError: if ``len(points) < 3`` (must have at least 3 points)
   :raises IndexError: if ``len(coordinate) < 2`` (each coordinate must have
      at least 2 items)

   .. ## pygame.gfxdraw.polygon ##

.. function:: aapolygon

   | :sl:`draw an antialiased polygon`
   | :sg:`aapolygon(surface, points, color) -> None`

   Draws an unfilled antialiased polygon on the given surface.

   The adjacent coordinates in the ``points`` argument, as well as the first
   and last points, will be connected by line segments.
   e.g. For the points ``[(x1, y1), (x2, y2), (x3, y3)]`` a line segment will
   be drawn from ``(x1, y1)`` to ``(x2, y2)``, from ``(x2, y2)`` to
   ``(x3, y3)``, and from ``(x3, y3)`` to ``(x1, y1)``.

   :param Surface surface: surface to draw on
   :param points: a sequence of 3 or more (x, y) coordinates, where each
      *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats (float values
      will be truncated)
   :type points: tuple(coordinate) or list(coordinate)
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   :raises ValueError: if ``len(points) < 3`` (must have at least 3 points)
   :raises IndexError: if ``len(coordinate) < 2`` (each coordinate must have
      at least 2 items)

   .. ## pygame.gfxdraw.aapolygon ##

.. function:: filled_polygon

   | :sl:`draw a filled polygon`
   | :sg:`filled_polygon(surface, points, color) -> None`

   Draws a filled polygon on the given surface. For an unfilled polygon use
   :meth:`polygon`.

   The adjacent coordinates in the ``points`` argument, as well as the first
   and last points, will be connected by line segments.
   e.g. For the points ``[(x1, y1), (x2, y2), (x3, y3)]`` a line segment will
   be drawn from ``(x1, y1)`` to ``(x2, y2)``, from ``(x2, y2)`` to
   ``(x3, y3)``, and from ``(x3, y3)`` to ``(x1, y1)``.

   :param Surface surface: surface to draw on
   :param points: a sequence of 3 or more (x, y) coordinates, where each
      *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats (float values
      will be truncated)`
   :type points: tuple(coordinate) or list(coordinate)
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   :raises ValueError: if ``len(points) < 3`` (must have at least 3 points)
   :raises IndexError: if ``len(coordinate) < 2`` (each coordinate must have
      at least 2 items)

   .. ## pygame.gfxdraw.filled_polygon ##

.. function:: textured_polygon

   | :sl:`draw a textured polygon`
   | :sg:`textured_polygon(surface, points, texture, tx, ty) -> None`

   Draws a textured polygon on the given surface. For better performance, the
   surface and the texture should have the same format.

   A per-pixel alpha texture blit to a per-pixel alpha surface will differ from
   a :func:`pygame.Surface.blit` blit. Also, a per-pixel alpha texture cannot be
   used with an 8-bit per pixel destination.

   The adjacent coordinates in the ``points`` argument, as well as the first
   and last points, will be connected by line segments.
   e.g. For the points ``[(x1, y1), (x2, y2), (x3, y3)]`` a line segment will
   be drawn from ``(x1, y1)`` to ``(x2, y2)``, from ``(x2, y2)`` to
   ``(x3, y3)``, and from ``(x3, y3)`` to ``(x1, y1)``.

   :param Surface surface: surface to draw on
   :param points: a sequence of 3 or more (x, y) coordinates, where each
      *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats (float values
      will be truncated)
   :type points: tuple(coordinate) or list(coordinate)
   :param Surface texture: texture to draw on the polygon
   :param int tx: x offset of the texture
   :param int ty: y offset of the texture

   :returns: ``None``
   :rtype: NoneType

   :raises ValueError: if ``len(points) < 3`` (must have at least 3 points)
   :raises IndexError: if ``len(coordinate) < 2`` (each coordinate must have
      at least 2 items)

   .. ## pygame.gfxdraw.textured_polygon ##

.. function:: bezier

   | :sl:`draw a Bezier curve`
   | :sg:`bezier(surface, points, steps, color) -> None`

   Draws a Bézier curve on the given surface.

   :param Surface surface: surface to draw on
   :param points: a sequence of 3 or more (x, y) coordinates used to form a
      curve, where each *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats (float values
      will be truncated)
   :type points: tuple(coordinate) or list(coordinate)
   :param int steps: number of steps for the interpolation, the minimum is 2
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or tuple(int, int, int, [int])

   :returns: ``None``
   :rtype: NoneType

   :raises ValueError: if ``steps < 2``
   :raises ValueError: if ``len(points) < 3`` (must have at least 3 points)
   :raises IndexError: if ``len(coordinate) < 2`` (each coordinate must have
      at least 2 items)

   .. ## pygame.gfxdraw.bezier ##

.. ## pygame.gfxdraw ##
