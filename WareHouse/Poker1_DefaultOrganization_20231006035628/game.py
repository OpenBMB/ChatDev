'''
Game module that manages the Texas Hold'em Poker game.
'''
from player import HumanPlayer, AIPlayer
from deck import Deck
class Game:
    def __init__(self):
        self.players = []
        self.deck = Deck()
        self.community_cards = []
        self.small_blind = 5
        self.big_blind = 10
        self.current_bet = 0
        self.pot = 0
    def start(self):
        self.initialize_players()
        self.initialize_blinds()
        self.play_round()
    def initialize_players(self):
        self.players.append(HumanPlayer("Human", 1000))
        self.players.append(AIPlayer("AI 1", 1000))
        self.players.append(AIPlayer("AI 2", 1000))
        self.players.append(AIPlayer("AI 3", 1000))
        self.players.append(AIPlayer("AI 4", 1000))
    def initialize_blinds(self):
        for player in self.players:
            if player.name == "AI 4":
                player.blind = self.small_blind
            elif player.name == "Human":
                player.blind = self.big_blind
    def play_round(self):
        while len(self.players) > 1:
            self.deck.shuffle()
            self.reset_round()
            self.collect_blinds()
            self.deal_hole_cards()
            self.play_betting_round()
            if len(self.players) > 1:
                self.deal_community_cards()
                self.play_betting_round()
                self.deal_community_cards()
                self.play_betting_round()
                self.deal_community_cards()
                self.play_betting_round()
                if len(self.players) > 1:
                    self.determine_winner()
                elif len(self.players) == 1:
                    self.players[0].chips += pot
    def reset_round(self):
        self.community_cards = []
        self.current_bet = 0
        self.pot = 0
        for player in self.players:
            player.reset()
    def collect_blinds(self):
        for player in self.players:
            if player.blind == self.small_blind:
                self.pot += player.blind_bet(self.small_blind)
            elif player.blind == self.big_blind:
                self.pot += player.blind_bet(self.big_blind)
    def deal_hole_cards(self):
        for player in self.players:
            player.receive_cards(self.deck.draw(2))
    def play_betting_round(self):
        for player in self.players:
            if len(self.community_cards) != 0:
                player.previous_bet = 0
                player.blind = 0
                self.current_bet = 0
                
            else:
                self.current_bet = 10
                
        if len(self.community_cards) != 0:
            print (f"Community cards: {self.community_cards}")
         
        print (f"Pot: {self.pot}")
        current_player_index = self.get_next_player_index(0)
        last_raiser_index = None
        while True:
            current_player = self.players[current_player_index]
            if current_player.is_active():
                action = current_player.make_decision(self.current_bet)
                if action == "fold":
                    current_player.fold()
                elif action == "check":
                    if last_raiser_index is not None:
                        if (self.current_bet > current_player.previous_bet):
                            print(f"{current_player.name} attempted to check. Forcing fold...")
                            current_player.fold() #Bot likes to check to avoid calling, force them to fold with this
                    else:
                        current_player.check()
                elif action == "call":
                    if last_raiser_index is not None: #Someone raised
                        if (amount >= current_player.chips): #All in
                            self.pot += current_player.all_in()
                        else: #Has the chips to call
                            prev_bet = current_player.call(self.current_bet - current_player.previous_bet - current_player.blind)
                            self.pot += prev_bet                           
                            current_player.previous_bet += prev_bet + current_player.blind
                            current_player.blind = 0
                    else: #No one raised, pay big blind
                        self.pot += current_player.call(self.big_blind - current_player.blind)
                        self.previous_bet = 10
                        current_player.previous_bet = 10
                        current_player.blind = 0
                elif action == "raise":             
                    amount = current_player.get_raise_amount(self.current_bet)                   
                    new_amount = amount + self.current_bet*2 - current_player.blind - current_player.previous_bet
                    self.current_bet = new_amount + current_player.blind + current_player.previous_bet
                    current_player.blind = 0                    
                    self.pot += current_player.raise_bet(new_amount)                   
                    print(f"Current top bet is: {self.current_bet}")
                    last_raiser_index = current_player_index
                    current_player.previous_bet = self.current_bet
            current_player_index = self.get_next_player_index(current_player_index)
            if current_player_index == last_raiser_index:
                break
    def deal_community_cards(self):
        if len(self.players[0].community_cards) == 0:
            self.community_cards.extend(self.deck.draw(3))
        elif len(self.players[0].community_cards) == 3:
            self.community_cards.extend(self.deck.draw(1))
        elif len(self.players[0].community_cards) == 4:
            self.community_cards.extend(self.deck.draw(1))
        for player in self.players:
            player.receive_community_cards(self.community_cards)
    def determine_winner(self):
        best_hand_value = 0
        winners = []
        for player in self.players:
            if player.is_active():
                hand_value = self.calculate_hand_value(player)
                if hand_value > best_hand_value:
                    best_hand_value = hand_value
                    winners = [player]
                elif hand_value == best_hand_value:
                    winners.append(player)

        if len(winners) == 1:
            winning_player = winners[0]
            print(f"{winning_player.name} wins with {self.get_hand_name(best_hand_value)}!")
            winning_player.chips += self.pot
        else:
            print("It's a tie!")

    def calculate_hand_value(self, player):
        # Implement logic to calculate the unique hand value as described in the provided information.
        hand_type = self.determine_hand_type(player.hand)
        card_values = [self.get_card_value(card) for card in player.hand]
        hand_value = hand_type

        for card_value in card_values:
            hand_value = (hand_value << 4) + card_value

        print(f"{player.name} with cards: {player.hand} has hand value: {hand_value}")
        return hand_value

    def determine_hand_type(self, hand):
        # Sort the hand in descending order based on card values
        sorted_hand = sorted(hand, key=lambda card: self.get_card_value(card), reverse=True)
        
        # Check for specific hand types in decreasing order of rank
        if self.is_royal_flush(sorted_hand):
            return 9  # Royal flush
        if self.is_straight_flush(sorted_hand):
            return 8  # Straight flush
        if self.is_four_of_a_kind(sorted_hand):
            return 7  # Four of a kind
        if self.is_full_house(sorted_hand):
            return 6  # Full house
        if self.is_flush(sorted_hand):
            return 5  # Flush
        if self.is_straight(sorted_hand):
            return 4  # Straight
        if self.is_three_of_a_kind(sorted_hand):
            return 3  # Three of a kind
        if self.is_two_pair(sorted_hand):
            return 2  # Two pair
        if self.is_pair(sorted_hand):
            return 1  # Pair

        return 0  # High card

    def get_card_value(self, card):
        # Map card ranks (2, 3, 4, etc.) to their corresponding values (0 to 12)
        rank_to_value = {
            "2": 0, "3": 1, "4": 2, "5": 3, "6": 4, "7": 5, "8": 6,
            "9": 7, "10": 8, "J": 9, "Q": 10, "K": 11, "A": 12
        }
        rank = card.split()[0]  # Extract the rank from the card string
        return rank_to_value.get(rank, 0)  # Default to 0 for unknown ranks

    def get_hand_name(self, hand_type):
        # Map hand types to their human-readable names
        hand_names = {
            9: "Royal flush", 8: "Straight flush", 7: "Four of a kind",
            6: "Full house", 5: "Flush", 4: "Straight",
            3: "Three of a kind", 2: "Two pair", 1: "Pair", 0: "High card"
        }
        return hand_names.get(hand_type, "Unknown")

    def is_royal_flush(self, hand):
        # Check for a Royal flush (A, K, Q, J, 10 of the same suit)
        return self.is_straight_flush(hand) and self.get_card_value(hand[0]) == 12

    def is_straight_flush(self, hand):
        # Check for a Straight flush (five consecutive cards of the same suit)
        return self.is_straight(hand) and self.is_flush(hand)

    def is_four_of_a_kind(self, hand):
        # Check for Four of a kind (four cards of the same rank)
        return self.has_n_of_a_kind(hand, 4)

    def is_full_house(self, hand):
        # Check for a Full house (three cards of one rank and two cards of another rank)
        return self.has_n_of_a_kind(hand, 3) and self.has_n_of_a_kind(hand, 2)

    def is_flush(self, hand):
        # Check for a Flush (five cards of the same suit)
        suits = [card.split()[-1] for card in hand]
        return all(suit == suits[0] for suit in suits)

    def is_straight(self, hand):
        # Check for a Straight (five consecutive cards of different suits)
        values = [self.get_card_value(card) for card in hand]
        values.sort()
        return all(values[i] == values[i - 1] + 1 for i in range(1, len(values)))

    def is_three_of_a_kind(self, hand):
        # Check for Three of a kind (three cards of the same rank)
        return self.has_n_of_a_kind(hand, 3)

    def is_two_pair(self, hand):
        # Check for Two pair (two cards of one rank and two cards of another rank)
        ranks = [self.get_card_value(card) for card in hand]
        rank_counts = {rank: ranks.count(rank) for rank in set(ranks)}
        return list(rank_counts.values()).count(2) == 2

    def is_pair(self, hand):
        # Check for a Pair (two cards of the same rank)
        return self.has_n_of_a_kind(hand, 2)

    def has_n_of_a_kind(self, hand, n):
        # Helper function to check if there are 'n' cards of the same rank in the hand
        ranks = [self.get_card_value(card) for card in hand]
        rank_counts = {rank: ranks.count(rank) for rank in set(ranks)}
        return n in rank_counts.values()
    
    def get_next_player_index(self, current_index):
        next_index = current_index + 1
        if next_index >= len(self.players):
            next_index = 0
        return next_index
