from tkinter import messagebox
from game import Game
game = Game()
while True:
    row = int(input("Enter the row: "))
    col = int(input("Enter the column: "))
    if game.make_move(row, col):
        if game.check_winner(row, col):
            print("Player", game.current_player, "wins!")
            break
    else:
        print("Invalid move. Try again.")
    if input("Do you want to play again? (y/n): ") == "n":
        break
    else:
        game.reset()