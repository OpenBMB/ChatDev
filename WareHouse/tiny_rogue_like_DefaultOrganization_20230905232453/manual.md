# Roguelike Game User Manual

## Introduction

Welcome to the Roguelike Game! This game is designed to provide an exciting and challenging gaming experience inspired by the Tower of the Sorcerer game. In this game, you will navigate through a maze-like dungeon, encountering monsters, treasures, and doors. Your goal is to reach the next level by finding and touching the door while managing your character's health points (hp).

## Installation

To play the Roguelike Game, you need to install the following dependencies:

- Python (version 3.6 or higher)
- Pygame (version 2.0.1)

You can install the dependencies by running the following command in your terminal:

```
pip install -r requirements.txt
```

## How to Play

Once you have installed the dependencies, you can start playing the Roguelike Game by running the `main.py` file. Use the following command in your terminal:

```
python main.py
```

### Controls

- Use the W key to move the player character up.
- Use the S key to move the player character down.
- Use the A key to move the player character left.
- Use the D key to move the player character right.

### Game Rules

- The player character can walk on the floor tiles.
- The player character can go to the next level by touching a door.
- The player character's hp is calculated by subtracting the monster's hp from the character's hp.
- The player character's hp is randomly restored to a value between 20 and 30 after touching a treasure chest.
- The player character cannot pass through walls.
- There must be at least one path from the starting position to the door.

### Game Interface

The game interface consists of an 80x80 grid representing the game map. The player character is represented by a red rectangle, while the floor tiles, walls, doors, and treasure chests are represented by different colors.

### Scoring

Your score in the Roguelike Game is determined by the number of levels you successfully complete. Try to reach as many levels as possible to achieve a high score!

## Conclusion

Thank you for choosing the Roguelike Game! We hope you enjoy playing and have a great gaming experience. If you have any questions or feedback, please don't hesitate to contact us. Happy gaming!