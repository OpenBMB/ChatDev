'''
This file contains the logic for generating the schedule of water breaks.
'''
from datetime import timedelta
def generate_schedule(start_time, end_time, interval):
    schedule = []
    current_time = start_time
    while current_time < end_time:
        schedule.append(current_time)
        current_time += timedelta(minutes=interval)
    return schedule