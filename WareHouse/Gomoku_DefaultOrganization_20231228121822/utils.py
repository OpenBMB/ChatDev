'''
This file contains utility functions for the Gomoku game.
'''
def print_board(board):
    for row in board:
        print(' '.join(row))