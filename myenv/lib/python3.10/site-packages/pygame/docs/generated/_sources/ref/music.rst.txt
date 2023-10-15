.. include:: common.txt

:mod:`pygame.mixer.music`
=========================

.. module:: pygame.mixer.music
   :synopsis: pygame module for controlling streamed audio

| :sl:`pygame module for controlling streamed audio`

The music module is closely tied to :mod:`pygame.mixer`. Use the music module
to control the playback of music in the sound mixer.

The difference between the music playback and regular Sound playback is that
the music is streamed, and never actually loaded all at once. The mixer system
only supports a single music stream at once.

On older pygame versions, ``MP3`` support was limited under Mac and Linux. This
changed in pygame ``v2.0.2`` which got improved MP3 support. Consider using
``OGG`` file format for music as that can give slightly better compression than
MP3 in most cases.

.. function:: load

   | :sl:`Load a music file for playback`
   | :sg:`load(filename) -> None`
   | :sg:`load(fileobj, namehint="") -> None`

   This will load a music filename/file object and prepare it for playback. If
   a music stream is already playing it will be stopped. This does not start
   the music playing.

   If you are loading from a file object, the namehint parameter can be used to specify
   the type of music data in the object. For example: :code:`load(fileobj, "ogg")`.

   .. versionchanged:: 2.0.2 Added optional ``namehint`` argument

   .. ## pygame.mixer.music.load ##

.. function:: unload

   | :sl:`Unload the currently loaded music to free up resources`
   | :sg:`unload() -> None`

   This closes resources like files for any music that may be loaded.

   .. versionadded:: 2.0.0

   .. ## pygame.mixer.music.load ##


.. function:: play

   | :sl:`Start the playback of the music stream`
   | :sg:`play(loops=0, start=0.0, fade_ms=0) -> None`

   This will play the loaded music stream. If the music is already playing it
   will be restarted.
   
   ``loops`` is an optional integer argument, which is ``0`` by default, which 
   indicates how many times to repeat the music. The music repeats indefinitely if 
   this argument is set to ``-1``. 
   
   ``start`` is an optional float argument, which is ``0.0`` by default, which 
   denotes the position in time from which the music starts playing. The starting 
   position depends on the format of the music played. ``MP3`` and ``OGG`` use 
   the position as time in seconds. For ``MP3`` files the start time position
   selected may not be accurate as things like variable bit rate encoding and ID3
   tags can throw off the timing calculations. For ``MOD``  music it is the pattern 
   order number. Passing a start position will raise a NotImplementedError if 
   the start position cannot be set.

   ``fade_ms`` is an optional integer argument, which is ``0`` by default,
   which denotes the period of time (in milliseconds) over which the music
   will fade up from volume level ``0.0`` to full volume (or the volume level
   previously set by :func:`set_volume`). The sample may end before the fade-in
   is complete. If the music is already streaming ``fade_ms`` is ignored.
   
   .. versionchanged:: 2.0.0 Added optional ``fade_ms`` argument

   .. ## pygame.mixer.music.play ##

.. function:: rewind

   | :sl:`restart music`
   | :sg:`rewind() -> None`

   Resets playback of the current music to the beginning. If :func:`pause` has
   previously been used to pause the music, the music will remain paused.
   
   .. note:: :func:`rewind` supports a limited number of file types and notably
             ``WAV`` files are NOT supported. For unsupported file types use :func:`play`
             which will restart the music that's already playing (note that this
             will start the music playing again even if previously paused).

   .. ## pygame.mixer.music.rewind ##

.. function:: stop

   | :sl:`stop the music playback`
   | :sg:`stop() -> None`

   Stops the music playback if it is currently playing.
   endevent will be triggered, if set.
   It won't unload the music.

   .. ## pygame.mixer.music.stop ##

.. function:: pause

   | :sl:`temporarily stop music playback`
   | :sg:`pause() -> None`

   Temporarily stop playback of the music stream. It can be resumed with the
   :func:`unpause` function.

   .. ## pygame.mixer.music.pause ##

.. function:: unpause

   | :sl:`resume paused music`
   | :sg:`unpause() -> None`

   This will resume the playback of a music stream after it has been paused.

   .. ## pygame.mixer.music.unpause ##

.. function:: fadeout

   | :sl:`stop music playback after fading out`
   | :sg:`fadeout(time) -> None`

   Fade out and stop the currently playing music.

   The ``time`` argument denotes the integer milliseconds for which the 
   fading effect is generated.

   Note, that this function blocks until the music has faded out. Calls 
   to :func:`fadeout` and :func:`set_volume` will have no effect during 
   this time. If an event was set using :func:`set_endevent` it will be 
   called after the music has faded.

   .. ## pygame.mixer.music.fadeout ##

.. function:: set_volume

   | :sl:`set the music volume`
   | :sg:`set_volume(volume) -> None`

   Set the volume of the music playback.
   
   The ``volume`` argument is a float between ``0.0`` and ``1.0`` that sets 
   the volume level. When new music is loaded the volume is reset to full
   volume. If ``volume`` is a negative value it will be ignored and the
   volume will remain set at the current level. If the ``volume`` argument
   is greater than ``1.0``, the volume will be set to ``1.0``.

   .. ## pygame.mixer.music.set_volume ##

.. function:: get_volume

   | :sl:`get the music volume`
   | :sg:`get_volume() -> value`

   Returns the current volume for the mixer. The value will be between ``0.0`` 
   and ``1.0``.

   .. ## pygame.mixer.music.get_volume ##

.. function:: get_busy

   | :sl:`check if the music stream is playing`
   | :sg:`get_busy() -> bool`

   Returns True when the music stream is actively playing. When the music is
   idle this returns False. In pygame 2.0.1 and above this function returns
   False when the music is paused. In pygame 1 it returns True when the music
   is paused.

   .. versionchanged:: 2.0.1 Returns False when music paused.

   .. ## pygame.mixer.music.get_busy ##

.. function:: set_pos

   | :sl:`set position to play from`
   | :sg:`set_pos(pos) -> None`

   This sets the position in the music file where playback will start.
   The meaning of "pos", a float (or a number that can be converted to a float),
   depends on the music format.
   
   For ``MOD`` files, pos is the integer pattern number in the module.
   For ``OGG`` it is the absolute position, in seconds, from
   the beginning of the sound. For ``MP3`` files, it is the relative position,
   in seconds, from the current position. For absolute positioning in an ``MP3``
   file, first call :func:`rewind`.

   Other file formats are unsupported. Newer versions of SDL_mixer have
   better positioning support than earlier ones. An SDLError is raised if a
   particular format does not support positioning.

   Function :func:`set_pos` calls underlining SDL_mixer function
   ``Mix_SetMusicPosition``.

   .. versionadded:: 1.9.2

   .. ## pygame.mixer.music.set_pos ##

.. function:: get_pos

   | :sl:`get the music play time`
   | :sg:`get_pos() -> time`

   This gets the number of milliseconds that the music has been playing for.
   The returned time only represents how long the music has been playing; it
   does not take into account any starting position offsets.

   .. ## pygame.mixer.music.get_pos ##

.. function:: queue

   | :sl:`queue a sound file to follow the current`
   | :sg:`queue(filename) -> None`
   | :sg:`queue(fileobj, namehint="", loops=0) -> None`

   This will load a sound file and queue it. A queued sound file will begin as
   soon as the current sound naturally ends. Only one sound can be queued at a
   time. Queuing a new sound while another sound is queued will result in the
   new sound becoming the queued sound. Also, if the current sound is ever
   stopped or changed, the queued sound will be lost.

   If you are loading from a file object, the namehint parameter can be used to specify
   the type of music data in the object. For example: :code:`queue(fileobj, "ogg")`.

   The following example will play music by Bach six times, then play music by
   Mozart once:

   ::

       pygame.mixer.music.load('bach.ogg')
       pygame.mixer.music.play(5)        # Plays six times, not five!
       pygame.mixer.music.queue('mozart.ogg')

   .. versionchanged:: 2.0.2 Added optional ``namehint`` argument

   .. ## pygame.mixer.music.queue ##

.. function:: set_endevent

   | :sl:`have the music send an event when playback stops`
   | :sg:`set_endevent() -> None`
   | :sg:`set_endevent(type) -> None`

   This causes pygame to signal (by means of the event queue) when the music is
   done playing. The argument determines the type of event that will be queued.

   The event will be queued every time the music finishes, not just the first
   time. To stop the event from being queued, call this method with no
   argument.

   .. ## pygame.mixer.music.set_endevent ##

.. function:: get_endevent

   | :sl:`get the event a channel sends when playback stops`
   | :sg:`get_endevent() -> type`

   Returns the event type to be sent every time the music finishes playback. If
   there is no endevent the function returns ``pygame.NOEVENT``.

   .. ## pygame.mixer.music.get_endevent ##

.. ## pygame.mixer.music ##
