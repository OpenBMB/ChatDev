'''
This file contains the Ball class that represents the game ball.
'''
import pygame
import random
class Ball:
    def __init__(self, x, y):
        self.radius = 10
        self.x = x
        self.y = y
        self.speed_x = random.choice([-2, 2])
        self.speed_y = random.choice([-2, 2])
        self.rect = pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)
    def update(self, paddle1, paddle2):
        self.x += self.speed_x
        self.y += self.speed_y
        if self.y <= self.radius or self.y >= 400 - self.radius:
            self.speed_y *= -1
        ball_bbox = pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)
        paddle1_bbox = paddle1.rect.inflate(-5, -5)
        paddle2_bbox = paddle2.rect.inflate(-5, -5)
        if ball_bbox.colliderect(paddle1_bbox) or ball_bbox.colliderect(paddle2_bbox):
            self.speed_x *= -1
        self.rect.x = self.x - self.radius
        self.rect.y = self.y - self.radius
    def draw(self, screen):
        pygame.draw.circle(screen, (255, 255, 255), (self.x, self.y), self.radius)
    def reset(self):
        self.x = 400
        self.y = 200
        self.speed_x = random.choice([-2, 2])
        self.speed_y = random.choice([-2, 2])
        self.rect.x = self.x - self.radius
        self.rect.y = self.y - self.radius