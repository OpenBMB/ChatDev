.. include:: common.txt

:mod:`pygame.Overlay`
=====================

.. currentmodule:: pygame

.. warning::
	This module is non functional in pygame 2.0 and above, unless you have manually compiled pygame with SDL1.
	This module will not be supported in the future.

.. class:: Overlay

   | :sl:`pygame object for video overlay graphics`
   | :sg:`Overlay(format, (width, height)) -> Overlay`

   The Overlay objects provide support for accessing hardware video overlays.
   Video overlays do not use standard ``RGB`` pixel formats, and can use
   multiple resolutions of data to create a single image.

   The Overlay objects represent lower level access to the display hardware. To
   use the object you must understand the technical details of video overlays.

   The Overlay format determines the type of pixel data used. Not all hardware
   will support all types of overlay formats. Here is a list of available
   format types:

   ::

     YV12_OVERLAY, IYUV_OVERLAY, YUY2_OVERLAY, UYVY_OVERLAY, YVYU_OVERLAY

   The width and height arguments control the size for the overlay image data.
   The overlay image can be displayed at any size, not just the resolution of
   the overlay.

   The overlay objects are always visible, and always show above the regular
   display contents.

   .. method:: display

      | :sl:`set the overlay pixel data`
      | :sg:`display((y, u, v)) -> None`
      | :sg:`display() -> None`

      Display the YUV data in SDL's overlay planes. The y, u, and v arguments
      are strings of binary data. The data must be in the correct format used
      to create the Overlay.

      If no argument is passed in, the Overlay will simply be redrawn with the
      current data. This can be useful when the Overlay is not really hardware
      accelerated.

      The strings are not validated, and improperly sized strings could crash
      the program.

      .. ## Overlay.display ##

   .. method:: set_location

      | :sl:`control where the overlay is displayed`
      | :sg:`set_location(rect) -> None`

      Set the location for the overlay. The overlay will always be shown
      relative to the main display Surface. This does not actually redraw the
      overlay, it will be updated on the next call to ``Overlay.display()``.

      .. ## Overlay.set_location ##

   .. method:: get_hardware

      | :sl:`test if the Overlay is hardware accelerated`
      | :sg:`get_hardware(rect) -> int`

      Returns a True value when the Overlay is hardware accelerated. If the
      platform does not support acceleration, software rendering is used.

      .. ## Overlay.get_hardware ##

   .. ## pygame.Overlay ##
