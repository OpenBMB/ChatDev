import os
import platform
import unittest
import pygame
import time

Clock = pygame.time.Clock


class ClockTypeTest(unittest.TestCase):
    __tags__ = ["timing"]

    def test_construction(self):
        """Ensure a Clock object can be created"""
        c = Clock()

        self.assertTrue(c, "Clock cannot be constructed")

    def test_get_fps(self):
        """test_get_fps tests pygame.time.get_fps()"""
        # Initialization check, first call should return 0 fps
        c = Clock()
        self.assertEqual(c.get_fps(), 0)
        # Type check get_fps should return float
        self.assertTrue(type(c.get_fps()) == float)
        # Allowable margin of error in percentage
        delta = 0.30
        # Test fps correctness for 100, 60 and 30 fps
        self._fps_test(c, 100, delta)
        self._fps_test(c, 60, delta)
        self._fps_test(c, 30, delta)

    def _fps_test(self, clock, fps, delta):
        """ticks fps times each second, hence get_fps() should return fps"""
        delay_per_frame = 1.0 / fps
        for f in range(fps):  # For one second tick and sleep
            clock.tick()
            time.sleep(delay_per_frame)
        # We should get around fps (+- fps*delta -- delta % of fps)
        self.assertAlmostEqual(clock.get_fps(), fps, delta=fps * delta)

    def test_get_rawtime(self):
        iterations = 10
        delay = 0.1
        delay_miliseconds = delay * (10**3)  # actual time difference between ticks
        framerate_limit = 5
        delta = 50  # allowable error in milliseconds

        # Testing Clock Initialization
        c = Clock()
        self.assertEqual(c.get_rawtime(), 0)

        # Testing Raw Time with Frame Delay
        for f in range(iterations):
            time.sleep(delay)
            c.tick(framerate_limit)
            c1 = c.get_rawtime()
            self.assertAlmostEqual(delay_miliseconds, c1, delta=delta)

        # Testing get_rawtime() = get_time()
        for f in range(iterations):
            time.sleep(delay)
            c.tick()
            c1 = c.get_rawtime()
            c2 = c.get_time()
            self.assertAlmostEqual(c1, c2, delta=delta)

    @unittest.skipIf(platform.machine() == "s390x", "Fails on s390x")
    @unittest.skipIf(
        os.environ.get("CI", None), "CI can have variable time slices, slow."
    )
    def test_get_time(self):
        # Testing parameters
        delay = 0.1  # seconds
        delay_miliseconds = delay * (10**3)
        iterations = 10
        delta = 50  # milliseconds

        # Testing Clock Initialization
        c = Clock()
        self.assertEqual(c.get_time(), 0)

        # Testing within delay parameter range
        for i in range(iterations):
            time.sleep(delay)
            c.tick()
            c1 = c.get_time()
            self.assertAlmostEqual(delay_miliseconds, c1, delta=delta)

        # Comparing get_time() results with the 'time' module
        for i in range(iterations):
            t0 = time.time()
            time.sleep(delay)
            c.tick()
            t1 = time.time()
            c1 = c.get_time()  # elapsed time in milliseconds
            d0 = (t1 - t0) * (
                10**3
            )  #'time' module elapsed time converted to milliseconds
            self.assertAlmostEqual(d0, c1, delta=delta)

    @unittest.skipIf(platform.machine() == "s390x", "Fails on s390x")
    @unittest.skipIf(
        os.environ.get("CI", None), "CI can have variable time slices, slow."
    )
    def test_tick(self):
        """Tests time.Clock.tick()"""
        """
        Loops with a set delay a few times then checks what tick reports to
        verify its accuracy. Then calls tick with a desired frame-rate and
        verifies it is not faster than the desired frame-rate nor is it taking
        a dramatically long time to complete
        """

        # Adjust this value to increase the acceptable sleep jitter
        epsilon = 5  # 1.5

        # Adjust this value to increase the acceptable locked frame-rate jitter
        epsilon2 = 0.3
        # adjust this value to increase the acceptable frame-rate margin
        epsilon3 = 20
        testing_framerate = 60
        milliseconds = 5.0

        collection = []
        c = Clock()

        # verify time.Clock.tick() will measure the time correctly
        c.tick()
        for i in range(100):
            time.sleep(milliseconds / 1000)  # convert to seconds
            collection.append(c.tick())

        # removes the first highest and lowest value
        for outlier in [min(collection), max(collection)]:
            if outlier != milliseconds:
                collection.remove(outlier)

        average_time = float(sum(collection)) / len(collection)

        # assert the deviation from the intended frame-rate is within the
        # acceptable amount (the delay is not taking a dramatically long time)
        self.assertAlmostEqual(average_time, milliseconds, delta=epsilon)

        # verify tick will control the frame-rate

        c = Clock()
        collection = []

        start = time.time()

        for i in range(testing_framerate):
            collection.append(c.tick(testing_framerate))

        # remove the highest and lowest outliers
        for outlier in [min(collection), max(collection)]:
            if outlier != round(1000 / testing_framerate):
                collection.remove(outlier)

        end = time.time()

        # Since calling tick with a desired fps will prevent the program from
        # running at greater than the given fps, 100 iterations at 100 fps
        # should last no less than 1 second
        self.assertAlmostEqual(end - start, 1, delta=epsilon2)

        average_tick_time = float(sum(collection)) / len(collection)
        self.assertAlmostEqual(
            1000 / average_tick_time, testing_framerate, delta=epsilon3
        )

    def test_tick_busy_loop(self):
        """Test tick_busy_loop"""

        c = Clock()

        # Test whether the return value of tick_busy_loop is equal to
        # (FPS is accurate) or greater than (slower than the set FPS)
        # with a small margin for error based on differences in how this
        # test runs in practise - it either sometimes runs slightly fast
        # or seems to based on a rounding error.
        second_length = 1000
        shortfall_tolerance = 1  # (ms) The amount of time a tick is allowed to run short of, to account for underlying rounding errors
        sample_fps = 40

        self.assertGreaterEqual(
            c.tick_busy_loop(sample_fps),
            (second_length / sample_fps) - shortfall_tolerance,
        )
        pygame.time.wait(10)  # incur delay between ticks that's faster than sample_fps
        self.assertGreaterEqual(
            c.tick_busy_loop(sample_fps),
            (second_length / sample_fps) - shortfall_tolerance,
        )
        pygame.time.wait(200)  # incur delay between ticks that's slower than sample_fps
        self.assertGreaterEqual(
            c.tick_busy_loop(sample_fps),
            (second_length / sample_fps) - shortfall_tolerance,
        )

        high_fps = 500
        self.assertGreaterEqual(
            c.tick_busy_loop(high_fps), (second_length / high_fps) - shortfall_tolerance
        )

        low_fps = 1
        self.assertGreaterEqual(
            c.tick_busy_loop(low_fps), (second_length / low_fps) - shortfall_tolerance
        )

        low_non_factor_fps = 35  # 1000/35 makes 28.5714285714
        frame_length_without_decimal_places = int(
            second_length / low_non_factor_fps
        )  # Same result as math.floor
        self.assertGreaterEqual(
            c.tick_busy_loop(low_non_factor_fps),
            frame_length_without_decimal_places - shortfall_tolerance,
        )

        high_non_factor_fps = 750  # 1000/750 makes 1.3333...
        frame_length_without_decimal_places_2 = int(
            second_length / high_non_factor_fps
        )  # Same result as math.floor
        self.assertGreaterEqual(
            c.tick_busy_loop(high_non_factor_fps),
            frame_length_without_decimal_places_2 - shortfall_tolerance,
        )

        zero_fps = 0
        self.assertEqual(c.tick_busy_loop(zero_fps), 0)

        # Check behaviour of unexpected values

        negative_fps = -1
        self.assertEqual(c.tick_busy_loop(negative_fps), 0)

        fractional_fps = 32.75
        frame_length_without_decimal_places_3 = int(second_length / fractional_fps)
        self.assertGreaterEqual(
            c.tick_busy_loop(fractional_fps),
            frame_length_without_decimal_places_3 - shortfall_tolerance,
        )

        bool_fps = True
        self.assertGreaterEqual(
            c.tick_busy_loop(bool_fps), (second_length / bool_fps) - shortfall_tolerance
        )


class TimeModuleTest(unittest.TestCase):
    __tags__ = ["timing"]

    @unittest.skipIf(platform.machine() == "s390x", "Fails on s390x")
    @unittest.skipIf(
        os.environ.get("CI", None), "CI can have variable time slices, slow."
    )
    def test_delay(self):
        """Tests time.delay() function."""
        millis = 50  # millisecond to wait on each iteration
        iterations = 20  # number of iterations
        delta = 150  # Represents acceptable margin of error for wait in ms
        # Call checking function
        self._wait_delay_check(pygame.time.delay, millis, iterations, delta)
        # After timing behaviour, check argument type exceptions
        self._type_error_checks(pygame.time.delay)

    def test_get_ticks(self):
        """Tests time.get_ticks()"""
        """
         Iterates and delays for arbitrary amount of time for each iteration,
         check get_ticks to equal correct gap time
        """
        iterations = 20
        millis = 50
        delta = 15  # Acceptable margin of error in ms
        # Assert return type to be int
        self.assertTrue(type(pygame.time.get_ticks()) == int)
        for i in range(iterations):
            curr_ticks = pygame.time.get_ticks()  # Save current tick count
            curr_time = time.time()  # Save current time
            pygame.time.delay(millis)  # Delay for millis
            # Time and Ticks difference from start of the iteration
            time_diff = round((time.time() - curr_time) * 1000)
            ticks_diff = pygame.time.get_ticks() - curr_ticks
            # Assert almost equality of the ticking time and time difference
            self.assertAlmostEqual(ticks_diff, time_diff, delta=delta)

    @unittest.skipIf(platform.machine() == "s390x", "Fails on s390x")
    @unittest.skipIf(
        os.environ.get("CI", None), "CI can have variable time slices, slow."
    )
    def test_set_timer(self):
        """Tests time.set_timer()"""
        """
        Tests if a timer will post the correct amount of eventid events in
        the specified delay. Test is posting event objects work.
        Also tests if setting milliseconds to 0 stops the timer and if
        the once argument and repeat arguments work.
        """
        pygame.init()
        TIMER_EVENT_TYPE = pygame.event.custom_type()
        timer_event = pygame.event.Event(TIMER_EVENT_TYPE)
        delta = 50
        timer_delay = 100
        test_number = 8  # Number of events to read for the test
        events = 0  # Events read

        pygame.event.clear()
        pygame.time.set_timer(TIMER_EVENT_TYPE, timer_delay)

        # Test that 'test_number' events are posted in the right amount of time
        t1 = pygame.time.get_ticks()
        max_test_time = t1 + timer_delay * test_number + delta
        while events < test_number:
            for event in pygame.event.get():
                if event == timer_event:
                    events += 1

            # The test takes too much time
            if pygame.time.get_ticks() > max_test_time:
                break

        pygame.time.set_timer(TIMER_EVENT_TYPE, 0)
        t2 = pygame.time.get_ticks()
        # Is the number ef events and the timing right?
        self.assertEqual(events, test_number)
        self.assertAlmostEqual(timer_delay * test_number, t2 - t1, delta=delta)

        # Test that the timer stopped when set with 0ms delay.
        pygame.time.delay(200)
        self.assertNotIn(timer_event, pygame.event.get())

        # Test that the old timer for an event is deleted when a new timer is set
        pygame.time.set_timer(TIMER_EVENT_TYPE, timer_delay)
        pygame.time.delay(int(timer_delay * 3.5))
        self.assertEqual(pygame.event.get().count(timer_event), 3)
        pygame.time.set_timer(TIMER_EVENT_TYPE, timer_delay * 10)  # long wait time
        pygame.time.delay(timer_delay * 5)
        self.assertNotIn(timer_event, pygame.event.get())
        pygame.time.set_timer(TIMER_EVENT_TYPE, timer_delay * 3)
        pygame.time.delay(timer_delay * 7)
        self.assertEqual(pygame.event.get().count(timer_event), 2)
        pygame.time.set_timer(TIMER_EVENT_TYPE, timer_delay)
        pygame.time.delay(int(timer_delay * 5.5))
        self.assertEqual(pygame.event.get().count(timer_event), 5)

        # Test that the loops=True works
        pygame.time.set_timer(TIMER_EVENT_TYPE, 10, True)
        pygame.time.delay(40)
        self.assertEqual(pygame.event.get().count(timer_event), 1)

        # Test a variety of event objects, test loops argument
        events_to_test = [
            pygame.event.Event(TIMER_EVENT_TYPE),
            pygame.event.Event(
                TIMER_EVENT_TYPE, foo="9gwz5", baz=12, lol=[124, (34, "")]
            ),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a"),
        ]
        repeat = 3
        millis = 50
        for e in events_to_test:
            pygame.time.set_timer(e, millis, loops=repeat)
            pygame.time.delay(2 * millis * repeat)
            self.assertEqual(pygame.event.get().count(e), repeat)
        pygame.quit()

    def test_wait(self):
        """Tests time.wait() function."""
        millis = 100  # millisecond to wait on each iteration
        iterations = 10  # number of iterations
        delta = 50  # Represents acceptable margin of error for wait in ms
        # Call checking function
        self._wait_delay_check(pygame.time.wait, millis, iterations, delta)
        # After timing behaviour, check argument type exceptions
        self._type_error_checks(pygame.time.wait)

    def _wait_delay_check(self, func_to_check, millis, iterations, delta):
        """ "
        call func_to_check(millis) "iterations" times and check each time if
        function "waited" for given millisecond (+- delta). At the end, take
        average time for each call (whole_duration/iterations), which should
        be equal to millis (+- delta - acceptable margin of error).
        *Created to avoid code duplication during delay and wait tests
        """
        # take starting time for duration calculation
        start_time = time.time()
        for i in range(iterations):
            wait_time = func_to_check(millis)
            # Check equality of wait_time and millis with margin of error delta
            self.assertAlmostEqual(wait_time, millis, delta=delta)
        stop_time = time.time()
        # Cycle duration in millisecond
        duration = round((stop_time - start_time) * 1000)
        # Duration/Iterations should be (almost) equal to predefined millis
        self.assertAlmostEqual(duration / iterations, millis, delta=delta)

    def _type_error_checks(self, func_to_check):
        """Checks 3 TypeError (float, tuple, string) for the func_to_check"""
        """Intended for time.delay and time.wait functions"""
        # Those methods throw no exceptions on negative integers
        self.assertRaises(TypeError, func_to_check, 0.1)  # check float
        self.assertRaises(TypeError, pygame.time.delay, (0, 1))  # check tuple
        self.assertRaises(TypeError, pygame.time.delay, "10")  # check string


###############################################################################

if __name__ == "__main__":
    unittest.main()
