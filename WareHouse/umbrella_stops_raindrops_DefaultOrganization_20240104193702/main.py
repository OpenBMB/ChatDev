import tkinter as tk
from raindrop import Raindrop
import random
class MainApp:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=800, height=600)
        self.canvas.pack()
        self.umbrella = self.canvas.create_oval(0, 0, 50, 50, fill='blue')
        self.canvas.bind('<Motion>', self.move_umbrella)
        self.raindrops = []
        self.create_raindrop()  # Start creating raindrops
        self.root.after(100, self.check_raindrop_collision)  # Check collision periodically
    def move_umbrella(self, event):
        x, y = event.x, event.y
        self.canvas.coords(self.umbrella, x-25, y-25, x+25, y+25)
    def check_raindrop_collision(self):
        umbrella_coords = self.canvas.coords(self.umbrella)
        for raindrop in self.raindrops:
            raindrop_coords = self.canvas.coords(raindrop.id)
            if self.is_collision(umbrella_coords, raindrop_coords):
                self.canvas.delete(raindrop.id)
                self.raindrops.remove(raindrop)
        self.root.after(100, self.check_raindrop_collision)  # Check collision periodically
    def is_collision(self, coords1, coords2):
        if len(coords2) < 4:
            return False
        x1, y1, x2, y2 = coords1
        x3, y3, x4, y4 = coords2
        if x3 < x2 and x4 > x1 and y3 < y2 and y4 > y1:
            return True
        return False
    def create_raindrop(self):
        x = random.randint(0, self.canvas.winfo_width())  # Random x position
        raindrop = Raindrop(self.canvas, x)
        self.raindrops.append(raindrop)
        self.canvas.after(10, self.create_raindrop)
root = tk.Tk()
app = MainApp(root)
root.mainloop()
