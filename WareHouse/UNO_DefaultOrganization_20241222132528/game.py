'''
This file contains the Game class which represents the UNO game logic.
'''
import random
class Game:
    def __init__(self):
        self.players = []
        self.current_player = None
        self.deck = []
        self.discard_pile = []
    def add_player(self, player):
        '''
        Add a player to the game.
        '''
        self.players.append(player)
    def start_game(self):
        '''
        Start the game by initializing the deck, shuffling it, dealing cards to players, and setting the current player.
        '''
        self.deck = create_deck()
        shuffle_deck(self.deck)
        self.deal_cards()
        self.current_player = random.choice(self.players)
    def deal_cards(self):
        '''
        Deal 7 cards to each player from the deck.
        '''
        for _ in range(7):
            for player in self.players:
                card = self.deck.pop()
                player.hand.append(card)
    def play_card(self, card):
        '''
        Play a card by adding it to the discard pile and removing it from the current player's hand.
        '''
        if card.is_valid_play(self.discard_pile[-1]):
            self.discard_pile.append(card)
            self.current_player.hand.remove(card)
            self.next_turn()
            return True
        return False
    def draw_card(self):
        '''
        Draw a card from the deck and add it to the current player's hand.
        '''
        card = self.deck.pop()
        self.current_player.hand.append(card)
        self.next_turn()
    def skip_turn(self):
        '''
        Skip the current player's turn and move to the next player.
        '''
        self.next_turn()
    def is_game_over(self):
        '''
        Check if the game is over by determining if any player has an empty hand.
        '''
        for player in self.players:
            if len(player.hand) == 0:
                return True
        return False
    def get_winner(self):
        '''
        Get the winner of the game by finding the player with the fewest cards in their hand.
        '''
        winner = self.players[0]
        for player in self.players[1:]:
            if len(player.hand) < len(winner.hand):
                winner = player
        return winner
    def next_turn(self):
        '''
        Move to the next player's turn.
        '''
        index = self.players.index(self.current_player)
        index = (index + 1) % len(self.players)
        self.current_player = self.players[index]
class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
    def play_card(self, card):
        '''
        Play a card by removing it from the player's hand.
        '''
        self.hand.remove(card)
    def draw_card(self, card):
        '''
        Draw a card by adding it to the player's hand.
        '''
        self.hand.append(card)
    def skip_turn(self):
        '''
        Skip the player's turn.
        '''
        pass
    def get_hand(self):
        '''
        Get the player's hand.
        '''
        return self.hand
class Card:
    def __init__(self, color, value):
        self.color = color
        self.value = value
    def is_valid_play(self, top_card):
        '''
        Check if the card is a valid play by comparing its color or value with the top card.
        '''
        return self.color == top_card.color or self.value == top_card.value
    def __str__(self):
        '''
        Convert the card to a string representation.
        '''
        return f"{self.color} {self.value}"
def create_deck():
    '''
    Create a deck of UNO cards.
    '''
    colors = ["Red", "Blue", "Green", "Yellow"]
    values = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "Skip", "Reverse", "Draw Two"]
    deck = []
    for color in colors:
        for value in values:
            card = Card(color, value)
            deck.append(card)
    return deck
def shuffle_deck(deck):
    '''
    Shuffle the deck of cards.
    '''
    random.shuffle(deck)
def get_top_card(discard_pile):
    '''
    Get the top card from the discard pile.
    '''
    return discard_pile[-1]
def get_next_player(players, current_player):
    '''
    Get the next player in the turn order.
    '''
    index = players.index(current_player)
    index = (index + 1) % len(players)
    return players[index]