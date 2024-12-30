import pygame
from enum import Enum

# Window Settings
WINDOW_WIDTH = 1080
WINDOW_HEIGHT = 900
CELL_SIZE = 100
GRID_ROWS = 7
GRID_COLS = 9
TOP_MARGIN = 100
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 100, 0)
BROWN = (139, 69, 19)
YELLOW = (255, 255, 0)
LAWN_GREEN = (124, 252, 0)
GRAY = (128, 128, 128)
RED = (255, 0, 0)

# Game States
class GameState(Enum):
    MENU = 1
    PLAYING = 2
    PAUSED = 3
    GAME_OVER = 4

# Plant Types
class PlantType(Enum):
    SUNFLOWER = 1
    PEASHOOTER = 2
    ROSE_SHOOTER = 3
    CHOMPER = 4
    SNOW_PEA = 5

# Zombie Types
class ZombieType(Enum):
    NORMAL = 1
    CONE = 2
    BUCKET = 3
    NEWSPAPER = 4
    DANCING = 5

# Plant Stats
PLANT_STATS = {
    PlantType.SUNFLOWER: {"health": 100, "cost": 50, "color": YELLOW},
    PlantType.PEASHOOTER: {"health": 120, "cost": 100, "color": GREEN},
    PlantType.ROSE_SHOOTER: {"health": 140, "cost": 150, "color": (255, 192, 203)},
    PlantType.CHOMPER: {"health": 180, "cost": 175, "color": (148, 0, 211)},
    PlantType.SNOW_PEA: {"health": 130, "cost": 175, "color": (0, 191, 255)}
}

# Zombie Stats
ZOMBIE_STATS = {
    ZombieType.NORMAL: {"health": 300, "speed": 0.4, "damage": 0.4},
    ZombieType.CONE: {"health": 450, "speed": 0.45, "damage": 0.3},
    ZombieType.BUCKET: {"health": 550, "speed": 0.35, "damage": 0.5},
    ZombieType.NEWSPAPER: {"health": 200, "speed": 0.6, "damage": 0.3},
    ZombieType.DANCING: {"health": 350, "speed": 0.5, "damage": 0.35}
} 