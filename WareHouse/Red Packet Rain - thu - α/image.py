import pygame
import tkinter as tk
from tkinter import filedialog
import random

class Image:
    def __init__(self, file_path):
        # Load the image
        self.image = pygame.image.load(file_path)

        # Resize the image
        self.image = pygame.transform.scale(self.image, (50, 50))

        # Get the image's rect with a random x-coordinate
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, 750)  # Adjust the range based on your preferences

        # Randomly position the image at the top of the screen
        self.rect.y = random.randint(-100, 0)

    def move_image(self):
        # Move the image down the screen
        self.rect.y += 3

        # If the image has moved off the bottom of the screen, move it back to the top
        if self.rect.y > 600:
            self.rect.y = random.randint(-100, 0)

    def remove_image(self):
        # Move the image back to the top of the screen with a new random x-coordinate
        self.rect.y = random.randint(-100, 0)
        self.rect.x = random.randint(0, 750)  # Adjust the range based on your preferences

def select_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename()
    return file_path
