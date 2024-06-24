'''
Toolbar module for the Pixel Art Creator application.
Contains the Toolbar class which manages the editing tools and color selection.
'''
import tkinter as tk
from tkinter import colorchooser, filedialog
class Toolbar:
    def __init__(self, master, canvas):
        self.master = master
        self.canvas = canvas
        self.frame = tk.Frame(self.master, width=100, bg='lightgrey')
        self.frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.create_widgets()
    def create_widgets(self):
        self.color_button = tk.Button(self.frame, text="Change Color", command=self.change_color)
        self.color_button.pack(pady=5)
        self.clear_button = tk.Button(self.frame, text="Clear Canvas", command=self.canvas.clear_canvas)
        self.clear_button.pack(pady=5)
        self.export_button = tk.Button(self.frame, text="Export Image", command=self.export_image)
        self.export_button.pack(pady=5)
    def change_color(self):
        color = colorchooser.askcolor(title="Choose color")[1]
        if color:
            self.canvas.change_color(color)
    def export_image(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", 
                                                 filetypes=[("PNG files", "*.png"), ("All Files", "*.*")])
        if file_path:
            self.canvas.export_image(file_path)