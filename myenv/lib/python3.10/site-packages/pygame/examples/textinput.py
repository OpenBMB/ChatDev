#!/usr/bin/env python
""" pg.examples.textinput

A little "console" where you can write in text.

Shows how to use the TEXTEDITING and TEXTINPUT events.
"""
import sys
import os
from typing import List

import pygame
import pygame as pg
import pygame.freetype as freetype

# This environment variable is important
# If not added the candidate list will not show
os.environ["SDL_IME_SHOW_UI"] = "1"


class TextInput:
    """
    A simple TextInput class that allows you to receive inputs in pygame.
    """

    # Add font name for each language,
    # otherwise some text can't be correctly displayed.
    FONT_NAMES = ",".join(
        str(x)
        for x in [
            "notosanscjktcregular",
            "notosansmonocjktcregular",
            "notosansregular,",
            "microsoftjhengheimicrosoftjhengheiuilight",
            "microsoftyaheimicrosoftyaheiuilight",
            "msgothicmsuigothicmspgothic",
            "msmincho",
            "Arial",
        ]
    )

    def __init__(
        self, prompt: str, pos, screen_dimensions, print_event: bool, text_color="white"
    ) -> None:
        self.prompt = prompt
        self.print_event = print_event
        # position of chatlist and chatbox
        self.CHAT_LIST_POS = pg.Rect((pos[0], pos[1] + 50), (screen_dimensions[0], 400))
        self.CHAT_BOX_POS = pg.Rect(pos, (screen_dimensions[1], 40))
        self.CHAT_LIST_MAXSIZE = 20

        self._ime_editing = False
        self._ime_text = ""
        self._ime_text_pos = 0
        self._ime_editing_text = ""
        self._ime_editing_pos = 0
        self.chat_list: List[str] = []

        # Freetype
        # The font name can be a comma separated list
        # of font names to search for.
        self.font = freetype.SysFont(self.FONT_NAMES, 24)
        self.font_small = freetype.SysFont(self.FONT_NAMES, 16)
        self.text_color = text_color

        print("Using font: " + self.font.name)

    def update(self, events) -> None:
        """
        Updates the text input widget
        """
        for event in events:
            if event.type == pg.KEYDOWN:
                if self.print_event:
                    print(event)

                if self._ime_editing:
                    if len(self._ime_editing_text) == 0:
                        self._ime_editing = False
                    continue

                if event.key == pg.K_BACKSPACE:
                    if len(self._ime_text) > 0 and self._ime_text_pos > 0:
                        self._ime_text = (
                            self._ime_text[0 : self._ime_text_pos - 1]
                            + self._ime_text[self._ime_text_pos :]
                        )
                        self._ime_text_pos = max(0, self._ime_text_pos - 1)

                elif event.key == pg.K_DELETE:
                    self._ime_text = (
                        self._ime_text[0 : self._ime_text_pos]
                        + self._ime_text[self._ime_text_pos + 1 :]
                    )
                elif event.key == pg.K_LEFT:
                    self._ime_text_pos = max(0, self._ime_text_pos - 1)
                elif event.key == pg.K_RIGHT:
                    self._ime_text_pos = min(
                        len(self._ime_text), self._ime_text_pos + 1
                    )
                # Handle ENTER key
                elif event.key in [pg.K_RETURN, pg.K_KP_ENTER]:
                    # Block if we have no text to append
                    if len(self._ime_text) == 0:
                        continue

                    # Append chat list
                    self.chat_list.append(self._ime_text)
                    if len(self.chat_list) > self.CHAT_LIST_MAXSIZE:
                        self.chat_list.pop(0)
                    self._ime_text = ""
                    self._ime_text_pos = 0

            elif event.type == pg.TEXTEDITING:
                if self.print_event:
                    print(event)
                self._ime_editing = True
                self._ime_editing_text = event.text
                self._ime_editing_pos = event.start

            elif event.type == pg.TEXTINPUT:
                if self.print_event:
                    print(event)
                self._ime_editing = False
                self._ime_editing_text = ""
                self._ime_text = (
                    self._ime_text[0 : self._ime_text_pos]
                    + event.text
                    + self._ime_text[self._ime_text_pos :]
                )
                self._ime_text_pos += len(event.text)

    def draw(self, screen: pygame.Surface) -> None:
        """
        Draws the text input widget onto the provided surface
        """

        # Chat List updates
        chat_height = self.CHAT_LIST_POS.height / self.CHAT_LIST_MAXSIZE
        for i, chat in enumerate(self.chat_list):
            self.font_small.render_to(
                screen,
                (self.CHAT_LIST_POS.x, self.CHAT_LIST_POS.y + i * chat_height),
                chat,
                self.text_color,
            )

        # Chat box updates
        start_pos = self.CHAT_BOX_POS.copy()
        ime_text_l = self.prompt + self._ime_text[0 : self._ime_text_pos]
        ime_text_m = (
            self._ime_editing_text[0 : self._ime_editing_pos]
            + "|"
            + self._ime_editing_text[self._ime_editing_pos :]
        )
        ime_text_r = self._ime_text[self._ime_text_pos :]

        rect_text_l = self.font.render_to(
            screen, start_pos, ime_text_l, self.text_color
        )
        start_pos.x += rect_text_l.width

        # Editing texts should be underlined
        rect_text_m = self.font.render_to(
            screen,
            start_pos,
            ime_text_m,
            self.text_color,
            None,
            freetype.STYLE_UNDERLINE,
        )
        start_pos.x += rect_text_m.width
        self.font.render_to(screen, start_pos, ime_text_r, self.text_color)


class Game:
    """
    A class that handles the game's events, mainloop etc.
    """

    # CONSTANTS
    # Frames per second, the general speed of the program
    FPS = 50
    # Size of window
    SCREEN_WIDTH, SCREEN_HEIGHT = 640, 480
    BG_COLOR = "black"

    def __init__(self, caption: str) -> None:
        # Initialize
        pg.init()
        self.screen = pg.display.set_mode((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        pg.display.set_caption(caption)
        self.clock = pg.time.Clock()

        # Text input
        # Set to true or add 'showevent' in argv to see IME and KEYDOWN events
        self.print_event = "showevent" in sys.argv
        self.text_input = TextInput(
            prompt="> ",
            pos=(0, 20),
            screen_dimensions=(self.SCREEN_WIDTH, self.SCREEN_HEIGHT),
            print_event=self.print_event,
            text_color="green",
        )

    def main_loop(self) -> None:
        pg.key.start_text_input()
        input_rect = pg.Rect(80, 80, 320, 40)
        pg.key.set_text_input_rect(input_rect)

        while True:
            events = pg.event.get()
            for event in events:
                if event.type == pg.QUIT:
                    pg.quit()
                    return

            self.text_input.update(events)

            # Screen updates
            self.screen.fill(self.BG_COLOR)
            self.text_input.draw(self.screen)

            pg.display.update()
            self.clock.tick(self.FPS)


# Main loop process
def main():
    game = Game("Text Input Example")
    game.main_loop()


if __name__ == "__main__":
    main()
