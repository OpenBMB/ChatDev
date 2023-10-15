.. include:: common.txt

:mod:`pygame.fastevent`
=======================

.. module:: pygame.fastevent
   :synopsis: pygame module for interacting with events and queues from multiple
              threads.

| :sl:`pygame module for interacting with events and queues`

IMPORTANT NOTE: THIS MODULE IS DEPRECATED IN PYGAME 2.2

In older pygame versions before pygame 2, :mod:`pygame.event` was not well
suited for posting events from different threads. This module served as a
replacement (with less features) for multithreaded use. Now, the usage of this
module is highly discouraged in favour of use of the main :mod:`pygame.event`
module. This module will be removed in a future pygame version.

Below, the legacy docs of the module is provided

.. function:: init

   | :sl:`initialize pygame.fastevent`
   | :sg:`init() -> None`

   Initialize the pygame.fastevent module.

   .. ## pygame.fastevent.init ##

.. function:: get_init

   | :sl:`returns True if the fastevent module is currently initialized`
   | :sg:`get_init() -> bool`

   Returns True if the pygame.fastevent module is currently initialized.

   .. ## pygame.fastevent.get_init ##

.. function:: pump

   | :sl:`internally process pygame event handlers`
   | :sg:`pump() -> None`

   For each frame of your game, you will need to make some sort of call to the
   event queue. This ensures your program can internally interact with the rest
   of the operating system.

   This function is not necessary if your program is consistently processing
   events on the queue through the other :mod:`pygame.fastevent` functions.

   There are important things that must be dealt with internally in the event
   queue. The main window may need to be repainted or respond to the system. If
   you fail to make a call to the event queue for too long, the system may
   decide your program has locked up.

   .. ## pygame.fastevent.pump ##

.. function:: wait

   | :sl:`wait for an event`
   | :sg:`wait() -> Event`

   Returns the current event on the queue. If there are no messages
   waiting on the queue, this will not return until one is available.
   Sometimes it is important to use this wait to get events from the queue,
   it will allow your application to idle when the user isn't doing anything
   with it.

   .. ## pygame.fastevent.wait ##

.. function:: poll

   | :sl:`get an available event`
   | :sg:`poll() -> Event`

   Returns next event on queue. If there is no event waiting on the queue,
   this will return an event with type NOEVENT.

   .. ## pygame.fastevent.poll ##

.. function:: get

   | :sl:`get all events from the queue`
   | :sg:`get() -> list of Events`

   This will get all the messages and remove them from the queue.

   .. ## pygame.fastevent.get ##

.. function:: post

   | :sl:`place an event on the queue`
   | :sg:`post(Event) -> None`

   This will post your own event objects onto the event queue. You can post
   any event type you want, but some care must be taken. For example, if you
   post a MOUSEBUTTONDOWN event to the queue, it is likely any code receiving
   the event will expect the standard MOUSEBUTTONDOWN attributes to be
   available, like 'pos' and 'button'.

   Because pygame.fastevent.post() may have to wait for the queue to empty,
   you can get into a dead lock if you try to append an event on to a full
   queue from the thread that processes events. For that reason I do not
   recommend using this function in the main thread of an SDL program.

   .. ## pygame.fastevent.post ##

.. ## pygame.fastevent ##