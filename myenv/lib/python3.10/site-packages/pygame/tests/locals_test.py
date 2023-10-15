import unittest

import pygame.constants
import pygame.locals


class LocalsTest(unittest.TestCase):
    def test_locals_has_all_constants(self):
        constants_set = set(pygame.constants.__all__)
        locals_set = set(pygame.locals.__all__)

        # locals should have everything that constants has
        self.assertEqual(constants_set - locals_set, set())


if __name__ == "__main__":
    unittest.main()
