'''
This file contains the ProgressTracker class which records users' performance and displays statistics.
'''
class ProgressTracker:
    def __init__(self):
        self.statistics = []
    def record_performance(self, accuracy, speed):
        self.statistics.append((accuracy, speed))
    def display_statistics(self):
        if len(self.statistics) == 0:
            print("No statistics available.")
        else:
            print("Statistics:")
            for i, (accuracy, speed) in enumerate(self.statistics):
                print(f"Exercise {i+1}:")
                print(f"Accuracy: {accuracy}%")
                print(f"Speed: {speed} characters per minute")