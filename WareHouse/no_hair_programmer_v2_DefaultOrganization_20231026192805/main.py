'''
This is the main file of the Programmer Life Reboot Simulator application.
'''
import tkinter as tk
from tkinter import messagebox
import random
class ProgrammerLifeSimulator:
    hair_loss_events = [
        "秃头", "地中海", "严重掉发", "隐约掉发", "发量普通", "乌黑浓密", "多毛症"
    ]
    def __init__(self):
        self.age = 18
        self.hair = "乌黑浓密"
        self.root = tk.Tk()
        self.root.title("Programmer Life Reboot Simulator")
        self.root.geometry("400x300")
        self.age_label = tk.Label(self.root, text="Age: 18")
        self.age_label.pack()
        self.hair_label = tk.Label(self.root, text="Hair: 乌黑浓密")
        self.hair_label.pack()
        self.go_on_button = tk.Button(self.root, text="Go On", command=self.go_on)
        self.go_on_button.pack()
    def go_on(self):
        n = random.randint(1, 10)
        self.age += n
        self.age_label.config(text=f"Age: {self.age}")
        hair_loss = random.choice(ProgrammerLifeSimulator.hair_loss_events)
        self.hair_label.config(text=f"Hair: {hair_loss}")
        if hair_loss == "秃头":
            self.root.destroy()
            messagebox.showinfo("Game Over", f"You lived until {self.age} years old. Congratulations on reaching the pinnacle of a programmer's life - 秃头!")
if __name__ == "__main__":
    simulator = ProgrammerLifeSimulator()
    simulator.root.mainloop()