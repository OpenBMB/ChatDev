# Online UNO Game User Manual

## Introduction

Welcome to the Online UNO Game! This user manual will guide you through the installation process and explain how to use and play the game.

The Online UNO Game is a web-based implementation of the popular card game UNO. It allows you to play UNO with your friends online, no matter where they are. The game provides a user-friendly interface and supports all the standard UNO rules.

## Installation

To install and run the Online UNO Game, please follow these steps:

1. Make sure you have Python installed on your computer. If not, you can download it from the official Python website: [https://www.python.org/downloads/](https://www.python.org/downloads/)

2. Download the game code from the provided source files.

3. Open a terminal or command prompt and navigate to the directory where you downloaded the game code.

4. Create a virtual environment for the game by running the following command:

   ```
   python -m venv env
   ```

5. Activate the virtual environment by running the appropriate command for your operating system:

   - For Windows:

     ```
     env\Scripts\activate
     ```

   - For macOS and Linux:

     ```
     source env/bin/activate
     ```

6. Install the required dependencies by running the following command:

   ```
   pip install -r requirements.txt
   ```

7. Once the installation is complete, you are ready to run the game!

## Usage

To start the Online UNO Game, follow these steps:

1. Make sure you have activated the virtual environment as explained in the installation steps.

2. In the terminal or command prompt, navigate to the directory where you downloaded the game code.

3. Run the following command to start the game:

   ```
   python main.py
   ```

4. The game window will open, displaying the game interface.

5. Share the game URL with your friends so they can join the game.

6. Follow the on-screen instructions to play the game. Use the buttons and input fields provided to perform game actions, such as drawing cards or playing cards.

7. Enjoy playing UNO with your friends online!

## Game Interface

The game interface consists of the following elements:

- **Game State**: This section displays the current state of the game, including the current player, the current card on the discard pile, and any special rules in effect.

- **Player Hand**: This section displays the cards in your hand. Click on a card to select it for playing.

- **Game Actions**: This section provides buttons and input fields for performing game actions, such as drawing cards or playing cards. Use these controls to interact with the game.

## Game Rules

The Online UNO Game follows the standard rules of UNO. Here are some key rules to keep in mind:

- The game starts with each player being dealt 7 cards.

- The player who goes first is determined randomly.

- Players take turns clockwise.

- To play a card, it must match either the color or the value of the card on the discard pile.

- Special cards have unique effects. For example, "Skip" skips the next player's turn, "Reverse" changes the direction of play, and "Draw Two" makes the next player draw two cards.

- If you don't have a playable card, you must draw a card from the deck. If the drawn card is playable, you can play it immediately.

- The first player to get rid of all their cards wins the game.

## Conclusion

Congratulations! You have successfully installed and learned how to use the Online UNO Game. Gather your friends, start a game, and have fun playing UNO online!

If you encounter any issues or have any feedback, please don't hesitate to contact our support team. Enjoy the game!