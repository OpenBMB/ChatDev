#!/usr/bin/env python
""" pygame.examples.music_drop_fade
Fade in and play music from a list while observing several events

Adds music files to a playlist whenever played by one of the following methods
Music files passed from the commandline are played
Music files and filenames are played when drag and dropped onto the pygame window
Polls the clipboard and plays music files if it finds one there

Keyboard Controls:
* Press space or enter to pause music playback
* Press up or down to change the music volume
* Press left or right to seek 5 seconds into the track
* Press escape to quit
* Press any other button to skip to the next music file in the list
"""

import pygame as pg
import os, sys

VOLUME_CHANGE_AMOUNT = 0.02  # how fast should up and down arrows change the volume?


def add_file(filename):
    """
    This function will check if filename exists and is a music file
    If it is the file will be added to a list of music files(even if already there)
    Type checking is by the extension of the file, not by its contents
    We can only discover if the file is valid when we mixer.music.load() it later

    It looks in the file directory and its data subdirectory
    """
    if filename.rpartition(".")[2].lower() not in music_file_types:
        print(f"{filename} not added to file list")
        print("only these files types are allowed: ", music_file_types)
        return False
    elif os.path.exists(filename):
        music_file_list.append(filename)
    elif os.path.exists(os.path.join(main_dir, filename)):
        music_file_list.append(os.path.join(main_dir, filename))
    elif os.path.exists(os.path.join(data_dir, filename)):
        music_file_list.append(os.path.join(data_dir, filename))
    else:
        print("file not found")
        return False
    print(f"{filename} added to file list")
    return True


def play_file(filename):
    """
    This function will call add_file and play it if successful
    The music will fade in during the first 4 seconds
    set_endevent is used to post a MUSIC_DONE event when the song finishes
    The main loop will call play_next() when the MUSIC_DONE event is received
    """
    global starting_pos

    if add_file(filename):
        try:  # we must do this in case the file is not a valid audio file
            pg.mixer.music.load(music_file_list[-1])
        except pg.error as e:
            print(e)  # print description such as 'Not an Ogg Vorbis audio stream'
            if filename in music_file_list:
                music_file_list.remove(filename)
                print(f"{filename} removed from file list")
            return
        pg.mixer.music.play(fade_ms=4000)
        pg.mixer.music.set_volume(volume)

        if filename.rpartition(".")[2].lower() in music_can_seek:
            print("file supports seeking")
            starting_pos = 0
        else:
            print("file does not support seeking")
            starting_pos = -1
        pg.mixer.music.set_endevent(MUSIC_DONE)


def play_next():
    """
    This function will play the next song in music_file_list
    It uses pop(0) to get the next song and then appends it to the end of the list
    The song will fade in during the first 4 seconds
    """

    global starting_pos
    if len(music_file_list) > 1:
        nxt = music_file_list.pop(0)

        try:
            pg.mixer.music.load(nxt)
        except pg.error as e:
            print(e)
            print(f"{nxt} removed from file list")

        music_file_list.append(nxt)
        print("starting next song: ", nxt)
    else:
        nxt = music_file_list[0]
    pg.mixer.music.play(fade_ms=4000)
    pg.mixer.music.set_volume(volume)
    pg.mixer.music.set_endevent(MUSIC_DONE)

    if nxt.rpartition(".")[2].lower() in music_can_seek:
        starting_pos = 0
    else:
        starting_pos = -1


def draw_text_line(text, y=0):
    """
    Draws a line of text onto the display surface
    The text will be centered horizontally at the given y position
    The text's height is added to y and returned to the caller
    """
    screen = pg.display.get_surface()
    surf = font.render(text, 1, (255, 255, 255))
    y += surf.get_height()
    x = (screen.get_width() - surf.get_width()) / 2
    screen.blit(surf, (x, y))
    return y


def change_music_position(amount):
    """
    Changes current playback position by amount seconds.
    This only works with OGG and MP3 files.
    music.get_pos() returns how many milliseconds the song has played, not
    the current position in the file. We must track the starting position
    ourselves. music.set_pos() will set the position in seconds.
    """
    global starting_pos

    if starting_pos >= 0:  # will be -1 unless play_file() was OGG or MP3
        played_for = pg.mixer.music.get_pos() / 1000.0
        old_pos = starting_pos + played_for
        starting_pos = old_pos + amount
        pg.mixer.music.play(start=starting_pos)
        print(f"jumped from {old_pos} to {starting_pos}")


MUSIC_DONE = pg.event.custom_type()  # event to be set as mixer.music.set_endevent()
main_dir = os.path.split(os.path.abspath(__file__))[0]
data_dir = os.path.join(main_dir, "data")

starting_pos = 0  # needed to fast forward and rewind
volume = 0.75
music_file_list = []
music_file_types = ("mp3", "ogg", "mid", "mod", "it", "xm", "wav")
music_can_seek = ("mp3", "ogg", "mod", "it", "xm")


def main():
    global font  # this will be used by the draw_text_line function
    global volume, starting_pos
    running = True
    paused = False

    # we will be polling for key up and key down events
    # users should be able to change the volume by holding the up and down arrows
    # the change_volume variable will be set by key down events and cleared by key up events
    change_volume = 0

    pg.init()
    pg.display.set_mode((640, 480))
    font = pg.font.SysFont("Arial", 24)
    clock = pg.time.Clock()

    pg.scrap.init()
    pg.SCRAP_TEXT = pg.scrap.get_types()[0]  # TODO remove when scrap module is fixed
    clipped = pg.scrap.get(pg.SCRAP_TEXT).decode("UTF-8")
    # store the current text from the clipboard TODO remove decode

    # add the command line arguments to the  music_file_list
    for arg in sys.argv[1:]:
        add_file(arg)
    play_file("house_lo.ogg")  # play default music included with pygame

    # draw instructions on screen
    y = draw_text_line("Drop music files or path names onto this window", 20)
    y = draw_text_line("Copy file names into the clipboard", y)
    y = draw_text_line("Or feed them from the command line", y)
    y = draw_text_line("If it's music it will play!", y)
    y = draw_text_line("SPACE to pause or UP/DOWN to change volume", y)
    y = draw_text_line("LEFT and RIGHT will skip around the track", y)
    draw_text_line("Other keys will start the next track", y)

    """
    This is the main loop
    It will respond to drag and drop, clipboard changes, and key presses
    """
    while running:
        for ev in pg.event.get():
            if ev.type == pg.QUIT:
                running = False
            elif ev.type == pg.DROPTEXT:
                play_file(ev.text)
            elif ev.type == pg.DROPFILE:
                play_file(ev.file)
            elif ev.type == MUSIC_DONE:
                play_next()
            elif ev.type == pg.KEYDOWN:
                if ev.key == pg.K_ESCAPE:
                    running = False  # exit loop
                elif ev.key in (pg.K_SPACE, pg.K_RETURN):
                    if paused:
                        pg.mixer.music.unpause()
                        paused = False
                    else:
                        pg.mixer.music.pause()
                        paused = True
                elif ev.key == pg.K_UP:
                    change_volume = VOLUME_CHANGE_AMOUNT
                elif ev.key == pg.K_DOWN:
                    change_volume = -VOLUME_CHANGE_AMOUNT
                elif ev.key == pg.K_RIGHT:
                    change_music_position(+5)
                elif ev.key == pg.K_LEFT:
                    change_music_position(-5)

                else:
                    play_next()

            elif ev.type == pg.KEYUP:
                if ev.key in (pg.K_UP, pg.K_DOWN):
                    change_volume = 0

        # is the user holding up or down?
        if change_volume:
            volume += change_volume
            volume = min(max(0, volume), 1)  # volume should be between 0 and 1
            pg.mixer.music.set_volume(volume)
            print("volume:", volume)

        # TODO remove decode when SDL2 scrap is fixed
        new_text = pg.scrap.get(pg.SCRAP_TEXT).decode("UTF-8")
        if new_text != clipped:  # has the clipboard changed?
            clipped = new_text
            play_file(clipped)  # try to play the file if it has

        pg.display.flip()
        clock.tick(9)  # keep CPU use down by updating screen less often

    pg.quit()


if __name__ == "__main__":
    main()
