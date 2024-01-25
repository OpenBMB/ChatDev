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
    def check_winner(self, x, y):
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            count += self.count_in_direction(x, y, dx, dy)
            count += self.count_in_direction(x, y, -dx, -dy)
            if count >= 5:
                return True
        return False
    def count_in_direction(self, x, y, dx, dy):
        count = 0
        player = self.board[y][x]
        while True:
            x += dx
            y += dy
            if not (0 <= x < 15 and 0 <= y < 15):
                break
            if self.board[y][x] == player:
                count += 1
            else:
                break
        return count
    def reset(self):
        self.board = [[0] * 15 for _ in range(15)]
        self.current_player = 1