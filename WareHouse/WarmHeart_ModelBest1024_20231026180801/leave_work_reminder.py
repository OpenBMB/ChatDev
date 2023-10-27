'''
This file contains the logic for reminding the user to leave work at 9 PM.
'''
from datetime import datetime, time
import schedule
import conversation_topics  # Add this import statement
def remind_leave_work(app):
    current_time = datetime.now().strftime("%H:%M")
    print(f"Reminder: It's {current_time}. Leave work now!")
    # Add your additional logic here, such as sending notifications or displaying reminders in the app
    # Implement your logic to remind the user to leave work at 9 PM
    # Update the reminder label in the app
    app.reminder_label.config(text=f"Reminder: It's {current_time}. Leave work now!")
    # Get conversation topics
    topics = conversation_topics.get_conversation_topics()
    print("Conversation topics for tomorrow:")
    topics = "\n".join(topics)
    app.reminder_label.config(text=f"To avoid awkward moments in the office elevator, here are some conversation topics: \n{topics}")
# Schedule the leave work reminder
schedule.every().day.at("21:00").do(lambda: remind_leave_work(app))