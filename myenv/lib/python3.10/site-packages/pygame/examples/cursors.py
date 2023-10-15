#!/usr/bin/env python
""" pygame.examples.cursors
Click a button and the cursor will change.
This example will show you:
*The different types of cursors that exist
*How to create a cursor
*How to set a cursor
*How to make a simple button
"""

import pygame as pg
import os


# Create a system cursor

system_cursor1 = pg.SYSTEM_CURSOR_CROSSHAIR
system_cursor2 = pg.SYSTEM_CURSOR_HAND
system_cursor3 = pg.SYSTEM_CURSOR_IBEAM


# Create a color cursor

surf = pg.Surface((40, 40))
surf.fill((120, 50, 50))
color_cursor = pg.cursors.Cursor((20, 20), surf)


# Create a color cursor with an image surface

main_dir = os.path.split(os.path.abspath(__file__))[0]
image_name = os.path.join(main_dir, "data", "cursor.png")
image = pg.image.load(image_name)
image_cursor = pg.cursors.Cursor(
    (image.get_width() // 2, image.get_height() // 2), image
)


# Create a bitmap cursor from simple strings

# sized 24x24
thickarrow_strings = (
    "XX                      ",
    "XXX                     ",
    "XXXX                    ",
    "XX.XX                   ",
    "XX..XX                  ",
    "XX...XX                 ",
    "XX....XX                ",
    "XX.....XX               ",
    "XX......XX              ",
    "XX.......XX             ",
    "XX........XX            ",
    "XX........XXX           ",
    "XX......XXXXX           ",
    "XX.XXX..XX              ",
    "XXXX XX..XX             ",
    "XX   XX..XX             ",
    "     XX..XX             ",
    "      XX..XX            ",
    "      XX..XX            ",
    "       XXXX             ",
    "       XX               ",
    "                        ",
    "                        ",
    "                        ",
)

bitmap_cursor1 = pg.cursors.Cursor(
    (24, 24),
    (0, 0),
    *pg.cursors.compile(thickarrow_strings, black="X", white=".", xor="o"),
)


# Create a bitmap cursor from premade simple strings

bitmap_cursor2 = pg.cursors.diamond


# Calculate if mouse position is inside circle
def check_circle(mouse_pos_x, mouse_pos_y, center_x, center_y, radius):
    return (mouse_pos_x - center_x) ** 2 + (mouse_pos_y - center_y) ** 2 < radius**2


def main():
    pg.init()
    pg.display.set_caption("Cursors Example")

    pg.font.init()
    font = pg.font.Font(None, 30)
    font1 = pg.font.Font(None, 24)

    bg = pg.display.set_mode((500, 400))
    bg.fill((183, 201, 226))

    # Initialize circles
    radius1 = 40
    radius2 = 40
    radius3 = 40
    radius4 = 40
    radius5 = 40
    radius6 = 40
    radius7 = 40

    pos_x1 = 82
    pos_x2 = 138
    pos_x3 = 194
    pos_x4 = 250
    pos_x5 = 306
    pos_x6 = 362
    pos_x7 = 418

    pos_y1 = 140
    pos_y2 = 220
    pos_y3 = 140
    pos_y4 = 220
    pos_y5 = 140
    pos_y6 = 220
    pos_y7 = 140

    circle1 = pg.draw.circle(bg, (255, 255, 255), (pos_x1, pos_y1), radius1)
    circle2 = pg.draw.circle(bg, (255, 255, 255), (pos_x2, pos_y2), radius2)
    circle3 = pg.draw.circle(bg, (255, 255, 255), (pos_x3, pos_y3), radius3)
    circle4 = pg.draw.circle(bg, (255, 255, 255), (pos_x4, pos_y4), radius4)
    circle5 = pg.draw.circle(bg, (255, 255, 255), (pos_x5, pos_y5), radius5)
    circle6 = pg.draw.circle(bg, (255, 255, 255), (pos_x6, pos_y6), radius6)
    circle7 = pg.draw.circle(bg, (255, 255, 255), (pos_x7, pos_y7), radius7)

    # Initialize button
    button_text = font1.render("Click here to change cursor", True, (0, 0, 0))
    button = pg.draw.rect(
        bg,
        (180, 180, 180),
        (139, 300, button_text.get_width() + 5, button_text.get_height() + 50),
    )
    button_text_rect = button_text.get_rect(center=button.center)
    bg.blit(button_text, button_text_rect)

    pg.display.update()

    cursors = [
        system_cursor1,
        color_cursor,
        system_cursor2,
        image_cursor,
        system_cursor3,
        bitmap_cursor1,
        bitmap_cursor2,
    ]

    index = 0
    pg.mouse.set_cursor(cursors[index])

    pressed = False
    clock = pg.time.Clock()

    while True:
        clock.tick(50)

        mouse_x, mouse_y = pg.mouse.get_pos()

        # Check if mouse is inside a circle to change its color
        if check_circle(mouse_x, mouse_y, circle1.centerx, circle1.centery, radius1):
            circle1 = pg.draw.circle(bg, (255, 0, 0), (pos_x1, pos_y1), radius1)
        else:
            circle1 = pg.draw.circle(bg, (255, 255, 255), (pos_x1, pos_y1), radius1)

        if check_circle(mouse_x, mouse_y, circle2.centerx, circle2.centery, radius2):
            circle2 = pg.draw.circle(bg, (255, 127, 0), (pos_x2, pos_y2), radius2)
        else:
            circle2 = pg.draw.circle(bg, (255, 255, 255), (pos_x2, pos_y2), radius2)

        if check_circle(mouse_x, mouse_y, circle3.centerx, circle3.centery, radius3):
            circle3 = pg.draw.circle(bg, (255, 255, 0), (pos_x3, pos_y3), radius3)
        else:
            circle3 = pg.draw.circle(bg, (255, 255, 255), (pos_x3, pos_y3), radius3)

        if check_circle(mouse_x, mouse_y, circle4.centerx, circle4.centery, radius3):
            circle4 = pg.draw.circle(bg, (0, 255, 0), (pos_x4, pos_y4), radius4)
        else:
            circle4 = pg.draw.circle(bg, (255, 255, 255), (pos_x4, pos_y4), radius4)

        if check_circle(mouse_x, mouse_y, circle5.centerx, circle5.centery, radius4):
            circle5 = pg.draw.circle(bg, (0, 0, 255), (pos_x5, pos_y5), radius5)
        else:
            circle5 = pg.draw.circle(bg, (255, 255, 255), (pos_x5, pos_y5), radius5)

        if check_circle(mouse_x, mouse_y, circle6.centerx, circle6.centery, radius6):
            circle6 = pg.draw.circle(bg, (75, 0, 130), (pos_x6, pos_y6), radius6)
        else:
            circle6 = pg.draw.circle(bg, (255, 255, 255), (pos_x6, pos_y6), radius6)

        if check_circle(mouse_x, mouse_y, circle7.centerx, circle7.centery, radius7):
            circle7 = pg.draw.circle(bg, (148, 0, 211), (pos_x7, pos_y7), radius7)
        else:
            circle7 = pg.draw.circle(bg, (255, 255, 255), (pos_x7, pos_y7), radius7)

        bg.fill((183, 201, 226), (0, 15, bg.get_width(), 50))
        text1 = font.render(
            (f"This is a {pg.mouse.get_cursor().type} cursor"), True, (0, 0, 0)
        )
        text_rect1 = text1.get_rect(center=(bg.get_width() / 2, 40))
        bg.blit(text1, text_rect1)

        button = pg.draw.rect(
            bg,
            (100, 149, 240),
            (139, 300, button_text.get_width() + 5, button_text.get_height() + 50),
        )
        bg.blit(button_text, button_text_rect)

        # Check if button was clicked and change cursor
        if button.collidepoint(mouse_x, mouse_y):
            button = pg.draw.rect(
                bg,
                (60, 100, 255),
                (
                    139,
                    300,
                    button_text.get_width() + 5,
                    button_text.get_height() + 50,
                ),
            )
            bg.blit(button_text, button_text_rect)

            if pg.mouse.get_pressed()[0] == 1 and pressed == False:
                button = pg.draw.rect(
                    bg,
                    (0, 0, 139),
                    (
                        139,
                        300,
                        button_text.get_width() + 5,
                        button_text.get_height() + 50,
                    ),
                )
                bg.blit(button_text, button_text_rect)
                index += 1
                index %= len(cursors)
                pg.mouse.set_cursor(cursors[index])
                pg.display.update()
                pg.time.delay(40)

        if pg.mouse.get_pressed()[0] == 1:
            pressed = True
        elif pg.mouse.get_pressed()[0] == 0:
            pressed = False

        for event in pg.event.get():
            if event.type == pg.QUIT:
                pg.quit()
                raise SystemExit

        pg.display.update()


if __name__ == "__main__":
    main()
