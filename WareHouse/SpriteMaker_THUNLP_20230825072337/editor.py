'''
Editor
This class represents the pixel art editor. It contains the GUI elements and handles user interactions.
'''
import tkinter as tk
from canvas import Canvas
from toolbar import Toolbar
class Editor:
    def __init__(self, root):
        self.root = root
        self.root.title("Pixel Art Editor")
        self.canvas = Canvas(self.root)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.toolbar = Toolbar(self.root, self.canvas)
        self.toolbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind("<Configure>", self.on_canvas_resize)
    def on_canvas_resize(self, event):
        self.canvas.redraw_pixels()