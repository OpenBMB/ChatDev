'''
The Game class representing the game logic.
'''
import random
class Game:
    def __init__(self):
        self.player_score = 0
        self.computer_score = 0
        self.player_choice = None
        self.computer_choice = None
    def start_game(self):
        self.player_score = 0
        self.computer_score = 0
    def play_round(self, player_choice):
        self.player_choice = player_choice
        self.computer_choice = self.get_computer_choice()
        winner = self.determine_winner(self.player_choice, self.computer_choice)
        if winner == "player":
            self.player_score += 1
        elif winner == "computer":
            self.computer_score += 1
    def get_computer_choice(self):
        choices = ["rock", "paper", "scissors"]
        return random.choice(choices)
    def determine_winner(self, player_choice, computer_choice):
        if player_choice == computer_choice:
            return "tie"
        elif (
            (player_choice == "rock" and computer_choice == "scissors")
            or (player_choice == "paper" and computer_choice == "rock")
            or (player_choice == "scissors" and computer_choice == "paper")
        ):
            return "player"
        else:
            return "computer"
    def reset_game(self):
        self.player_score = 0
        self.computer_score = 0
        self.player_choice = None
        self.computer_choice = None