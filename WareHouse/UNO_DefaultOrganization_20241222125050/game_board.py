'''
This file contains the GameBoard class to manage the game board and display the current state of the game.
'''
class GameBoard:
    def __init__(self):
        self.current_card = None
    def set_current_card(self, card):
        self.current_card = card
    def get_current_card(self):
        return self.current_card