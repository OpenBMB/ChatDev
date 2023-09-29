'''
This file contains the UI class which represents the graphical user interface for the stone age city simulation.
'''
import tkinter as tk
class UI:
    def __init__(self, city):
        self.city = city
        self.root = tk.Tk()
        self.root.title("Stone Age City Simulation")
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()
        self.root.after(1000, self.update)
    def update(self):
        self.city.advance()
        self.draw_agents()
        self.root.after(1000, self.update)
    def draw_agents(self):
        self.canvas.delete("all")
        for agent in self.city.agents:
            self.canvas.create_oval(10, 10, 30, 30, fill="red")
    def run(self):
        self.root.mainloop()