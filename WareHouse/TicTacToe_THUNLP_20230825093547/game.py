'''
This file contains the Game class that represents the tic-tac-toe game logic.
'''
class Game:
    def __init__(self):
        self.board = [['' for _ in range(3)] for _ in range(3)]
        self.current_player = 'X'
    def make_move(self, row, col):
        if self.board[row][col] == '':
            self.board[row][col] = self.current_player
            self.current_player = 'O' if self.current_player == 'X' else 'X'
            return True
        return False
    def is_game_over(self):
        return self.is_winner('X') or self.is_winner('O') or self.is_board_full()
    def is_winner(self, player):
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] == player:
                return True
            if self.board[0][i] == self.board[1][i] == self.board[2][i] == player:
                return True
        if self.board[0][0] == self.board[1][1] == self.board[2][2] == player:
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] == player:
            return True
        return False
    def is_board_full(self):
        for row in self.board:
            if '' in row:
                return False
        return True
    def get_winner(self):
        if self.is_winner('X'):
            return 'X'
        if self.is_winner('O'):
            return 'O'
        return None