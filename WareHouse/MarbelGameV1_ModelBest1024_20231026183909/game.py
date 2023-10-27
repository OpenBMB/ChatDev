'''
This file contains the Game class which manages the pinball game.
'''
import tkinter as tk
from player import Player
class Game:
    def __init__(self, window):
        self.window = window
        self.canvas = tk.Canvas(self.window, width=800, height=600)
        self.canvas.pack()
        self.player = Player(self.canvas)
    def start(self):
        self.canvas.bind("<Button-1>", self.player.move)
        self.canvas.focus_set()
        self.update()
    def update(self):
        self.player.update()
        self.window.after(10, self.update)
# player.py