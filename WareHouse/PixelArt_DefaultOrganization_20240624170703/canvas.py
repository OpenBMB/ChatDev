'''
Canvas module for the Pixel Art Creator application.
Contains the Canvas class which manages the pixel grid and drawing operations.
'''
import tkinter as tk
from PIL import Image, ImageDraw
class Canvas:
    def __init__(self, master, pixel_size=20, grid_size=32):
        self.master = master
        self.pixel_size = pixel_size
        self.grid_size = grid_size
        self.color = "black"
        self.canvas = tk.Canvas(self.master, width=self.pixel_size*self.grid_size, 
                                height=self.pixel_size*self.grid_size)
        self.canvas.pack()
        self.create_grid()
        self.canvas.bind("<B1-Motion>", self.draw_pixel)
        self.canvas.bind("<Button-1>", self.draw_pixel)
    def create_grid(self):
        for i in range(0, self.grid_size * self.pixel_size, self.pixel_size):
            self.canvas.create_line([(i, 0), (i, self.grid_size * self.pixel_size)], fill='grey')
            self.canvas.create_line([(0, i), (self.grid_size * self.pixel_size, i)], fill='grey')
    def draw_pixel(self, event):
        x = event.x - (event.x % self.pixel_size)
        y = event.y - (event.y % self.pixel_size)
        self.canvas.create_rectangle(x, y, x + self.pixel_size, y + self.pixel_size, fill=self.color, outline="")
    def change_color(self, new_color):
        self.color = new_color
    def clear_canvas(self):
        self.canvas.delete("all")
        self.create_grid()
    def export_image(self, filename):
        image = Image.new("RGB", (self.grid_size * self.pixel_size, self.grid_size * self.pixel_size), "white")
        draw = ImageDraw.Draw(image)
        for item in self.canvas.find_all():
            if self.canvas.type(item) == "rectangle":
                coords = self.canvas.coords(item)
                color = self.canvas.itemcget(item, "fill")
                if color and color != "":
                    x1, y1, x2, y2 = coords
                    draw.rectangle([x1, y1, x2, y2], fill=color)
        image.save(filename)