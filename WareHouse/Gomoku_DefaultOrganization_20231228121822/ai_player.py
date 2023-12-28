'''
This file contains the AI player logic for the Gomoku game.
'''
import random
from main import GomokuGame
class AIPlayer:
    def __init__(self, game):
        self.game = game
    def make_move(self):
        empty_cells = []
        for row in range(15):
            for col in range(15):
                if self.game.board[row][col] == ' ':
                    empty_cells.append((row, col))
        if empty_cells:
            row, col = random.choice(empty_cells)
            self.game.play_move(row, col)