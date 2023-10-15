.. include:: common.txt

:mod:`pygame.sndarray`
======================

.. module:: pygame.sndarray
   :synopsis: pygame module for accessing sound sample data

| :sl:`pygame module for accessing sound sample data`

Functions to convert between NumPy arrays and Sound objects. This
module will only be functional when pygame can use the external NumPy
package. If NumPy can't be imported, ``surfarray`` becomes a ``MissingModule``
object.

Sound data is made of thousands of samples per second, and each sample is the
amplitude of the wave at a particular moment in time. For example, in 22-kHz
format, element number 5 of the array is the amplitude of the wave after
5/22000 seconds.

The arrays are indexed by the ``X`` axis first, followed by the ``Y`` axis.
Each sample is an 8-bit or 16-bit integer, depending on the data format. A
stereo sound file has two values per sample, while a mono sound file only has
one.

.. function:: array

   | :sl:`copy Sound samples into an array`
   | :sg:`array(Sound) -> array`

   Creates a new array for the sound data and copies the samples. The array
   will always be in the format returned from ``pygame.mixer.get_init()``.

   .. ## pygame.sndarray.array ##

.. function:: samples

   | :sl:`reference Sound samples into an array`
   | :sg:`samples(Sound) -> array`

   Creates a new array that directly references the samples in a Sound object.
   Modifying the array will change the Sound. The array will always be in the
   format returned from ``pygame.mixer.get_init()``.

   .. ## pygame.sndarray.samples ##

.. function:: make_sound

   | :sl:`convert an array into a Sound object`
   | :sg:`make_sound(array) -> Sound`

   Create a new playable Sound object from an array. The mixer module must be
   initialized and the array format must be similar to the mixer audio format.

   .. ## pygame.sndarray.make_sound ##

.. function:: use_arraytype

   | :sl:`Sets the array system to be used for sound arrays`
   | :sg:`use_arraytype (arraytype) -> None`

   DEPRECATED: Uses the requested array type for the module functions. The
   only supported arraytype is ``'numpy'``. Other values will raise ValueError.
   Using this function will raise a ``DeprecationWarning``.
   .. ## pygame.sndarray.use_arraytype ##

.. function:: get_arraytype

   | :sl:`Gets the currently active array type.`
   | :sg:`get_arraytype () -> str`

   DEPRECATED: Returns the currently active array type. This will be a value of the
   ``get_arraytypes()`` tuple and indicates which type of array module is used
   for the array creation. Using this function will raise a ``DeprecationWarning``.

   .. versionadded:: 1.8

   .. ## pygame.sndarray.get_arraytype ##

.. function:: get_arraytypes

   | :sl:`Gets the array system types currently supported.`
   | :sg:`get_arraytypes () -> tuple`

   DEPRECATED: Checks, which array systems are available and returns them as a tuple of
   strings. The values of the tuple can be used directly in the
   :func:`pygame.sndarray.use_arraytype` () method. If no supported array
   system could be found, None will be returned.  Using this function will raise a
   ``DeprecationWarning``.

   .. versionadded:: 1.8

   .. ## pygame.sndarray.get_arraytypes ##

.. ## pygame.sndarray ##
