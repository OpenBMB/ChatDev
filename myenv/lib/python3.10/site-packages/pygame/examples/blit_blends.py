#!/usr/bin/env python
""" pygame.examples.blit_blends

Blending colors in different ways with different blend modes.

It also shows some tricks with the surfarray.
Including how to do additive blending.


Keyboard Controls
-----------------

* R, G, B - add a bit of Red, Green, or Blue.
* A - Add blend mode
* S - Subtractive blend mode
* M - Multiply blend mode
* = key BLEND_MAX blend mode.
* - key BLEND_MIN blend mode.
* 1, 2, 3, 4 - use different images.

"""
import os
import pygame as pg
import time

main_dir = os.path.split(os.path.abspath(__file__))[0]
data_dir = os.path.join(main_dir, "data")

try:
    import pygame.surfarray
    import numpy
except ImportError:
    print("no surfarray for you!  install numpy")


def main():
    pg.init()
    pg.mixer.quit()  # remove ALSA underflow messages for Debian squeeze
    screen = pg.display.set_mode((640, 480))

    im1 = pg.Surface(screen.get_size())
    # im1= im1.convert()
    im1.fill((100, 0, 0))

    im2 = pg.Surface(screen.get_size())
    im2.fill((0, 50, 0))
    # we make a srcalpha copy of it.
    # im3= im2.convert(SRCALPHA)
    im3 = im2
    im3.set_alpha(127)

    images = {}
    images[pg.K_1] = im2
    images[pg.K_2] = pg.image.load(os.path.join(data_dir, "chimp.png"))
    images[pg.K_3] = pg.image.load(os.path.join(data_dir, "alien3.gif"))
    images[pg.K_4] = pg.image.load(os.path.join(data_dir, "liquid.bmp"))
    img_to_blit = im2.convert()
    iaa = img_to_blit.convert_alpha()

    blits = {}
    blits[pg.K_a] = pg.BLEND_ADD
    blits[pg.K_s] = pg.BLEND_SUB
    blits[pg.K_m] = pg.BLEND_MULT
    blits[pg.K_EQUALS] = pg.BLEND_MAX
    blits[pg.K_MINUS] = pg.BLEND_MIN

    blitsn = {}
    blitsn[pg.K_a] = "BLEND_ADD"
    blitsn[pg.K_s] = "BLEND_SUB"
    blitsn[pg.K_m] = "BLEND_MULT"
    blitsn[pg.K_EQUALS] = "BLEND_MAX"
    blitsn[pg.K_MINUS] = "BLEND_MIN"

    screen.blit(im1, (0, 0))
    pg.display.flip()
    clock = pg.time.Clock()
    print("one pixel is:%s:" % [im1.get_at((0, 0))])

    going = True
    while going:
        clock.tick(60)

        for event in pg.event.get():
            if event.type == pg.QUIT:
                going = False
            if event.type == pg.KEYDOWN:
                usage()

            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                going = False

            elif event.type == pg.KEYDOWN and event.key in images.keys():
                img_to_blit = images[event.key]
                iaa = img_to_blit.convert_alpha()

            elif event.type == pg.KEYDOWN and event.key in blits.keys():
                t1 = time.time()
                # blits is a dict keyed with key -> blit flag.  eg BLEND_ADD.
                im1.blit(img_to_blit, (0, 0), None, blits[event.key])
                t2 = time.time()
                print("one pixel is:%s:" % [im1.get_at((0, 0))])
                print(f"time to do:{t2 - t1}:")

            elif event.type == pg.KEYDOWN and event.key in [pg.K_t]:
                for bkey in blits.keys():
                    t1 = time.time()

                    for x in range(300):
                        im1.blit(img_to_blit, (0, 0), None, blits[bkey])

                    t2 = time.time()

                    # show which key we're doing...
                    onedoing = blitsn[bkey]
                    print(f"time to do :{onedoing}: is :{t2 - t1}:")

            elif event.type == pg.KEYDOWN and event.key in [pg.K_o]:
                t1 = time.time()
                # blits is a dict keyed with key -> blit flag.  eg BLEND_ADD.
                im1.blit(iaa, (0, 0))
                t2 = time.time()
                print("one pixel is:%s:" % [im1.get_at((0, 0))])
                print(f"time to do:{t2 - t1}:")

            elif event.type == pg.KEYDOWN and event.key == pg.K_SPACE:
                # this additive blend without clamp two surfaces.
                # im1.set_alpha(127)
                # im1.blit(im1, (0,0))
                # im1.set_alpha(255)
                t1 = time.time()

                im1p = pygame.surfarray.pixels2d(im1)
                im2p = pygame.surfarray.pixels2d(im2)
                im1p += im2p
                del im1p
                del im2p
                t2 = time.time()
                print("one pixel is:%s:" % [im1.get_at((0, 0))])
                print(f"time to do:{t2 - t1}:")

            elif event.type == pg.KEYDOWN and event.key in [pg.K_z]:
                t1 = time.time()
                im1p = pygame.surfarray.pixels3d(im1)
                im2p = pygame.surfarray.pixels3d(im2)
                im1p16 = im1p.astype(numpy.uint16)
                im2p16 = im1p.astype(numpy.uint16)
                im1p16 += im2p16
                im1p16 = numpy.minimum(im1p16, 255)
                pygame.surfarray.blit_array(im1, im1p16)

                del im1p
                del im2p
                t2 = time.time()
                print("one pixel is:%s:" % [im1.get_at((0, 0))])
                print(f"time to do:{t2 - t1}:")

            elif event.type == pg.KEYDOWN and event.key in [pg.K_r, pg.K_g, pg.K_b]:
                # this adds one to each pixel.
                colmap = {}
                colmap[pg.K_r] = 0x10000
                colmap[pg.K_g] = 0x00100
                colmap[pg.K_b] = 0x00001
                im1p = pygame.surfarray.pixels2d(im1)
                im1p += colmap[event.key]
                del im1p
                print("one pixel is:%s:" % [im1.get_at((0, 0))])

            elif event.type == pg.KEYDOWN and event.key == pg.K_p:
                print("one pixel is:%s:" % [im1.get_at((0, 0))])

            elif event.type == pg.KEYDOWN and event.key == pg.K_f:
                # this additive blend without clamp two surfaces.

                t1 = time.time()
                im1.set_alpha(127)
                im1.blit(im2, (0, 0))
                im1.set_alpha(255)

                t2 = time.time()
                print("one pixel is:%s:" % [im1.get_at((0, 0))])
                print(f"time to do:{t2 - t1}:")

        screen.blit(im1, (0, 0))
        pg.display.flip()

    pg.quit()


def usage():
    print("press keys 1-5 to change image to blit.")
    print("A - ADD, S- SUB, M- MULT, - MIN, + MAX")
    print("T - timing test for special blend modes.")


if __name__ == "__main__":
    usage()
    main()
