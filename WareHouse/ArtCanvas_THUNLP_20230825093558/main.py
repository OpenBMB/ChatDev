'''
Virtual Painting Studio App
'''
import tkinter as tk
from tkinter import Canvas, Frame
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Virtual Painting Studio")
        self.canvas = Canvas(self)
        self.canvas.pack()
        self.toolbar = Toolbar(self)
        self.toolbar.pack()
class Canvas(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, width=800, height=600, bg="white")
        self.bind("<B1-Motion>", self.draw)
    def draw(self, event):
        x, y = event.x, event.y
        brush_size = self.master.toolbar.get_brush_size()
        brush_color = self.master.toolbar.get_brush_color()
        self.create_oval(x-brush_size, y-brush_size, x+brush_size, y+brush_size, fill=brush_color)
class Toolbar(Frame):
    def __init__(self, master):
        super().__init__(master)
        self.brush_size = tk.Scale(self, from_=1, to=10, orient=tk.HORIZONTAL, label="Brush Size")
        self.brush_size.set(5)
        self.brush_size.pack(side=tk.LEFT)
        self.brush_color = tk.StringVar()
        self.brush_color.set("black")
        self.color_menu = tk.OptionMenu(self, self.brush_color, "black", "red", "green", "blue")
        self.color_menu.pack(side=tk.LEFT)
    def get_brush_size(self):
        return self.brush_size.get()
    def get_brush_color(self):
        return self.brush_color.get()
if __name__ == "__main__":
    app = App()
    app.mainloop()