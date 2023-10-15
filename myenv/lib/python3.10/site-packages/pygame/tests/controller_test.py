import unittest
import pygame
import pygame._sdl2.controller as controller
from pygame.tests.test_utils import prompt, question


class ControllerModuleTest(unittest.TestCase):
    def setUp(self):
        controller.init()

    def tearDown(self):
        controller.quit()

    def test_init(self):
        controller.quit()
        controller.init()
        self.assertTrue(controller.get_init())

    def test_init__multiple(self):
        controller.init()
        controller.init()
        self.assertTrue(controller.get_init())

    def test_quit(self):
        controller.quit()
        self.assertFalse(controller.get_init())

    def test_quit__multiple(self):
        controller.quit()
        controller.quit()
        self.assertFalse(controller.get_init())

    def test_get_init(self):
        self.assertTrue(controller.get_init())

    def test_get_eventstate(self):
        controller.set_eventstate(True)
        self.assertTrue(controller.get_eventstate())

        controller.set_eventstate(False)
        self.assertFalse(controller.get_eventstate())

        controller.set_eventstate(True)

    def test_get_count(self):
        self.assertGreaterEqual(controller.get_count(), 0)

    def test_is_controller(self):
        for i in range(controller.get_count()):
            if controller.is_controller(i):
                c = controller.Controller(i)
                self.assertIsInstance(c, controller.Controller)
                c.quit()
            else:
                with self.assertRaises(pygame._sdl2.sdl2.error):
                    c = controller.Controller(i)

        with self.assertRaises(TypeError):
            controller.is_controller("Test")

    def test_name_forindex(self):
        self.assertIsNone(controller.name_forindex(-1))


class ControllerTypeTest(unittest.TestCase):
    def setUp(self):
        controller.init()

    def tearDown(self):
        controller.quit()

    def _get_first_controller(self):
        for i in range(controller.get_count()):
            if controller.is_controller(i):
                return controller.Controller(i)

    def test_construction(self):
        c = self._get_first_controller()
        if c:
            self.assertIsInstance(c, controller.Controller)
        else:
            self.skipTest("No controller connected")

    def test__auto_init(self):
        c = self._get_first_controller()
        if c:
            self.assertTrue(c.get_init())
        else:
            self.skipTest("No controller connected")

    def test_get_init(self):
        c = self._get_first_controller()
        if c:
            self.assertTrue(c.get_init())
            c.quit()
            self.assertFalse(c.get_init())
        else:
            self.skipTest("No controller connected")

    def test_from_joystick(self):
        for i in range(controller.get_count()):
            if controller.is_controller(i):
                joy = pygame.joystick.Joystick(i)
                break
        else:
            self.skipTest("No controller connected")

        c = controller.Controller.from_joystick(joy)
        self.assertIsInstance(c, controller.Controller)

    def test_as_joystick(self):
        c = self._get_first_controller()
        if c:
            joy = c.as_joystick()
            self.assertIsInstance(joy, type(pygame.joystick.Joystick(0)))
        else:
            self.skipTest("No controller connected")

    def test_get_mapping(self):
        c = self._get_first_controller()
        if c:
            mapping = c.get_mapping()
            self.assertIsInstance(mapping, dict)
            self.assertIsNotNone(mapping["a"])
        else:
            self.skipTest("No controller connected")

    def test_set_mapping(self):
        c = self._get_first_controller()
        if c:
            mapping = c.get_mapping()
            mapping["a"] = "b3"
            mapping["y"] = "b0"
            c.set_mapping(mapping)
            new_mapping = c.get_mapping()

            self.assertEqual(len(mapping), len(new_mapping))
            for i in mapping:
                if mapping[i] not in ("a", "y"):
                    self.assertEqual(mapping[i], new_mapping[i])
                else:
                    if i == "a":
                        self.assertEqual(new_mapping[i], mapping["y"])
                    else:
                        self.assertEqual(new_mapping[i], mapping["a"])
        else:
            self.skipTest("No controller connected")


class ControllerInteractiveTest(unittest.TestCase):
    __tags__ = ["interactive"]

    def _get_first_controller(self):
        for i in range(controller.get_count()):
            if controller.is_controller(i):
                return controller.Controller(i)

    def setUp(self):
        controller.init()

    def tearDown(self):
        controller.quit()

    def test__get_count_interactive(self):
        prompt(
            "Please connect at least one controller "
            "before the test for controller.get_count() starts"
        )

        # Reset the number of joysticks counted
        controller.quit()
        controller.init()

        joystick_num = controller.get_count()
        ans = question(
            "get_count() thinks there are {} joysticks "
            "connected. Is that correct?".format(joystick_num)
        )

        self.assertTrue(ans)

    def test_set_eventstate_on_interactive(self):
        c = self._get_first_controller()
        if not c:
            self.skipTest("No controller connected")

        pygame.display.init()
        pygame.font.init()

        screen = pygame.display.set_mode((400, 400))
        font = pygame.font.Font(None, 20)
        running = True

        screen.fill((255, 255, 255))
        screen.blit(
            font.render("Press button 'x' (on ps4) or 'a' (on xbox).", True, (0, 0, 0)),
            (0, 0),
        )
        pygame.display.update()

        controller.set_eventstate(True)

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.CONTROLLERBUTTONDOWN:
                    running = False

        pygame.display.quit()
        pygame.font.quit()

    def test_set_eventstate_off_interactive(self):
        c = self._get_first_controller()
        if not c:
            self.skipTest("No controller connected")

        pygame.display.init()
        pygame.font.init()

        screen = pygame.display.set_mode((400, 400))
        font = pygame.font.Font(None, 20)
        running = True

        screen.fill((255, 255, 255))
        screen.blit(
            font.render("Press button 'x' (on ps4) or 'a' (on xbox).", True, (0, 0, 0)),
            (0, 0),
        )
        pygame.display.update()

        controller.set_eventstate(False)

        while running:
            for event in pygame.event.get(pygame.QUIT):
                if event:
                    running = False

            if c.get_button(pygame.CONTROLLER_BUTTON_A):
                if pygame.event.peek(pygame.CONTROLLERBUTTONDOWN):
                    pygame.display.quit()
                    pygame.font.quit()
                    self.fail()
                else:
                    running = False

        pygame.display.quit()
        pygame.font.quit()

    def test_get_button_interactive(self):
        c = self._get_first_controller()
        if not c:
            self.skipTest("No controller connected")

        pygame.display.init()
        pygame.font.init()

        screen = pygame.display.set_mode((400, 400))
        font = pygame.font.Font(None, 20)
        running = True

        label1 = font.render(
            "Press button 'x' (on ps4) or 'a' (on xbox).", True, (0, 0, 0)
        )

        label2 = font.render(
            'The two values should match up. Press "y" or "n" to confirm.',
            True,
            (0, 0, 0),
        )

        is_pressed = [False, False]  # event, get_button()
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.CONTROLLERBUTTONDOWN and event.button == 0:
                    is_pressed[0] = True
                if event.type == pygame.CONTROLLERBUTTONUP and event.button == 0:
                    is_pressed[0] = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_y:
                        running = False
                    if event.key == pygame.K_n:
                        running = False
                        pygame.display.quit()
                        pygame.font.quit()
                        self.fail()

            is_pressed[1] = c.get_button(pygame.CONTROLLER_BUTTON_A)

            screen.fill((255, 255, 255))
            screen.blit(label1, (0, 0))
            screen.blit(label2, (0, 20))
            screen.blit(font.render(str(is_pressed), True, (0, 0, 0)), (0, 40))
            pygame.display.update()

        pygame.display.quit()
        pygame.font.quit()

    def test_get_axis_interactive(self):
        c = self._get_first_controller()
        if not c:
            self.skipTest("No controller connected")

        pygame.display.init()
        pygame.font.init()

        screen = pygame.display.set_mode((400, 400))
        font = pygame.font.Font(None, 20)
        running = True

        label1 = font.render(
            "Press down the right trigger. The value on-screen should", True, (0, 0, 0)
        )

        label2 = font.render(
            "indicate how far the trigger is pressed down. This value should",
            True,
            (0, 0, 0),
        )

        label3 = font.render(
            'be in the range of 0-32767. Press "y" or "n" to confirm.', True, (0, 0, 0)
        )

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_y:
                        running = False
                    if event.key == pygame.K_n:
                        running = False
                        pygame.display.quit()
                        pygame.font.quit()
                        self.fail()

            right_trigger = c.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT)

            screen.fill((255, 255, 255))
            screen.blit(label1, (0, 0))
            screen.blit(label2, (0, 20))
            screen.blit(label3, (0, 40))
            screen.blit(font.render(str(right_trigger), True, (0, 0, 0)), (0, 60))
            pygame.display.update()

        pygame.display.quit()
        pygame.font.quit()


if __name__ == "__main__":
    unittest.main()
