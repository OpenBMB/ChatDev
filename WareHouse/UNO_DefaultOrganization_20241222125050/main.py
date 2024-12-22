'''
This file contains the main logic for the online UNO game.
'''
import tkinter as tk
from deck import Deck
from hand import Hand
from game_board import GameBoard
class UNOGame:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Online UNO Game")
        self.canvas = tk.Canvas(self.root, width=800, height=600)
        self.canvas.pack()
        self.deck = Deck()
        self.hand = Hand()
        self.game_board = GameBoard()
        self.draw_initial_cards()
        self.start_game()  # Start the game
        self.root.mainloop()
    def draw_initial_cards(self):
        for _ in range(7):
            card = self.deck.draw_card()
            self.hand.add_card(card)
    def draw_card(self):
        card = self.deck.draw_card()
        self.hand.add_card(card)
    def play_card(self, card):
        self.hand.remove_card(card)
        self.game_board.set_current_card(card)
    def get_current_card(self):
        return self.game_board.get_current_card()
    def get_hand(self):
        return self.hand.get_cards()
    def start_game(self):
        # TODO: Implement web interface and game logic
        pass
if __name__ == "__main__":
    game = UNOGame()