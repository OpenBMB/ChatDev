#!/usr/bin/env python
""" pygame.examples.dropfile

Drag and drop an image on here.

Uses these events:

* DROPBEGIN
* DROPCOMPLETE
* DROPTEXT
* DROPFILE
"""
import pygame as pg


def main():
    pg.init()

    going = True
    surf = pg.display.set_mode((640, 480))
    font = pg.font.SysFont("Arial", 24)
    clock = pg.time.Clock()

    spr_file_text = font.render("Drag and drop a file or image!", 1, (255, 255, 255))
    spr_file_text_rect = spr_file_text.get_rect()
    spr_file_text_rect.center = surf.get_rect().center

    spr_file_image = None
    spr_file_image_rect = None

    while going:
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                going = False
            elif ev.type == pg.DROPBEGIN:
                print(ev)
                print("File drop begin!")
            elif ev.type == pg.DROPCOMPLETE:
                print(ev)
                print("File drop complete!")
            elif ev.type == pg.DROPTEXT:
                print(ev)
                spr_file_text = font.render(ev.text, 1, (255, 255, 255))
                spr_file_text_rect = spr_file_text.get_rect()
                spr_file_text_rect.center = surf.get_rect().center
            elif ev.type == pg.DROPFILE:
                print(ev)
                spr_file_text = font.render(ev.file, 1, (255, 255, 255))
                spr_file_text_rect = spr_file_text.get_rect()
                spr_file_text_rect.center = surf.get_rect().center

                # Try to open the file if it's an image
                filetype = ev.file[-3:]
                if filetype in ["png", "bmp", "jpg"]:
                    spr_file_image = pg.image.load(ev.file).convert()
                    spr_file_image.set_alpha(127)
                    spr_file_image_rect = spr_file_image.get_rect()
                    spr_file_image_rect.center = surf.get_rect().center

        surf.fill((0, 0, 0))
        surf.blit(spr_file_text, spr_file_text_rect)
        if spr_file_image and spr_file_image_rect is not None:
            surf.blit(spr_file_image, spr_file_image_rect)

        pg.display.flip()
        clock.tick(30)

    pg.quit()


if __name__ == "__main__":
    main()
