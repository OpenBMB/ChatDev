'''
Pixel Art Creator App
'''
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog
from PIL import Image
class PixelArtCreatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pixel Art Creator")
        self.canvas = PixelCanvas(self)
        self.toolbar = Toolbar(self, self.canvas)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
class PixelCanvas(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, bg="white")
        self.pixel_size = 10
        self.current_color = "black"
        self.undo_stack = []
        self.redo_stack = []
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
    def on_click(self, event):
        x, y = event.x, event.y
        self.draw_pixel(x, y)
    def on_drag(self, event):
        x, y = event.x, event.y
        self.draw_pixel(x, y)
    def draw_pixel(self, x, y):
        x1 = x - (x % self.pixel_size)
        y1 = y - (y % self.pixel_size)
        x2 = x1 + self.pixel_size
        y2 = y1 + self.pixel_size
        self.create_rectangle(x1, y1, x2, y2, fill=self.current_color, outline="")
        self.undo_stack.append(self.get_state())
    def set_pixel_size(self, size):
        self.pixel_size = size
    def set_color(self, color):
        self.current_color = color
    def clear_canvas(self):
        self.delete("all")
        self.undo_stack = []
        self.redo_stack = []
    def undo(self):
        if self.undo_stack:
            state = self.undo_stack.pop()
            self.redo_stack.append(self.get_state())
            self.set_state(state)
    def redo(self):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(self.get_state())
            self.set_state(state)
    def get_state(self):
        return self.postscript(colormode="color")
    def set_state(self, state):
        self.delete("all")
        self.create_image((0, 0), image=tk.PhotoImage(data=state), anchor=tk.NW)
class Toolbar(tk.Frame):
    def __init__(self, master, canvas):
        super().__init__(master)
        self.canvas = canvas
        self.create_widgets()
    def create_widgets(self):
        self.pixel_size_label = ttk.Label(self, text="Pixel Size:")
        self.pixel_size_entry = ttk.Entry(self, width=5)
        self.pixel_size_entry.insert(tk.END, "10")
        self.pixel_size_entry.bind("<Return>", self.on_pixel_size_change)
        self.color_button = ttk.Button(self, text="Color", command=self.on_color_button_click)
        self.clear_button = ttk.Button(self, text="Clear", command=self.on_clear_button_click)
        self.undo_button = ttk.Button(self, text="Undo", command=self.on_undo_button_click)
        self.redo_button = ttk.Button(self, text="Redo", command=self.on_redo_button_click)
        self.pixel_size_label.pack(side=tk.TOP, pady=5)
        self.pixel_size_entry.pack(side=tk.TOP)
        self.color_button.pack(side=tk.TOP, pady=5)
        self.clear_button.pack(side=tk.TOP)
        self.undo_button.pack(side=tk.TOP)
        self.redo_button.pack(side=tk.TOP)
    def on_pixel_size_change(self, event):
        size = int(self.pixel_size_entry.get())
        self.canvas.set_pixel_size(size)
    def on_color_button_click(self):
        color = colorchooser.askcolor()[1]
        self.canvas.set_color(color)
    def on_clear_button_click(self):
        self.canvas.clear_canvas()
    def on_undo_button_click(self):
        self.canvas.undo()
    def on_redo_button_click(self):
        self.canvas.redo()
if __name__ == "__main__":
    app = PixelArtCreatorApp()
    app.mainloop()