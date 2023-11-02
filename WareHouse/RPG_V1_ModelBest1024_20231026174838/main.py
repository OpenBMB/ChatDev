'''
This is the main file of the 2D horizontal shooting RPG game.
'''
import pygame
from player import Player
from enemy import Enemy
from projectile import Projectile
# Initialize the game
pygame.init()
# Set up the game window
window_width = 800
window_height = 600
window = pygame.display.set_mode((window_width, window_height))
pygame.display.set_caption("2D Shooting RPG Game")
# Create the player object
player = Player(window_width // 2, window_height - 50)
# Create enemy objects
enemies = []
for i in range(5):
    enemy = Enemy()
    enemies.append(enemy)
# Create projectile objects
projectiles = []
# Game loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                projectile = Projectile(player.x + player.width // 2 - 5, player.y)
                projectiles.append(projectile)
    # Update player and enemies
    player.update()
    for enemy in enemies:
        enemy.update()
    # Update projectiles
    for projectile in projectiles:
        projectile.update()
    # Check for collision between projectiles and enemies
    for projectile in projectiles:
        for enemy in enemies:
            if projectile.x < enemy.x + enemy.width and projectile.x + projectile.width > enemy.x and \
                    projectile.y < enemy.y + enemy.height and projectile.y + projectile.height > enemy.y:
                projectiles.remove(projectile)
                enemies.remove(enemy)
    # Draw the game objects
    window.fill((0, 0, 0))
    player.draw(window)
    for enemy in enemies:
        enemy.draw(window)
    for projectile in projectiles:
        projectile.draw(window)
    pygame.display.update()
# Quit the game
pygame.quit()