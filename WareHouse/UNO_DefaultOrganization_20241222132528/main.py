'''
This is the main file of the online UNO game.
'''
import tkinter as tk
from game import Game, Player, Card
class UnoGameGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Online UNO Game")
        self.game = Game()
        self.canvas = tk.Canvas(self.master, width=800, height=600)
        self.canvas.pack()
        self.draw_cards()
    def draw_cards(self):
        # Implement logic to draw cards on the canvas
        for i, card in enumerate(self.game.current_player.hand):
            self.canvas.create_text(100 + i * 100, 100, text=str(card))
    def play_card(self, card):
        # Implement logic to play a card
        if self.game.play_card(card):
            self.canvas.delete("all")
            self.draw_cards()
    def draw_card(self):
        # Implement logic to draw a card
        self.game.draw_card()
        self.canvas.delete("all")
        self.draw_cards()
    def skip_turn(self):
        # Implement logic to skip a turn
        self.game.skip_turn()
        self.canvas.delete("all")
        self.draw_cards()
    def quit_game(self):
        # Implement logic to quit the game
        self.master.destroy()
root = tk.Tk()
game_gui = UnoGameGUI(root)
root.mainloop()