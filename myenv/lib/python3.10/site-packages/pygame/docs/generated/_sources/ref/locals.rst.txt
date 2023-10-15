.. include:: common.txt

:mod:`pygame.locals`
====================

.. module:: pygame.locals
   :synopsis: pygame constants

| :sl:`pygame constants`

This module contains various constants used by pygame. Its contents are
automatically placed in the pygame module namespace. However, an application
can use ``pygame.locals`` to include only the pygame constants with a ``from
pygame.locals import *``.

Detailed descriptions of the various constants can be found throughout the
pygame documentation. Here are the locations of some of them.

   - The :mod:`pygame.display` module contains flags like ``FULLSCREEN`` used
     by :func:`pygame.display.set_mode`.
   - The :mod:`pygame.event` module contains the various event types.
   - The :mod:`pygame.key` module lists the keyboard constants and modifiers
     (``K_``\* and ``MOD_``\*) relating to the ``key`` and ``mod`` attributes of
     the ``KEYDOWN`` and ``KEYUP`` events.
   - The :mod:`pygame.time` module defines ``TIMER_RESOLUTION``.

.. ## pygame.locals ##
