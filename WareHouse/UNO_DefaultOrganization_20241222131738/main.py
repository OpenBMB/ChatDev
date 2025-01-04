import tkinter as tk
from game import Game
class UnoGameGUI:
    def __init__(self, master):
        self.master = master
        self.game = Game()
        self.canvas = tk.Canvas(self.master, width=800, height=600)
        self.canvas.pack()
        self.draw_cards()
        self.canvas.bind("<Button-1>", self.on_click)
    def draw_cards(self):
        # Clear the canvas before drawing the cards
        self.canvas.delete("all")
        # Draw the cards on the canvas
        for i, card in enumerate(self.game.current_player.hand):
            self.canvas.create_text(100 + i * 100, 300, text=card)
    def on_click(self, event):
        # Handle mouse click events
        x = event.x
        y = event.y
        # Check if the click is on a card
        for i, card in enumerate(self.game.current_player.hand):
            if 100 + i * 100 <= x <= 200 + i * 100 and 300 <= y <= 400:
                self.game.play_card(card)
                self.draw_cards()
                self.game.next_turn()
                break
root = tk.Tk()
game_gui = UnoGameGUI(root)
game_gui.game.start_game()  # Start the game
root.mainloop()