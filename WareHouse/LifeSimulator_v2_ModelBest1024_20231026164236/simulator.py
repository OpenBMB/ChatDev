'''
This file contains the Simulator class which handles the simulation logic.
'''
import random
class Simulator:
    def __init__(self):
        self.age = 5
        self.money = 1000
    def go_on(self):
        n = random.randint(1, 10)
        self.age += n
        event = random.choice(["earn_money", "yes", "good", "lose_money", "death"])
        if event in ("earn_money", "yes", "good"):
            earned_money = random.randint(1, 100000)
            self.money += earned_money
        elif event == "lose_money":
            lost_money = random.randint(1, 100000)
            # if lost_money > self.money:
            #     lost_money = self.money
            self.money -= lost_money
        elif event == "death":
            restart = random.randint(-1, 10)
            if restart > 0:
                self.money -= random.randint(1, 100000)
                event = "sick"
            # self.money = 0
        return self.age, self.money, event