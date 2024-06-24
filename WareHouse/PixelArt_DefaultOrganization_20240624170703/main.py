'''
Main file for the Pixel Art Creator application.
Contains the PixelArtCreator class which sets up the main window and manages the application.
'''
import tkinter as tk
from canvas import Canvas
from toolbar import Toolbar
class PixelArtCreator:
    def __init__(self, master):
        self.master = master
        self.master.title("Pixel Art Creator")
        self.canvas = Canvas(self.master)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.toolbar = Toolbar(self.master, self.canvas)
        self.toolbar.pack(side=tk.RIGHT, fill=tk.Y)
if __name__ == "__main__":
    root = tk.Tk()
    app = PixelArtCreator(root)
    root.mainloop()