'''
This is the main file of the virtual aquarium life simulator.
'''
import tkinter as tk
from aquarium import Aquarium, Fish, Effect
class AquariumApp(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("Virtual Aquarium")
        self.aquarium = Aquarium()
        self.canvas = tk.Canvas(self, width=800, height=600)
        self.canvas.pack()
        self.update_aquarium()
    def update_aquarium(self):
        self.canvas.delete("all")
        self.aquarium.update()
        self.draw_aquarium()
        self.after(100, self.update_aquarium)
    def draw_aquarium(self):
        for fish in self.aquarium.fishes:
            self.canvas.create_oval(fish.x, fish.y, fish.x+20, fish.y+20, fill="blue")
        for effect in self.aquarium.effects:
            self.canvas.create_oval(effect.x, effect.y, effect.x+10, effect.y+10, fill="yellow")
if __name__ == "__main__":
    app = AquariumApp()
    app.mainloop()