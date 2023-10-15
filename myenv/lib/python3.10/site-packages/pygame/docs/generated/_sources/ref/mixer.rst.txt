.. include:: common.txt

:mod:`pygame.mixer`
===================

.. module:: pygame.mixer
   :synopsis: pygame module for loading and playing sounds

| :sl:`pygame module for loading and playing sounds`

This module contains classes for loading Sound objects and controlling
playback. The mixer module is optional and depends on SDL_mixer. Your program
should test that :mod:`pygame.mixer` is available and initialized before using
it.

The mixer module has a limited number of channels for playback of sounds.
Usually programs tell pygame to start playing audio and it selects an available
channel automatically. The default is 8 simultaneous channels, but complex
programs can get more precise control over the number of channels and their
use.

All sound playback is mixed in background threads. When you begin to play a
Sound object, it will return immediately while the sound continues to play. A
single Sound object can also be actively played back multiple times.

The mixer also has a special streaming channel. This is for music playback and
is accessed through the :mod:`pygame.mixer.music` module. Consider using this
module for playing long running music. Unlike mixer module, the music module
streams the music from the files without loading music at once into memory.

The mixer module must be initialized like other pygame modules, but it has some
extra conditions. The ``pygame.mixer.init()`` function takes several optional
arguments to control the playback rate and sample size. Pygame will default to
reasonable values, but pygame cannot perform Sound resampling, so the mixer
should be initialized to match the values of your audio resources.

``NOTE``: For less laggy sound use a smaller buffer size. The default
is set to reduce the chance of scratchy sounds on some computers. You can
change the default buffer by calling :func:`pygame.mixer.pre_init` before
:func:`pygame.mixer.init` or :func:`pygame.init` is called. For example:
``pygame.mixer.pre_init(44100,-16,2, 1024)``


.. function:: init

   | :sl:`initialize the mixer module`
   | :sg:`init(frequency=44100, size=-16, channels=2, buffer=512, devicename=None, allowedchanges=AUDIO_ALLOW_FREQUENCY_CHANGE | AUDIO_ALLOW_CHANNELS_CHANGE) -> None`

   Initialize the mixer module for Sound loading and playback. The default
   arguments can be overridden to provide specific audio mixing. Keyword
   arguments are accepted. For backwards compatibility, argument values of 
   0 are replaced with the startup defaults, except for ``allowedchanges``,
   where -1 is used. (startup defaults may be changed by a :func:`pre_init` call).

   The size argument represents how many bits are used for each audio sample.
   If the value is negative then signed sample values will be used. Positive
   values mean unsigned audio samples will be used. An invalid value raises an
   exception.

   The channels argument is used to specify whether to use mono or stereo. 1
   for mono and 2 for stereo.

   The buffer argument controls the number of internal samples used in the
   sound mixer. The default value should work for most cases. It can be lowered
   to reduce latency, but sound dropout may occur. It can be raised to larger
   values to ensure playback never skips, but it will impose latency on sound
   playback. The buffer size must be a power of two (if not it is rounded up to
   the next nearest power of 2).

   Some platforms require the :mod:`pygame.mixer` module to be initialized
   after the display modules have initialized. The top level ``pygame.init()``
   takes care of this automatically, but cannot pass any arguments to the mixer
   init. To solve this, mixer has a function ``pygame.mixer.pre_init()`` to set
   the proper defaults before the toplevel init is used.

   When using allowedchanges=0 it will convert the samples at runtime to match
   what the hardware supports. For example a sound card may not
   support 16bit sound samples, so instead it will use 8bit samples internally.
   If AUDIO_ALLOW_FORMAT_CHANGE is supplied, then the requested format will
   change to the closest that SDL2 supports.

   Apart from 0, allowedchanged accepts the following constants ORed together:

      - AUDIO_ALLOW_FREQUENCY_CHANGE
      - AUDIO_ALLOW_FORMAT_CHANGE
      - AUDIO_ALLOW_CHANNELS_CHANGE
      - AUDIO_ALLOW_ANY_CHANGE

   It is safe to call this more than once, but after the mixer is initialized
   you cannot change the playback arguments without first calling
   ``pygame.mixer.quit()``.

   .. versionchanged:: 1.8 The default ``buffersize`` changed from 1024 to 3072.
   .. versionchanged:: 1.9.1 The default ``buffersize`` changed from 3072 to 4096.
   .. versionchanged:: 2.0.0 The default ``buffersize`` changed from 4096 to 512. 
   .. versionchanged:: 2.0.0 The default ``frequency`` changed from 22050 to 44100.
   .. versionchanged:: 2.0.0 ``size`` can be 32 (32-bit floats).
   .. versionchanged:: 2.0.0 ``channels`` can also be 4 or 6.
   .. versionadded:: 2.0.0 ``allowedchanges``, ``devicename`` arguments added

   .. ## pygame.mixer.init ##

.. function:: pre_init

   | :sl:`preset the mixer init arguments`
   | :sg:`pre_init(frequency=44100, size=-16, channels=2, buffer=512, devicename=None, allowedchanges=AUDIO_ALLOW_FREQUENCY_CHANGE | AUDIO_ALLOW_CHANNELS_CHANGE) -> None`

   Call pre_init to change the defaults used when the real
   ``pygame.mixer.init()`` is called. Keyword arguments are accepted. The best
   way to set custom mixer playback values is to call
   ``pygame.mixer.pre_init()`` before calling the top level ``pygame.init()``.
   For backwards compatibility, argument values of 0 are replaced with the
   startup defaults, except for ``allowedchanges``, where -1 is used.

   .. versionchanged:: 1.8 The default ``buffersize`` changed from 1024 to 3072.
   .. versionchanged:: 1.9.1 The default ``buffersize`` changed from 3072 to 4096.
   .. versionchanged:: 2.0.0 The default ``buffersize`` changed from 4096 to 512. 
   .. versionchanged:: 2.0.0 The default ``frequency`` changed from 22050 to 44100.
   .. versionadded:: 2.0.0 ``allowedchanges``, ``devicename`` arguments added

   .. ## pygame.mixer.pre_init ##

.. function:: quit

   | :sl:`uninitialize the mixer`
   | :sg:`quit() -> None`

   This will uninitialize :mod:`pygame.mixer`. All playback will stop and any
   loaded Sound objects may not be compatible with the mixer if it is
   reinitialized later.

   .. ## pygame.mixer.quit ##

.. function:: get_init

   | :sl:`test if the mixer is initialized`
   | :sg:`get_init() -> (frequency, format, channels)`

   If the mixer is initialized, this returns the playback arguments it is
   using. If the mixer has not been initialized this returns ``None``.

   .. ## pygame.mixer.get_init ##

.. function:: stop

   | :sl:`stop playback of all sound channels`
   | :sg:`stop() -> None`

   This will stop all playback of all active mixer channels.

   .. ## pygame.mixer.stop ##

.. function:: pause

   | :sl:`temporarily stop playback of all sound channels`
   | :sg:`pause() -> None`

   This will temporarily stop all playback on the active mixer channels. The
   playback can later be resumed with ``pygame.mixer.unpause()``

   .. ## pygame.mixer.pause ##

.. function:: unpause

   | :sl:`resume paused playback of sound channels`
   | :sg:`unpause() -> None`

   This will resume all active sound channels after they have been paused.

   .. ## pygame.mixer.unpause ##

.. function:: fadeout

   | :sl:`fade out the volume on all sounds before stopping`
   | :sg:`fadeout(time) -> None`

   This will fade out the volume on all active channels over the time argument
   in milliseconds. After the sound is muted the playback will stop.

   .. ## pygame.mixer.fadeout ##

.. function:: set_num_channels

   | :sl:`set the total number of playback channels`
   | :sg:`set_num_channels(count) -> None`

   Sets the number of available channels for the mixer. The default value is 8.
   The value can be increased or decreased. If the value is decreased, sounds
   playing on the truncated channels are stopped.

   .. ## pygame.mixer.set_num_channels ##

.. function:: get_num_channels

   | :sl:`get the total number of playback channels`
   | :sg:`get_num_channels() -> count`

   Returns the number of currently active playback channels.

   .. ## pygame.mixer.get_num_channels ##

.. function:: set_reserved

   | :sl:`reserve channels from being automatically used`
   | :sg:`set_reserved(count) -> count`

   The mixer can reserve any number of channels that will not be automatically
   selected for playback by Sounds. This means that whenever you play a Sound 
   without specifying a channel, a reserved channel will never be used. If sounds
   are currently playing on the reserved channels they will not be stopped.

   This allows the application to reserve a specific number of channels for
   important sounds that must not be dropped or have a guaranteed channel to
   play on.

   Will return number of channels actually reserved, this may be less than requested
   depending on the number of channels previously allocated.

   .. ## pygame.mixer.set_reserved ##

.. function:: find_channel

   | :sl:`find an unused channel`
   | :sg:`find_channel(force=False) -> Channel`

   This will find and return an inactive Channel object. If there are no
   inactive Channels this function will return ``None``. If there are no
   inactive channels and the force argument is ``True``, this will find the
   Channel with the longest running Sound and return it.

   .. ## pygame.mixer.find_channel ##

.. function:: get_busy

   | :sl:`test if any sound is being mixed`
   | :sg:`get_busy() -> bool`

   Returns ``True`` if the mixer is busy mixing any channels. If the mixer is
   idle then this return ``False``.

   .. ## pygame.mixer.get_busy ##

.. function:: get_sdl_mixer_version

   | :sl:`get the mixer's SDL version`
   | :sg:`get_sdl_mixer_version() -> (major, minor, patch)`
   | :sg:`get_sdl_mixer_version(linked=True) -> (major, minor, patch)`

   :param bool linked: if ``True`` (default) the linked version number is
      returned, otherwise the compiled version number is returned

   :returns: the mixer's SDL library version number (linked or compiled
      depending on the ``linked`` parameter) as a tuple of 3 integers
      ``(major, minor, patch)``
   :rtype: tuple

   .. note::
      The linked and compile version numbers should be the same.

   .. versionadded:: 2.0.0

   .. ## pygame.mixer.get_sdl_mixer_version ##

.. class:: Sound

   | :sl:`Create a new Sound object from a file or buffer object`
   | :sg:`Sound(filename) -> Sound`
   | :sg:`Sound(file=filename) -> Sound`
   | :sg:`Sound(file=pathlib_path) -> Sound`
   | :sg:`Sound(buffer) -> Sound`
   | :sg:`Sound(buffer=buffer) -> Sound`
   | :sg:`Sound(object) -> Sound`
   | :sg:`Sound(file=object) -> Sound`
   | :sg:`Sound(array=object) -> Sound`

   Load a new sound buffer from a filename, a python file object or a readable
   buffer object. Limited resampling will be performed to help the sample match
   the initialize arguments for the mixer. A Unicode string can only be a file
   pathname. A bytes object can be either a pathname or a buffer object.
   Use the 'file' or 'buffer' keywords to avoid ambiguity; otherwise Sound may
   guess wrong. If the array keyword is used, the object is expected to export 
   a new buffer interface (The object is checked for a buffer interface first.)

   The Sound object represents actual sound sample data. Methods that change
   the state of the Sound object will the all instances of the Sound playback.
   A Sound object also exports a new buffer interface.

   The Sound can be loaded from an ``OGG`` audio file or from an uncompressed
   ``WAV``.

   Note: The buffer will be copied internally, no data will be shared between
   it and the Sound object.

   For now buffer and array support is consistent with ``sndarray.make_sound``
   for Numeric arrays, in that sample sign and byte order are ignored. This
   will change, either by correctly handling sign and byte order, or by raising
   an exception when different. Also, source samples are truncated to fit the
   audio sample size. This will not change.

   .. versionadded:: 1.8 ``pygame.mixer.Sound(buffer)``
   .. versionadded:: 1.9.2
      :class:`pygame.mixer.Sound` keyword arguments and array interface support
   .. versionadded:: 2.0.1 pathlib.Path support on Python 3.

   .. method:: play

      | :sl:`begin sound playback`
      | :sg:`play(loops=0, maxtime=0, fade_ms=0) -> Channel`

      Begin playback of the Sound (i.e., on the computer's speakers) on an
      available Channel. This will forcibly select a Channel, so playback may
      cut off a currently playing sound if necessary.

      The loops argument controls how many times the sample will be repeated
      after being played the first time. A value of 5 means that the sound will
      be played once, then repeated five times, and so is played a total of six
      times. The default value (zero) means the Sound is not repeated, and so
      is only played once. If loops is set to -1 the Sound will loop
      indefinitely (though you can still call ``stop()`` to stop it).

      The maxtime argument can be used to stop playback after a given number of
      milliseconds.

      The fade_ms argument will make the sound start playing at 0 volume and
      fade up to full volume over the time given. The sample may end before the
      fade-in is complete.

      This returns the Channel object for the channel that was selected.

      .. ## Sound.play ##

   .. method:: stop

      | :sl:`stop sound playback`
      | :sg:`stop() -> None`

      This will stop the playback of this Sound on any active Channels.

      .. ## Sound.stop ##

   .. method:: fadeout

      | :sl:`stop sound playback after fading out`
      | :sg:`fadeout(time) -> None`

      This will stop playback of the sound after fading it out over the time
      argument in milliseconds. The Sound will fade and stop on all actively
      playing channels.

      .. ## Sound.fadeout ##

   .. method:: set_volume

      | :sl:`set the playback volume for this Sound`
      | :sg:`set_volume(value) -> None`

      This will set the playback volume (loudness) for this Sound. This will
      immediately affect the Sound if it is playing. It will also affect any
      future playback of this Sound.

      :param float value: volume in the range of 0.0 to 1.0 (inclusive)

         | If value < 0.0, the volume will not be changed
         | If value > 1.0, the volume will be set to 1.0

      .. ## Sound.set_volume ##

   .. method:: get_volume

      | :sl:`get the playback volume`
      | :sg:`get_volume() -> value`

      Return a value from 0.0 to 1.0 representing the volume for this Sound.

      .. ## Sound.get_volume ##

   .. method:: get_num_channels

      | :sl:`count how many times this Sound is playing`
      | :sg:`get_num_channels() -> count`

      Return the number of active channels this sound is playing on.

      .. ## Sound.get_num_channels ##

   .. method:: get_length

      | :sl:`get the length of the Sound`
      | :sg:`get_length() -> seconds`

      Return the length of this Sound in seconds.

      .. ## Sound.get_length ##

   .. method:: get_raw

      | :sl:`return a bytestring copy of the Sound samples.`
      | :sg:`get_raw() -> bytes`

      Return a copy of the Sound object buffer as a bytes.

      .. versionadded:: 1.9.2

      .. ## Sound.get_raw ##

   .. ## pygame.mixer.Sound ##

.. class:: Channel

   | :sl:`Create a Channel object for controlling playback`
   | :sg:`Channel(id) -> Channel`

   Return a Channel object for one of the current channels. The id must be a
   value from 0 to the value of ``pygame.mixer.get_num_channels()``.

   The Channel object can be used to get fine control over the playback of
   Sounds. A channel can only playback a single Sound at time. Using channels
   is entirely optional since pygame can manage them by default.

   .. method:: play

      | :sl:`play a Sound on a specific Channel`
      | :sg:`play(Sound, loops=0, maxtime=0, fade_ms=0) -> None`

      This will begin playback of a Sound on a specific Channel. If the Channel
      is currently playing any other Sound it will be stopped.

      The loops argument has the same meaning as in ``Sound.play()``: it is the
      number of times to repeat the sound after the first time. If it is 3, the
      sound will be played 4 times (the first time, then three more). If loops
      is -1 then the playback will repeat indefinitely.

      As in ``Sound.play()``, the maxtime argument can be used to stop playback
      of the Sound after a given number of milliseconds.

      As in ``Sound.play()``, the fade_ms argument can be used fade in the
      sound.

      .. ## Channel.play ##

   .. method:: stop

      | :sl:`stop playback on a Channel`
      | :sg:`stop() -> None`

      Stop sound playback on a channel. After playback is stopped the channel
      becomes available for new Sounds to play on it.

      .. ## Channel.stop ##

   .. method:: pause

      | :sl:`temporarily stop playback of a channel`
      | :sg:`pause() -> None`

      Temporarily stop the playback of sound on a channel. It can be resumed at
      a later time with ``Channel.unpause()``

      .. ## Channel.pause ##

   .. method:: unpause

      | :sl:`resume pause playback of a channel`
      | :sg:`unpause() -> None`

      Resume the playback on a paused channel.

      .. ## Channel.unpause ##

   .. method:: fadeout

      | :sl:`stop playback after fading channel out`
      | :sg:`fadeout(time) -> None`

      Stop playback of a channel after fading out the sound over the given time
      argument in milliseconds.

      .. ## Channel.fadeout ##

   .. method:: set_volume

      | :sl:`set the volume of a playing channel`
      | :sg:`set_volume(value) -> None`
      | :sg:`set_volume(left, right) -> None`

      Set the volume (loudness) of a playing sound. When a channel starts to
      play its volume value is reset. This only affects the current sound. The
      value argument is between 0.0 and 1.0.

      If one argument is passed, it will be the volume of both speakers. If two
      arguments are passed and the mixer is in stereo mode, the first argument
      will be the volume of the left speaker and the second will be the volume
      of the right speaker. (If the second argument is ``None``, the first
      argument will be the volume of both speakers.)

      If the channel is playing a Sound on which ``set_volume()`` has also been
      called, both calls are taken into account. For example:

      ::

          sound = pygame.mixer.Sound("s.wav")
          channel = s.play()      # Sound plays at full volume by default
          sound.set_volume(0.9)   # Now plays at 90% of full volume.
          sound.set_volume(0.6)   # Now plays at 60% (previous value replaced).
          channel.set_volume(0.5) # Now plays at 30% (0.6 * 0.5).

      .. ## Channel.set_volume ##

   .. method:: get_volume

      | :sl:`get the volume of the playing channel`
      | :sg:`get_volume() -> value`

      Return the volume of the channel for the current playing sound. This does
      not take into account stereo separation used by
      :meth:`Channel.set_volume`. The Sound object also has its own volume
      which is mixed with the channel.

      .. ## Channel.get_volume ##

   .. method:: get_busy

      | :sl:`check if the channel is active`
      | :sg:`get_busy() -> bool`

      Returns ``True`` if the channel is actively mixing sound. If the channel
      is idle this returns ``False``.

      .. ## Channel.get_busy ##

   .. method:: get_sound

      | :sl:`get the currently playing Sound`
      | :sg:`get_sound() -> Sound`

      Return the actual Sound object currently playing on this channel. If the
      channel is idle ``None`` is returned.

      .. ## Channel.get_sound ##

   .. method:: queue

      | :sl:`queue a Sound object to follow the current`
      | :sg:`queue(Sound) -> None`

      When a Sound is queued on a Channel, it will begin playing immediately
      after the current Sound is finished. Each channel can only have a single
      Sound queued at a time. The queued Sound will only play if the current
      playback finished automatically. It is cleared on any other call to
      ``Channel.stop()`` or ``Channel.play()``.

      If there is no sound actively playing on the Channel then the Sound will
      begin playing immediately.

      .. ## Channel.queue ##

   .. method:: get_queue

      | :sl:`return any Sound that is queued`
      | :sg:`get_queue() -> Sound`

      If a Sound is already queued on this channel it will be returned. Once
      the queued sound begins playback it will no longer be on the queue.

      .. ## Channel.get_queue ##

   .. method:: set_endevent

      | :sl:`have the channel send an event when playback stops`
      | :sg:`set_endevent() -> None`
      | :sg:`set_endevent(type) -> None`

      When an endevent is set for a channel, it will send an event to the
      pygame queue every time a sound finishes playing on that channel (not
      just the first time). Use ``pygame.event.get()`` to retrieve the endevent
      once it's sent.

      Note that if you called ``Sound.play(n)`` or ``Channel.play(sound,n)``,
      the end event is sent only once: after the sound has been played "n+1"
      times (see the documentation of Sound.play).

      If ``Channel.stop()`` or ``Channel.play()`` is called while the sound was
      still playing, the event will be posted immediately.

      The type argument will be the event id sent to the queue. This can be any
      valid event type, but a good choice would be a value between
      ``pygame.locals.USEREVENT`` and ``pygame.locals.NUMEVENTS``. If no type
      argument is given then the Channel will stop sending endevents.

      .. ## Channel.set_endevent ##

   .. method:: get_endevent

      | :sl:`get the event a channel sends when playback stops`
      | :sg:`get_endevent() -> type`

      Returns the event type to be sent every time the Channel finishes
      playback of a Sound. If there is no endevent the function returns
      ``pygame.NOEVENT``.

      .. ## Channel.get_endevent ##

   .. ## pygame.mixer.Channel ##

.. ## pygame.mixer ##
