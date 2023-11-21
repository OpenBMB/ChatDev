'''
This is the main file of the reminder app.
'''
import tkinter as tk
from datetime import datetime, timedelta
import schedule
from drink_water_reminder import remind_drink_water
from avoid_sitting_reminder import remind_avoid_sitting
from leave_work_reminder import remind_leave_work
from conversation_topics import get_conversation_topics
class ReminderApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Reminder App")
        self.create_widgets()
        self.root.mainloop()
    def create_widgets(self):
        self.reminder_label = tk.Label(self.root, text="")
        self.reminder_label.pack()
        self.drink_water_button = tk.Button(self.root, text="Drink Water", command=lambda: remind_drink_water(self))
        self.drink_water_button.pack()
        self.avoid_sitting_button = tk.Button(self.root, text="Avoid Sitting", command=lambda: remind_avoid_sitting(self))
        self.avoid_sitting_button.pack()
        self.leave_work_button = tk.Button(self.root, text="Leave Work", command=lambda: remind_leave_work(self))
        self.leave_work_button.pack()
if __name__ == "__main__":
    app = ReminderApp()