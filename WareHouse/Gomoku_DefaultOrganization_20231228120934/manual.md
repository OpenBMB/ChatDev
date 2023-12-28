# Gomoku Game User Manual

## Introduction

Welcome to the Gomoku Game User Manual! This manual will guide you on how to install the game and provide instructions on how to play it. Gomoku is a classic board game where the objective is to get five of your pieces in a row, either horizontally, vertically, or diagonally.

## Installation

To install and run the Gomoku game, please follow the steps below:

1. Make sure you have Python installed on your computer. If not, you can download it from the official Python website (https://www.python.org/downloads/).

2. Download the game files from the provided source.

3. Open a terminal or command prompt and navigate to the directory where you downloaded the game files.

4. Install the required dependencies by running the following command:

   ```
   pip install -r requirements.txt
   ```

   This will install the necessary packages, including `tkinter` and `numpy`.

## Playing the Game

Once you have installed the game, you can start playing by following these steps:

1. Open a terminal or command prompt and navigate to the directory where you downloaded the game files.

2. Run the game by executing the `main.py` file:

   ```
   python main.py
   ```

3. The game will start, and you will see an empty 15x15 grid representing the game board.

4. To make a move, enter the row and column numbers when prompted. The rows and columns are numbered from 0 to 14.

5. The game will alternate between two players, represented by 'X' and 'O'. 'X' always goes first.

6. After each move, the game will check if there is a winner. If a player has five pieces in a row, they win the game.

7. If a move is invalid or there is no winner yet, you will be prompted to make another move.

8. If you want to play again after a game ends, enter 'y' when prompted. Otherwise, enter 'n' to exit the game.

## Conclusion

Congratulations! You have successfully installed and played the Gomoku game. Enjoy playing and challenging your friends in this classic board game. If you have any questions or encounter any issues, please feel free to reach out to our support team for assistance. Happy gaming!