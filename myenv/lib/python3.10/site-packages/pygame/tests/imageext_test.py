import os
import os.path
import sys
import unittest

from pygame.tests.test_utils import example_path
import pygame, pygame.image, pygame.pkgdata


imageext = sys.modules["pygame.imageext"]


class ImageextModuleTest(unittest.TestCase):
    # Most of the testing is done indirectly through image_test.py
    # This just confirms file path encoding and error handling.
    def test_save_non_string_file(self):
        im = pygame.Surface((10, 10), 0, 32)
        self.assertRaises(TypeError, imageext.save_extended, im, [])

    def test_load_non_string_file(self):
        self.assertRaises(TypeError, imageext.load_extended, [])

    @unittest.skip("SDL silently removes invalid characters")
    def test_save_bad_filename(self):
        im = pygame.Surface((10, 10), 0, 32)
        u = "a\x00b\x00c.png"
        self.assertRaises(pygame.error, imageext.save_extended, im, u)

    @unittest.skip("SDL silently removes invalid characters")
    def test_load_bad_filename(self):
        u = "a\x00b\x00c.png"
        self.assertRaises(pygame.error, imageext.load_extended, u)

    def test_save_unknown_extension(self):
        im = pygame.Surface((10, 10), 0, 32)
        s = "foo.bar"
        self.assertRaises(pygame.error, imageext.save_extended, im, s)

    def test_load_unknown_extension(self):
        s = "foo.bar"
        self.assertRaises(FileNotFoundError, imageext.load_extended, s)

    def test_load_unknown_file(self):
        s = "nonexistent.png"
        self.assertRaises(FileNotFoundError, imageext.load_extended, s)

    def test_load_unicode_path_0(self):
        u = example_path("data/alien1.png")
        im = imageext.load_extended(u)

    def test_load_unicode_path_1(self):
        """non-ASCII unicode"""
        import shutil

        orig = example_path("data/alien1.png")
        temp = os.path.join(example_path("data"), "你好.png")
        shutil.copy(orig, temp)
        try:
            im = imageext.load_extended(temp)
        finally:
            os.remove(temp)

    def _unicode_save(self, temp_file):
        im = pygame.Surface((10, 10), 0, 32)
        try:
            with open(temp_file, "w") as f:
                pass
            os.remove(temp_file)
        except OSError:
            raise unittest.SkipTest("the path cannot be opened")

        self.assertFalse(os.path.exists(temp_file))

        try:
            imageext.save_extended(im, temp_file)

            self.assertGreater(os.path.getsize(temp_file), 10)
        finally:
            try:
                os.remove(temp_file)
            except OSError:
                pass

    def test_save_unicode_path_0(self):
        """unicode object with ASCII chars"""
        self._unicode_save("temp_file.png")

    def test_save_unicode_path_1(self):
        self._unicode_save("你好.png")


if __name__ == "__main__":
    unittest.main()
