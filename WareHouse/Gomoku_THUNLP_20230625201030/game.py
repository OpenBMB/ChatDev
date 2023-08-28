'''
This file contains the Game class for managing the gomoku game logic.
'''
class Game:
    def __init__(self):
        # Initialize game variables
        self.board = [[0] * 15 for _ in range(15)]
        self.current_player = 1
        self.game_over = False
    def make_move(self, row, col):
        # Check if the move is valid
        if self.board[row][col] != 0 or self.game_over:
            return
        # Place the player's stone on the board
        self.board[row][col] = self.current_player
        # Check for a winning move
        if self.check_win(row, col):
            self.game_over = True
        # Check if the game board is full and there is no winner
        elif self.is_board_full():
            self.game_over = True
        # Switch to the next player
        self.current_player = 3 - self.current_player
    def check_win(self, row, col):
        # Check for a winning move horizontally
        count = 1
        for i in range(1, 5):
            if col - i >= 0 and self.board[row][col - i] == self.current_player:
                count += 1
            else:
                break
        for i in range(1, 5):
            if col + i < 15 and self.board[row][col + i] == self.current_player:
                count += 1
            else:
                break
        if count >= 5:
            return True
        # Check for a winning move vertically
        count = 1
        for i in range(1, 5):
            if row - i >= 0 and self.board[row - i][col] == self.current_player:
                count += 1
            else:
                break
        for i in range(1, 5):
            if row + i < 15 and self.board[row + i][col] == self.current_player:
                count += 1
            else:
                break
        if count >= 5:
            return True
        # Check for a winning move diagonally (top-left to bottom-right)
        count = 1
        for i in range(1, 5):
            if row - i >= 0 and col - i >= 0 and self.board[row - i][col - i] == self.current_player:
                count += 1
            else:
                break
        for i in range(1, 5):
            if row + i < 15 and col + i < 15 and self.board[row + i][col + i] == self.current_player:
                count += 1
            else:
                break
        if count >= 5:
            return True
        # Check for a winning move diagonally (top-right to bottom-left)
        count = 1
        for i in range(1, 5):
            if row - i >= 0 and col + i < 15 and self.board[row - i][col + i] == self.current_player:
                count += 1
            else:
                break
        for i in range(1, 5):
            if row + i < 15 and col - i >= 0 and self.board[row + i][col - i] == self.current_player:
                count += 1
            else:
                break
        if count >= 5:
            return True
        return False
    def is_board_full(self):
        for row in self.board:
            if 0 in row:
                return False
        return True