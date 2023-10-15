import collections
import time
import unittest
import os

import pygame

EVENT_TYPES = (
    #   pygame.NOEVENT,
    #   pygame.ACTIVEEVENT,
    pygame.KEYDOWN,
    pygame.KEYUP,
    pygame.MOUSEMOTION,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
    pygame.JOYAXISMOTION,
    pygame.JOYBALLMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
    pygame.VIDEORESIZE,
    pygame.VIDEOEXPOSE,
    pygame.QUIT,
    pygame.SYSWMEVENT,
    pygame.USEREVENT,
    #   pygame.NUMEVENTS,
)

EVENT_TEST_PARAMS = collections.defaultdict(dict)
EVENT_TEST_PARAMS.update(
    {
        pygame.KEYDOWN: {"key": pygame.K_SPACE},
        pygame.KEYUP: {"key": pygame.K_SPACE},
        pygame.MOUSEMOTION: dict(),
        pygame.MOUSEBUTTONDOWN: dict(button=1),
        pygame.MOUSEBUTTONUP: dict(button=1),
    }
)


NAMES_AND_EVENTS = (
    ("NoEvent", pygame.NOEVENT),
    ("ActiveEvent", pygame.ACTIVEEVENT),
    ("KeyDown", pygame.KEYDOWN),
    ("KeyUp", pygame.KEYUP),
    ("MouseMotion", pygame.MOUSEMOTION),
    ("MouseButtonDown", pygame.MOUSEBUTTONDOWN),
    ("MouseButtonUp", pygame.MOUSEBUTTONUP),
    ("JoyAxisMotion", pygame.JOYAXISMOTION),
    ("JoyBallMotion", pygame.JOYBALLMOTION),
    ("JoyHatMotion", pygame.JOYHATMOTION),
    ("JoyButtonDown", pygame.JOYBUTTONDOWN),
    ("JoyButtonUp", pygame.JOYBUTTONUP),
    ("VideoResize", pygame.VIDEORESIZE),
    ("VideoExpose", pygame.VIDEOEXPOSE),
    ("Quit", pygame.QUIT),
    ("SysWMEvent", pygame.SYSWMEVENT),
    ("MidiIn", pygame.MIDIIN),
    ("MidiOut", pygame.MIDIOUT),
    ("UserEvent", pygame.USEREVENT),
    ("Unknown", 0xFFFF),
    ("FingerMotion", pygame.FINGERMOTION),
    ("FingerDown", pygame.FINGERDOWN),
    ("FingerUp", pygame.FINGERUP),
    ("MultiGesture", pygame.MULTIGESTURE),
    ("MouseWheel", pygame.MOUSEWHEEL),
    ("TextInput", pygame.TEXTINPUT),
    ("TextEditing", pygame.TEXTEDITING),
    ("ControllerAxisMotion", pygame.CONTROLLERAXISMOTION),
    ("ControllerButtonDown", pygame.CONTROLLERBUTTONDOWN),
    ("ControllerButtonUp", pygame.CONTROLLERBUTTONUP),
    ("ControllerDeviceAdded", pygame.CONTROLLERDEVICEADDED),
    ("ControllerDeviceRemoved", pygame.CONTROLLERDEVICEREMOVED),
    ("ControllerDeviceMapped", pygame.CONTROLLERDEVICEREMAPPED),
    ("DropFile", pygame.DROPFILE),
    ("AudioDeviceAdded", pygame.AUDIODEVICEADDED),
    ("AudioDeviceRemoved", pygame.AUDIODEVICEREMOVED),
    ("DropText", pygame.DROPTEXT),
    ("DropBegin", pygame.DROPBEGIN),
    ("DropComplete", pygame.DROPCOMPLETE),
)


class EventTypeTest(unittest.TestCase):
    def test_Event(self):
        """Ensure an Event object can be created."""
        e = pygame.event.Event(pygame.USEREVENT, some_attr=1, other_attr="1")

        self.assertEqual(e.some_attr, 1)
        self.assertEqual(e.other_attr, "1")

        # Event now uses tp_dictoffset and tp_members:
        # https://github.com/pygame/pygame/issues/62
        self.assertEqual(e.type, pygame.USEREVENT)
        self.assertIs(e.dict, e.__dict__)

        e.some_attr = 12

        self.assertEqual(e.some_attr, 12)

        e.new_attr = 15

        self.assertEqual(e.new_attr, 15)

        self.assertRaises(AttributeError, setattr, e, "type", 0)
        self.assertRaises(AttributeError, setattr, e, "dict", None)

        # Ensure attributes are visible to dir(), part of the original
        # posted request.
        d = dir(e)
        attrs = ("type", "dict", "__dict__", "some_attr", "other_attr", "new_attr")

        for attr in attrs:
            self.assertIn(attr, d)

        # redundant type field as kwarg
        self.assertRaises(ValueError, pygame.event.Event, 10, type=100)

    def test_as_str(self):
        # Bug reported on Pygame mailing list July 24, 2011:
        # For Python 3.x str(event) to raises an UnicodeEncodeError when
        # an event attribute is a string with a non-ascii character.
        try:
            str(pygame.event.Event(EVENT_TYPES[0], a="\xed"))
        except UnicodeEncodeError:
            self.fail("Event object raised exception for non-ascii character")
        # Passed.

    def test_event_bool(self):
        self.assertFalse(pygame.event.Event(pygame.NOEVENT))
        for event_type in [
            pygame.MOUSEBUTTONDOWN,
            pygame.ACTIVEEVENT,
            pygame.WINDOWLEAVE,
            pygame.USEREVENT_DROPFILE,
        ]:
            self.assertTrue(pygame.event.Event(event_type))

    def test_event_equality(self):
        """Ensure that events can be compared correctly."""
        a = pygame.event.Event(EVENT_TYPES[0], a=1)
        b = pygame.event.Event(EVENT_TYPES[0], a=1)
        c = pygame.event.Event(EVENT_TYPES[1], a=1)
        d = pygame.event.Event(EVENT_TYPES[0], a=2)

        self.assertTrue(a == a)
        self.assertFalse(a != a)
        self.assertTrue(a == b)
        self.assertFalse(a != b)
        self.assertTrue(a != c)
        self.assertFalse(a == c)
        self.assertTrue(a != d)
        self.assertFalse(a == d)


race_condition_notification = """
This test is dependent on timing. The event queue is cleared in preparation for
tests. There is a small window where outside events from the OS may have effected
results. Try running the test again.
"""


class EventModuleArgsTest(unittest.TestCase):
    def setUp(self):
        pygame.display.init()
        pygame.event.clear()

    def tearDown(self):
        pygame.display.quit()

    def test_get(self):
        pygame.event.get()
        pygame.event.get(None)
        pygame.event.get(None, True)

        pygame.event.get(pump=False)
        pygame.event.get(pump=True)
        pygame.event.get(eventtype=None)
        pygame.event.get(eventtype=[pygame.KEYUP, pygame.KEYDOWN])
        pygame.event.get(eventtype=pygame.USEREVENT, pump=False)

        # event type out of range
        self.assertRaises(ValueError, pygame.event.get, 0x00010000)
        self.assertRaises(TypeError, pygame.event.get, 1 + 2j)
        self.assertRaises(TypeError, pygame.event.get, "foo")

    def test_clear(self):
        pygame.event.clear()
        pygame.event.clear(None)
        pygame.event.clear(None, True)

        pygame.event.clear(pump=False)
        pygame.event.clear(pump=True)
        pygame.event.clear(eventtype=None)
        pygame.event.clear(eventtype=[pygame.KEYUP, pygame.KEYDOWN])
        pygame.event.clear(eventtype=pygame.USEREVENT, pump=False)

        # event type out of range
        self.assertRaises(ValueError, pygame.event.clear, 0x0010FFFFF)
        self.assertRaises(TypeError, pygame.event.get, ["a", "b", "c"])

    def test_peek(self):
        pygame.event.peek()
        pygame.event.peek(None)
        pygame.event.peek(None, True)

        pygame.event.peek(pump=False)
        pygame.event.peek(pump=True)
        pygame.event.peek(eventtype=None)
        pygame.event.peek(eventtype=[pygame.KEYUP, pygame.KEYDOWN])
        pygame.event.peek(eventtype=pygame.USEREVENT, pump=False)

        class Foo:
            pass

        # event type out of range
        self.assertRaises(ValueError, pygame.event.peek, -1)
        self.assertRaises(ValueError, pygame.event.peek, [-10])
        self.assertRaises(TypeError, pygame.event.peek, Foo())


class EventCustomTypeTest(unittest.TestCase):
    """Those tests are special in that they need the _custom_event counter to
    be reset before and/or after being run."""

    def setUp(self):
        pygame.quit()
        pygame.init()
        pygame.display.init()

    def tearDown(self):
        pygame.quit()

    def test_custom_type(self):
        self.assertEqual(pygame.event.custom_type(), pygame.USEREVENT + 1)
        atype = pygame.event.custom_type()
        atype2 = pygame.event.custom_type()

        self.assertEqual(atype, atype2 - 1)

        ev = pygame.event.Event(atype)
        pygame.event.post(ev)
        queue = pygame.event.get(atype)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].type, atype)

    def test_custom_type__end_boundary(self):
        """Ensure custom_type() raises error when no more custom types.

        The last allowed custom type number should be (pygame.NUMEVENTS - 1).
        """
        last = -1
        start = pygame.event.custom_type() + 1
        for _ in range(start, pygame.NUMEVENTS):
            last = pygame.event.custom_type()

        self.assertEqual(last, pygame.NUMEVENTS - 1)
        with self.assertRaises(pygame.error):
            pygame.event.custom_type()

    def test_custom_type__reset(self):
        """Ensure custom events get 'deregistered' by quit()."""
        before = pygame.event.custom_type()
        self.assertEqual(before, pygame.event.custom_type() - 1)
        pygame.quit()
        pygame.init()
        pygame.display.init()
        self.assertEqual(before, pygame.event.custom_type())


class EventModuleTest(unittest.TestCase):
    def _assertCountEqual(self, *args, **kwargs):
        # Handle method name differences between Python versions.
        # Is this still needed?
        self.assertCountEqual(*args, **kwargs)

    def _assertExpectedEvents(self, expected, got):
        """Find events like expected events, raise on unexpected or missing,
        ignore additional event properties if expected properties are present."""

        # This does greedy matching, don't encode an NP-hard problem
        # into your input data, *please*
        items_left = got[:]
        for expected_element in expected:
            for item in items_left:
                for key in expected_element.__dict__:
                    if item.__dict__[key] != expected_element.__dict__[key]:
                        break
                else:
                    # found item!
                    items_left.remove(item)
                    break
            else:
                raise AssertionError(
                    "Expected "
                    + str(expected_element)
                    + " among remaining events "
                    + str(items_left)
                    + " out of "
                    + str(got)
                )
        if len(items_left) > 0:
            raise AssertionError("Unexpected Events: " + str(items_left))

    def setUp(self):
        pygame.display.init()
        pygame.event.clear()  # flush events

    def tearDown(self):
        pygame.event.clear()  # flush events
        pygame.display.quit()

    def test_event_numevents(self):
        """Ensures NUMEVENTS does not exceed the maximum SDL number of events."""
        # Ref: https://www.libsdl.org/tmp/SDL/include/SDL_events.h
        MAX_SDL_EVENTS = 0xFFFF  # SDL_LASTEVENT = 0xFFFF

        self.assertLessEqual(pygame.NUMEVENTS, MAX_SDL_EVENTS)

    def test_event_attribute(self):
        e1 = pygame.event.Event(pygame.USEREVENT, attr1="attr1")
        self.assertEqual(e1.attr1, "attr1")

    def test_set_blocked(self):
        """Ensure events can be blocked from the queue."""
        event = EVENT_TYPES[0]
        unblocked_event = EVENT_TYPES[1]
        pygame.event.set_blocked(event)

        self.assertTrue(pygame.event.get_blocked(event))
        self.assertFalse(pygame.event.get_blocked(unblocked_event))

        posted = pygame.event.post(
            pygame.event.Event(event, **EVENT_TEST_PARAMS[event])
        )
        self.assertFalse(posted)

        # post an unblocked event
        posted = pygame.event.post(
            pygame.event.Event(unblocked_event, **EVENT_TEST_PARAMS[unblocked_event])
        )
        self.assertTrue(posted)

        ret = pygame.event.get()
        should_be_blocked = [e for e in ret if e.type == event]
        should_be_allowed_types = [e.type for e in ret if e.type != event]

        self.assertEqual(should_be_blocked, [])
        self.assertTrue(unblocked_event in should_be_allowed_types)

    def test_set_blocked__event_sequence(self):
        """Ensure a sequence of event types can be blocked."""
        event_types = [
            pygame.KEYDOWN,
            pygame.KEYUP,
            pygame.MOUSEMOTION,
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.WINDOWFOCUSLOST,
            pygame.USEREVENT,
        ]

        pygame.event.set_blocked(event_types)

        for etype in event_types:
            self.assertTrue(pygame.event.get_blocked(etype))

    def test_set_blocked_all(self):
        """Ensure all events can be unblocked at once."""
        pygame.event.set_blocked(None)

        for e in EVENT_TYPES:
            self.assertTrue(pygame.event.get_blocked(e))

    def test_post__and_poll(self):
        """Ensure events can be posted to the queue."""
        e1 = pygame.event.Event(pygame.USEREVENT, attr1="attr1")
        pygame.event.post(e1)
        posted_event = pygame.event.poll()

        self.assertEqual(e1.attr1, posted_event.attr1, race_condition_notification)

        # fuzzing event types
        for i in range(1, 13):
            pygame.event.post(
                pygame.event.Event(EVENT_TYPES[i], **EVENT_TEST_PARAMS[EVENT_TYPES[i]])
            )

            self.assertEqual(
                pygame.event.poll().type, EVENT_TYPES[i], race_condition_notification
            )

    def test_post_and_get_keydown(self):
        """Ensure keydown events can be posted to the queue."""
        activemodkeys = pygame.key.get_mods()

        events = [
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y, mod=activemodkeys),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g, unicode="g"),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode=None),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_m, mod=None, window=None),
            pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_e, mod=activemodkeys, unicode="e"
            ),
        ]

        for e in events:
            pygame.event.post(e)
            posted_event = pygame.event.poll()
            self.assertEqual(e, posted_event, race_condition_notification)

    def test_post_large_user_event(self):
        pygame.event.post(
            pygame.event.Event(
                pygame.USEREVENT, {"a": "a" * 1024}, test=list(range(100))
            )
        )
        e = pygame.event.poll()

        self.assertEqual(e.type, pygame.USEREVENT)
        self.assertEqual(e.a, "a" * 1024)
        self.assertEqual(e.test, list(range(100)))

    def test_post_blocked(self):
        """
        Test blocked events are not posted. Also test whether post()
        returns a boolean correctly
        """
        pygame.event.set_blocked(pygame.USEREVENT)
        self.assertFalse(pygame.event.post(pygame.event.Event(pygame.USEREVENT)))
        self.assertFalse(pygame.event.poll())
        pygame.event.set_allowed(pygame.USEREVENT)
        self.assertTrue(pygame.event.post(pygame.event.Event(pygame.USEREVENT)))
        self.assertEqual(pygame.event.poll(), pygame.event.Event(pygame.USEREVENT))

    def test_get(self):
        """Ensure get() retrieves all the events on the queue."""
        event_cnt = 10
        for _ in range(event_cnt):
            pygame.event.post(pygame.event.Event(pygame.USEREVENT))

        queue = pygame.event.get()

        self.assertEqual(len(queue), event_cnt)
        self.assertTrue(all(e.type == pygame.USEREVENT for e in queue))

    def test_get_type(self):
        ev = pygame.event.Event(pygame.USEREVENT)
        pygame.event.post(ev)
        queue = pygame.event.get(pygame.USEREVENT)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].type, pygame.USEREVENT)

        TESTEVENTS = 10
        for _ in range(TESTEVENTS):
            pygame.event.post(ev)
        q = pygame.event.get([pygame.USEREVENT])
        self.assertEqual(len(q), TESTEVENTS)
        for event in q:
            self.assertEqual(event, ev)

    def test_get_exclude_throw(self):
        self.assertRaises(
            pygame.error, pygame.event.get, pygame.KEYDOWN, False, pygame.KEYUP
        )

    def test_get_exclude(self):
        pygame.event.post(pygame.event.Event(pygame.USEREVENT))
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN))

        queue = pygame.event.get(exclude=pygame.KEYDOWN)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].type, pygame.USEREVENT)

        pygame.event.post(pygame.event.Event(pygame.KEYUP))
        pygame.event.post(pygame.event.Event(pygame.USEREVENT))
        queue = pygame.event.get(exclude=(pygame.KEYDOWN, pygame.KEYUP))
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0].type, pygame.USEREVENT)

        queue = pygame.event.get()
        self.assertEqual(len(queue), 2)

    def test_get__empty_queue(self):
        """Ensure get() works correctly on an empty queue."""
        expected_events = []
        pygame.event.clear()

        # Ensure all events can be checked.
        retrieved_events = pygame.event.get()

        self.assertListEqual(retrieved_events, expected_events)

        # Ensure events can be checked individually.
        for event_type in EVENT_TYPES:
            retrieved_events = pygame.event.get(event_type)

            self.assertListEqual(retrieved_events, expected_events)

        # Ensure events can be checked as a sequence.
        retrieved_events = pygame.event.get(EVENT_TYPES)

        self.assertListEqual(retrieved_events, expected_events)

    def test_get__event_sequence(self):
        """Ensure get() can handle a sequence of event types."""
        event_types = [pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEMOTION]
        other_event_type = pygame.MOUSEBUTTONUP

        # Test when no events in the queue.
        expected_events = []
        pygame.event.clear()
        retrieved_events = pygame.event.get(event_types)

        # don't use self._assertCountEqual here. This checks for
        # expected properties in events, and ignores unexpected ones, for
        # forward compatibility with SDL2.
        self._assertExpectedEvents(expected=expected_events, got=retrieved_events)

        # Test when an event type not in the list is in the queue.
        expected_events = []
        pygame.event.clear()
        pygame.event.post(
            pygame.event.Event(other_event_type, **EVENT_TEST_PARAMS[other_event_type])
        )

        retrieved_events = pygame.event.get(event_types)

        self._assertExpectedEvents(expected=expected_events, got=retrieved_events)

        # Test when 1 event type in the list is in the queue.
        expected_events = [
            pygame.event.Event(event_types[0], **EVENT_TEST_PARAMS[event_types[0]])
        ]
        pygame.event.clear()
        pygame.event.post(expected_events[0])

        retrieved_events = pygame.event.get(event_types)

        self._assertExpectedEvents(expected=expected_events, got=retrieved_events)

        # Test all events in the list are in the queue.
        pygame.event.clear()
        expected_events = []

        for etype in event_types:
            expected_events.append(
                pygame.event.Event(etype, **EVENT_TEST_PARAMS[etype])
            )
            pygame.event.post(expected_events[-1])

        retrieved_events = pygame.event.get(event_types)

        self._assertExpectedEvents(expected=expected_events, got=retrieved_events)

    def test_get_clears_queue(self):
        """Ensure get() clears the event queue after a call"""
        pygame.event.get()  # should clear the queue completely by getting all events
        self.assertEqual(pygame.event.get(), [])

    def test_clear(self):
        """Ensure clear() removes all the events on the queue."""
        for e in EVENT_TYPES:
            pygame.event.post(pygame.event.Event(e, **EVENT_TEST_PARAMS[e]))
        poll_event = pygame.event.poll()

        self.assertNotEqual(poll_event.type, pygame.NOEVENT)

        pygame.event.clear()
        poll_event = pygame.event.poll()

        self.assertEqual(poll_event.type, pygame.NOEVENT, race_condition_notification)

    def test_clear__empty_queue(self):
        """Ensure clear() works correctly on an empty queue."""
        expected_events = []
        pygame.event.clear()

        # Test calling clear() on an already empty queue.
        pygame.event.clear()

        retrieved_events = pygame.event.get()

        self.assertListEqual(retrieved_events, expected_events)

    def test_clear__event_sequence(self):
        """Ensure a sequence of event types can be cleared from the queue."""
        cleared_event_types = EVENT_TYPES[:5]
        expected_event_types = EVENT_TYPES[5:10]
        expected_events = []

        # Add the events to the queue.
        for etype in cleared_event_types:
            pygame.event.post(pygame.event.Event(etype, **EVENT_TEST_PARAMS[etype]))

        for etype in expected_events:
            expected_events.append(
                pygame.event.Event(etype, **EVENT_TEST_PARAMS[etype])
            )
            pygame.event.post(expected_events[-1])

        # Clear the cleared_events from the queue.
        pygame.event.clear(cleared_event_types)

        # Check the rest of the events in the queue.
        remaining_events = pygame.event.get()

        self._assertCountEqual(remaining_events, expected_events)

    def test_event_name(self):
        """Ensure event_name() returns the correct event name."""
        for expected_name, event in NAMES_AND_EVENTS:
            self.assertEqual(
                pygame.event.event_name(event), expected_name, f"0x{event:X}"
            )

    def test_event_name__userevent_range(self):
        """Ensures event_name() returns the correct name for user events.

        Tests the full range of user events.
        """
        expected_name = "UserEvent"

        for event in range(pygame.USEREVENT, pygame.NUMEVENTS):
            self.assertEqual(
                pygame.event.event_name(event), expected_name, f"0x{event:X}"
            )

    def test_event_name__userevent_boundary(self):
        """Ensures event_name() does not return 'UserEvent' for events
        just outside the user event range.
        """
        unexpected_name = "UserEvent"

        for event in (pygame.USEREVENT - 1, pygame.NUMEVENTS):
            self.assertNotEqual(
                pygame.event.event_name(event), unexpected_name, f"0x{event:X}"
            )

    def test_event_name__kwargs(self):
        """Ensure event_name() returns the correct event name when kwargs used."""
        for expected_name, event in NAMES_AND_EVENTS:
            self.assertEqual(
                pygame.event.event_name(type=event), expected_name, f"0x{event:X}"
            )

    def test_peek(self):
        """Ensure queued events can be peeked at."""
        event_types = [pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEMOTION]

        for event_type in event_types:
            pygame.event.post(
                pygame.event.Event(event_type, **EVENT_TEST_PARAMS[event_type])
            )

        # Ensure events can be checked individually.
        for event_type in event_types:
            self.assertTrue(pygame.event.peek(event_type))

        # Ensure events can be checked as a sequence.
        self.assertTrue(pygame.event.peek(event_types))

    def test_peek__event_sequence(self):
        """Ensure peek() can handle a sequence of event types."""
        event_types = [pygame.KEYDOWN, pygame.KEYUP, pygame.MOUSEMOTION]
        other_event_type = pygame.MOUSEBUTTONUP

        # Test when no events in the queue.
        pygame.event.clear()
        peeked = pygame.event.peek(event_types)

        self.assertFalse(peeked)

        # Test when an event type not in the list is in the queue.
        pygame.event.clear()
        pygame.event.post(
            pygame.event.Event(other_event_type, **EVENT_TEST_PARAMS[other_event_type])
        )

        peeked = pygame.event.peek(event_types)

        self.assertFalse(peeked)

        # Test when 1 event type in the list is in the queue.
        pygame.event.clear()
        pygame.event.post(
            pygame.event.Event(event_types[0], **EVENT_TEST_PARAMS[event_types[0]])
        )

        peeked = pygame.event.peek(event_types)

        self.assertTrue(peeked)

        # Test all events in the list are in the queue.
        pygame.event.clear()
        for etype in event_types:
            pygame.event.post(pygame.event.Event(etype, **EVENT_TEST_PARAMS[etype]))

        peeked = pygame.event.peek(event_types)

        self.assertTrue(peeked)

    def test_peek__empty_queue(self):
        """Ensure peek() works correctly on an empty queue."""
        pygame.event.clear()

        # Ensure all events can be checked.
        peeked = pygame.event.peek()

        self.assertFalse(peeked)

        # Ensure events can be checked individually.
        for event_type in EVENT_TYPES:
            peeked = pygame.event.peek(event_type)
            self.assertFalse(peeked)

        # Ensure events can be checked as a sequence.
        peeked = pygame.event.peek(EVENT_TYPES)

        self.assertFalse(peeked)

    def test_set_allowed(self):
        """Ensure a blocked event type can be unblocked/allowed."""
        event = EVENT_TYPES[0]
        pygame.event.set_blocked(event)

        self.assertTrue(pygame.event.get_blocked(event))

        pygame.event.set_allowed(event)

        self.assertFalse(pygame.event.get_blocked(event))

    def test_set_allowed__event_sequence(self):
        """Ensure a sequence of blocked event types can be unblocked/allowed."""
        event_types = [
            pygame.KEYDOWN,
            pygame.KEYUP,
            pygame.MOUSEMOTION,
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
        ]
        pygame.event.set_blocked(event_types)

        pygame.event.set_allowed(event_types)

        for etype in event_types:
            self.assertFalse(pygame.event.get_blocked(etype))

    def test_set_allowed_all(self):
        """Ensure all events can be unblocked/allowed at once."""
        pygame.event.set_blocked(None)

        for e in EVENT_TYPES:
            self.assertTrue(pygame.event.get_blocked(e))

        pygame.event.set_allowed(None)

        for e in EVENT_TYPES:
            self.assertFalse(pygame.event.get_blocked(e))

    def test_pump(self):
        """Ensure pump() functions properly."""
        pygame.event.pump()

    # @unittest.skipIf(
    #     os.environ.get("SDL_VIDEODRIVER") == "dummy",
    #     'requires the SDL_VIDEODRIVER to be a non "dummy" value',
    # )
    # Fails on SDL 2.0.18
    @unittest.skip("flaky test, and broken on 2.0.18 windows")
    def test_set_grab__and_get_symmetric(self):
        """Ensure event grabbing can be enabled and disabled.

        WARNING: Moving the mouse off the display during this test can cause it
                 to fail.
        """
        surf = pygame.display.set_mode((10, 10))
        pygame.event.set_grab(True)

        self.assertTrue(pygame.event.get_grab())

        pygame.event.set_grab(False)

        self.assertFalse(pygame.event.get_grab())

    def test_get_blocked(self):
        """Ensure an event's blocked state can be retrieved."""
        # Test each event is not blocked.
        pygame.event.set_allowed(None)

        for etype in EVENT_TYPES:
            blocked = pygame.event.get_blocked(etype)

            self.assertFalse(blocked)

        # Test each event type is blocked.
        pygame.event.set_blocked(None)

        for etype in EVENT_TYPES:
            blocked = pygame.event.get_blocked(etype)

            self.assertTrue(blocked)

    def test_get_blocked__event_sequence(self):
        """Ensure get_blocked() can handle a sequence of event types."""
        event_types = [
            pygame.KEYDOWN,
            pygame.KEYUP,
            pygame.MOUSEMOTION,
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.WINDOWMINIMIZED,
            pygame.USEREVENT,
        ]

        # Test no event types in the list are blocked.
        blocked = pygame.event.get_blocked(event_types)

        self.assertFalse(blocked)

        # Test when 1 event type in the list is blocked.
        pygame.event.set_blocked(event_types[2])

        blocked = pygame.event.get_blocked(event_types)

        self.assertTrue(blocked)

        # Test all event types in the list are blocked.
        pygame.event.set_blocked(event_types)

        blocked = pygame.event.get_blocked(event_types)

        self.assertTrue(blocked)

    # @unittest.skipIf(
    #     os.environ.get("SDL_VIDEODRIVER") == "dummy",
    #     'requires the SDL_VIDEODRIVER to be a non "dummy" value',
    # )
    # Fails on SDL 2.0.18
    @unittest.skip("flaky test, and broken on 2.0.18 windows")
    def test_get_grab(self):
        """Ensure get_grab() works as expected"""
        surf = pygame.display.set_mode((10, 10))
        # Test 5 times
        for i in range(5):
            pygame.event.set_grab(i % 2)
            self.assertEqual(pygame.event.get_grab(), i % 2)

    @unittest.skipIf(
        os.environ.get("SDL_VIDEODRIVER") == "dummy",
        "requires the SDL_VIDEODRIVER to be a non dummy value",
    )
    @unittest.skipIf(pygame.get_sdl_version() < (2, 0, 16), "Needs at least SDL 2.0.16")
    def test_set_keyboard_grab_and_get_keyboard_grab(self):
        """Ensure set_keyboard_grab() and get_keyboard_grab() work as expected"""

        surf = pygame.display.set_mode((10, 10))

        pygame.event.set_keyboard_grab(True)
        self.assertTrue(pygame.event.get_keyboard_grab())

        pygame.event.set_keyboard_grab(False)
        self.assertFalse(pygame.event.get_keyboard_grab())

    def test_poll(self):
        """Ensure poll() works as expected"""
        pygame.event.clear()
        ev = pygame.event.poll()
        # poll() on empty queue should return NOEVENT
        self.assertEqual(ev.type, pygame.NOEVENT)

        # test poll returns stuff in same order
        e1 = pygame.event.Event(pygame.USEREVENT)
        e2 = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)
        e3 = pygame.event.Event(pygame.KEYUP, key=pygame.K_a)
        pygame.event.post(e1)
        pygame.event.post(e2)
        pygame.event.post(e3)

        self.assertEqual(pygame.event.poll().type, e1.type)
        self.assertEqual(pygame.event.poll().type, e2.type)
        self.assertEqual(pygame.event.poll().type, e3.type)
        self.assertEqual(pygame.event.poll().type, pygame.NOEVENT)


class EventModuleTestsWithTiming(unittest.TestCase):
    __tags__ = ["timing"]

    def setUp(self):
        pygame.display.init()
        pygame.event.clear()  # flush events

    def tearDown(self):
        pygame.event.clear()  # flush events
        pygame.display.quit()

    def test_event_wait(self):
        """Ensure wait() waits for an event on the queue."""
        # Test case without timeout.
        event = pygame.event.Event(EVENT_TYPES[0], **EVENT_TEST_PARAMS[EVENT_TYPES[0]])
        pygame.event.post(event)
        wait_event = pygame.event.wait()

        self.assertEqual(wait_event.type, event.type)

        # Test case with timeout and no event in the queue.
        wait_event = pygame.event.wait(100)
        self.assertEqual(wait_event.type, pygame.NOEVENT)

        # Test case with timeout and an event in the queue.
        event = pygame.event.Event(EVENT_TYPES[0], **EVENT_TEST_PARAMS[EVENT_TYPES[0]])
        pygame.event.post(event)
        wait_event = pygame.event.wait(100)

        self.assertEqual(wait_event.type, event.type)

        # test wait with timeout waits for the correct duration
        pygame.time.set_timer(pygame.USEREVENT, 50, 3)

        for wait_time, expected_type, expected_time in (
            (60, pygame.USEREVENT, 50),
            (65, pygame.USEREVENT, 50),
            (20, pygame.NOEVENT, 20),
            (45, pygame.USEREVENT, 30),
            (70, pygame.NOEVENT, 70),
        ):
            start_time = time.perf_counter()
            self.assertEqual(pygame.event.wait(wait_time).type, expected_type)
            self.assertAlmostEqual(
                time.perf_counter() - start_time, expected_time / 1000, delta=0.01
            )

        # test wait without timeout waits for the full duration
        pygame.time.set_timer(pygame.USEREVENT, 100, 1)

        start_time = time.perf_counter()
        self.assertEqual(pygame.event.wait().type, pygame.USEREVENT)
        self.assertAlmostEqual(time.perf_counter() - start_time, 0.1, delta=0.01)

        # test wait returns no event if event is arriving later
        pygame.time.set_timer(pygame.USEREVENT, 50, 1)
        self.assertEqual(pygame.event.wait(40).type, pygame.NOEVENT)


################################################################################

if __name__ == "__main__":
    unittest.main()
