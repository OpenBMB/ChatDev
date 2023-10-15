#    pygame - Python Game Library
#    Copyright (C) 2000-2003  Pete Shinners
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Library General Public
#    License as published by the Free Software Foundation; either
#    version 2 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Library General Public License for more details.
#
#    You should have received a copy of the GNU Library General Public
#    License along with this library; if not, write to the Free
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
#    Pete Shinners
#    pete@shinners.org


"""Set of functions from pygame that are handy to have in
the local namespace for your module"""

import pygame
from pygame.constants import *  # pylint: disable=wildcard-import; lgtm[py/polluting-import]
from pygame.rect import Rect
from pygame.color import Color

__all__ = pygame.constants.__all__ + ["Rect", "Color"]
