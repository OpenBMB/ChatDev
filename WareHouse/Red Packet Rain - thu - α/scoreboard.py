'''
This file contains the Scoreboard class, which handles the game's scoreboard.
'''
import pygame
import random
class Scoreboard:
    def __init__(self):
        self.score = 0
        self.font = pygame.font.Font(None, 36)
        self.score_text = self.font.render('Score: ' + str(self.score), 1, (255, 255, 255))
    def update_score(self):
        # Increase the score by a random amount between 1 and 6
        self.score += random.randint(1, 6)
        # Update the score text
        self.score_text = self.font.render('Score: ' + str(self.score), 1, (255, 255, 255))
        # Check if the score has reached 100
        if self.score >= 100:
            print("Congratulations! You have reached a score of 100!")