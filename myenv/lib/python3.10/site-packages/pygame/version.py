##    pygame - Python Game Library
##    Copyright (C) 2000-2003  Pete Shinners
##
##    This library is free software; you can redistribute it and/or
##    modify it under the terms of the GNU Library General Public
##    License as published by the Free Software Foundation; either
##    version 2 of the License, or (at your option) any later version.
##
##    This library is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##    Library General Public License for more details.
##
##    You should have received a copy of the GNU Library General Public
##    License along with this library; if not, write to the Free
##    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
##
##    Pete Shinners
##    pete@shinners.org

"""Simply the current installed pygame version. The version information is
stored in the regular pygame module as 'pygame.ver'. Keeping the version
information also available in a separate module allows you to test the
pygame version without importing the main pygame module.

The python version information should always compare greater than any previous
releases. (hmm, until we get to versions > 10)
"""
from pygame.base import get_sdl_version

###############
# This file is generated with version.py.in
##

class SoftwareVersion(tuple):
    """
    A class for storing data about software versions.
    """
    __slots__ = ()
    fields = "major", "minor", "patch"

    def __new__(cls, major, minor, patch):
        return tuple.__new__(cls, (major, minor, patch))

    def __repr__(self):
        fields = (f"{fld}={val}" for fld, val in zip(self.fields, self))
        return f"{str(self.__class__.__name__)}({', '.join(fields)})"

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"

    major = property(lambda self: self[0])
    minor = property(lambda self: self[1])
    patch = property(lambda self: self[2])

class PygameVersion(SoftwareVersion):
    """
    Pygame Version class.
    """

class SDLVersion(SoftwareVersion):
    """
    SDL Version class.
    """

_sdl_tuple = get_sdl_version()
SDL = SDLVersion(_sdl_tuple[0], _sdl_tuple[1], _sdl_tuple[2])
ver = "2.5.1"  # pylint: disable=invalid-name
vernum = PygameVersion(2, 5, 1)
rev = ""  # pylint: disable=invalid-name

__all__ = ["SDL", "ver", "vernum", "rev"]
