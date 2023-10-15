import unittest


import pygame


class MidiInputTest(unittest.TestCase):
    __tags__ = ["interactive"]

    def setUp(self):
        import pygame.midi

        pygame.midi.init()
        in_id = pygame.midi.get_default_input_id()
        if in_id != -1:
            self.midi_input = pygame.midi.Input(in_id)
        else:
            self.midi_input = None

    def tearDown(self):
        if self.midi_input:
            self.midi_input.close()
        pygame.midi.quit()

    def test_Input(self):
        i = pygame.midi.get_default_input_id()
        if self.midi_input:
            self.assertEqual(self.midi_input.device_id, i)

        # try feeding it an input id.
        i = pygame.midi.get_default_output_id()

        # can handle some invalid input too.
        self.assertRaises(pygame.midi.MidiException, pygame.midi.Input, i)
        self.assertRaises(pygame.midi.MidiException, pygame.midi.Input, 9009)
        self.assertRaises(pygame.midi.MidiException, pygame.midi.Input, -1)
        self.assertRaises(TypeError, pygame.midi.Input, "1234")
        self.assertRaises(OverflowError, pygame.midi.Input, pow(2, 99))

    def test_poll(self):
        if not self.midi_input:
            self.skipTest("No midi Input device")

        self.assertFalse(self.midi_input.poll())
        # TODO fake some incoming data

        pygame.midi.quit()
        self.assertRaises(RuntimeError, self.midi_input.poll)
        # set midi_input to None to avoid error in tearDown
        self.midi_input = None

    def test_read(self):
        if not self.midi_input:
            self.skipTest("No midi Input device")

        read = self.midi_input.read(5)
        self.assertEqual(read, [])
        # TODO fake some  incoming data

        pygame.midi.quit()
        self.assertRaises(RuntimeError, self.midi_input.read, 52)
        # set midi_input to None to avoid error in tearDown
        self.midi_input = None

    def test_close(self):
        if not self.midi_input:
            self.skipTest("No midi Input device")

        self.assertIsNotNone(self.midi_input._input)
        self.midi_input.close()
        self.assertIsNone(self.midi_input._input)


class MidiOutputTest(unittest.TestCase):
    __tags__ = ["interactive"]

    def setUp(self):
        import pygame.midi

        pygame.midi.init()
        m_out_id = pygame.midi.get_default_output_id()
        if m_out_id != -1:
            self.midi_output = pygame.midi.Output(m_out_id)
        else:
            self.midi_output = None

    def tearDown(self):
        if self.midi_output:
            self.midi_output.close()
        pygame.midi.quit()

    def test_Output(self):
        i = pygame.midi.get_default_output_id()
        if self.midi_output:
            self.assertEqual(self.midi_output.device_id, i)

        # try feeding it an input id.
        i = pygame.midi.get_default_input_id()

        # can handle some invalid input too.
        self.assertRaises(pygame.midi.MidiException, pygame.midi.Output, i)
        self.assertRaises(pygame.midi.MidiException, pygame.midi.Output, 9009)
        self.assertRaises(pygame.midi.MidiException, pygame.midi.Output, -1)
        self.assertRaises(TypeError, pygame.midi.Output, "1234")
        self.assertRaises(OverflowError, pygame.midi.Output, pow(2, 99))

    def test_note_off(self):
        if self.midi_output:
            out = self.midi_output
            out.note_on(5, 30, 0)
            out.note_off(5, 30, 0)
            with self.assertRaises(ValueError) as cm:
                out.note_off(5, 30, 25)
            self.assertEqual(str(cm.exception), "Channel not between 0 and 15.")
            with self.assertRaises(ValueError) as cm:
                out.note_off(5, 30, -1)
            self.assertEqual(str(cm.exception), "Channel not between 0 and 15.")

    def test_note_on(self):
        if self.midi_output:
            out = self.midi_output
            out.note_on(5, 30, 0)
            out.note_on(5, 42, 10)
            with self.assertRaises(ValueError) as cm:
                out.note_on(5, 30, 25)
            self.assertEqual(str(cm.exception), "Channel not between 0 and 15.")
            with self.assertRaises(ValueError) as cm:
                out.note_on(5, 30, -1)
            self.assertEqual(str(cm.exception), "Channel not between 0 and 15.")

    def test_set_instrument(self):
        if not self.midi_output:
            self.skipTest("No midi device")
        out = self.midi_output
        out.set_instrument(5)
        out.set_instrument(42, channel=2)
        with self.assertRaises(ValueError) as cm:
            out.set_instrument(-6)
        self.assertEqual(str(cm.exception), "Undefined instrument id: -6")
        with self.assertRaises(ValueError) as cm:
            out.set_instrument(156)
        self.assertEqual(str(cm.exception), "Undefined instrument id: 156")
        with self.assertRaises(ValueError) as cm:
            out.set_instrument(5, -1)
        self.assertEqual(str(cm.exception), "Channel not between 0 and 15.")
        with self.assertRaises(ValueError) as cm:
            out.set_instrument(5, 16)
        self.assertEqual(str(cm.exception), "Channel not between 0 and 15.")

    def test_write(self):
        if not self.midi_output:
            self.skipTest("No midi device")

        out = self.midi_output
        out.write([[[0xC0, 0, 0], 20000]])
        # is equivalent to
        out.write([[[0xC0], 20000]])
        # example from the docstring :
        # 1. choose program change 1 at time 20000 and
        # 2. send note 65 with velocity 100 500 ms later
        out.write([[[0xC0, 0, 0], 20000], [[0x90, 60, 100], 20500]])

        out.write([])
        verrry_long = [[[0x90, 60, i % 100], 20000 + 100 * i] for i in range(1024)]
        out.write(verrry_long)

        too_long = [[[0x90, 60, i % 100], 20000 + 100 * i] for i in range(1025)]
        self.assertRaises(IndexError, out.write, too_long)
        # test wrong data
        with self.assertRaises(TypeError) as cm:
            out.write("Non sens ?")
        error_msg = "unsupported operand type(s) for &: 'str' and 'int'"
        self.assertEqual(str(cm.exception), error_msg)

        with self.assertRaises(TypeError) as cm:
            out.write(["Hey what's that?"])
        self.assertEqual(str(cm.exception), error_msg)

    def test_write_short(self):
        if not self.midi_output:
            self.skipTest("No midi device")

        out = self.midi_output
        # program change
        out.write_short(0xC0)
        # put a note on, then off.
        out.write_short(0x90, 65, 100)
        out.write_short(0x80, 65, 100)
        out.write_short(0x90)

    def test_write_sys_ex(self):
        if not self.midi_output:
            self.skipTest("No midi device")

        out = self.midi_output
        out.write_sys_ex(pygame.midi.time(), [0xF0, 0x7D, 0x10, 0x11, 0x12, 0x13, 0xF7])

    def test_pitch_bend(self):
        # FIXME : pitch_bend in the code, but not in documentation
        if not self.midi_output:
            self.skipTest("No midi device")

        out = self.midi_output
        with self.assertRaises(ValueError) as cm:
            out.pitch_bend(5, channel=-1)
        self.assertEqual(str(cm.exception), "Channel not between 0 and 15.")
        with self.assertRaises(ValueError) as cm:
            out.pitch_bend(5, channel=16)
        with self.assertRaises(ValueError) as cm:
            out.pitch_bend(-10001, 1)
        self.assertEqual(
            str(cm.exception),
            "Pitch bend value must be between " "-8192 and +8191, not -10001.",
        )
        with self.assertRaises(ValueError) as cm:
            out.pitch_bend(10665, 2)

    def test_close(self):
        if not self.midi_output:
            self.skipTest("No midi device")
        self.assertIsNotNone(self.midi_output._output)
        self.midi_output.close()
        self.assertIsNone(self.midi_output._output)

    def test_abort(self):
        if not self.midi_output:
            self.skipTest("No midi device")
        self.assertEqual(self.midi_output._aborted, 0)
        self.midi_output.abort()
        self.assertEqual(self.midi_output._aborted, 1)


class MidiModuleTest(unittest.TestCase):
    """Midi module tests that require midi hardware or midi.init().

    See MidiModuleNonInteractiveTest for non-interactive module tests.
    """

    __tags__ = ["interactive"]

    def setUp(self):
        import pygame.midi

        pygame.midi.init()

    def tearDown(self):
        pygame.midi.quit()

    def test_get_count(self):
        c = pygame.midi.get_count()
        self.assertIsInstance(c, int)
        self.assertTrue(c >= 0)

    def test_get_default_input_id(self):
        midin_id = pygame.midi.get_default_input_id()
        # if there is a not None return make sure it is an int.
        self.assertIsInstance(midin_id, int)
        self.assertTrue(midin_id >= -1)
        pygame.midi.quit()
        self.assertRaises(RuntimeError, pygame.midi.get_default_output_id)

    def test_get_default_output_id(self):
        c = pygame.midi.get_default_output_id()
        self.assertIsInstance(c, int)
        self.assertTrue(c >= -1)
        pygame.midi.quit()
        self.assertRaises(RuntimeError, pygame.midi.get_default_output_id)

    def test_get_device_info(self):
        an_id = pygame.midi.get_default_output_id()
        if an_id != -1:
            interf, name, input, output, opened = pygame.midi.get_device_info(an_id)
            self.assertEqual(output, 1)
            self.assertEqual(input, 0)
            self.assertEqual(opened, 0)

        an_in_id = pygame.midi.get_default_input_id()
        if an_in_id != -1:
            r = pygame.midi.get_device_info(an_in_id)
            # if r is None, it means that the id is out of range.
            interf, name, input, output, opened = r

            self.assertEqual(output, 0)
            self.assertEqual(input, 1)
            self.assertEqual(opened, 0)
        out_of_range = pygame.midi.get_count()
        for num in range(out_of_range):
            self.assertIsNotNone(pygame.midi.get_device_info(num))
        info = pygame.midi.get_device_info(out_of_range)
        self.assertIsNone(info)

    def test_init(self):
        pygame.midi.quit()
        self.assertRaises(RuntimeError, pygame.midi.get_count)
        # initialising many times should be fine.
        pygame.midi.init()
        pygame.midi.init()
        pygame.midi.init()
        pygame.midi.init()

        self.assertTrue(pygame.midi.get_init())

    def test_quit(self):
        # It is safe to call this more than once.
        pygame.midi.quit()
        pygame.midi.init()
        pygame.midi.quit()
        pygame.midi.quit()
        pygame.midi.init()
        pygame.midi.init()
        pygame.midi.quit()

        self.assertFalse(pygame.midi.get_init())

    def test_get_init(self):
        # Already initialized as pygame.midi.init() was called in setUp().
        self.assertTrue(pygame.midi.get_init())

    def test_time(self):
        mtime = pygame.midi.time()
        self.assertIsInstance(mtime, int)
        # should be close to 2-3... since the timer is just init'd.
        self.assertTrue(0 <= mtime < 100)


class MidiModuleNonInteractiveTest(unittest.TestCase):
    """Midi module tests that do not require midi hardware or midi.init().

    See MidiModuleTest for interactive module tests.
    """

    def setUp(self):
        import pygame.midi

    def test_midiin(self):
        """Ensures the MIDIIN event id exists in the midi module.

        The MIDIIN event id can be accessed via the midi module for backward
        compatibility.
        """
        self.assertEqual(pygame.midi.MIDIIN, pygame.MIDIIN)
        self.assertEqual(pygame.midi.MIDIIN, pygame.locals.MIDIIN)

        self.assertNotEqual(pygame.midi.MIDIIN, pygame.MIDIOUT)
        self.assertNotEqual(pygame.midi.MIDIIN, pygame.locals.MIDIOUT)

    def test_midiout(self):
        """Ensures the MIDIOUT event id exists in the midi module.

        The MIDIOUT event id can be accessed via the midi module for backward
        compatibility.
        """
        self.assertEqual(pygame.midi.MIDIOUT, pygame.MIDIOUT)
        self.assertEqual(pygame.midi.MIDIOUT, pygame.locals.MIDIOUT)

        self.assertNotEqual(pygame.midi.MIDIOUT, pygame.MIDIIN)
        self.assertNotEqual(pygame.midi.MIDIOUT, pygame.locals.MIDIIN)

    def test_MidiException(self):
        """Ensures the MidiException is raised as expected."""

        def raiseit():
            raise pygame.midi.MidiException("Hello Midi param")

        with self.assertRaises(pygame.midi.MidiException) as cm:
            raiseit()

        self.assertEqual(cm.exception.parameter, "Hello Midi param")

    def test_midis2events(self):
        """Ensures midi events are properly converted to pygame events."""
        # List/tuple indexes.
        MIDI_DATA = 0
        MD_STATUS = 0
        MD_DATA1 = 1
        MD_DATA2 = 2
        MD_DATA3 = 3

        TIMESTAMP = 1

        # Midi events take the form of:
        # ((status, data1, data2, data3), timestamp)
        midi_events = (
            ((0xC0, 0, 1, 2), 20000),
            ((0x90, 60, 1000, "string_data"), 20001),
            (("0", "1", "2", "3"), "4"),
        )
        expected_num_events = len(midi_events)

        # Test different device ids.
        for device_id in range(3):
            pg_events = pygame.midi.midis2events(midi_events, device_id)

            self.assertEqual(len(pg_events), expected_num_events)

            for i, pg_event in enumerate(pg_events):
                # Get the original midi data for comparison.
                midi_event = midi_events[i]
                midi_event_data = midi_event[MIDI_DATA]

                # Can't directly check event instance as pygame.event.Event is
                # a function.
                # self.assertIsInstance(pg_event, pygame.event.Event)
                self.assertEqual(pg_event.__class__.__name__, "Event")
                self.assertEqual(pg_event.type, pygame.MIDIIN)
                self.assertEqual(pg_event.status, midi_event_data[MD_STATUS])
                self.assertEqual(pg_event.data1, midi_event_data[MD_DATA1])
                self.assertEqual(pg_event.data2, midi_event_data[MD_DATA2])
                self.assertEqual(pg_event.data3, midi_event_data[MD_DATA3])
                self.assertEqual(pg_event.timestamp, midi_event[TIMESTAMP])
                self.assertEqual(pg_event.vice_id, device_id)

    def test_midis2events__missing_event_data(self):
        """Ensures midi events with missing values are handled properly."""
        midi_event_missing_data = ((0xC0, 0, 1), 20000)
        midi_event_missing_timestamp = ((0xC0, 0, 1, 2),)

        for midi_event in (midi_event_missing_data, midi_event_missing_timestamp):
            with self.assertRaises(ValueError):
                events = pygame.midi.midis2events([midi_event], 0)

    def test_midis2events__extra_event_data(self):
        """Ensures midi events with extra values are handled properly."""
        midi_event_extra_data = ((0xC0, 0, 1, 2, "extra"), 20000)
        midi_event_extra_timestamp = ((0xC0, 0, 1, 2), 20000, "extra")

        for midi_event in (midi_event_extra_data, midi_event_extra_timestamp):
            with self.assertRaises(ValueError):
                events = pygame.midi.midis2events([midi_event], 0)

    def test_midis2events__extra_event_data_missing_timestamp(self):
        """Ensures midi events with extra data and no timestamps are handled
        properly.
        """
        midi_event_extra_data_no_timestamp = ((0xC0, 0, 1, 2, "extra"),)

        with self.assertRaises(ValueError):
            events = pygame.midi.midis2events([midi_event_extra_data_no_timestamp], 0)

    def test_conversions(self):
        """of frequencies to midi note numbers and ansi note names."""
        from pygame.midi import frequency_to_midi, midi_to_frequency, midi_to_ansi_note

        self.assertEqual(frequency_to_midi(27.5), 21)
        self.assertEqual(frequency_to_midi(36.7), 26)
        self.assertEqual(frequency_to_midi(4186.0), 108)
        self.assertEqual(midi_to_frequency(21), 27.5)
        self.assertEqual(midi_to_frequency(26), 36.7)
        self.assertEqual(midi_to_frequency(108), 4186.0)
        self.assertEqual(midi_to_ansi_note(21), "A0")
        self.assertEqual(midi_to_ansi_note(71), "B4")
        self.assertEqual(midi_to_ansi_note(82), "A#5")
        self.assertEqual(midi_to_ansi_note(83), "B5")
        self.assertEqual(midi_to_ansi_note(93), "A6")
        self.assertEqual(midi_to_ansi_note(94), "A#6")
        self.assertEqual(midi_to_ansi_note(95), "B6")
        self.assertEqual(midi_to_ansi_note(96), "C7")
        self.assertEqual(midi_to_ansi_note(102), "F#7")
        self.assertEqual(midi_to_ansi_note(108), "C8")


if __name__ == "__main__":
    unittest.main()
