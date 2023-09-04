'''
This file contains the TypingTutor class which provides real-time feedback on typing accuracy and speed.
'''
import keyboard
import time
class TypingTutor:
    def __init__(self, progress_tracker):
        self.current_sentence = ""
        self.errors = 0
        self.total_chars = 0
        self.progress_tracker = progress_tracker
        self.start_time = 0
    def start_tutor(self):
        print("Type the following sentence:")
        self.current_sentence = "The quick brown fox jumps over the lazy dog."
        print(self.current_sentence)
        self.start_time = time.time()
        keyboard.on_press(self.check_typing)
    def check_typing(self, key):
        if key.name == "enter":
            keyboard.unhook(self.check_typing)
            accuracy = self.calculate_accuracy()
            speed = self.calculate_speed()
            print(f"Accuracy: {accuracy}%")
            print(f"Speed: {speed} characters per minute")
            self.progress_tracker.record_performance(accuracy, speed)
        else:
            self.total_chars += 1
            if key.name != self.current_sentence[self.total_chars - 1]:
                self.errors += 1
    def calculate_accuracy(self):
        accuracy = ((self.total_chars - self.errors) / self.total_chars) * 100
        return round(accuracy, 2)
    def calculate_speed(self):
        elapsed_time = time.time() - self.start_time
        speed = (self.total_chars / elapsed_time) * 60
        return round(speed, 2)