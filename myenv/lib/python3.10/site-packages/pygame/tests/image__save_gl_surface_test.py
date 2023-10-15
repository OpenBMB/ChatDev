import os
import unittest

from pygame.tests import test_utils
import pygame
from pygame.locals import *


@unittest.skipIf(
    os.environ.get("SDL_VIDEODRIVER") == "dummy",
    'OpenGL requires a non-"dummy" SDL_VIDEODRIVER',
)
class GL_ImageSave(unittest.TestCase):
    def test_image_save_works_with_opengl_surfaces(self):
        """
        |tags:display,slow,opengl|
        """

        pygame.display.init()
        screen = pygame.display.set_mode((640, 480), OPENGL | DOUBLEBUF)
        pygame.display.flip()

        tmp_dir = test_utils.get_tmp_dir()
        # Try the imageext module.
        tmp_file = os.path.join(tmp_dir, "opengl_save_surface_test.png")
        pygame.image.save(screen, tmp_file)

        self.assertTrue(os.path.exists(tmp_file))

        os.remove(tmp_file)

        # Only test the image module.
        tmp_file = os.path.join(tmp_dir, "opengl_save_surface_test.bmp")
        pygame.image.save(screen, tmp_file)

        self.assertTrue(os.path.exists(tmp_file))

        os.remove(tmp_file)

        # stops tonnes of tmp dirs building up in trunk dir
        os.rmdir(tmp_dir)
        pygame.display.quit()


if __name__ == "__main__":
    unittest.main()
