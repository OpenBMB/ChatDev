'''
This file contains the countdown timer functionality.
'''
import tkinter as tk
from datetime import datetime, date
class CountdownTimer:
    def __init__(self, schedule):
        self.schedule = schedule
        self.current_index = 0
        self.remaining_time = 0
        self.timer_label = None
    def start(self):
        self.update_timer()
    def update_timer(self):
        now = datetime.now().time()

        # today = date.today()

        current_break = self.schedule[self.current_index].time()

        # current_break = datetime.combine(today, current_break)
        if now >= current_break:
            self.current_index += 1
            if self.current_index >= len(self.schedule):
                self.timer_label.config(text="No more breaks scheduled.")
                return
            current_break = self.schedule[self.current_index].time()
        remaining_time = datetime.combine(datetime.today(), current_break) - datetime.combine(datetime.today(), now)

        # remaining_time =  current_break - now

        self.remaining_time = remaining_time.total_seconds()
        if self.timer_label:
            self.timer_label.pack_forget()
        self.timer_label = tk.Label(text=f"Next break in: {remaining_time}")
        self.timer_label.pack()
        self.timer_label.after(1000, self.update_timer)