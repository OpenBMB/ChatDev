'''
This is the main file of the DnD mission generator website.
'''
import tkinter as tk
from tkinter import ttk
import webbrowser
class DnDMissionGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("DnD Mission Generator")
        self.root.geometry("800x600")
        self.style = ttk.Style()
        self.style.theme_use("default")
        self.style.configure("TButton", padding=(10, 5, 10, 5), font='Helvetica 12')
        self.generate_button = ttk.Button(self.root, text="Generate Mission", command=self.generate_mission)
        self.generate_button.pack(pady=20)
    def generate_mission(self):
        # Add your mission generation logic here
        mission = self.generate_random_mission()
        self.open_mission_in_browser(mission)
    def generate_random_mission(self):
        # Add your random mission generation logic here
        mission = "This is a randomly generated mission."
        return mission
    def open_mission_in_browser(self, mission):
        # Open the mission in a new browser tab
        url = "https://example.com/mission?text=" + mission
        webbrowser.open_new_tab(url)
if __name__ == "__main__":
    root = tk.Tk()
    app = DnDMissionGenerator(root)
    root.mainloop()