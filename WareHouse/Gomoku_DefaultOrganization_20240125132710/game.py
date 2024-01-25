'''
This file contains the Game class for the Gomoku game.
'''
class Game:
    def __init__(self):
        self.board_size = 15
        self.board = [[0] * self.board_size for _ in range(self.board_size)]
        self.current_player = 1
    def make_move(self, row, col):
        if self.board[row][col] == 0:
            self.board[row][col] = self.current_player
            self.current_player = 3 - self.current_player
    def check_winner(self):
        for row in range(self.board_size):
            for col in range(self.board_size):
                if self.board[row][col] != 0:
                    if self.check_horizontal(row, col) or self.check_vertical(row, col) or self.check_diagonal(row, col):
                        return self.board[row][col]
        return 0
    def check_horizontal(self, row, col):
        count = 1
        for i in range(1, 5):
            if col + i < self.board_size and self.board[row][col + i] == self.board[row][col]:
                count += 1
            else:
                break
        for i in range(1, 5):
            if col - i >= 0 and self.board[row][col - i] == self.board[row][col]:
                count += 1
            else:
                break
        return count >= 5
    def check_vertical(self, row, col):
        count = 1
        for i in range(1, 5):
            if row + i < self.board_size and self.board[row + i][col] == self.board[row][col]:
                count += 1
            else:
                break
        for i in range(1, 5):
            if row - i >= 0 and self.board[row - i][col] == self.board[row][col]:
                count += 1
            else:
                break
        return count >= 5
    def check_diagonal(self, row, col):
        count = 1
        for i in range(1, 5):
            if row + i < self.board_size and col + i < self.board_size and self.board[row + i][col + i] == self.board[row][col]:
                count += 1
            else:
                break
        for i in range(1, 5):
            if row - i >= 0 and col - i >= 0 and self.board[row - i][col - i] == self.board[row][col]:
                count += 1
            else:
                break
        if count > 5:
            return True
        count = 1
        for i in range(1, 5):
            if row + i < self.board_size and col - i >= 0 and self.board[row + i][col - i] == self.board[row][col]:
                count += 1
            else:
                break
        for i in range(1, 5):
            if row - i >= 0 and col + i < self.board_size and self.board[row - i][col + i] == self.board[row][col]:
                count += 1
            else:
                break
        return count > 5