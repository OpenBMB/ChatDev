'''
This file contains the logic for reminding the user to avoid prolonged sitting.
'''
import schedule
from datetime import datetime, timedelta
def remind_avoid_sitting(app):
    current_time = datetime.now().strftime("%H:%M")
    # Add your additional logic here, such as sending notifications or displaying reminders in the app
    # Schedule the next reminder
    next_reminder_time = datetime.now() + timedelta(hours=1)
    schedule.every().day.at(next_reminder_time.strftime("%H:%M")).do(lambda: remind_avoid_sitting(app))
    app.reminder_label.config(text=f"Reminder: It's {current_time}. Avoid prolonged sitting!\n" + f"Next reminder: {next_reminder_time.strftime('%H:%M')}")
    # Implement your logic to remind the user to avoid prolonged sitting
# Add the missing import statement for leave_work_reminder