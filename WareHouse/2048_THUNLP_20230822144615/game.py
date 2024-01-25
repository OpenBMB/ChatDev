'''
Game Logic
'''
import random
class Game:
    def __init__(self):
        self.grid = [[0] * 10 for _ in range(10)]
        self.add_random_tile()
        self.add_random_tile()
    def add_random_tile(self):
        empty_spots = []
        for row in range(10):
            for col in range(10):
                if self.grid[row][col] == 0:
                    empty_spots.append((row, col))
        if empty_spots:
            row, col = random.choice(empty_spots)
            self.grid[row][col] = random.choice([2, 4])
    def move_up(self):
        self.move_tiles("up")
        self.merge_tiles("up")
        self.move_tiles("up")
        self.add_random_tile()
    def move_down(self):
        self.move_tiles("down")
        self.merge_tiles("down")
        self.move_tiles("down")
        self.add_random_tile()
    def move_left(self):
        self.move_tiles("left")
        self.merge_tiles("left")
        self.move_tiles("left")
        self.add_random_tile()
    def move_right(self):
        self.move_tiles("right")
        self.merge_tiles("right")
        self.move_tiles("right")
        self.add_random_tile()
    def move_tiles(self, direction):
        if direction == "up":
            for col in range(10):
                for row in range(1, 10):
                    if self.grid[row][col] != 0:
                        self.move_tile(row, col, -1, 0)
        elif direction == "down":
            for col in range(10):
                for row in range(8, -1, -1):
                    if self.grid[row][col] != 0:
                        self.move_tile(row, col, 1, 0)
        elif direction == "left":
            for row in range(10):
                for col in range(1, 10):
                    if self.grid[row][col] != 0:
                        self.move_tile(row, col, 0, -1)
        elif direction == "right":
            for row in range(10):
                for col in range(8, -1, -1):
                    if self.grid[row][col] != 0:
                        self.move_tile(row, col, 0, 1)
    def move_tile(self, row, col, row_offset, col_offset):
        value = self.grid[row][col]
        self.grid[row][col] = 0
        while 0 <= row + row_offset < 10 and 0 <= col + col_offset < 10 and self.grid[row + row_offset][col + col_offset] == 0:
            row += row_offset
            col += col_offset
        self.grid[row][col] = value
    def merge_tiles(self, direction):
        if direction == "up":
            for col in range(10):
                for row in range(1, 10):
                    if self.grid[row][col] == self.grid[row - 1][col]:
                        self.grid[row - 1][col] *= 2
                        self.grid[row][col] = 0
        elif direction == "down":
            for col in range(10):
                for row in range(8, -1, -1):
                    if self.grid[row][col] == self.grid[row + 1][col]:
                        self.grid[row + 1][col] *= 2
                        self.grid[row][col] = 0
        elif direction == "left":
            for row in range(10):
                for col in range(1, 10):
                    if self.grid[row][col] == self.grid[row][col - 1]:
                        self.grid[row][col - 1] *= 2
                        self.grid[row][col] = 0
        elif direction == "right":
            for row in range(10):
                for col in range(8, -1, -1):
                    if self.grid[row][col] == self.grid[row][col + 1]:
                        self.grid[row][col + 1] *= 2
                        self.grid[row][col] = 0
    def is_game_over(self):
        for row in range(10):
            for col in range(10):
                if self.grid[row][col] == 2048:
                    return True
                if self.grid[row][col] == 0:
                    return False
                if row < 9 and self.grid[row][col] == self.grid[row + 1][col]:
                    return False
                if col < 9 and self.grid[row][col] == self.grid[row][col + 1]:
                    return False
        return True