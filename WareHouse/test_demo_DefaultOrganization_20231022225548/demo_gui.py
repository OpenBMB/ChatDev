import tkinter as tk
class DemoGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Demo GUI")
        self.create_widgets()
    def create_widgets(self):
        self.label = tk.Label(self.root, text="Hello, World!")
        self.label.pack()
        self.button = tk.Button(self.root, text="Click Me", command=self.button_clicked)
        self.button.pack()
    def button_clicked(self):
        self.label.config(text="Button Clicked!")