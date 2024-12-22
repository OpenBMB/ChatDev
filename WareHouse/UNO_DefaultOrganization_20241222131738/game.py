import random
from player import Player
class Game:
    def __init__(self):
        self.players = []
        self.deck = []
        self.discard_pile = []
        self.current_player = None
    def start_game(self):
        # Initialize the game, shuffle the deck, deal cards, etc.
        colors = ["red", "blue", "green", "yellow"]
        numbers = [str(i) for i in range(10)] * 2
        special_cards = ["skip", "reverse", "draw_two"] * 2
        wild_cards = ["wild", "wild_draw_four"] * 4
        self.deck = colors + numbers + special_cards + wild_cards
        random.shuffle(self.deck)
        self.players = [Player("Player 1"), Player("Player 2")]
        for _ in range(7):
            for player in self.players:
                player.add_card(self.draw_card())
        self.current_player = self.players[0]
    def next_turn(self):
        # Move to the next player's turn
        index = self.players.index(self.current_player)
        index = (index + 1) % len(self.players)
        self.current_player = self.players[index]
    def play_card(self, card):
        # Play a card from the player's hand
        self.current_player.remove_card(card)
        self.discard_pile.append(card)
    def draw_card(self):
        # Draw a card from the deck
        if len(self.deck) == 0:
            self.deck = self.discard_pile[:-1]
            random.shuffle(self.deck)
            self.discard_pile = [self.discard_pile[-1]]
        return self.deck.pop()
    def check_winner(self):
        # Check if a player has won the game
        for player in self.players:
            if len(player.hand) == 0:
                return player
        return None