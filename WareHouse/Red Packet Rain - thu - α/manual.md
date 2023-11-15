# Red Packet Rain Game

A captivating game developed in Python that engages users from the start.

## Quick Install

Before you start, make sure you have Python installed on your computer. You can download Python from [here](https://www.python.org/downloads/).

You will also need to install the `pygame` and `tkinter` libraries. You can install them using pip:

```
pip install pygame
pip install python-tk
```

## 🤔 What is this?

The 'Red Packet Rain' game is a visually immersive experience where user-uploaded images descend slowly in sequence from random starting points at the top of the page. The game begins with a file selection pop-up window, allowing users to select an image file representing a red envelope. The chosen image undergoes intelligent resizing for seamless integration into the game.

In the game, a dynamic scoreboard in the top left corner displays the score, starting from zero. Each image serves as an interactive element. Clicking on an image results in its disappearance, accompanied by a random increase in the score on the scoreboard, ranging from 1 to 6. The game concludes when the score reaches 100, with a heartfelt congratulatory note.

## 📖 How to Play

1. Run the `main.py` script to start the game.
2. A file selection pop-up window will appear. Select an image file that you want to use in the game.
3. The game window will appear with your chosen image descending from the top of the screen.
4. Click on the images to make them disappear and increase your score. The score is displayed in the top left corner of the game window.
5. The game concludes when your score reaches 100. A congratulatory message will be printed in the console.

## 📚 Documentation

Please see the comments in the code for a detailed explanation of how each part of the game works.

- `main.py`: This is the main file for the game. It handles the initialization of the game window and the game loop.
- `gamewindow.py`: This file contains the GameWindow class, which handles the creation and management of the game window.
- `image.py`: This file contains the Image class, which handles the image file selected by the user.
- `scoreboard.py`: This file contains the Scoreboard class, which handles the game's scoreboard.