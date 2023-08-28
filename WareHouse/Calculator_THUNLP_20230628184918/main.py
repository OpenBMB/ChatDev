'''
This is the main file that initializes the calculator GUI.
'''
import tkinter as tk
from calculator import Calculator
if __name__ == "__main__":
    root = tk.Tk()
    calculator = Calculator(root)
    root.mainloop()