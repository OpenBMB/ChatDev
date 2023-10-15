'''
This file contains the ColorPickerGUI class which represents the graphical user interface of the RGB color picker application.
It uses the tkinter library to create the GUI.
'''
import tkinter as tk
from tkinter import ttk
from tkinter.colorchooser import askcolor
class ColorPickerGUI:
    def __init__(self):
        # Create the main window
        self.root = tk.Tk()
        self.root.title("RGB Color Picker")
        # Create the RGB sliders
        self.red_slider = ttk.Scale(self.root, from_=0, to=255, orient=tk.HORIZONTAL)
        self.green_slider = ttk.Scale(self.root, from_=0, to=255, orient=tk.HORIZONTAL)
        self.blue_slider = ttk.Scale(self.root, from_=0, to=255, orient=tk.HORIZONTAL)
        # Create the color preview label
        self.color_label = tk.Label(self.root, width=20, height=5, relief=tk.RAISED)
        # Create the hex color code label
        self.hex_label = tk.Label(self.root, width=20, height=2, relief=tk.SUNKEN)
        # Create the pick color button
        self.pick_color_button = ttk.Button(self.root, text="Pick Color", command=self.pick_color)
        # Pack the widgets
        self.red_slider.pack()
        self.green_slider.pack()
        self.blue_slider.pack()
        self.color_label.pack()
        self.hex_label.pack()
        self.pick_color_button.pack()
    def start(self):
        # Start the main event loop
        self.root.mainloop()
    def pick_color(self):
        # Open the color picker dialog
        color = askcolor()
        if color[1] is not None:
            # Update the RGB sliders and color labels
            self.red_slider.set(int(color[0][0]))
            self.green_slider.set(int(color[0][1]))
            self.blue_slider.set(int(color[0][2]))
            self.update_color_label()
    def update_color_label(self):
        # Get the RGB values from the sliders
        red = int(self.red_slider.get())
        green = int(self.green_slider.get())
        blue = int(self.blue_slider.get())
        # Update the color preview label
        self.color_label.configure(bg=f"#{red:02x}{green:02x}{blue:02x}")
        # Update the hex color code label
        self.hex_label.configure(text=f"#{red:02x}{green:02x}{blue:02x}")