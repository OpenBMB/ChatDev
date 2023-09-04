'''
This file contains the TypingExercise class which manages the typing exercises.
'''
import random
import time
class TypingExercise:
    def __init__(self, progress_tracker):
        self.exercises = [
            "The quick brown fox jumps over the lazy dog.",
            "Programming is fun and challenging.",
            "Practice makes perfect.",
            "Typing speed matters in the digital world.",
            "I love coding in Python."
        ]
        self.progress_tracker = progress_tracker
    def start_exercise(self):
        exercise = random.choice(self.exercises)
        print("Type the following sentence:")
        print(exercise)
        print("Press Enter to start.")
        input()
        start_time = time.time()
        user_input = input()
        end_time = time.time()
        elapsed_time = end_time - start_time
        accuracy = self.calculate_accuracy(exercise, user_input)
        speed = self.calculate_speed(user_input, elapsed_time)
        print(f"Accuracy: {accuracy}%")
        print(f"Speed: {speed} characters per minute")
        self.progress_tracker.record_performance(accuracy, speed)
    def calculate_accuracy(self, exercise, user_input):
        correct_chars = sum([1 for c1, c2 in zip(exercise, user_input) if c1 == c2])
        accuracy = (correct_chars / len(exercise)) * 100
        return round(accuracy, 2)
    def calculate_speed(self, user_input, elapsed_time):
        num_chars = len(user_input)
        speed = (num_chars / elapsed_time) * 60
        return round(speed, 2)