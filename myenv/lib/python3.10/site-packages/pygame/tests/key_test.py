import os
import time
import unittest

import pygame
import pygame.key

# keys that are not tested for const-name match
SKIPPED_KEYS = {"K_UNKNOWN"}

# This is the expected compat output
KEY_NAME_COMPAT = {
    "K_0": "0",
    "K_1": "1",
    "K_2": "2",
    "K_3": "3",
    "K_4": "4",
    "K_5": "5",
    "K_6": "6",
    "K_7": "7",
    "K_8": "8",
    "K_9": "9",
    "K_AC_BACK": "AC Back",
    "K_AMPERSAND": "&",
    "K_ASTERISK": "*",
    "K_AT": "@",
    "K_BACKQUOTE": "`",
    "K_BACKSLASH": "\\",
    "K_BACKSPACE": "backspace",
    "K_BREAK": "break",
    "K_CAPSLOCK": "caps lock",
    "K_CARET": "^",
    "K_CLEAR": "clear",
    "K_COLON": ":",
    "K_COMMA": ",",
    "K_CURRENCYSUBUNIT": "CurrencySubUnit",
    "K_CURRENCYUNIT": "euro",
    "K_DELETE": "delete",
    "K_DOLLAR": "$",
    "K_DOWN": "down",
    "K_END": "end",
    "K_EQUALS": "=",
    "K_ESCAPE": "escape",
    "K_EURO": "euro",
    "K_EXCLAIM": "!",
    "K_F1": "f1",
    "K_F10": "f10",
    "K_F11": "f11",
    "K_F12": "f12",
    "K_F13": "f13",
    "K_F14": "f14",
    "K_F15": "f15",
    "K_F2": "f2",
    "K_F3": "f3",
    "K_F4": "f4",
    "K_F5": "f5",
    "K_F6": "f6",
    "K_F7": "f7",
    "K_F8": "f8",
    "K_F9": "f9",
    "K_GREATER": ">",
    "K_HASH": "#",
    "K_HELP": "help",
    "K_HOME": "home",
    "K_INSERT": "insert",
    "K_KP0": "[0]",
    "K_KP1": "[1]",
    "K_KP2": "[2]",
    "K_KP3": "[3]",
    "K_KP4": "[4]",
    "K_KP5": "[5]",
    "K_KP6": "[6]",
    "K_KP7": "[7]",
    "K_KP8": "[8]",
    "K_KP9": "[9]",
    "K_KP_0": "[0]",
    "K_KP_1": "[1]",
    "K_KP_2": "[2]",
    "K_KP_3": "[3]",
    "K_KP_4": "[4]",
    "K_KP_5": "[5]",
    "K_KP_6": "[6]",
    "K_KP_7": "[7]",
    "K_KP_8": "[8]",
    "K_KP_9": "[9]",
    "K_KP_DIVIDE": "[/]",
    "K_KP_ENTER": "enter",
    "K_KP_EQUALS": "equals",
    "K_KP_MINUS": "[-]",
    "K_KP_MULTIPLY": "[*]",
    "K_KP_PERIOD": "[.]",
    "K_KP_PLUS": "[+]",
    "K_LALT": "left alt",
    "K_LCTRL": "left ctrl",
    "K_LEFT": "left",
    "K_LEFTBRACKET": "[",
    "K_LEFTPAREN": "(",
    "K_LESS": "<",
    "K_LGUI": "left meta",
    "K_LMETA": "left meta",
    "K_LSHIFT": "left shift",
    "K_LSUPER": "left meta",
    "K_MENU": "menu",
    "K_MINUS": "-",
    "K_MODE": "alt gr",
    "K_NUMLOCK": "numlock",
    "K_NUMLOCKCLEAR": "numlock",
    "K_PAGEDOWN": "page down",
    "K_PAGEUP": "page up",
    "K_PAUSE": "break",
    "K_PERCENT": "%",
    "K_PERIOD": ".",
    "K_PLUS": "+",
    "K_POWER": "power",
    "K_PRINT": "print screen",
    "K_PRINTSCREEN": "print screen",
    "K_QUESTION": "?",
    "K_QUOTE": "'",
    "K_QUOTEDBL": '"',
    "K_RALT": "right alt",
    "K_RCTRL": "right ctrl",
    "K_RETURN": "return",
    "K_RGUI": "right meta",
    "K_RIGHT": "right",
    "K_RIGHTBRACKET": "]",
    "K_RIGHTPAREN": ")",
    "K_RMETA": "right meta",
    "K_RSHIFT": "right shift",
    "K_RSUPER": "right meta",
    "K_SCROLLLOCK": "scroll lock",
    "K_SCROLLOCK": "scroll lock",
    "K_SEMICOLON": ";",
    "K_SLASH": "/",
    "K_SPACE": "space",
    "K_SYSREQ": "sys req",
    "K_TAB": "tab",
    "K_UNDERSCORE": "_",
    "K_UP": "up",
    "K_a": "a",
    "K_b": "b",
    "K_c": "c",
    "K_d": "d",
    "K_e": "e",
    "K_f": "f",
    "K_g": "g",
    "K_h": "h",
    "K_i": "i",
    "K_j": "j",
    "K_k": "k",
    "K_l": "l",
    "K_m": "m",
    "K_n": "n",
    "K_o": "o",
    "K_p": "p",
    "K_q": "q",
    "K_r": "r",
    "K_s": "s",
    "K_t": "t",
    "K_u": "u",
    "K_v": "v",
    "K_w": "w",
    "K_x": "x",
    "K_y": "y",
    "K_z": "z",
}


class KeyModuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        # This makes sure pygame is always initialized before each test (in
        # case a test calls pygame.quit()).
        if not pygame.get_init():
            pygame.init()
        if not pygame.display.get_init():
            pygame.display.init()

    def test_import(self):
        """does it import?"""
        import pygame.key

    # fixme: test_get_focused failing systematically in some linux
    # fixme: test_get_focused failing on SDL 2.0.18 on Windows
    @unittest.skip("flaky test, and broken on 2.0.18 windows")
    def test_get_focused(self):
        # This test fails in SDL2 in some linux
        # This test was skipped in SDL1.
        focused = pygame.key.get_focused()
        self.assertFalse(focused)  # No window to focus
        self.assertIsInstance(focused, int)
        # Dummy video driver never gets keyboard focus.
        if os.environ.get("SDL_VIDEODRIVER") != "dummy":
            # Positive test, fullscreen with events grabbed
            display_sizes = pygame.display.list_modes()
            if display_sizes == -1:
                display_sizes = [(500, 500)]
            pygame.display.set_mode(size=display_sizes[-1], flags=pygame.FULLSCREEN)
            pygame.event.set_grab(True)
            # Pump event queue to get window focus on macos
            pygame.event.pump()
            focused = pygame.key.get_focused()
            self.assertIsInstance(focused, int)
            self.assertTrue(focused)
            # Now test negative, iconify takes away focus
            pygame.event.clear()
            # TODO: iconify test fails in windows
            if os.name != "nt":
                pygame.display.iconify()
                # Apparent need to pump event queue in order to make sure iconify
                # happens. See display_test.py's test_get_active_iconify
                for _ in range(50):
                    time.sleep(0.01)
                    pygame.event.pump()
                self.assertFalse(pygame.key.get_focused())
                # Test if focus is returned when iconify is gone
                pygame.display.set_mode(size=display_sizes[-1], flags=pygame.FULLSCREEN)
                for i in range(50):
                    time.sleep(0.01)
                    pygame.event.pump()
                self.assertTrue(pygame.key.get_focused())
        # Test if a quit display raises an error:
        pygame.display.quit()
        with self.assertRaises(pygame.error) as cm:
            pygame.key.get_focused()

    def test_get_pressed(self):
        states = pygame.key.get_pressed()
        self.assertEqual(states[pygame.K_RIGHT], 0)

    # def test_get_pressed_not_iter(self):
    #     states = pygame.key.get_pressed()
    #     with self.assertRaises(TypeError):
    #         next(states)
    #     with self.assertRaises(TypeError):
    #         for k in states:
    #             pass

    def test_name_and_key_code(self):
        for const_name in dir(pygame):
            if not const_name.startswith("K_") or const_name in SKIPPED_KEYS:
                continue

            try:
                expected_str_name = KEY_NAME_COMPAT[const_name]
            except KeyError:
                self.fail(
                    "If you are seeing this error in a test run, you probably added a "
                    "new pygame key constant, but forgot to update key_test unitests"
                )

            const_val = getattr(pygame, const_name)

            # with these tests below, we also make sure that key.name and key.key_code
            # can work together and handle each others outputs

            # test positional args
            self.assertEqual(pygame.key.name(const_val), expected_str_name)
            # test kwarg
            self.assertEqual(pygame.key.name(key=const_val), expected_str_name)

            # test positional args
            self.assertEqual(pygame.key.key_code(expected_str_name), const_val)
            # test kwarg
            self.assertEqual(pygame.key.key_code(name=expected_str_name), const_val)

            alt_name = pygame.key.name(const_val, use_compat=False)
            self.assertIsInstance(alt_name, str)

            # This is a test for an implementation detail of name with use_compat=False
            # If this test breaks in the future for any key, it is safe to put skips on
            # failing keys (the implementation detail is documented as being unreliable)
            self.assertEqual(pygame.key.key_code(alt_name), const_val)

        self.assertRaises(TypeError, pygame.key.name, "fizzbuzz")
        self.assertRaises(TypeError, pygame.key.key_code, pygame.K_a)

        self.assertRaises(ValueError, pygame.key.key_code, "fizzbuzz")

    def test_set_and_get_mods(self):
        pygame.key.set_mods(pygame.KMOD_CTRL)
        self.assertEqual(pygame.key.get_mods(), pygame.KMOD_CTRL)

        pygame.key.set_mods(pygame.KMOD_ALT)
        self.assertEqual(pygame.key.get_mods(), pygame.KMOD_ALT)
        pygame.key.set_mods(pygame.KMOD_CTRL | pygame.KMOD_ALT)
        self.assertEqual(pygame.key.get_mods(), pygame.KMOD_CTRL | pygame.KMOD_ALT)

    def test_set_and_get_repeat(self):
        self.assertEqual(pygame.key.get_repeat(), (0, 0))

        pygame.key.set_repeat(10, 15)
        self.assertEqual(pygame.key.get_repeat(), (10, 15))

        pygame.key.set_repeat()
        self.assertEqual(pygame.key.get_repeat(), (0, 0))


if __name__ == "__main__":
    unittest.main()
