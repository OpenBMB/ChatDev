'''
This is the main file for the Life Restart Simulator application.
'''
import tkinter as tk
from tkinter import messagebox
from simulator import Simulator
import random
import sys

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Life Restart Simulator")
        self.simulator = Simulator()
        self.age_label = tk.Label(self, text="\n\n      欢迎,你来到了 5岁 的时候~      \n\n")
        self.age_label.pack()
        self.money_label = tk.Label(self, text="\n\n      你现在身上有 $1000      \n      点击GoOn开始模拟人生      \n\n")
        self.money_label.pack()
        self.go_on_button = tk.Button(self, text="Go On", command=self.go_on)
        self.go_on_button.pack()

    def go_on(self):
        age, money, event = self.simulator.go_on()
        message = ''
        if event == 'earn_money':
            message = random.choice(["你遇到幸运的事情大赚了一笔!!", "你升职加薪,财富增加!!", "你突然中了彩票"])
        elif event == 'lose_money':
            message = random.choice(["你遇到难受的事情财富减少...", "你回家路上不小心丢了一大笔钱..."])
        elif event == 'sick':
            message = random.choice(["你生了一场大病, 财产减少..."])
        self.age_label.config(text=f"\n\n      你现在来到了: {age} 岁      \n      {message}      \n")
        self.money_label.config(text=f"\n\n      你现在拥有的财富是: ${money}      \n\n")
        if event == "death":
            self.go_on_button.config(state=tk.DISABLED)
            messagebox.showinfo("Game Over", f"你一直活到 {age} 岁, 你积攒的财富有 ${money}.")
            sys.exit()


if __name__ == "__main__":
    app = Application()
    app.mainloop()
