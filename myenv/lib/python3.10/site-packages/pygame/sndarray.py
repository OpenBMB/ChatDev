##    pygame - Python Game Library
##    Copyright (C) 2008 Marcus von Appen
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
##    Marcus von Appen
##    mva@sysfault.org

"""pygame module for accessing sound sample data

Functions to convert between NumPy arrays and Sound objects. This module
will only be functional when pygame can use the external NumPy package.
If NumPy can't be imported, surfarray becomes a MissingModule object.

Sound data is made of thousands of samples per second, and each sample
is the amplitude of the wave at a particular moment in time. For
example, in 22-kHz format, element number 5 of the array is the
amplitude of the wave after 5/22000 seconds.

Each sample is an 8-bit or 16-bit integer, depending on the data format.
A stereo sound file has two values per sample, while a mono sound file
only has one.

Sounds with 16-bit data will be treated as unsigned integers,
if the sound sample type requests this.
"""

from pygame import mixer
import numpy

import warnings


__all__ = [
    "array",
    "samples",
    "make_sound",
    "use_arraytype",
    "get_arraytype",
    "get_arraytypes",
]


def array(sound):
    """pygame.sndarray.array(Sound): return array

    Copy Sound samples into an array.

    Creates a new array for the sound data and copies the samples. The
    array will always be in the format returned from
    pygame.mixer.get_init().
    """

    return numpy.array(sound, copy=True)


def samples(sound):
    """pygame.sndarray.samples(Sound): return array

    Reference Sound samples into an array.

    Creates a new array that directly references the samples in a Sound
    object. Modifying the array will change the Sound. The array will
    always be in the format returned from pygame.mixer.get_init().
    """

    return numpy.array(sound, copy=False)


def make_sound(array):
    """pygame.sndarray.make_sound(array): return Sound

    Convert an array into a Sound object.

    Create a new playable Sound object from an array. The mixer module
    must be initialized and the array format must be similar to the mixer
    audio format.
    """

    return mixer.Sound(array=array)


def use_arraytype(arraytype):
    """pygame.sndarray.use_arraytype(arraytype): return None

    DEPRECATED - only numpy arrays are now supported.
    """
    warnings.warn(
        DeprecationWarning(
            "only numpy arrays are now supported, "
            "this function will be removed in a "
            "future version of the module"
        )
    )
    arraytype = arraytype.lower()
    if arraytype != "numpy":
        raise ValueError("invalid array type")


def get_arraytype():
    """pygame.sndarray.get_arraytype(): return str

    DEPRECATED - only numpy arrays are now supported.
    """
    warnings.warn(
        DeprecationWarning(
            "only numpy arrays are now supported, "
            "this function will be removed in a "
            "future version of the module"
        )
    )
    return "numpy"


def get_arraytypes():
    """pygame.sndarray.get_arraytypes(): return tuple

    DEPRECATED - only numpy arrays are now supported.
    """
    warnings.warn(
        DeprecationWarning(
            "only numpy arrays are now supported, "
            "this function will be removed in a "
            "future version of the module"
        )
    )
    return ("numpy",)
