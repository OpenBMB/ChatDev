'''
This file contains the main application logic and GUI setup.
'''
import tkinter as tk
from timer import Timer
class TimerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Timer App")
        self.timer = Timer()
        self.time_var = tk.StringVar()
        self.time_var.set("00:00:00")
        self.format_var = tk.StringVar()
        self.format_var.set("HH:MM:SS")
        self.create_widgets()
    def create_widgets(self):
        self.time_label = tk.Label(self, textvariable=self.time_var, font=("Arial", 24))
        self.time_label.pack(pady=10)
        self.format_label = tk.Label(self, text="Time Format:")
        self.format_label.pack()
        self.format_entry = tk.Entry(self, textvariable=self.format_var)
        self.format_entry.pack(pady=5)
        self.start_button = tk.Button(self, text="Start", command=self.start_timer)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(self, text="Stop", command=self.stop_timer)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.reset_button = tk.Button(self, text="Reset", command=self.reset_timer)
        self.reset_button.pack(side=tk.LEFT, padx=5)
    def start_timer(self):
        self.timer.start()
        self.update_time()
    def stop_timer(self):
        self.timer.stop()
    def reset_timer(self):
        self.timer.reset()
        self.update_time()
    def update_time(self):
        if self.timer.is_running():
            try:
                time = self.timer.get_time(self.format_var.get())
                self.time_var.set(time)
            except ValueError:
                self.time_var.set("Invalid time format")
        self.after(100, self.update_time)
if __name__ == "__main__":
    app = TimerApp()
    app.mainloop()