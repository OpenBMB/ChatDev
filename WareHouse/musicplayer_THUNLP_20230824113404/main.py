'''
This is the main file for the Music Player application. It uses the tkinter library for the GUI, pygame for playing the music, and mutagen for handling the metadata of mp3 files. The changes include a directory selection dialog, metadata display on the GUI, improved error handling, and a method to unpause the music. Now, it also handles the case where the user selects a non-mp3 file. The bug related to the os module has been fixed by removing the os.setsid() line and using the selected directory directly when loading the mp3 files.
'''
import os
import pygame
from tkinter import *
from tkinter import filedialog
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2
class MusicPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("MusicPlayer")
        self.root.geometry("1000x200+200+200")
        pygame.init()
        pygame.mixer.init()
        self.track = StringVar()
        self.status = StringVar()
        self.metadata = StringVar()
        self.volume = DoubleVar()
        self.volume.set(pygame.mixer.music.get_volume())
        trackframe = LabelFrame(self.root, text="Song Track", font=("times new roman", 15, "bold"), bg="Navyblue",
                                fg="white", bd=5, relief=GROOVE)
        trackframe.place(x=0, y=0, width=600, height=100)
        songtrack = Label(trackframe, textvariable=self.track, width=20, font=("times new roman", 24, "bold"),
                          bg="Orange", fg="gold").grid(row=0, column=0, padx=10, pady=5)
        trackstatus = Label(trackframe, textvariable=self.status, font=("times new roman", 24, "bold"), bg="orange",
                            fg="gold").grid(row=0, column=1, padx=10, pady=5)
        metadata_label = Label(trackframe, textvariable=self.metadata, font=("times new roman", 16, "bold"),
                               bg="orange", fg="gold")
        metadata_label.grid(row=1, column=0, padx=10, pady=5)
        volumecontrol = Scale(trackframe, variable=self.volume, from_=0.0, to=1.0, orient=HORIZONTAL, resolution=0.1,
                              command=self.change_volume)
        volumecontrol.grid(row=0, column=2, padx=10, pady=5)
        buttonframe = LabelFrame(self.root, text="Control Panel", font=("times new roman", 15, "bold"), bg="grey",
                                 fg="white", bd=5, relief=GROOVE)
        buttonframe.place(x=0, y=100, width=600, height=100)
        playbtn = Button(buttonframe, text="PLAY", command=self.play_music, width=10, height=1,
                         font=("times new roman", 16, "bold"), fg="navyblue", bg="pink").grid(row=0, column=0,
                                                                                                padx=10, pady=5)
        pausebtn = Button(buttonframe, text="PAUSE", command=self.pause_music, width=8, height=1,
                          font=("times new roman", 16, "bold"), fg="navyblue", bg="pink").grid(row=0, column=1,
                                                                                               padx=10, pady=5)
        stopbtn = Button(buttonframe, text="STOP", command=self.stop_music, width=10, height=1,
                         font=("times new roman", 16, "bold"), fg="navyblue", bg="pink").grid(row=0, column=2,
                                                                                              padx=10, pady=5)
        unpausebtn = Button(buttonframe, text="UNPAUSE", command=self.unpause_music, width=10, height=1,
                            font=("times new roman", 16, "bold"), fg="navyblue", bg="pink").grid(row=0, column=3,
                                                                                                 padx=10, pady=5)
        songsframe = LabelFrame(self.root, text="Song Playlist", font=("times new roman", 15, "bold"), bg="grey",
                                fg="white", bd=5, relief=GROOVE)
        songsframe.place(x=600, y=0, width=400, height=200)
        scrol_y = Scrollbar(songsframe, orient=VERTICAL)
        self.playlist = Listbox(songsframe, yscrollcommand=scrol_y.set, selectbackground="gold", selectmode=SINGLE,
                                font=("times new roman", 12, "bold"), bg="silver", fg="navyblue", bd=5, relief=GROOVE)
        scrol_y.pack(side=RIGHT, fill=Y)
        scrol_y.config(command=self.playlist.yview)
        self.playlist.pack(fill=BOTH)
        self.select_directory()
    def select_directory(self):
        self.directory = filedialog.askdirectory()
        self.load_mp3_files()
    def load_mp3_files(self):
        songtracks = os.listdir(self.directory)
        self.playlist.delete(0, END)
        for track in songtracks:
            if track.endswith('.mp3'):
                self.playlist.insert(END, track)
    def play_music(self):
        try:
            selected_track = self.playlist.get(ACTIVE)
            if not selected_track.endswith('.mp3'):
                self.metadata.set("Error: Selected file is not an mp3 file.")
                return
            self.track.set(selected_track)
            self.status.set("-Playing")
            pygame.mixer.music.load(os.path.join(self.directory, selected_track))
            pygame.mixer.music.play()
            audio = MP3(os.path.join(self.directory, selected_track), ID3=ID3)
            self.metadata.set('Title: ' + audio["TIT2"].text[0] + ', Artist: ' + audio["TPE1"].text[0] + ', Duration: ' +
                              str(audio.info.length))
        except Exception as e:
            self.metadata.set("An error occurred: " + str(e))
    def stop_music(self):
        self.status.set("-Stopped")
        pygame.mixer.music.stop()
    def pause_music(self):
        self.status.set("-Paused")
        pygame.mixer.music.pause()
    def unpause_music(self):
        self.status.set("-Playing")
        pygame.mixer.music.unpause()
    def change_volume(self, v):
        pygame.mixer.music.set_volume(self.volume.get())
root = Tk()
MusicPlayer(root)
root.mainloop()