#!/usr/bin/env python
""" pygame.examples.scaletest

Shows an interactive image scaler.

"""
import sys
import time
import pygame as pg


def main(imagefile, convert_alpha=False, run_speed_test=False):
    """show an interactive image scaler

    Args:
        imagefile - name of source image (required)
        convert_alpha - use convert_alpha() on the surf (default False)
        run_speed_test - (default False)
    """

    # initialize display
    pg.display.init()
    # load background image
    background = pg.image.load(imagefile)

    if run_speed_test:
        if convert_alpha:
            # convert_alpha() requires the display mode to be set
            pg.display.set_mode((1, 1))
            background = background.convert_alpha()

        SpeedTest(background)
        return

    # start fullscreen mode
    screen = pg.display.set_mode((1024, 768), pg.FULLSCREEN)
    if convert_alpha:
        background = background.convert_alpha()

    # turn off the mouse pointer
    pg.mouse.set_visible(0)
    # main loop
    bRunning = True
    bUp = False
    bDown = False
    bLeft = False
    bRight = False
    cursize = [background.get_width(), background.get_height()]
    while bRunning:
        image = pg.transform.smoothscale(background, cursize)
        imgpos = image.get_rect(centerx=512, centery=384)
        screen.fill((255, 255, 255))
        screen.blit(image, imgpos)
        pg.display.flip()
        for event in pg.event.get():
            if event.type == pg.QUIT or (
                event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE
            ):
                bRunning = False
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_UP:
                    bUp = True
                if event.key == pg.K_DOWN:
                    bDown = True
                if event.key == pg.K_LEFT:
                    bLeft = True
                if event.key == pg.K_RIGHT:
                    bRight = True
            if event.type == pg.KEYUP:
                if event.key == pg.K_UP:
                    bUp = False
                if event.key == pg.K_DOWN:
                    bDown = False
                if event.key == pg.K_LEFT:
                    bLeft = False
                if event.key == pg.K_RIGHT:
                    bRight = False
        if bUp:
            cursize[1] -= 2
            if cursize[1] < 1:
                cursize[1] = 1
        if bDown:
            cursize[1] += 2
        if bLeft:
            cursize[0] -= 2
            if cursize[0] < 1:
                cursize[0] = 1
        if bRight:
            cursize[0] += 2
    pg.quit()


def SpeedTest(image):
    print(f"\nImage Scaling Speed Test - Image Size {str(image.get_size())}\n")

    imgsize = [image.get_width(), image.get_height()]
    duration = 0.0
    for i in range(128):
        shrinkx = (imgsize[0] * i) // 128
        shrinky = (imgsize[1] * i) // 128
        start = time.time()
        tempimg = pg.transform.smoothscale(image, (shrinkx, shrinky))
        duration += time.time() - start
        del tempimg

    print(f"Average transform.smoothscale shrink time: {duration / 128 * 1000:.4f} ms.")

    duration = 0.0
    for i in range(128):
        expandx = (imgsize[0] * (i + 129)) // 128
        expandy = (imgsize[1] * (i + 129)) // 128
        start = time.time()
        tempimg = pg.transform.smoothscale(image, (expandx, expandy))
        duration += time.time() - start
        del tempimg

    print(f"Average transform.smoothscale expand time: {duration / 128 * 1000:.4f} ms.")

    duration = 0.0
    for i in range(128):
        shrinkx = (imgsize[0] * i) // 128
        shrinky = (imgsize[1] * i) // 128
        start = time.time()
        tempimg = pg.transform.scale(image, (shrinkx, shrinky))
        duration += time.time() - start
        del tempimg

    print(f"Average transform.scale shrink time: {duration / 128 * 1000:.4f} ms.")

    duration = 0.0
    for i in range(128):
        expandx = (imgsize[0] * (i + 129)) // 128
        expandy = (imgsize[1] * (i + 129)) // 128
        start = time.time()
        tempimg = pg.transform.scale(image, (expandx, expandy))
        duration += time.time() - start
        del tempimg

    print(f"Average transform.scale expand time: {duration / 128 * 1000:.4f} ms.")


if __name__ == "__main__":
    # check input parameters
    if len(sys.argv) < 2:
        print(f"\nUsage: {sys.argv[0]} imagefile [-t] [-convert_alpha]")
        print("    imagefile       image filename (required)")
        print("    -t              run speed test")
        print("    -convert_alpha  use convert_alpha() on the image's " "surface\n")
    else:
        main(
            sys.argv[1],
            convert_alpha="-convert_alpha" in sys.argv,
            run_speed_test="-t" in sys.argv,
        )
