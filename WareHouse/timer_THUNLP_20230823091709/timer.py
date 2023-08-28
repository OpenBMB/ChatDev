'''
This file contains the Timer class that handles the timer logic.
'''
import time
class Timer:
    def __init__(self):
        self.start_time = 0
        self.elapsed_time = 0
        self.running = False
    def start(self):
        if not self.running:
            self.start_time = time.time()
            self.running = True
    def stop(self):
        if self.running:
            self.elapsed_time += time.time() - self.start_time
            self.running = False
    def reset(self):
        self.start_time = time.time()
        self.elapsed_time = 0
        self.running = False
    def is_running(self):
        return self.running
    def get_time(self, format_str):
        if self.running:
            elapsed = self.elapsed_time + (time.time() - self.start_time)
        else:
            elapsed = self.elapsed_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        if format_str == "HH:MM:SS":
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        elif format_str == "MM:SS:MS":
            milliseconds = int((elapsed % 1) * 1000)
            return f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
        else:
            raise ValueError("Invalid time format")