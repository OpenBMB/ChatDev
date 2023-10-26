'''
This is the main file that runs the demo.
'''
import tkinter as tk
from demo_gui import DemoGUI
def main():
    root = tk.Tk()
    demo_gui = DemoGUI(root)
    root.mainloop()
if __name__ == "__main__":
    main()