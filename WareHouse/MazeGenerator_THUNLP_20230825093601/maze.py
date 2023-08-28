'''
This file contains the Maze class that represents the maze.
'''
import random
import tkinter as tk
class Cell:
    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.visited = False
        self.walls = {
            "top": True,
            "right": True,
            "bottom": True,
            "left": True
        }
class Maze:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.grid = [[Cell(row, col) for col in range(cols)] for row in range(rows)]
    def generate(self):
        stack = []
        current = self.grid[0][0]
        current.visited = True
        while True:
            neighbors = self.get_unvisited_neighbors(current)
            if len(neighbors) > 0:
                neighbor = random.choice(neighbors)
                stack.append(current)
                self.remove_walls(current, neighbor)
                current = neighbor
                current.visited = True
            elif len(stack) > 0:
                current = stack.pop()
            else:
                break
    def get_unvisited_neighbors(self, cell):
        neighbors = []
        if cell.row > 0 and not self.grid[cell.row - 1][cell.col].visited:
            neighbors.append(self.grid[cell.row - 1][cell.col])
        if cell.col < self.cols - 1 and not self.grid[cell.row][cell.col + 1].visited:
            neighbors.append(self.grid[cell.row][cell.col + 1])
        if cell.row < self.rows - 1 and not self.grid[cell.row + 1][cell.col].visited:
            neighbors.append(self.grid[cell.row + 1][cell.col])
        if cell.col > 0 and not self.grid[cell.row][cell.col - 1].visited:
            neighbors.append(self.grid[cell.row][cell.col - 1])
        return neighbors
    def remove_walls(self, current, neighbor):
        if current.row > neighbor.row:
            current.walls["top"] = False
            neighbor.walls["bottom"] = False
        elif current.col < neighbor.col:
            current.walls["right"] = False
            neighbor.walls["left"] = False
        elif current.row < neighbor.row:
            current.walls["bottom"] = False
            neighbor.walls["top"] = False
        elif current.col > neighbor.col:
            current.walls["left"] = False
            neighbor.walls["right"] = False