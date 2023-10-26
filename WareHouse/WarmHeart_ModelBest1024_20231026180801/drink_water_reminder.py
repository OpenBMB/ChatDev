'''
This file contains the logic for reminding the user to drink water.
'''
from datetime import datetime, timedelta
import schedule
from avoid_sitting_reminder import remind_avoid_sitting  # Add this import statement
def remind_drink_water(app):
    current_time = datetime.now().strftime("%H:%M")
    print(f"Reminder: It's {current_time}. Drink water!")
    # Add your additional logic here, such as sending notifications or displaying reminders in the app
    # Schedule the next reminder
    next_reminder_time = datetime.now() + timedelta(minutes=60)
    schedule.every().day.at(next_reminder_time.strftime("%H:%M")).do(lambda: remind_drink_water(app))
    # Update the reminder label in the app
    app.reminder_label.config(text=f"Reminder: It's {current_time}. Drink water in one hour!")