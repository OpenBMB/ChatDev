'''
Player module that defines the HumanPlayer and AIPlayer classes.
'''
import sys
import random
class Player:
    def __init__(self, name, chips):
        self.name = name
        self.chips = chips
        self.hand = []
        self.community_cards = []
        self.active = True
        self.blind = 0
        self.previous_bet = 0
        self.is_in_showdown = True
    def receive_cards(self, cards):
        self.hand.extend(cards)
    def receive_community_cards(self, cards):
        self.community_cards = cards
    def is_active(self):
        return self.active
    def all_in(self):
        tmp = self.chips
        self.chips = 0
        self.active = False
        print(f"{self.name} is All In for {tmp}")
        return tmp
    def fold(self):
        print(f"{self.name} folded.")
        self.active = False
        self.is_in_showdown = False
    def check(self):
        prompt = f"{self.name} checked."
        print(prompt)
        return 0
    def call(self, amount):
        self.chips -= amount
        prompt = f"{self.name} called {amount}. Remaining chips: {self.chips}"
        print(prompt)
        return amount
    def raise_bet(self, amount):
        self.chips -= amount
        prompt = f"{self.name} raised an additonal {amount}. Remaining chips: {self.chips}"
        print(prompt)
        return amount
    def blind_bet(self, amount):
        self.chips -= amount
        #self.previous_bet = amount
        prompt = f"{self.name} posted blind of {amount}. Remaining chips: {self.chips}"
        print(prompt)
        return amount
    def reset(self):
        self.hand = []
        self.community_cards = []
        self.active = True
        self.is_in_showdown = True
class HumanPlayer(Player):
    def make_decision(self, current_bet):
        cards = ", ".join(self.hand)
        prompt = f"Your cards: {cards}"
        print(prompt)
        prompt = f"Community cards: {self.community_cards}"
        print(prompt)
        decision = input("Enter your decision (fold/check/bet/call/raise): ")
        if decision == "fold" or decision == "check":
            return decision
        elif decision == "q":
            print("Quitting...")
            sys.exit() #Goodbye mf
        elif decision == "call":
            return decision
        elif decision == "raise":
            return decision
        else:
            print("Invalid decision. Please enter a valid decision.")
            return self.make_decision(current_bet)
    def get_raise_amount(self, current_bet):
        try:
                amount = int(input(f"Enter the raise amount: {current_bet*2} + "))
                return amount
        except ValueError:
            print("Invalid input.")
            return self.get_raise_amount(current_bet)
            
class AIPlayer(Player):
    def make_decision(self, current_bet):
        if random.random() < 0.05:  # 5% chance of making a random decision
            return random.choice(["fold", "check", "bet", "call", "raise"])
        else:
            if current_bet > self.chips:
                return random.choice(["call, fold"])
            elif current_bet == 0:
                return random.choice(["check", "raise"])
            elif current_bet > self.previous_bet:
                return random.choice(["fold", "call", "raise"])
            else:
                return random.choice(["check", "call", "raise"])
    def get_raise_amount(self, current_bet):
        therand = random.randint(0, 100)
        print(f"Raise increment: {therand}")
        return therand
