'''
This is the main file for the typing practice software.
'''
from typing_practice import TypingPractice
from progress_tracker import ProgressTracker
def main():
    progress_tracker = ProgressTracker()
    typing_practice = TypingPractice(progress_tracker)
    typing_practice.start()
if __name__ == "__main__":
    main()