'''
This is the main file that runs the online HTML world clock application.
'''
import tkinter as tk
from datetime import datetime
import pytz
class WorldClockApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Online HTML World Clock")
        self.clock_label = tk.Label(self.master, font=("Arial", 24))
        self.clock_label.pack(pady=20)
        self.update_clock()
    def update_clock(self):
        current_time = datetime.now()
        utc_time = pytz.utc.localize(current_time)
        timezones = {
            "New York": "America/New_York",
            "London": "Europe/London",
            "Tokyo": "Asia/Tokyo",
            "Sydney": "Australia/Sydney",
            "Dublin": "Europe/Dublin"
        }
        clock_text = ""
        for city, timezone in timezones.items():
            city_time = utc_time.astimezone(pytz.timezone(timezone))
            clock_text += f"{city}: {city_time.strftime('%H:%M:%S')}\n"
        self.clock_label.config(text=clock_text)
        self.master.after(1000, self.update_clock)
def main():
    root = tk.Tk()
    app = WorldClockApp(root)
    root.mainloop()
if __name__ == "__main__":
    main()