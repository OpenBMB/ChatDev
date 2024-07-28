'''
This is the main file that serves as the entry point for the software.
'''
import tkinter as tk
from landing_page import LandingPage
def main():
    root = tk.Tk()
    landing_page = LandingPage(root)
    landing_page.pack()
    root.mainloop()
if __name__ == "__main__":
    main()