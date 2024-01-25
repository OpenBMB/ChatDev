'''
This file contains the Game class which manages the game logic.
'''
class Game:
    def __init__(self):
        self.board = [[0] * 15 for _ in range(15)]
        self.current_player = 1
    def make_move(self, x, y):
        if self.board[y][x] == 0:
            self.board[y][x] = self.current_player
            self.current_player = 3 - self.current_player
            return True
        return False
    def check_win(self, x, y):
        directions = [(1, 0), (0, 1), (1, 1), (1, -1), (-1, 0), (0, -1), (-1, -1), (-1, 1)]
        for dx, dy in directions:
            count = 1
            for i in range(-4, 5):
                nx = x + dx * i
                ny = y + dy * i
                if 0 <= nx < 15 and 0 <= ny < 15 and self.board[ny][nx] == self.current_player:
                    count += 1
                else:
                    break
            if count >= 5:
                return True
        return False