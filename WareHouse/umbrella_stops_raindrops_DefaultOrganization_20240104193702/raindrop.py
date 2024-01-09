import tkinter as tk
import random
class Raindrop:
    def __init__(self, canvas, x):
        self.canvas = canvas
        self.x = x
        self.y = 0
        self.id = self.canvas.create_oval(self.x-5, self.y-5, self.x+5, self.y+5, fill='gray')
        self.canvas.move(self.id, 0, self.y)
        self.fall_speed = random.randint(1, 5)
        self.canvas.after(50, self.fall)
    def fall(self):
        self.y += self.fall_speed
        self.canvas.move(self.id, 0, self.fall_speed)
        if self.y < self.canvas.winfo_height():
            self.canvas.after(50, self.fall)
        else:
            self.canvas.delete(self.id)