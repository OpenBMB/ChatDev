import os
import sys

if os.environ.get("SDL_VIDEODRIVER") == "dummy":
    __tags__ = ("ignore", "subprocess_ignore")
import unittest
from pygame.tests.test_utils import trunk_relative_path

import pygame
from pygame import scrap


class ScrapModuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((1, 1))
        scrap.init()

    @classmethod
    def tearDownClass(cls):
        # scrap.quit()  # Does not exist!
        pygame.display.quit()

    def test_init(self):
        """Ensures scrap module still initialized after multiple init calls."""
        scrap.init()
        scrap.init()

        self.assertTrue(scrap.get_init())

    def test_init__reinit(self):
        """Ensures reinitializing the scrap module doesn't clear its data."""
        data_type = pygame.SCRAP_TEXT
        expected_data = b"test_init__reinit"
        scrap.put(data_type, expected_data)

        scrap.init()

        self.assertEqual(scrap.get(data_type), expected_data)

    def test_get_init(self):
        """Ensures get_init gets the init state."""
        self.assertTrue(scrap.get_init())

    def todo_test_contains(self):
        """Ensures contains works as expected."""
        self.fail()

    def todo_test_get(self):
        """Ensures get works as expected."""
        self.fail()

    def test_get__owned_empty_type(self):
        """Ensures get works when there is no data of the requested type
        in the clipboard and the clipboard is owned by the pygame application.
        """
        # Use a unique data type identifier to ensure there is no preexisting
        # data.
        DATA_TYPE = "test_get__owned_empty_type"

        if scrap.lost():
            # Try to acquire the clipboard.
            scrap.put(pygame.SCRAP_TEXT, b"text to clipboard")

            if scrap.lost():
                self.skipTest("requires the pygame application to own the clipboard")

        data = scrap.get(DATA_TYPE)

        self.assertIsNone(data)

    def todo_test_get_types(self):
        """Ensures get_types works as expected."""
        self.fail()

    def todo_test_lost(self):
        """Ensures lost works as expected."""
        self.fail()

    def test_set_mode(self):
        """Ensures set_mode works as expected."""
        scrap.set_mode(pygame.SCRAP_SELECTION)
        scrap.set_mode(pygame.SCRAP_CLIPBOARD)

        self.assertRaises(ValueError, scrap.set_mode, 1099)

    def test_put__text(self):
        """Ensures put can place text into the clipboard."""
        scrap.put(pygame.SCRAP_TEXT, b"Hello world")

        self.assertEqual(scrap.get(pygame.SCRAP_TEXT), b"Hello world")

        scrap.put(pygame.SCRAP_TEXT, b"Another String")

        self.assertEqual(scrap.get(pygame.SCRAP_TEXT), b"Another String")

    @unittest.skipIf("pygame.image" not in sys.modules, "requires pygame.image module")
    def test_put__bmp_image(self):
        """Ensures put can place a BMP image into the clipboard."""
        sf = pygame.image.load(trunk_relative_path("examples/data/asprite.bmp"))
        expected_string = pygame.image.tostring(sf, "RGBA")
        scrap.put(pygame.SCRAP_BMP, expected_string)

        self.assertEqual(scrap.get(pygame.SCRAP_BMP), expected_string)

    def test_put(self):
        """Ensures put can place data into the clipboard
        when using a user defined type identifier.
        """
        DATA_TYPE = "arbitrary buffer"

        scrap.put(DATA_TYPE, b"buf")
        r = scrap.get(DATA_TYPE)

        self.assertEqual(r, b"buf")


class ScrapModuleClipboardNotOwnedTest(unittest.TestCase):
    """Test the scrap module's functionality when the pygame application is
    not the current owner of the clipboard.

    A separate class is used to prevent tests that acquire the clipboard from
    interfering with these tests.
    """

    @classmethod
    def setUpClass(cls):
        pygame.display.init()
        pygame.display.set_mode((1, 1))
        scrap.init()

    @classmethod
    def tearDownClass(cls):
        # scrap.quit()  # Does not exist!
        pygame.quit()
        pygame.display.quit()

    def _skip_if_clipboard_owned(self):
        # Skip test if the pygame application owns the clipboard. Currently,
        # there is no way to give up ownership.
        if not scrap.lost():
            self.skipTest("requires the pygame application to not own the clipboard")

    def test_get__not_owned(self):
        """Ensures get works when there is no data of the requested type
        in the clipboard and the clipboard is not owned by the pygame
        application.
        """
        self._skip_if_clipboard_owned()

        # Use a unique data type identifier to ensure there is no preexisting
        # data.
        DATA_TYPE = "test_get__not_owned"

        data = scrap.get(DATA_TYPE)

        self.assertIsNone(data)

    def test_get_types__not_owned(self):
        """Ensures get_types works when the clipboard is not owned
        by the pygame application.
        """
        self._skip_if_clipboard_owned()

        data_types = scrap.get_types()

        self.assertIsInstance(data_types, list)

    def test_contains__not_owned(self):
        """Ensures contains works when the clipboard is not owned
        by the pygame application.
        """
        self._skip_if_clipboard_owned()

        # Use a unique data type identifier to ensure there is no preexisting
        # data.
        DATA_TYPE = "test_contains__not_owned"

        contains = scrap.contains(DATA_TYPE)

        self.assertFalse(contains)

    def test_lost__not_owned(self):
        """Ensures lost works when the clipboard is not owned
        by the pygame application.
        """
        self._skip_if_clipboard_owned()

        lost = scrap.lost()

        self.assertTrue(lost)


class X11InteractiveTest(unittest.TestCase):
    __tags__ = ["ignore", "subprocess_ignore"]
    try:
        pygame.display.init()
    except Exception:
        pass
    else:
        if pygame.display.get_driver() == "x11":
            __tags__ = ["interactive"]
        pygame.display.quit()

    def test_issue_208(self):
        """PATCH: pygame.scrap on X11, fix copying into PRIMARY selection

        Copying into theX11 PRIMARY selection (mouse copy/paste) would not
        work due to a confusion between content type and clipboard type.

        """

        from pygame import display, event, freetype
        from pygame.locals import SCRAP_SELECTION, SCRAP_TEXT
        from pygame.locals import KEYDOWN, K_y, QUIT

        success = False
        freetype.init()
        font = freetype.Font(None, 24)
        display.init()
        display.set_caption("Interactive X11 Paste Test")
        screen = display.set_mode((600, 200))
        screen.fill(pygame.Color("white"))
        text = "Scrap put() succeeded."
        msg = (
            "Some text has been placed into the X11 clipboard."
            " Please click the center mouse button in an open"
            " text window to retrieve it."
            '\n\nDid you get "{}"? (y/n)'
        ).format(text)
        word_wrap(screen, msg, font, 6)
        display.flip()
        event.pump()
        scrap.init()
        scrap.set_mode(SCRAP_SELECTION)
        scrap.put(SCRAP_TEXT, text.encode("UTF-8"))
        while True:
            e = event.wait()
            if e.type == QUIT:
                break
            if e.type == KEYDOWN:
                success = e.key == K_y
                break
        pygame.display.quit()
        self.assertTrue(success)


def word_wrap(surf, text, font, margin=0, color=(0, 0, 0)):
    font.origin = True
    surf_width, surf_height = surf.get_size()
    width = surf_width - 2 * margin
    height = surf_height - 2 * margin
    line_spacing = int(1.25 * font.get_sized_height())
    x, y = margin, margin + line_spacing
    space = font.get_rect(" ")
    for word in iwords(text):
        if word == "\n":
            x, y = margin, y + line_spacing
        else:
            bounds = font.get_rect(word)
            if x + bounds.width + bounds.x >= width:
                x, y = margin, y + line_spacing
            if x + bounds.width + bounds.x >= width:
                raise ValueError("word too wide for the surface")
            if y + bounds.height - bounds.y >= height:
                raise ValueError("text to long for the surface")
            font.render_to(surf, (x, y), None, color)
            x += bounds.width + space.width
    return x, y


def iwords(text):
    #  r"\n|[^ ]+"
    #
    head = 0
    tail = head
    end = len(text)
    while head < end:
        if text[head] == " ":
            head += 1
            tail = head + 1
        elif text[head] == "\n":
            head += 1
            yield "\n"
            tail = head + 1
        elif tail == end:
            yield text[head:]
            head = end
        elif text[tail] == "\n":
            yield text[head:tail]
            head = tail
        elif text[tail] == " ":
            yield text[head:tail]
            head = tail
        else:
            tail += 1


if __name__ == "__main__":
    unittest.main()
