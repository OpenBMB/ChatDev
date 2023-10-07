# Circle Dodge Game User Manual

## Introduction

Welcome to the Circle Dodge Game! This game is a simple and fun application where you control a character using your mouse and try to avoid touching randomly sized circles flying around the screen. The objective is to survive as long as possible without colliding with any circles.

## Installation

To install and run the Circle Dodge Game, please follow the steps below:

1. Make sure you have Python installed on your computer. You can download Python from the official website: https://www.python.org/downloads/

2. Open a terminal or command prompt and navigate to the directory where you want to install the game.

3. Clone the game repository by running the following command:
   ```
   git clone https://github.com/your-username/circle-dodge-game.git
   ```

4. Navigate to the game directory:
   ```
   cd circle-dodge-game
   ```

5. Install the required dependencies by running the following command:
   ```
   pip install -r requirements.txt
   ```

## Usage

To play the Circle Dodge Game, follow these steps:

1. Open a terminal or command prompt and navigate to the game directory.

2. Run the game by executing the following command:
   ```
   python main.py
   ```

3. The game window will open, and you will see your character in the center of the screen.

4. Move your mouse to control the character. The character will follow the movement of your mouse cursor.

5. Randomly sized circles will continuously spawn and fly around the screen. Your goal is to avoid touching any of these circles.

6. If your character collides with a circle, the game will end, and a "Game Over" screen will be displayed for 2 seconds.

7. After the "Game Over" screen disappears, you can close the game window to exit the game.

## Customization

If you want to customize the game, you can modify the code in the following files:

- `main.py`: This file contains the main game loop and handles user input. You can change the game window size, character appearance, and other game logic.

- `character.py`: This file defines the `Character` class, which represents the user-controlled character in the game. You can modify the character's appearance and behavior.

- `circle.py`: This file defines the `Circle` class, which represents the randomly sized circles flying around the screen. You can modify the circle's appearance, spawn rate, and movement behavior.

## Conclusion

Congratulations! You have successfully installed and played the Circle Dodge Game. Enjoy the game and challenge yourself to achieve a high score by avoiding as many circles as possible. Have fun and happy dodging!