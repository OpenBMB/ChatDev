'''
This file handles the game logic for the Gomoku game.
'''
import pygame
class Board:
    def __init__(self, rows, cols, player_1_icon, player_2_icon, width, height):
        self.rows = rows
        self.cols = cols
        self.width = width
        self.height = height
        self.board = [[None for _ in range(cols)] for _ in range(rows)]
        self.current_player = 1
        self.player_1_icon =player_1_icon
        self.player_2_icon =player_2_icon
        self.game_state = 'ongoing'
        self.winner = None
    def place_stone(self, x, y):
        if self.game_state == 'ended':
            return
        row, col = self.get_board_position(x, y)
        if row >= 0 and row < self.rows and col >= 0 and col < self.cols:
            if self.board[row][col] is None:
                self.board[row][col] = self.current_player
                if self.check_win(row, col):
                    self.game_state = 'ended'
                    self.winner = self.current_player
                self.current_player = 1 if self.current_player == 2 else 2
    def get_board_position(self, x, y):
        row = y // (self.height // self.rows)
        col = x // (self.width // self.cols)
        return row, col
    def check_win(self, row, col):
        # Check horizontal, vertical and diagonal lines for a win
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            if self.count_stones(row, col, dx, dy) + self.count_stones(row, col, -dx, -dy) - 1 >= 5:
                return True
        return False
    def count_stones(self, row, col, dx, dy):
        count = 0
        while 0 <= row < self.rows and 0 <= col < self.cols and self.board[row][col] == self.current_player:
            count += 1
            row += dx
            col += dy
        return count
    def draw(self, window):
        for row in range(self.rows):
            for col in range(self.cols):
                if self.board[row][col] is not None:
                    icon = self.player_1_icon if self.board[row][col] == 1 else self.player_2_icon
                    window.blit(icon, (col * (self.width // self.cols), row * (self.height // self.rows)))