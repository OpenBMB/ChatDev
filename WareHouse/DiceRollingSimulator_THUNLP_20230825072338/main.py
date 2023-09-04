import tkinter as tk
from dice import Dice
class DiceRollerApp:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Dice Roller")
        self.label = tk.Label(self.window, text="Enter the number of sides on the dice:")
        self.label.pack()
        self.entry = tk.Entry(self.window)
        self.entry.pack()
        self.button = tk.Button(self.window, text="Roll Dice", command=self.roll_dice)
        self.button.pack()
        self.result_label = tk.Label(self.window, text="")
        self.result_label.pack()
        self.dice = None
    def roll_dice(self):
        num_sides = self.entry.get()
        try:
            num_sides = int(num_sides)
        except ValueError:
            self.result_label.config(text="Invalid input. Please enter a valid number of sides.")
            return
        if num_sides <= 0:
            self.result_label.config(text="Number of sides must be a positive integer.")
            return
        self.dice = Dice(num_sides)
        roll_result = self.dice.roll()
        self.result_label.config(text=f"The dice rolled: {roll_result}")
    def run(self):
        self.window.mainloop()
if __name__ == "__main__":
    app = DiceRollerApp()
    app.run()