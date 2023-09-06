'''
Level class for managing the game level.
'''
import pygame
import random
class Level:
    def __init__(self):
        self.width = 80
        self.height = 80
        self.floor_color = (255, 255, 255)
        self.wall_color = (0, 0, 0)
        self.door_color = (0, 255, 0)
        self.treasure_color = (255, 255, 0)
        self.level_data = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.generate_level()
    def generate_level(self):
        for y in range(self.height):
            for x in range(self.width):
                if random.random() < 0.3:
                    self.level_data[y][x] = 1
                elif random.random() < 0.05:
                    self.level_data[y][x] = 2
                elif random.random() < 0.05:
                    self.level_data[y][x] = 3
                else:
                    self.level_data[y][x] = 0
    def is_wall(self, x, y):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return True
        return self.level_data[y][x] == 1
    def is_door(self, x, y):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        return self.level_data[y][x] == 2
    def is_treasure(self, x, y):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        return self.level_data[y][x] == 3
    def next_level(self, player):
        player.x = 40  # Reset the player's position
        player.y = 40
        player.rect.x = player.x
        player.rect.y = player.y
        self.generate_level()
    def draw(self, screen):
        for y in range(self.height):
            for x in range(self.width):
                if self.level_data[y][x] == 0:
                    pygame.draw.rect(screen, self.floor_color, (x * 10, y * 10, 10, 10))
                elif self.level_data[y][x] == 1:
                    pygame.draw.rect(screen, self.wall_color, (x * 10, y * 10, 10, 10))
                elif self.level_data[y][x] == 2:
                    pygame.draw.rect(screen, self.door_color, (x * 10, y * 10, 10, 10))
                elif self.level_data[y][x] == 3:
                    pygame.draw.rect(screen, self.treasure_color, (x * 10, y * 10, 10, 10))