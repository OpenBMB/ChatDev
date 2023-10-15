.. include:: common.txt

:mod:`pygame.Rect`
==================

.. currentmodule:: pygame

.. class:: Rect

   | :sl:`pygame object for storing rectangular coordinates`
   | :sg:`Rect(left, top, width, height) -> Rect`
   | :sg:`Rect((left, top), (width, height)) -> Rect`
   | :sg:`Rect(object) -> Rect`

   Pygame uses Rect objects to store and manipulate rectangular areas. A Rect
   can be created from a combination of left, top, width, and height values.
   Rects can also be created from Python objects that are already a Rect or
   have an attribute named "rect".

   Any Pygame function that requires a Rect argument also accepts any of these
   values to construct a Rect. This makes it easier to create Rects on the fly
   as arguments for functions.

   The Rect functions that change the position or size of a Rect return a new
   copy of the Rect with the affected changes. The original Rect is not
   modified. Some methods have an alternate "in-place" version that returns
   None but affects the original Rect. These "in-place" methods are denoted
   with the "ip" suffix.

   The Rect object has several virtual attributes which can be used to move and
   align the Rect:

   ::

       x,y
       top, left, bottom, right
       topleft, bottomleft, topright, bottomright
       midtop, midleft, midbottom, midright
       center, centerx, centery
       size, width, height
       w,h

   All of these attributes can be assigned to:

   ::

       rect1.right = 10
       rect2.center = (20,30)

   Assigning to size, width or height changes the dimensions of the rectangle;
   all other assignments move the rectangle without resizing it. Notice that
   some attributes are integers and others are pairs of integers.

   If a Rect has a nonzero width or height, it will return ``True`` for a
   nonzero test. Some methods return a Rect with 0 size to represent an invalid
   rectangle. A Rect with a 0 size will not collide when using collision
   detection methods (e.g. :meth:`collidepoint`, :meth:`colliderect`, etc.).

   The coordinates for Rect objects are all integers. The size values can be
   programmed to have negative values, but these are considered illegal Rects
   for most operations.

   There are several collision tests between other rectangles. Most python
   containers can be searched for collisions against a single Rect.

   The area covered by a Rect does not include the right- and bottom-most edge
   of pixels. If one Rect's bottom border is another Rect's top border (i.e.,
   rect1.bottom=rect2.top), the two meet exactly on the screen but do not
   overlap, and ``rect1.colliderect(rect2)`` returns false.

   The Rect object is also iterable:

   ::

      r = Rect(0, 1, 2, 3)
      x, y, w, h = r

   .. versionadded:: 1.9.2
      The Rect class can be subclassed. Methods such as ``copy()`` and ``move()``
      will recognize this and return instances of the subclass.
      However, the subclass's ``__init__()`` method is not called,
      and ``__new__()`` is assumed to take no arguments. So these methods should be
      overridden if any extra attributes need to be copied.

   .. method:: copy

      | :sl:`copy the rectangle`
      | :sg:`copy() -> Rect`

      Returns a new rectangle having the same position and size as the original.

      New in pygame 1.9

      .. ## Rect.copy ##

   .. method:: move

      | :sl:`moves the rectangle`
      | :sg:`move(x, y) -> Rect`

      Returns a new rectangle that is moved by the given offset. The x and y
      arguments can be any integer value, positive or negative.

      .. ## Rect.move ##

   .. method:: move_ip

      | :sl:`moves the rectangle, in place`
      | :sg:`move_ip(x, y) -> None`

      Same as the ``Rect.move()`` method, but operates in place.

      .. ## Rect.move_ip ##

   .. method:: inflate

      | :sl:`grow or shrink the rectangle size`
      | :sg:`inflate(x, y) -> Rect`

      Returns a new rectangle with the size changed by the given offset. The
      rectangle remains centered around its current center. Negative values
      will shrink the rectangle. Note, uses integers, if the offset given is
      too small(< 2 > -2), center will be off.

      .. ## Rect.inflate ##

   .. method:: inflate_ip

      | :sl:`grow or shrink the rectangle size, in place`
      | :sg:`inflate_ip(x, y) -> None`

      Same as the ``Rect.inflate()`` method, but operates in place.

      .. ## Rect.inflate_ip ##

   .. method:: scale_by

      | :sl:`scale the rectangle by given a multiplier`
      | :sg:`scale_by(scalar) -> Rect`
      | :sg:`scale_by(scalex, scaley) -> Rect`

      Returns a new rectangle with the size scaled by the given multipliers.
      The rectangle remains centered around its current center. A single 
      scalar or separate width and height scalars are allowed. Values above
      one will increase the size of the rectangle, whereas values between
      zero and one will decrease the size of the rectangle.

      .. versionchanged:: 2.5.0 Added support for keyword arguments.

      .. ## Rect.scale_by ##

   .. method:: scale_by_ip

      | :sl:`grow or shrink the rectangle size, in place`
      | :sg:`scale_by_ip(scalar) -> None`
      | :sg:`scale_by_ip(scalex, scaley) -> None`

      Same as the ``Rect.scale_by()`` method, but operates in place.

      .. versionchanged:: 2.5.0 Added support for keyword arguments.

      .. ## Rect.scale_by_ip ##

   .. method:: update

      | :sl:`sets the position and size of the rectangle`
      | :sg:`update(left, top, width, height) -> None`
      | :sg:`update((left, top), (width, height)) -> None`
      | :sg:`update(object) -> None`

      Sets the position and size of the rectangle, in place. See
      parameters for :meth:`pygame.Rect` for the parameters of this function.

      .. versionadded:: 2.0.1

      .. ## Rect.update ##

   .. method:: clamp

      | :sl:`moves the rectangle inside another`
      | :sg:`clamp(Rect) -> Rect`

      Returns a new rectangle that is moved to be completely inside the
      argument Rect. If the rectangle is too large to fit inside, it is
      centered inside the argument Rect, but its size is not changed.

      .. ## Rect.clamp ##

   .. method:: clamp_ip

      | :sl:`moves the rectangle inside another, in place`
      | :sg:`clamp_ip(Rect) -> None`

      Same as the ``Rect.clamp()`` method, but operates in place.

      .. ## Rect.clamp_ip ##

   .. method:: clip

      | :sl:`crops a rectangle inside another`
      | :sg:`clip(Rect) -> Rect`

      Returns a new rectangle that is cropped to be completely inside the
      argument Rect. If the two rectangles do not overlap to begin with, a Rect
      with 0 size is returned.

      .. ## Rect.clip ##

   .. method:: clipline

      | :sl:`crops a line inside a rectangle`
      | :sg:`clipline(x1, y1, x2, y2) -> ((cx1, cy1), (cx2, cy2))`
      | :sg:`clipline(x1, y1, x2, y2) -> ()`
      | :sg:`clipline((x1, y1), (x2, y2)) -> ((cx1, cy1), (cx2, cy2))`
      | :sg:`clipline((x1, y1), (x2, y2)) -> ()`
      | :sg:`clipline((x1, y1, x2, y2)) -> ((cx1, cy1), (cx2, cy2))`
      | :sg:`clipline((x1, y1, x2, y2)) -> ()`
      | :sg:`clipline(((x1, y1), (x2, y2))) -> ((cx1, cy1), (cx2, cy2))`
      | :sg:`clipline(((x1, y1), (x2, y2))) -> ()`

      Returns the coordinates of a line that is cropped to be completely inside
      the rectangle. If the line does not overlap the rectangle, then an empty
      tuple is returned.

      The line to crop can be any of the following formats (floats can be used
      in place of ints, but they will be truncated):

         - four ints
         - 2 lists/tuples/Vector2s of 2 ints
         - a list/tuple of four ints
         - a list/tuple of 2 lists/tuples/Vector2s of 2 ints

      :returns: a tuple with the coordinates of the given line cropped to be
         completely inside the rectangle is returned, if the given line does
         not overlap the rectangle, an empty tuple is returned
      :rtype: tuple(tuple(int, int), tuple(int, int)) or ()

      :raises TypeError: if the line coordinates are not given as one of the
         above described line formats

      .. note ::
         This method can be used for collision detection between a rect and a
         line. See example code below.

      .. note ::
         The ``rect.bottom`` and ``rect.right`` attributes of a
         :mod:`pygame.Rect` always lie one pixel outside of its actual border.

      ::

         # Example using clipline().
         clipped_line = rect.clipline(line)

         if clipped_line:
             # If clipped_line is not an empty tuple then the line
             # collides/overlaps with the rect. The returned value contains
             # the endpoints of the clipped line.
             start, end = clipped_line
             x1, y1 = start
             x2, y2 = end
         else:
             print("No clipping. The line is fully outside the rect.")

      .. versionchanged:: 2.5.0 Added support for keyword arguments.

      .. versionadded:: 2.0.0

      .. ## Rect.clipline ##

   .. method:: union

      | :sl:`joins two rectangles into one`
      | :sg:`union(Rect) -> Rect`

      Returns a new rectangle that completely covers the area of the two
      provided rectangles. There may be area inside the new Rect that is not
      covered by the originals.

      .. ## Rect.union ##

   .. method:: union_ip

      | :sl:`joins two rectangles into one, in place`
      | :sg:`union_ip(Rect) -> None`

      Same as the ``Rect.union()`` method, but operates in place.

      .. ## Rect.union_ip ##

   .. method:: unionall

      | :sl:`the union of many rectangles`
      | :sg:`unionall(Rect_sequence) -> Rect`

      Returns the union of one rectangle with a sequence of many rectangles.

      .. versionchanged:: 2.5.0 Added support for keyword arguments.

      .. ## Rect.unionall ##

   .. method:: unionall_ip

      | :sl:`the union of many rectangles, in place`
      | :sg:`unionall_ip(Rect_sequence) -> None`

      The same as the ``Rect.unionall()`` method, but operates in place.

      .. versionchanged:: 2.5.0 Added support for keyword arguments.

      .. ## Rect.unionall_ip ##

   .. method:: fit

      | :sl:`resize and move a rectangle with aspect ratio`
      | :sg:`fit(Rect) -> Rect`

      Returns a new rectangle that is moved and resized to fit another. The
      aspect ratio of the original Rect is preserved, so the new rectangle may
      be smaller than the target in either width or height.

      .. ## Rect.fit ##

   .. method:: normalize

      | :sl:`correct negative sizes`
      | :sg:`normalize() -> None`

      This will flip the width or height of a rectangle if it has a negative
      size. The rectangle will remain in the same place, with only the sides
      swapped.

      .. ## Rect.normalize ##

   .. method:: contains

      | :sl:`test if one rectangle is inside another`
      | :sg:`contains(Rect) -> bool`

      Returns true when the argument is completely inside the Rect.

      .. ## Rect.contains ##

   .. method:: collidepoint

      | :sl:`test if a point is inside a rectangle`
      | :sg:`collidepoint(x, y) -> bool`
      | :sg:`collidepoint((x,y)) -> bool`

      Returns true if the given point is inside the rectangle. A point along
      the right or bottom edge is not considered to be inside the rectangle.

      .. note ::
         For collision detection between a rect and a line the :meth:`clipline`
         method can be used.

      .. ## Rect.collidepoint ##

   .. method:: colliderect

      | :sl:`test if two rectangles overlap`
      | :sg:`colliderect(Rect) -> bool`

      Returns true if any portion of either rectangle overlap (except the
      top+bottom or left+right edges).

      .. note ::
         For collision detection between a rect and a line the :meth:`clipline`
         method can be used.

      .. ## Rect.colliderect ##

   .. method:: collidelist

      | :sl:`test if one rectangle in a list intersects`
      | :sg:`collidelist(list) -> index`

      Test whether the rectangle collides with any in a sequence of rectangles.
      The index of the first collision found is returned. If no collisions are
      found an index of -1 is returned.

      .. versionchanged:: 2.5.0 Added support for keyword arguments.

      .. ## Rect.collidelist ##

   .. method:: collidelistall

      | :sl:`test if all rectangles in a list intersect`
      | :sg:`collidelistall(list) -> indices`

      Returns a list of all the indices that contain rectangles that collide
      with the Rect. If no intersecting rectangles are found, an empty list is
      returned.

      Not only Rects are valid arguments, but these are all valid calls:

      .. code-block:: python
    
          Rect = pygame.Rect
          r = Rect(0, 0, 10, 10)
          
          list_of_rects = [Rect(1, 1, 1, 1), Rect(2, 2, 2, 2)]
          indices0 = r.collidelistall(list_of_rects)
          
          list_of_lists = [[1, 1, 1, 1], [2, 2, 2, 2]]
          indices1 = r.collidelistall(list_of_lists)
          
          list_of_tuples = [(1, 1, 1, 1), (2, 2, 2, 2)]
          indices2 = r.collidelistall(list_of_tuples)
          
          list_of_double_tuples = [((1, 1), (1, 1)), ((2, 2), (2, 2))]
          indices3 = r.collidelistall(list_of_double_tuples)
          
          class ObjectWithRectAttribute(object):
              def __init__(self, r):
                  self.rect = r
          
          list_of_object_with_rect_attribute = [
              ObjectWithRectAttribute(Rect(1, 1, 1, 1)),
              ObjectWithRectAttribute(Rect(2, 2, 2, 2)),
          ]
          indices4 = r.collidelistall(list_of_object_with_rect_attribute)
          
          class ObjectWithCallableRectAttribute(object):
              def __init__(self, r):
                  self._rect = r
          
              def rect(self):
                  return self._rect
          
          list_of_object_with_callable_rect = [
              ObjectWithCallableRectAttribute(Rect(1, 1, 1, 1)),
              ObjectWithCallableRectAttribute(Rect(2, 2, 2, 2)),
          ]
          indices5 = r.collidelistall(list_of_object_with_callable_rect)

      .. versionchanged:: 2.5.0 Added support for keyword arguments.

      .. ## Rect.collidelistall ##

   .. method:: collideobjects

      | :sl:`test if any object in a list intersects`
      | :sg:`collideobjects(rect_list) -> object`
      | :sg:`collideobjects(obj_list, key=func) -> object`

      **Experimental:** feature still in development available for testing and feedback. It may change.
      `Please leave collideobjects feedback with authors <https://github.com/pygame/pygame/pull/3026>`_

      Test whether the rectangle collides with any object in the sequence.
      The object of the first collision found is returned. If no collisions are
      found then ``None`` is returned

      If key is given, then it should be a method taking an object from the list
      as input and returning a rect like object e.g. ``lambda obj: obj.rectangle``.
      If an object has multiple attributes of type Rect then key could return one
      of them.

      .. code-block:: python

          r = Rect(1, 1, 10, 10)

          rects = [
              Rect(1, 1, 10, 10),
              Rect(5, 5, 10, 10),
              Rect(15, 15, 1, 1),
              Rect(2, 2, 1, 1),
          ]

          result = r.collideobjects(rects)  # -> <rect(1, 1, 10, 10)>
          print(result)

          class ObjectWithSomRectAttribute:
              def __init__(self, name, collision_box, draw_rect):
                  self.name = name
                  self.draw_rect = draw_rect
                  self.collision_box = collision_box

              def __repr__(self):
                  return f'<{self.__class__.__name__}("{self.name}", {list(self.collision_box)}, {list(self.draw_rect)})>'

          objects = [
              ObjectWithSomRectAttribute("A", Rect(15, 15, 1, 1), Rect(150, 150, 50, 50)),
              ObjectWithSomRectAttribute("B", Rect(1, 1, 10, 10), Rect(300, 300, 50, 50)),
              ObjectWithSomRectAttribute("C", Rect(5, 5, 10, 10), Rect(200, 500, 50, 50)),
          ]

          # collision = r.collideobjects(objects) # this does not work because the items in the list are no Rect like object
          collision = r.collideobjects(
              objects, key=lambda o: o.collision_box
          )  # -> <ObjectWithSomRectAttribute("B", [1, 1, 10, 10], [300, 300, 50, 50])>
          print(collision)

          screen_rect = r.collideobjects(objects, key=lambda o: o.draw_rect)  # -> None
          print(screen_rect)

      .. versionadded:: 2.1.3

      .. ## Rect.collideobjects ##

   .. method:: collideobjectsall

      | :sl:`test if all objects in a list intersect`
      | :sg:`collideobjectsall(rect_list) -> objects`
      | :sg:`collideobjectsall(obj_list, key=func) -> objects`

      **Experimental:** feature still in development available for testing and feedback. It may change.
      `Please leave collideobjectsall feedback with authors <https://github.com/pygame/pygame/pull/3026>`_

      Returns a list of all the objects that contain rectangles that collide
      with the Rect. If no intersecting objects are found, an empty list is
      returned.

      If key is given, then it should be a method taking an object from the list
      as input and returning a rect like object e.g. ``lambda obj: obj.rectangle``.
      If an object has multiple attributes of type Rect then key could return one
      of them.

      .. code-block:: python

          r = Rect(1, 1, 10, 10)

          rects = [
              Rect(1, 1, 10, 10),
              Rect(5, 5, 10, 10),
              Rect(15, 15, 1, 1),
              Rect(2, 2, 1, 1),
          ]

          result = r.collideobjectsall(
              rects
          )  # -> [<rect(1, 1, 10, 10)>, <rect(5, 5, 10, 10)>, <rect(2, 2, 1, 1)>]
          print(result)

          class ObjectWithSomRectAttribute:
              def __init__(self, name, collision_box, draw_rect):
                  self.name = name
                  self.draw_rect = draw_rect
                  self.collision_box = collision_box

              def __repr__(self):
                  return f'<{self.__class__.__name__}("{self.name}", {list(self.collision_box)}, {list(self.draw_rect)})>'

          objects = [
              ObjectWithSomRectAttribute("A", Rect(1, 1, 10, 10), Rect(300, 300, 50, 50)),
              ObjectWithSomRectAttribute("B", Rect(5, 5, 10, 10), Rect(200, 500, 50, 50)),
              ObjectWithSomRectAttribute("C", Rect(15, 15, 1, 1), Rect(150, 150, 50, 50)),
          ]

          # collisions = r.collideobjectsall(objects) # this does not work because ObjectWithSomRectAttribute is not a Rect like object
          collisions = r.collideobjectsall(
              objects, key=lambda o: o.collision_box
          )  # -> [<ObjectWithSomRectAttribute("A", [1, 1, 10, 10], [300, 300, 50, 50])>, <ObjectWithSomRectAttribute("B", [5, 5, 10, 10], [200, 500, 50, 50])>]
          print(collisions)

          screen_rects = r.collideobjectsall(objects, key=lambda o: o.draw_rect)  # -> []
          print(screen_rects)

      .. versionadded:: 2.1.3

      .. ## Rect.collideobjectsall ##

   .. method:: collidedict

      | :sl:`test if one rectangle in a dictionary intersects`
      | :sg:`collidedict(dict) -> (key, value)`
      | :sg:`collidedict(dict) -> None`
      | :sg:`collidedict(dict, use_values=0) -> (key, value)`
      | :sg:`collidedict(dict, use_values=0) -> None`

      Returns the first key and value pair that intersects with the calling
      Rect object. If no collisions are found, ``None`` is returned. If
      ``use_values`` is 0 (default) then the dict's keys will be used in the
      collision detection, otherwise the dict's values will be used.

      .. note ::
         Rect objects cannot be used as keys in a dictionary (they are not
         hashable), so they must be converted to a tuple.
         e.g. ``rect.collidedict({tuple(key_rect) : value})``

      .. versionchanged:: 2.5.0 Added support for keyword arguments.
      
      .. ## Rect.collidedict ##

   .. method:: collidedictall

      | :sl:`test if all rectangles in a dictionary intersect`
      | :sg:`collidedictall(dict) -> [(key, value), ...]`
      | :sg:`collidedictall(dict, use_values=0) -> [(key, value), ...]`

      Returns a list of all the key and value pairs that intersect with the
      calling Rect object. If no collisions are found an empty list is returned.
      If ``use_values`` is 0 (default) then the dict's keys will be used in the
      collision detection, otherwise the dict's values will be used.

      .. note ::
         Rect objects cannot be used as keys in a dictionary (they are not
         hashable), so they must be converted to a tuple.
         e.g. ``rect.collidedictall({tuple(key_rect) : value})``

      .. versionchanged:: 2.5.0 Added support for keyword arguments.
      
      .. ## Rect.collidedictall ##

   .. ## pygame.Rect ##
