'''
This file contains the Game class which manages the game logic.
'''
class Game:
    def __init__(self):
        # Initialize the game board
        self.board = [[0] * 15 for _ in range(15)]
        self.current_player = 1
    def make_move(self, row, col):
        # Check if the move is valid
        if self.board[row][col] == 0:
            # Make the move
            self.board[row][col] = self.current_player
            # Switch to the next player
            self.current_player = 3 - self.current_player
            return True
        else:
            return False
    def check_winner(self):
        # Check rows
        for row in range(15):
            for col in range(11):
                if self.board[row][col] != 0 and self.board[row][col] == self.board[row][col+1] == self.board[row][col+2] == self.board[row][col+3] == self.board[row][col+4]:
                    return self.board[row][col]
        # Check columns
        for row in range(11):
            for col in range(15):
                if self.board[row][col] != 0 and self.board[row][col] == self.board[row+1][col] == self.board[row+2][col] == self.board[row+3][col] == self.board[row+4][col]:
                    return self.board[row][col]
        # Check diagonals
        for row in range(11):
            for col in range(11):
                if self.board[row][col] != 0 and self.board[row][col] == self.board[row+1][col+1] == self.board[row+2][col+2] == self.board[row+3][col+3] == self.board[row+4][col+4]:
                    return self.board[row][col]
        for row in range(11):
            for col in range(4, 15):
                if self.board[row][col] != 0 and self.board[row][col] == self.board[row+1][col-1] == self.board[row+2][col-2] == self.board[row+3][col-3] == self.board[row+4][col-4]:
                    return self.board[row][col]
        return 0