'''
Pixel Art Editor
This is the main file for the pixel art editor application. It initializes the GUI and starts the application.
'''
import tkinter as tk
from editor import Editor
def main():
    root = tk.Tk()
    editor = Editor(root)
    root.mainloop()
if __name__ == "__main__":
    main()