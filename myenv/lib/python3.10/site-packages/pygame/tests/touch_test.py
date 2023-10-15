import unittest
import os
import pygame
from pygame._sdl2 import touch
from pygame.tests.test_utils import question


has_touchdevice = touch.get_num_devices() > 0


class TouchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()

    @classmethod
    def tearDownClass(cls):
        pygame.display.quit()

    def test_num_devices(self):
        touch.get_num_devices()

    @unittest.skipIf(not has_touchdevice, "no touch devices found")
    def test_get_device(self):
        touch.get_device(0)

    def test_get_device__invalid(self):
        self.assertRaises(pygame.error, touch.get_device, -1234)
        self.assertRaises(TypeError, touch.get_device, "test")

    @unittest.skipIf(not has_touchdevice, "no touch devices found")
    def test_num_fingers(self):
        touch.get_num_fingers(touch.get_device(0))

    def test_num_fingers__invalid(self):
        self.assertRaises(TypeError, touch.get_num_fingers, "test")
        self.assertRaises(pygame.error, touch.get_num_fingers, -1234)


class TouchInteractiveTest(unittest.TestCase):
    __tags__ = ["interactive"]

    @unittest.skipIf(not has_touchdevice, "no touch devices found")
    def test_get_finger(self):
        """ask for touch input and check the dict"""

        pygame.display.init()
        pygame.font.init()

        os.environ["SDL_VIDEO_WINDOW_POS"] = "50,50"
        screen = pygame.display.set_mode((800, 600))
        screen.fill((255, 255, 255))

        font = pygame.font.Font(None, 32)
        instructions_str_1 = "Please place some fingers on your touch device"
        instructions_str_2 = (
            "Close the window when finished, " "and answer the question"
        )
        inst_1_render = font.render(instructions_str_1, True, pygame.Color("#000000"))
        inst_2_render = font.render(instructions_str_2, True, pygame.Color("#000000"))

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            finger_data_renders = []
            num_devices = pygame._sdl2.touch.get_num_devices()
            if num_devices > 0:
                first_device = pygame._sdl2.touch.get_device(0)
                num_fingers = pygame._sdl2.touch.get_num_fingers(first_device)
                if num_fingers > 0:
                    for finger_index in range(0, num_fingers):
                        data = pygame._sdl2.touch.get_finger(first_device, finger_index)
                        render = font.render(
                            f"finger - {data}", True, pygame.Color("#000000")
                        )

                        finger_data_renders.append(render)

            screen.fill((255, 255, 255))
            screen.blit(inst_1_render, (5, 5))
            screen.blit(inst_2_render, (5, 40))
            for index, finger in enumerate(finger_data_renders):
                screen.blit(finger, (5, 80 + (index * 40)))

            pygame.display.update()

        response = question("Does the finger data seem correct?")
        self.assertTrue(response)

        pygame.display.quit()


if __name__ == "__main__":
    unittest.main()
