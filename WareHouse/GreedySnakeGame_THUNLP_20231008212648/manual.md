# Greedy Snake Game User Manual

## Introduction

Welcome to the Greedy Snake Game! This game is a classic arcade-style game where you control a snake and try to eat as much food as possible to grow longer. The game features visually appealing graphics, intuitive controls, and smooth animation to provide an enjoyable gaming experience.

## Installation

To play the Greedy Snake Game, you need to install the following dependencies:

- Python 3.x
- Pygame library

You can install the Pygame library by running the following command:

```
pip install pygame
```

## Starting the Game

To start the Greedy Snake Game, follow these steps:

1. Open a terminal or command prompt.
2. Navigate to the directory where you have saved the game files.
3. Run the following command to start the game:

```
python main.py
```

## Game Controls

- Use the arrow keys (up, down, left, right) to control the snake's movement.
- Press the "Enter" key to start a new game or exit the game.

## Game Rules

1. The game starts with a snake of length 1 and a single food item on the grid.
2. The player controls the snake's movement using arrow keys.
3. The snake moves continuously in the direction it's facing.
4. The player's goal is to eat as much food as possible to grow longer.
5. When the snake consumes a piece of food, its length increases, and a new piece of food appears at a random location on the grid.
6. The game ends if the snake collides with the game boundaries or itself.
7. The player's score is based on the number of food items eaten.
8. The game difficulty level can be adjusted by increasing the snake's speed or changing the grid size.
9. Sound effects are included for actions like eating food or game over.

## Game Interface

The game interface consists of a grid where the snake and food items are displayed. The snake is represented by green rectangles, and the food items are represented by red rectangles. The score is displayed at the top of the screen.

## Game Over

The game ends when the snake collides with the game boundaries or itself. A "Game Over" message is displayed, along with the player's final score. To start a new game, press the "Enter" key.

## Adjusting Difficulty Level

To adjust the game's difficulty level, you can modify the following variables in the `settings.py` file:

- `snake_speed`: Controls the speed of the snake. Increase the value to make the snake move faster.
- `window_width` and `window_height`: Control the size of the game window. Increase or decrease the values to change the grid size.

## Conclusion

Enjoy playing the Greedy Snake Game! Try to beat your high score and challenge your friends to see who can eat the most food. Have fun!