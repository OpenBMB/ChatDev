import unittest
from pygame.tests.test_utils import question, prompt

import pygame
import pygame._sdl2.controller


class JoystickTypeTest(unittest.TestCase):
    def todo_test_Joystick(self):
        # __doc__ (as of 2008-08-02) for pygame.joystick.Joystick:

        # pygame.joystick.Joystick(id): return Joystick
        # create a new Joystick object
        #
        # Create a new joystick to access a physical device. The id argument
        # must be a value from 0 to pygame.joystick.get_count()-1.
        #
        # To access most of the Joystick methods, you'll need to init() the
        # Joystick. This is separate from making sure the joystick module is
        # initialized. When multiple Joysticks objects are created for the
        # same physical joystick device (i.e., they have the same ID number),
        # the state and values for those Joystick objects will be shared.
        #
        # The Joystick object allows you to get information about the types of
        # controls on a joystick device. Once the device is initialized the
        # Pygame event queue will start receiving events about its input.
        #
        # You can call the Joystick.get_name() and Joystick.get_id() functions
        # without initializing the Joystick object.
        #

        self.fail()


class JoystickModuleTest(unittest.TestCase):
    def test_get_init(self):
        # Check that get_init() matches what is actually happening
        def error_check_get_init():
            try:
                pygame.joystick.get_count()
            except pygame.error:
                return False
            return True

        # Start uninitialised
        self.assertEqual(pygame.joystick.get_init(), False)

        pygame.joystick.init()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # True
        pygame.joystick.quit()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # False

        pygame.joystick.init()
        pygame.joystick.init()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # True
        pygame.joystick.quit()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # False

        pygame.joystick.quit()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # False

        for i in range(100):
            pygame.joystick.init()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # True
        pygame.joystick.quit()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # False

        for i in range(100):
            pygame.joystick.quit()
        self.assertEqual(pygame.joystick.get_init(), error_check_get_init())  # False

    def test_init(self):
        """
        This unit test is for joystick.init()
        It was written to help reduce maintenance costs
        and to help test against changes to the code or
        different platforms.
        """
        pygame.quit()
        # test that pygame.init automatically calls joystick.init
        pygame.init()
        self.assertEqual(pygame.joystick.get_init(), True)

        # Controller module interferes with the joystick module.
        pygame._sdl2.controller.quit()

        # test that get_count doesn't work w/o joystick init
        # this is done before and after an init to test
        # that init activates the joystick functions
        pygame.joystick.quit()
        with self.assertRaises(pygame.error):
            pygame.joystick.get_count()

        # test explicit call(s) to joystick.init.
        # Also test that get_count works once init is called
        iterations = 20
        for i in range(iterations):
            pygame.joystick.init()
        self.assertEqual(pygame.joystick.get_init(), True)
        self.assertIsNotNone(pygame.joystick.get_count())

    def test_quit(self):
        """Test if joystick.quit works."""

        pygame.joystick.init()

        self.assertIsNotNone(pygame.joystick.get_count())  # Is not None before quit

        pygame.joystick.quit()

        with self.assertRaises(pygame.error):  # Raises error if quit worked
            pygame.joystick.get_count()

    def test_get_count(self):
        # Test that get_count correctly returns a non-negative number of joysticks
        pygame.joystick.init()

        try:
            count = pygame.joystick.get_count()
            self.assertGreaterEqual(
                count, 0, ("joystick.get_count() must " "return a value >= 0")
            )
        finally:
            pygame.joystick.quit()


class JoystickInteractiveTest(unittest.TestCase):
    __tags__ = ["interactive"]

    def test_get_count_interactive(self):
        # Test get_count correctly identifies number of connected joysticks
        prompt(
            "Please connect any joysticks/controllers now before starting the "
            "joystick.get_count() test."
        )

        pygame.joystick.init()
        # pygame.joystick.get_count(): return count
        # number of joysticks on the system, 0 means no joysticks connected
        count = pygame.joystick.get_count()

        response = question(
            "NOTE: Having Steam open may add an extra virtual controller for "
            "each joystick/controller physically plugged in.\n"
            f"joystick.get_count() thinks there is [{count}] joystick(s)/controller(s)"
            "connected to this system. Is this correct?"
        )

        self.assertTrue(response)

        # When you create Joystick objects using Joystick(id), you pass an
        # integer that must be lower than this count.
        # Test Joystick(id) for each connected joystick
        if count != 0:
            for x in range(count):
                pygame.joystick.Joystick(x)
            with self.assertRaises(pygame.error):
                pygame.joystick.Joystick(count)

        pygame.joystick.quit()


################################################################################

if __name__ == "__main__":
    unittest.main()
