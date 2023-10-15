.. include:: common.txt

:mod:`pygame.cdrom`
===================

.. module:: pygame.cdrom
   :synopsis: pygame module for audio cdrom control

| :sl:`pygame module for audio cdrom control`

.. warning::
	This module is non functional in pygame 2.0 and above, unless you have manually compiled pygame with SDL1.
	This module will not be supported in the future.
	One alternative for python cdrom functionality is `pycdio <https://pypi.org/project/pycdio/>`_.
	
The cdrom module manages the ``CD`` and ``DVD`` drives on a computer. It can
also control the playback of audio CDs. This module needs to be initialized
before it can do anything. Each ``CD`` object you create represents a cdrom
drive and must also be initialized individually before it can do most things.

.. function:: init

   | :sl:`initialize the cdrom module`
   | :sg:`init() -> None`

   Initialize the cdrom module. This will scan the system for all ``CD``
   devices. The module must be initialized before any other functions will
   work. This automatically happens when you call ``pygame.init()``.

   It is safe to call this function more than once.

   .. ## pygame.cdrom.init ##

.. function:: quit

   | :sl:`uninitialize the cdrom module`
   | :sg:`quit() -> None`

   Uninitialize the cdrom module. After you call this any existing ``CD``
   objects will no longer work.

   It is safe to call this function more than once.

   .. ## pygame.cdrom.quit ##

.. function:: get_init

   | :sl:`true if the cdrom module is initialized`
   | :sg:`get_init() -> bool`

   Test if the cdrom module is initialized or not. This is different than the
   ``CD.init()`` since each drive must also be initialized individually.

   .. ## pygame.cdrom.get_init ##

.. function:: get_count

   | :sl:`number of cd drives on the system`
   | :sg:`get_count() -> count`

   Return the number of cd drives on the system. When you create ``CD`` objects
   you need to pass an integer id that must be lower than this count. The count
   will be 0 if there are no drives on the system.

   .. ## pygame.cdrom.get_count ##

.. class:: CD

   | :sl:`class to manage a cdrom drive`
   | :sg:`CD(id) -> CD`

   You can create a ``CD`` object for each cdrom on the system. Use
   ``pygame.cdrom.get_count()`` to determine how many drives actually exist.
   The id argument is an integer of the drive, starting at zero.

   The ``CD`` object is not initialized, you can only call ``CD.get_id()`` and
   ``CD.get_name()`` on an uninitialized drive.

   It is safe to create multiple ``CD`` objects for the same drive, they will
   all cooperate normally.

   .. method:: init

      | :sl:`initialize a cdrom drive for use`
      | :sg:`init() -> None`

      Initialize the cdrom drive for use. The drive must be initialized for
      most ``CD`` methods to work. Even if the rest of pygame has been
      initialized.

      There may be a brief pause while the drive is initialized. Avoid
      ``CD.init()`` if the program should not stop for a second or two.

      .. ## CD.init ##

   .. method:: quit

      | :sl:`uninitialize a cdrom drive for use`
      | :sg:`quit() -> None`

      Uninitialize a drive for use. Call this when your program will not be
      accessing the drive for awhile.

      .. ## CD.quit ##

   .. method:: get_init

      | :sl:`true if this cd device initialized`
      | :sg:`get_init() -> bool`

      Test if this ``CDROM`` device is initialized. This is different than the
      ``pygame.cdrom.init()`` since each drive must also be initialized
      individually.

      .. ## CD.get_init ##

   .. method:: play

      | :sl:`start playing audio`
      | :sg:`play(track, start=None, end=None) -> None`

      Playback audio from an audio cdrom in the drive. Besides the track number
      argument, you can also pass a starting and ending time for playback. The
      start and end time are in seconds, and can limit the section of an audio
      track played.

      If you pass a start time but no end, the audio will play to the end of
      the track. If you pass a start time and 'None' for the end time, the
      audio will play to the end of the entire disc.

      See the ``CD.get_numtracks()`` and ``CD.get_track_audio()`` to find
      tracks to playback.

      Note, track 0 is the first track on the ``CD``. Track numbers start at
      zero.

      .. ## CD.play ##

   .. method:: stop

      | :sl:`stop audio playback`
      | :sg:`stop() -> None`

      Stops playback of audio from the cdrom. This will also lose the current
      playback position. This method does nothing if the drive isn't already
      playing audio.

      .. ## CD.stop ##

   .. method:: pause

      | :sl:`temporarily stop audio playback`
      | :sg:`pause() -> None`

      Temporarily stop audio playback on the ``CD``. The playback can be
      resumed at the same point with the ``CD.resume()`` method. If the ``CD``
      is not playing this method does nothing.

      Note, track 0 is the first track on the ``CD``. Track numbers start at
      zero.

      .. ## CD.pause ##

   .. method:: resume

      | :sl:`unpause audio playback`
      | :sg:`resume() -> None`

      Unpause a paused ``CD``. If the ``CD`` is not paused or already playing,
      this method does nothing.

      .. ## CD.resume ##

   .. method:: eject

      | :sl:`eject or open the cdrom drive`
      | :sg:`eject() -> None`

      This will open the cdrom drive and eject the cdrom. If the drive is
      playing or paused it will be stopped.

      .. ## CD.eject ##

   .. method:: get_id

      | :sl:`the index of the cdrom drive`
      | :sg:`get_id() -> id`

      Returns the integer id that was used to create the ``CD`` instance. This
      method can work on an uninitialized ``CD``.

      .. ## CD.get_id ##

   .. method:: get_name

      | :sl:`the system name of the cdrom drive`
      | :sg:`get_name() -> name`

      Return the string name of the drive. This is the system name used to
      represent the drive. It is often the drive letter or device name. This
      method can work on an uninitialized ``CD``.

      .. ## CD.get_name ##

   .. method:: get_busy

      | :sl:`true if the drive is playing audio`
      | :sg:`get_busy() -> bool`

      Returns True if the drive busy playing back audio.

      .. ## CD.get_busy ##

   .. method:: get_paused

      | :sl:`true if the drive is paused`
      | :sg:`get_paused() -> bool`

      Returns True if the drive is currently paused.

      .. ## CD.get_paused ##

   .. method:: get_current

      | :sl:`the current audio playback position`
      | :sg:`get_current() -> track, seconds`

      Returns both the current track and time of that track. This method works
      when the drive is either playing or paused.

      Note, track 0 is the first track on the ``CD``. Track numbers start at
      zero.

      .. ## CD.get_current ##

   .. method:: get_empty

      | :sl:`False if a cdrom is in the drive`
      | :sg:`get_empty() -> bool`

      Return False if there is a cdrom currently in the drive. If the drive is
      empty this will return True.

      .. ## CD.get_empty ##

   .. method:: get_numtracks

      | :sl:`the number of tracks on the cdrom`
      | :sg:`get_numtracks() -> count`

      Return the number of tracks on the cdrom in the drive. This will return
      zero of the drive is empty or has no tracks.

      .. ## CD.get_numtracks ##

   .. method:: get_track_audio

      | :sl:`true if the cdrom track has audio data`
      | :sg:`get_track_audio(track) -> bool`

      Determine if a track on a cdrom contains audio data. You can also call
      ``CD.num_tracks()`` and ``CD.get_all()`` to determine more information
      about the cdrom.

      Note, track 0 is the first track on the ``CD``. Track numbers start at
      zero.

      .. ## CD.get_track_audio ##

   .. method:: get_all

      | :sl:`get all track information`
      | :sg:`get_all() -> [(audio, start, end, length), ...]`

      Return a list with information for every track on the cdrom. The
      information consists of a tuple with four values. The audio value is True
      if the track contains audio data. The start, end, and length values are
      floating point numbers in seconds. Start and end represent absolute times
      on the entire disc.

      .. ## CD.get_all ##

   .. method:: get_track_start

      | :sl:`start time of a cdrom track`
      | :sg:`get_track_start(track) -> seconds`

      Return the absolute time in seconds where at start of the cdrom track.

      Note, track 0 is the first track on the ``CD``. Track numbers start at
      zero.

      .. ## CD.get_track_start ##

   .. method:: get_track_length

      | :sl:`length of a cdrom track`
      | :sg:`get_track_length(track) -> seconds`

      Return a floating point value in seconds of the length of the cdrom
      track.

      Note, track 0 is the first track on the ``CD``. Track numbers start at
      zero.

      .. ## CD.get_track_length ##

   .. ## pygame.cdrom.CD ##

.. ## pygame.cdrom ##
