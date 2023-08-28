'''
Canvas
This class represents the canvas where the user can draw and edit sprites pixel by pixel.
'''
import tkinter as tk
class Canvas(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, bg="white", bd=0, highlightthickness=0)
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.zoom = 1.0
        self.pixel_size = 10
        self.pixels = {}
    def on_click(self, event):
        x, y = self.get_pixel_coordinates(event.x, event.y)
        self.pixels[(x, y)] = "black"
        self.draw_pixel(x, y)
    def on_drag(self, event):
        x, y = self.get_pixel_coordinates(event.x, event.y)
        self.pixels[(x, y)] = "black"
        self.draw_pixel(x, y)
    def get_pixel_coordinates(self, x, y):
        x = int(x / (self.pixel_size * self.zoom))
        y = int(y / (self.pixel_size * self.zoom))
        return x, y
    def draw_pixel(self, x, y):
        x1 = x * self.pixel_size * self.zoom
        y1 = y * self.pixel_size * self.zoom
        x2 = x1 + self.pixel_size * self.zoom
        y2 = y1 + self.pixel_size * self.zoom
        self.create_rectangle(x1, y1, x2, y2, fill="black")
    def zoom_in(self):
        self.zoom *= 2.0
        self.redraw_pixels()
    def zoom_out(self):
        self.zoom /= 2.0
        self.redraw_pixels()
    def redraw_pixels(self):
        self.delete("all")
        for (x, y), color in self.pixels.items():
            self.draw_pixel(x, y)