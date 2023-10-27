'''
This is the main file of the application.
'''
import tkinter as tk
from datetime import datetime
from schedule import generate_schedule
from timer import CountdownTimer
def start_timer():
    start_time = datetime.strptime(start_entry.get(), "%H:%M")
    end_time = datetime.strptime(end_entry.get(), "%H:%M")
    interval = int(interval_entry.get())
    schedule = generate_schedule(start_time, end_time, interval)
    timer = CountdownTimer(schedule)
    timer_label.config(text="Next break in: ")
    timer.start()
# Create the main window
window = tk.Tk()
window.title("Water Break Reminder")
# Create labels and entry fields
start_label = tk.Label(window, text="Start Time (HH:MM): ")
start_label.pack()
start_entry = tk.Entry(window)
start_entry.pack()
end_label = tk.Label(window, text="End Time (HH:MM): ")
end_label.pack()
end_entry = tk.Entry(window)
end_entry.pack()
interval_label = tk.Label(window, text="Interval (minutes): ")
interval_label.pack()
interval_entry = tk.Entry(window)
interval_entry.pack()
start_button = tk.Button(window, text="Start Timer", command=start_timer)
start_button.pack()
timer_label = tk.Label(window, text="")
timer_label.pack()
# Start the main event loop
window.mainloop()