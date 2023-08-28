'''
This file contains the TypingPractice class which manages the typing practice software.
'''
from typing_exercise import TypingExercise
from typing_tutor import TypingTutor
from progress_tracker import ProgressTracker
class TypingPractice:
    def __init__(self, progress_tracker):
        self.typing_exercise = TypingExercise(progress_tracker)
        self.typing_tutor = TypingTutor(progress_tracker)
        self.progress_tracker = progress_tracker
    def start(self):
        while True:
            self.display_menu()
            choice = input("Enter your choice: ")
            if choice == "1":
                self.typing_exercise.start_exercise()
            elif choice == "2":
                self.typing_tutor.start_tutor()
            elif choice == "3":
                self.progress_tracker.display_statistics()
            elif choice == "4":
                break
            else:
                print("Invalid choice. Please try again.")
    def display_menu(self):
        print("Typing Practice Software")
        print("1. Start Typing Exercise")
        print("2. Start Typing Tutor")
        print("3. Display Statistics")
        print("4. Exit")