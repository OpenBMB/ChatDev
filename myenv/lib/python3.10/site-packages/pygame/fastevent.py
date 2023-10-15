"""
A compatibility shim for pygame.fastevent based on pygame.event.
This module was deprecated in pygame 2.2, and is scheduled for removal in a
future pygame version. If you are using pygame.fastevent, please migrate to
using regular pygame.event module
"""

import pygame.event
import pygame.display
from pygame import error, register_quit
from pygame.event import Event

_ft_init = False


def _ft_init_check():
    """
    Raises error if module is not init
    """
    if not _ft_init:
        raise error("fastevent system not initialized")


def _quit_hook():
    """
    Hook that gets run to quit module
    """
    global _ft_init
    _ft_init = False


def init():
    """init() -> None
    initialize pygame.fastevent
    """
    global _ft_init
    if not pygame.display.get_init():
        raise error("video system not initialized")

    register_quit(_quit_hook)
    _ft_init = True


def get_init():
    """get_init() -> bool
    returns True if the fastevent module is currently initialized
    """
    return _ft_init


def pump():
    """pump() -> None
    internally process pygame event handlers
    """
    _ft_init_check()
    pygame.event.pump()


def wait():
    """wait() -> Event
    wait for an event
    """
    _ft_init_check()
    return pygame.event.wait()


def poll():
    """poll() -> Event
    get an available event
    """
    _ft_init_check()
    return pygame.event.poll()


def get():
    """get() -> list of Events
    get all events from the queue
    """
    _ft_init_check()
    return pygame.event.get()


def post(event: Event):
    """post(Event) -> None
    place an event on the queue
    """
    _ft_init_check()
    pygame.event.post(event)
