.. include:: common.txt

:mod:`pygame._sdl2.touch`
=========================

.. module:: pygame._sdl2.touch
   :synopsis: pygame module to work with touch input

| :sl:`pygame module to work with touch input`

.. versionadded:: 2 This module requires SDL2.

.. function:: get_num_devices

   | :sl:`get the number of touch devices`
   | :sg:`get_num_devices() -> int`

   Return the number of available touch devices.

   .. ## pygame._sdl2.touch.get_num_devices ##

.. function:: get_device

   | :sl:`get the a touch device id for a given index`
   | :sg:`get_device(index) -> touchid`

   :param int index: This number is at least 0 and less than the
                     :func:`number of devices <pygame._sdl2.touch.get_num_devices()>`.

   Return an integer id associated with the given ``index``.

   .. ## pygame._sdl2.touch.get_device ##

.. function:: get_num_fingers

   | :sl:`the number of active fingers for a given touch device`
   | :sg:`get_num_fingers(touchid) -> int`

   Return the number of fingers active for the touch device
   whose id is `touchid`.

   .. ## pygame._sdl2.touch.get_num_fingers ##

.. function:: get_finger

   | :sl:`get information about an active finger`
   | :sg:`get_finger(touchid, index) -> int`

   :param int touchid: The touch device id.
   :param int index: The index of the finger to return
                     information about, between 0 and the
                     :func:`number of active fingers <pygame._sdl2.touch.get_num_fingers()>`.

   Return a dict for the finger ``index`` active on ``touchid``.
   The dict contains these keys:

   ::

      id         the id of the finger (an integer).
      x          the normalized x position of the finger, between 0 and 1.
      y          the normalized y position of the finger, between 0 and 1.
      pressure   the amount of pressure applied by the finger, between 0 and 1.

   .. ## pygame._sdl2.touch.get_finger ##

.. ## pygame._sdl2.touch ##
