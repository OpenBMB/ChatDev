# Texas Hold'em Poker Game User Manual

## Introduction

Welcome to the Texas Hold'em Poker Game! This game allows you to experience the excitement and strategy of playing Texas Hold'em Poker against AI opponents. The game follows the official No Limit Texas Hold'em rules and simulates a poker tournament with 1 human player and 4 AI characters.

## Installation

To install and run the Texas Hold'em Poker Game, please follow these steps:

1. Ensure that you have Python installed on your computer. You can download Python from the official website: https://www.python.org/downloads/

2. Clone or download the game code from the GitHub repository: [link to repository]

3. Open a terminal or command prompt and navigate to the directory where you downloaded the game code.

4. Create a virtual environment (optional but recommended) by running the following command:

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

7. You are now ready to play the Texas Hold'em Poker Game!

## Game Instructions

1. Open a terminal or command prompt and navigate to the directory where you downloaded the game code.

2. Activate the virtual environment (if you created one) by running the appropriate command as mentioned in the installation steps.

3. Run the game by executing the following command:

   ```
   python main.py
   ```

4. The game will start, and you will be prompted to enter your decisions during each betting round. The available decisions are:

   - Fold: To fold your hand and exit the current round.
   - Check: To pass the betting action to the next player without placing a bet.
   - Bet: To place a bet. You will be prompted to enter the bet amount.
   - Call: To match the current bet amount.
   - Raise: To increase the current bet amount. You will be prompted to enter the raise amount.

5. The AI characters will also make their decisions based on their hand and the community cards. They may occasionally make random decisions to add unpredictability to the game.

6. The game will continue until there is only one player left or until you choose to exit the game.

## Game Features

The Texas Hold'em Poker Game includes the following features:

- Realistic poker experience adhering to the official No Limit Texas Hold'em rules.
- Simulated poker tournament with 1 human player and 4 AI characters.
- Each player starts with $1000 in chips.
- Blinds set at $5 for the small blind and $10 for the big blind.
- Blinds increase according to the World Poker Tour incremental blinds guidelines.
- AI characters make decisions based on basic poker theory, with occasional random decisions.
- Actions available: checking, betting, raising, calling, and folding.
- Accurate tracking of chip counts for all players.
- Management of community cards and the deck.
- Determination of the winner(s) of each hand.

## Algorithm for Increasing Blinds

The algorithm for increasing blinds follows the World Poker Tour incremental blinds guidelines. The blinds increase at regular intervals to maintain a challenging pace. The specific algorithm is as follows:

1. The tournament starts with blinds set at $5 for the small blind and $10 for the big blind.

2. After a certain number of rounds (e.g., every 10 rounds), the blinds increase by a fixed amount (e.g., $5).

3. The new blinds are then applied to the next round and continue to increase at the same fixed amount after each interval.

4. This ensures that the blinds gradually increase over time, creating a more challenging gameplay experience.

## Conclusion

Congratulations! You are now ready to enjoy the Texas Hold'em Poker Game. Have fun playing against the AI characters and test your poker skills. Good luck!