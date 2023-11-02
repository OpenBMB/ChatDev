'''
This file contains the Player class which represents the player in the pinball game.
'''
class Player:
    def __init__(self, canvas):
        self.canvas = canvas
        self.score = 0
        self.level = 1
        self.ball = self.canvas.create_oval(395, 295, 405, 305, fill="red")
        self.player_shape = self.canvas.create_rectangle(50, 50, 100, 100, fill="blue")
        self.velocity_x = 1
        self.velocity_y = -1
        # self.ball_coords = self.canvas.coords(self.ball)
        # self.player_coords = self.canvas.coords(self.player_shape)

    def update(self):
        self.canvas.move(self.ball, self.velocity_x, self.velocity_y)
        # self.check_collision()
        self.check_collision_with_player()
        self.check_collision_with_walls()
    # def check_collision(self):
    #     ball_coords = self.canvas.coords(self.ball)
    #     if ball_coords[0] <= 0 or ball_coords[2] >= 800:
    #         self.velocity_x *= -1
    #     if ball_coords[1] <= 0 or ball_coords[3] >= 600:
    #         self.velocity_y *= -1
    def check_collision_with_walls(self):
        ball_coords = self.canvas.coords(self.ball)
        if ball_coords[0] <= 0 or ball_coords[2] >= 800:
            self.velocity_x *= -1
        if ball_coords[1] <= 0 or ball_coords[3] >= 600:
            self.velocity_y *= -1
    def check_collision_with_player(self):
        ball_coords = self.canvas.coords(self.ball)
        player_coords = self.canvas.coords(self.player_shape)

        # 检测玩家和球是否发生碰撞
        if (player_coords[0] < ball_coords[2] and
            player_coords[2] > ball_coords[0] and
            player_coords[1] < ball_coords[3] and
            player_coords[3] > ball_coords[1]):
            # 发生碰撞，可以在这里执行相应的操作
            self.score += 10  # 假设得分增加
    
    def move(self, event):
        # 获取鼠标点击的位置
        mouse_x = event.x
        mouse_y = event.y

        # 计算玩家当前位置
        player_x, player_y, _, _ = self.canvas.coords(self.player_shape)
        self.canvas.coords(self.player_shape, mouse_x - 25, mouse_y - 25, mouse_x + 25, mouse_y + 25)

        # 计算移动速度
        speed = 2

        # 计算移动方向
        dx = mouse_x - player_x
        dy = mouse_y - player_y

        # 计算归一化向量
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length > 0:
            dx /= length
            dy /= length

        # 设置新的速度
        self.x_speed = dx * speed
        self.y_speed = dy * speed
