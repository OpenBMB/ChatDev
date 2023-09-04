'''
This is the main file for the digital clock application.
It initializes the GUI and starts the clock.
'''
import tkinter as tk
from datetime import datetime
class DigitalClockApp:
    def __init__(self, root):
        """
        Initializes the DigitalClockApp class.
        Args:
            root (tkinter.Tk): The root window of the application.
        """
        self.root = root
        self.root.title("Digital Clock")
        self.time_label = tk.Label(root, font=("Arial", 80), bg="black", fg="white")
        self.time_label.pack(padx=50, pady=50)
        self.update_clock()
    def update_clock(self):
        """
        Updates the clock label with the current time.
        This method is called every second to update the clock label with the current time.
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_clock)
if __name__ == "__main__":
    root = tk.Tk()
    app = DigitalClockApp(root)
    root.mainloop()