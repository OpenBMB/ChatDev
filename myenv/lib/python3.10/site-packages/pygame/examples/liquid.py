#!/usr/bin/env python
""" pygame.examples.liquid

This example demonstrates a simplish water effect of an
image. It attempts to create a hardware display surface that
can use pageflipping for faster updates. Note that the colormap
from the loaded GIF image is copied to the colormap for the
display surface.

This is based on the demo named F2KWarp by Brad Graham of Freedom2000
done in BlitzBasic. I was just translating the BlitzBasic code to
pygame to compare the results. I didn't bother porting the text and
sound stuff, that's an easy enough challenge for the reader :]
"""

import pygame as pg
import os
from math import sin
import time

main_dir = os.path.split(os.path.abspath(__file__))[0]


def main():
    # initialize and setup screen
    pg.init()
    screen = pg.display.set_mode((640, 480), pg.HWSURFACE | pg.DOUBLEBUF)

    # load image and quadruple
    imagename = os.path.join(main_dir, "data", "liquid.bmp")
    bitmap = pg.image.load(imagename)
    bitmap = pg.transform.scale2x(bitmap)
    bitmap = pg.transform.scale2x(bitmap)

    # get the image and screen in the same format
    if screen.get_bitsize() == 8:
        screen.set_palette(bitmap.get_palette())
    else:
        bitmap = bitmap.convert()

    # prep some variables
    anim = 0.0

    # mainloop
    xblocks = range(0, 640, 20)
    yblocks = range(0, 480, 20)
    stopevents = pg.QUIT, pg.KEYDOWN, pg.MOUSEBUTTONDOWN
    while True:
        for e in pg.event.get():
            if e.type in stopevents:
                return

        anim = anim + 0.02
        for x in xblocks:
            xpos = (x + (sin(anim + x * 0.01) * 15)) + 20
            for y in yblocks:
                ypos = (y + (sin(anim + y * 0.01) * 15)) + 20
                screen.blit(bitmap, (x, y), (xpos, ypos, 20, 20))

        pg.display.flip()
        time.sleep(0.01)


if __name__ == "__main__":
    main()
    pg.quit()


"""BTW, here is the code from the BlitzBasic example this was derived
from. i've snipped the sound and text stuff out.
-----------------------------------------------------------------
; Brad@freedom2000.com

; Load a bmp pic (800x600) and slice it into 1600 squares
Graphics 640,480
SetBuffer BackBuffer()
bitmap$="f2kwarp.bmp"
pic=LoadAnimImage(bitmap$,20,15,0,1600)

; use SIN to move all 1600 squares around to give liquid effect
Repeat
f=0:w=w+10:If w=360 Then w=0
For y=0 To 599 Step 15
For x = 0 To 799 Step 20
f=f+1:If f=1600 Then f=0
DrawBlock pic,(x+(Sin(w+x)*40))/1.7+80,(y+(Sin(w+y)*40))/1.7+60,f
Next:Next:Flip:Cls
Until KeyDown(1)
"""
