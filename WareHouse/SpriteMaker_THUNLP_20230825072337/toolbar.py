'''
Toolbar
This class represents the toolbar with various tools for coloring, shading, and creating animation frames.
'''
import tkinter as tk
class Toolbar(tk.Frame):
    def __init__(self, parent, canvas):
        super().__init__(parent)
        self.canvas = canvas
        self.color_picker = tk.Button(self, text="Color Picker", command=self.pick_color)
        self.color_picker.pack()
        self.zoom_in_button = tk.Button(self, text="Zoom In", command=self.canvas.zoom_in)
        self.zoom_in_button.pack()
        self.zoom_out_button = tk.Button(self, text="Zoom Out", command=self.canvas.zoom_out)
        self.zoom_out_button.pack()
    def pick_color(self):
        color = tk.colorchooser.askcolor()[1]
        self.canvas.itemconfig(tk.ALL, fill=color)