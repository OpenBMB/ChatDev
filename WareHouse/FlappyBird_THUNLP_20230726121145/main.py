'''
Flappy Bird Game
'''
import tkinter as tk
import random
class FlappyBirdGame:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Flappy Bird")
        self.canvas = tk.Canvas(self.window, width=400, height=600)
        self.canvas.pack()
        self.bird = Bird(self.canvas)
        self.pipes = []
        self.score = 0
        self.is_game_over = False
        self.canvas.bind("<space>", self.jump)
        self.canvas.bind("<Button-1>", self.jump)
        self.canvas.focus_set()
        self.update()
    def jump(self, event):
        if not self.is_game_over:
            self.bird.jump()
    def create_pipe(self):
        if random.random() < 0.01:
            gap_height = random.randint(100, 250)  # Decrease the gap height range
            print("gap_height", gap_height)
            pipe = Pipe(self.canvas, gap_height)
            self.pipes.append(pipe)
    def move_pipes(self):
        for pipe in self.pipes:
            pipe.move()
            if pipe.is_offscreen():
                self.pipes.remove(pipe)
                self.score += 1
    def check_collision(self):
        for pipe in self.pipes:
            if pipe.collides_with(self.bird):
                self.is_game_over = True
    def update(self):
        if not self.is_game_over:
            self.bird.move()
            self.move_pipes()
            self.create_pipe()
            self.check_collision()
            self.canvas.delete("score")
            self.canvas.create_text(50, 50, text=f"Score: {self.score}", tag="score", fill="white", font=("Arial", 16))
            self.canvas.after(20, self.update)
        else:
            self.canvas.create_text(200, 300, text="Game Over", fill="white", font=("Arial", 32))
class Bird:
    def __init__(self, canvas):
        self.canvas = canvas
        self.id = self.canvas.create_oval(50, 300, 70, 320, fill="yellow")
        self.y_speed = 0
    def jump(self):
        self.y_speed = -5
    def move(self):
        self.canvas.move(self.id, 0, self.y_speed)
        self.y_speed += 0.2
    def get_position(self):
        return self.canvas.coords(self.id)
class Pipe:
    def __init__(self, canvas, gap_height):
        self.canvas = canvas
        self.top_pipe = self.canvas.create_rectangle(400, 0, 420, gap_height, fill="green")
        self.bottom_pipe = self.canvas.create_rectangle(400, gap_height + 150, 420, 600, fill="green")
        self.x_speed = -2
    def move(self):
        self.canvas.move(self.top_pipe, self.x_speed, 0)
        self.canvas.move(self.bottom_pipe, self.x_speed, 0)
    def is_offscreen(self):
        return self.canvas.coords(self.top_pipe)[2] < 0
    def collides_with(self, bird):
        bird_pos = bird.get_position()
        top_pipe_pos = self.canvas.coords(self.top_pipe)
        bottom_pipe_pos = self.canvas.coords(self.bottom_pipe)
        if bird_pos[2] > top_pipe_pos[0] and bird_pos[0] < top_pipe_pos[2]:
            if bird_pos[1] < top_pipe_pos[3] or bird_pos[3] > bottom_pipe_pos[1]:
                return True
        return False
if __name__ == "__main__":
    game = FlappyBirdGame()
    game.window.mainloop()