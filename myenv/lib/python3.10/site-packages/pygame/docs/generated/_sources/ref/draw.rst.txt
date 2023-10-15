.. include:: common.txt

:mod:`pygame.draw`
==================

.. module:: pygame.draw
   :synopsis: pygame module for drawing shapes

| :sl:`pygame module for drawing shapes`

Draw several simple shapes to a surface. These functions will work for
rendering to any format of surface.

Most of the functions take a width argument to represent the size of stroke
(thickness) around the edge of the shape. If a width of 0 is passed the shape
will be filled (solid).

All the drawing functions respect the clip area for the surface and will be
constrained to that area. The functions return a rectangle representing the
bounding area of changed pixels. This bounding rectangle is the 'minimum'
bounding box that encloses the affected area.

All the drawing functions accept a color argument that can be one of the
following formats:

   - a :mod:`pygame.Color` object
   - an ``(RGB)`` triplet (tuple/list)
   - an ``(RGBA)`` quadruplet (tuple/list)
   - an integer value that has been mapped to the surface's pixel format
     (see :func:`pygame.Surface.map_rgb` and :func:`pygame.Surface.unmap_rgb`)

A color's alpha value will be written directly into the surface (if the
surface contains pixel alphas), but the draw function will not draw
transparently.

These functions temporarily lock the surface they are operating on. Many
sequential drawing calls can be sped up by locking and unlocking the surface
object around the draw calls (see :func:`pygame.Surface.lock` and
:func:`pygame.Surface.unlock`).

.. note ::
   See the :mod:`pygame.gfxdraw` module for alternative draw methods.


.. function:: rect

   | :sl:`draw a rectangle`
   | :sg:`rect(surface, color, rect) -> Rect`
   | :sg:`rect(surface, color, rect, width=0, border_radius=0, border_top_left_radius=-1, border_top_right_radius=-1, border_bottom_left_radius=-1, border_bottom_right_radius=-1) -> Rect`

   Draws a rectangle on the given surface.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param Rect rect: rectangle to draw, position and dimensions
   :param int width: (optional) used for line thickness or to indicate that
      the rectangle is to be filled (not to be confused with the width value
      of the ``rect`` parameter)

         | if ``width == 0``, (default) fill the rectangle
         | if ``width > 0``, used for line thickness
         | if ``width < 0``, nothing will be drawn
         |
      
      .. versionchanged:: 2.1.1 
          Drawing rects with width now draws the width correctly inside the 
          rect's area, rather than using an internal call to draw.lines(), 
          which had half the width spill outside the rect area.

   :param int border_radius: (optional) used for drawing rectangle with rounded corners.
      The supported range is [0, min(height, width) / 2], with 0 representing a rectangle
      without rounded corners.
   :param int border_top_left_radius: (optional) used for setting the value of top left
      border. If you don't set this value, it will use the border_radius value.
   :param int border_top_right_radius: (optional) used for setting the value of top right
      border. If you don't set this value, it will use the border_radius value.
   :param int border_bottom_left_radius: (optional) used for setting the value of bottom left
      border. If you don't set this value, it will use the border_radius value.
   :param int border_bottom_right_radius: (optional) used for setting the value of bottom right
      border. If you don't set this value, it will use the border_radius value.

         | if ``border_radius < 1`` it will draw rectangle without rounded corners
         | if any of border radii has the value ``< 0`` it will use value of the border_radius
         | If sum of radii on the same side of the rectangle is greater than the rect size the radii
         | will get scaled

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the position of the given ``rect``
      parameter and its width and height will be 0
   :rtype: Rect

   .. note::
      The :func:`pygame.Surface.fill()` method works just as well for drawing
      filled rectangles and can be hardware accelerated on some platforms.

   .. versionchanged:: 2.0.0 Added support for keyword arguments.
   .. versionchanged:: 2.0.0.dev8 Added support for border radius.

   .. ## pygame.draw.rect ##

.. function:: polygon

   | :sl:`draw a polygon`
   | :sg:`polygon(surface, color, points) -> Rect`
   | :sg:`polygon(surface, color, points, width=0) -> Rect`

   Draws a polygon on the given surface.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param points: a sequence of 3 or more (x, y) coordinates that make up the
      vertices of the polygon, each *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats,
      e.g. ``[(x1, y1), (x2, y2), (x3, y3)]``
   :type points: tuple(coordinate) or list(coordinate)
   :param int width: (optional) used for line thickness or to indicate that
      the polygon is to be filled

         | if width == 0, (default) fill the polygon
         | if width > 0, used for line thickness
         | if width < 0, nothing will be drawn
         |

         .. note::
            When using ``width`` values ``> 1``, the edge lines will grow
            outside the original boundary of the polygon. For more details on
            how the thickness for edge lines grow, refer to the ``width`` notes
            of the :func:`pygame.draw.line` function.

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the position of the first point in the
      ``points`` parameter (float values will be truncated) and its width and
      height will be 0
   :rtype: Rect

   :raises ValueError: if ``len(points) < 3`` (must have at least 3 points)
   :raises TypeError: if ``points`` is not a sequence or ``points`` does not
      contain number pairs

   .. note::
       For an aapolygon, use :func:`aalines()` with ``closed=True``.

   .. versionchanged:: 2.0.0 Added support for keyword arguments.

   .. ## pygame.draw.polygon ##

.. function:: circle

   | :sl:`draw a circle`
   | :sg:`circle(surface, color, center, radius) -> Rect`
   | :sg:`circle(surface, color, center, radius, width=0, draw_top_right=None, draw_top_left=None, draw_bottom_left=None, draw_bottom_right=None) -> Rect`

   Draws a circle on the given surface.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param center: center point of the circle as a sequence of 2 ints/floats,
      e.g. ``(x, y)``
   :type center: tuple(int or float, int or float) or
      list(int or float, int or float) or Vector2(int or float, int or float)
   :param radius: radius of the circle, measured from the ``center`` parameter,
      nothing will be drawn if the ``radius`` is less than 1
   :type radius: int or float
   :param int width: (optional) used for line thickness or to indicate that
      the circle is to be filled

         | if ``width == 0``, (default) fill the circle
         | if ``width > 0``, used for line thickness
         | if ``width < 0``, nothing will be drawn
         |

         .. note::
            When using ``width`` values ``> 1``, the edge lines will only grow
            inward.
   :param bool draw_top_right: (optional) if this is set to True then the top right corner
      of the circle will be drawn
   :param bool draw_top_left: (optional) if this is set to True then the top left corner
      of the circle will be drawn
   :param bool draw_bottom_left: (optional) if this is set to True then the bottom left corner
      of the circle will be drawn
   :param bool draw_bottom_right: (optional) if this is set to True then the bottom right corner
      of the circle will be drawn

         | if any of the draw_circle_part is True then it will draw all circle parts that have the True
         | value, otherwise it will draw the entire circle.

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the ``center`` parameter value (float
      values will be truncated) and its width and height will be 0
   :rtype: Rect

   :raises TypeError: if ``center`` is not a sequence of two numbers
   :raises TypeError: if ``radius`` is not a number

   .. versionchanged:: 2.0.0 Added support for keyword arguments.
      Nothing is drawn when the radius is 0 (a pixel at the ``center`` coordinates
      used to be drawn when the radius equaled 0).
      Floats, and Vector2 are accepted for the ``center`` param.
      The drawing algorithm was improved to look more like a circle.
   .. versionchanged:: 2.0.0.dev8 Added support for drawing circle quadrants.

   .. ## pygame.draw.circle ##

.. function:: ellipse

   | :sl:`draw an ellipse`
   | :sg:`ellipse(surface, color, rect) -> Rect`
   | :sg:`ellipse(surface, color, rect, width=0) -> Rect`

   Draws an ellipse on the given surface.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param Rect rect: rectangle to indicate the position and dimensions of the
      ellipse, the ellipse will be centered inside the rectangle and bounded
      by it
   :param int width: (optional) used for line thickness or to indicate that
      the ellipse is to be filled (not to be confused with the width value
      of the ``rect`` parameter)

         | if ``width == 0``, (default) fill the ellipse
         | if ``width > 0``, used for line thickness
         | if ``width < 0``, nothing will be drawn
         |

         .. note::
            When using ``width`` values ``> 1``, the edge lines will only grow
            inward from the original boundary of the ``rect`` parameter.

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the position of the given ``rect``
      parameter and its width and height will be 0
   :rtype: Rect

   .. versionchanged:: 2.0.0 Added support for keyword arguments.

   .. ## pygame.draw.ellipse ##

.. function:: arc

   | :sl:`draw an elliptical arc`
   | :sg:`arc(surface, color, rect, start_angle, stop_angle) -> Rect`
   | :sg:`arc(surface, color, rect, start_angle, stop_angle, width=1) -> Rect`

   Draws an elliptical arc on the given surface.

   The two angle arguments are given in radians and indicate the start and stop
   positions of the arc. The arc is drawn in a counterclockwise direction from
   the ``start_angle`` to the ``stop_angle``.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param Rect rect: rectangle to indicate the position and dimensions of the
      ellipse which the arc will be based on, the ellipse will be centered
      inside the rectangle
   :param float start_angle: start angle of the arc in radians
   :param float stop_angle: stop angle of the arc in
      radians

         | if ``start_angle < stop_angle``, the arc is drawn in a
            counterclockwise direction from the ``start_angle`` to the
            ``stop_angle``
         | if ``start_angle > stop_angle``, tau (tau == 2 * pi) will be added
            to the ``stop_angle``, if the resulting stop angle value is greater
            than the ``start_angle`` the above ``start_angle < stop_angle`` case
            applies, otherwise nothing will be drawn
         | if ``start_angle == stop_angle``, nothing will be drawn
         |

   :param int width: (optional) used for line thickness (not to be confused
      with the width value of the ``rect`` parameter)

         | if ``width == 0``, nothing will be drawn
         | if ``width > 0``, (default is 1) used for line thickness
         | if ``width < 0``, same as ``width == 0``

         .. note::
            When using ``width`` values ``> 1``, the edge lines will only grow
            inward from the original boundary of the ``rect`` parameter.

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the position of the given ``rect``
      parameter and its width and height will be 0
   :rtype: Rect

   .. versionchanged:: 2.0.0 Added support for keyword arguments.

   .. ## pygame.draw.arc ##

.. function:: line

   | :sl:`draw a straight line`
   | :sg:`line(surface, color, start_pos, end_pos) -> Rect`
   | :sg:`line(surface, color, start_pos, end_pos, width=1) -> Rect`

   Draws a straight line on the given surface. There are no endcaps. For thick
   lines the ends are squared off.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param start_pos: start position of the line, (x, y)
   :type start_pos: tuple(int or float, int or float) or
      list(int or float, int or float) or Vector2(int or float, int or float)
   :param end_pos: end position of the line, (x, y)
   :type end_pos: tuple(int or float, int or float) or
      list(int or float, int or float) or Vector2(int or float, int or float)
   :param int width: (optional) used for line thickness

         | if width >= 1, used for line thickness (default is 1)
         | if width < 1, nothing will be drawn
         |

         .. note::
            When using ``width`` values ``> 1``, lines will grow as follows.

            For odd ``width`` values, the thickness of each line grows with the
            original line being in the center.

            For even ``width`` values, the thickness of each line grows with the
            original line being offset from the center (as there is no exact
            center line drawn). As a result, lines with a slope < 1
            (horizontal-ish) will have 1 more pixel of thickness below the
            original line (in the y direction). Lines with a slope >= 1
            (vertical-ish) will have 1 more pixel of thickness to the right of
            the original line (in the x direction).

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the ``start_pos`` parameter value (float
      values will be truncated) and its width and height will be 0
   :rtype: Rect

   :raises TypeError: if ``start_pos`` or ``end_pos`` is not a sequence of
      two numbers

   .. versionchanged:: 2.0.0 Added support for keyword arguments.

   .. ## pygame.draw.line ##

.. function:: lines

   | :sl:`draw multiple contiguous straight line segments`
   | :sg:`lines(surface, color, closed, points) -> Rect`
   | :sg:`lines(surface, color, closed, points, width=1) -> Rect`

   Draws a sequence of contiguous straight lines on the given surface. There are
   no endcaps or miter joints. For thick lines the ends are squared off.
   Drawing thick lines with sharp corners can have undesired looking results.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param bool closed: if ``True`` an additional line segment is drawn between
      the first and last points in the ``points`` sequence
   :param points: a sequence of 2 or more (x, y) coordinates, where each
      *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats and adjacent
      coordinates will be connected by a line segment, e.g. for the
      points ``[(x1, y1), (x2, y2), (x3, y3)]`` a line segment will be drawn
      from ``(x1, y1)`` to ``(x2, y2)`` and from ``(x2, y2)`` to ``(x3, y3)``,
      additionally if the ``closed`` parameter is ``True`` another line segment
      will be drawn from ``(x3, y3)`` to ``(x1, y1)``
   :type points: tuple(coordinate) or list(coordinate)
   :param int width: (optional) used for line thickness

         | if width >= 1, used for line thickness (default is 1)
         | if width < 1, nothing will be drawn
         |

         .. note::
            When using ``width`` values ``> 1`` refer to the ``width`` notes
            of :func:`line` for details on how thick lines grow.

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the position of the first point in the
      ``points`` parameter (float values will be truncated) and its width and
      height will be 0
   :rtype: Rect

   :raises ValueError: if ``len(points) < 2`` (must have at least 2 points)
   :raises TypeError: if ``points`` is not a sequence or ``points`` does not
      contain number pairs

   .. versionchanged:: 2.0.0 Added support for keyword arguments.

   .. ## pygame.draw.lines ##

.. function:: aaline

   | :sl:`draw a straight antialiased line`
   | :sg:`aaline(surface, color, start_pos, end_pos) -> Rect`
   | :sg:`aaline(surface, color, start_pos, end_pos, blend=1) -> Rect`

   Draws a straight antialiased line on the given surface.

   The line has a thickness of one pixel and the endpoints have a height and
   width of one pixel each.

   The way a line and its endpoints are drawn:
      If both endpoints are equal, only a single pixel is drawn (after
      rounding floats to nearest integer).

      Otherwise if the line is not steep (i.e. if the length along the x-axis
      is greater than the height along the y-axis):

         For each endpoint:

            If ``x``, the endpoint's x-coordinate, is a whole number find
            which pixels would be covered by it and draw them.

            Otherwise:

               Calculate the position of the nearest point with a whole number
               for its x-coordinate, when extending the line past the
               endpoint.

               Find which pixels would be covered and how much by that point.

               If the endpoint is the left one, multiply the coverage by (1 -
               the decimal part of ``x``).

               Otherwise multiply the coverage by the decimal part of ``x``.

               Then draw those pixels.

               *e.g.:*
                  | The left endpoint of the line ``((1, 1.3), (5, 3))`` would
                    cover 70% of the pixel ``(1, 1)`` and 30% of the pixel
                    ``(1, 2)`` while the right one would cover 100% of the
                    pixel ``(5, 3)``.
                  | The left endpoint of the line ``((1.2, 1.4), (4.6, 3.1))``
                    would cover 56% *(i.e. 0.8 * 70%)* of the pixel ``(1, 1)``
                    and 24% *(i.e. 0.8 * 30%)* of the pixel ``(1, 2)`` while
                    the right one would cover 42% *(i.e. 0.6 * 70%)* of the
                    pixel ``(5, 3)`` and 18% *(i.e. 0.6 * 30%)* of the pixel
                    ``(5, 4)`` while the right

         Then for each point between the endpoints, along the line, whose
         x-coordinate is a whole number:

            Find which pixels would be covered and how much by that point and
            draw them.

            *e.g.:*
               | The points along the line ``((1, 1), (4, 2.5))`` would be
                 ``(2, 1.5)`` and ``(3, 2)`` and would cover 50% of the pixel
                 ``(2, 1)``, 50% of the pixel ``(2, 2)`` and 100% of the pixel
                 ``(3, 2)``.
               | The points along the line ``((1.2, 1.4), (4.6, 3.1))`` would
                 be ``(2, 1.8)`` (covering 20% of the pixel ``(2, 1)`` and 80%
                 of the pixel ``(2, 2)``), ``(3, 2.3)`` (covering 70% of the
                 pixel ``(3, 2)`` and 30% of the pixel ``(3, 3)``) and ``(4,
                 2.8)`` (covering 20% of the pixel ``(2, 1)`` and 80% of the
                 pixel ``(2, 2)``)

      Otherwise do the same for steep lines as for non-steep lines except
      along the y-axis instead of the x-axis (using ``y`` instead of ``x``,
      top instead of left and bottom instead of right).

   .. note::
      Regarding float values for coordinates, a point with coordinate
      consisting of two whole numbers is considered being right in the center
      of said pixel (and having a height and width of 1 pixel would therefore
      completely cover it), while a point with coordinate where one (or both)
      of the numbers have non-zero decimal parts would be partially covering
      two (or four if both numbers have decimal parts) adjacent pixels, *e.g.*
      the point ``(1.4, 2)`` covers 60% of the pixel ``(1, 2)`` and 40% of the
      pixel ``(2,2)``.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param start_pos: start position of the line, (x, y)
   :type start_pos: tuple(int or float, int or float) or
      list(int or float, int or float) or Vector2(int or float, int or float)
   :param end_pos: end position of the line, (x, y)
   :type end_pos: tuple(int or float, int or float) or
      list(int or float, int or float) or Vector2(int or float, int or float)
   :param int blend: (optional) (deprecated) if non-zero (default) the line will be blended
      with the surface's existing pixel shades, otherwise it will overwrite them

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the ``start_pos`` parameter value (float
      values will be truncated) and its width and height will be 0
   :rtype: Rect

   :raises TypeError: if ``start_pos`` or ``end_pos`` is not a sequence of
      two numbers

   .. versionchanged:: 2.0.0 Added support for keyword arguments.

   .. ## pygame.draw.aaline ##

.. function:: aalines

   | :sl:`draw multiple contiguous straight antialiased line segments`
   | :sg:`aalines(surface, color, closed, points) -> Rect`
   | :sg:`aalines(surface, color, closed, points, blend=1) -> Rect`

   Draws a sequence of contiguous straight antialiased lines on the given
   surface.

   :param Surface surface: surface to draw on
   :param color: color to draw with, the alpha value is optional if using a
      tuple ``(RGB[A])``
   :type color: Color or int or tuple(int, int, int, [int])
   :param bool closed: if ``True`` an additional line segment is drawn between
      the first and last points in the ``points`` sequence
   :param points: a sequence of 2 or more (x, y) coordinates, where each
      *coordinate* in the sequence must be a
      tuple/list/:class:`pygame.math.Vector2` of 2 ints/floats and adjacent
      coordinates will be connected by a line segment, e.g. for the
      points ``[(x1, y1), (x2, y2), (x3, y3)]`` a line segment will be drawn
      from ``(x1, y1)`` to ``(x2, y2)`` and from ``(x2, y2)`` to ``(x3, y3)``,
      additionally if the ``closed`` parameter is ``True`` another line segment
      will be drawn from ``(x3, y3)`` to ``(x1, y1)``
   :type points: tuple(coordinate) or list(coordinate)
   :param int blend: (optional) (deprecated) if non-zero (default) each line will be blended
      with the surface's existing pixel shades, otherwise the pixels will be
      overwritten

   :returns: a rect bounding the changed pixels, if nothing is drawn the
      bounding rect's position will be the position of the first point in the
      ``points`` parameter (float values will be truncated) and its width and
      height will be 0
   :rtype: Rect

   :raises ValueError: if ``len(points) < 2`` (must have at least 2 points)
   :raises TypeError: if ``points`` is not a sequence or ``points`` does not
      contain number pairs

   .. versionchanged:: 2.0.0 Added support for keyword arguments.

   .. ## pygame.draw.aalines ##

.. ## pygame.draw ##

.. figure:: code_examples/draw_module_example.png
   :alt: draw module example

   Example code for draw module.

.. literalinclude:: code_examples/draw_module_example.py

