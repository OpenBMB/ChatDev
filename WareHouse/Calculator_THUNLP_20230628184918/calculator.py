'''
This file contains the Calculator class that defines the calculator GUI and its functionality.
'''
import tkinter as tk
from PIL import Image, ImageTk
class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Basic Calculator")
        self.entry = tk.Entry(self.root, width=30)
        self.entry.grid(row=0, column=0, columnspan=4, padx=10, pady=10)
        self.create_buttons()
    def create_buttons(self):
        buttons = [
            ("7", "button_7.png"), ("8", "button_8.png"), ("9", "button_9.png"), ("/", "button_divide.png"),
            ("4", "button_4.png"), ("5", "button_5.png"), ("6", "button_6.png"), ("*", "button_multiply.png"),
            ("1", "button_1.png"), ("2", "button_2.png"), ("3", "button_3.png"), ("-", "button_minus.png"),
            ("0", "button_0.png"), (".", "button_decimal.png"), ("=", "button_equal.png"), ("+", "button_plus.png")
        ]
        row = 1
        col = 0
        for button_text, image_file in buttons:
            image = Image.open(image_file).resize((50, 50))
            photo = ImageTk.PhotoImage(image)
            button = tk.Button(self.root, image=photo, command=lambda button_text=button_text: self.button_click(button_text))
            button.image = photo
            button.grid(row=row, column=col, padx=5, pady=5)
            col += 1
            if col > 3:
                col = 0
                row += 1
    def button_click(self, button_text):
        current_value = self.entry.get()
        if button_text == "=":
            try:
                result = eval(current_value)
                self.entry.delete(0, tk.END)
                self.entry.insert(tk.END, str(result))
            except:
                self.entry.delete(0, tk.END)
                self.entry.insert(tk.END, "Error")
        else:
            self.entry.insert(tk.END, button_text)