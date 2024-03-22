# Snake Game User Manual

Welcome to the Snake Game! This user manual will guide you through the installation process and explain how to play the game.

## Table of Contents
1. [Installation](#installation)
2. [Game Controls](#game-controls)
3. [Gameplay](#gameplay)
4. [Scoring](#scoring)
5. [Game Over](#game-over)

## 1. Installation <a name="installation"></a>

To play the Snake Game, you need to have Python and the Pygame library installed on your computer. Follow the steps below to install the necessary dependencies:

1. Install Python: Visit the [Python website](https://www.python.org/downloads/) and download the latest version of Python for your operating system. Follow the installation instructions provided.

2. Install Pygame: Open a terminal or command prompt and run the following command:

   ```
   pip install pygame
   ```

   If you're using Anaconda, you can run the following command instead:

   ```
   conda install -c cogsci pygame
   ```

   This will install the Pygame library.

3. Download the Snake Game files: Download the `main.py`, `snake.py`, `food.py`, and `requirements.txt` files from the provided source.

4. Install additional dependencies: Open a terminal or command prompt, navigate to the directory where you downloaded the Snake Game files, and run the following command:

   ```
   pip install -r requirements.txt
   ```

   This will install any additional dependencies required by the game.

## 2. Game Controls <a name="game-controls"></a>

The Snake Game is controlled using the arrow keys on your keyboard. Use the following keys to control the snake:

- **Up Arrow**: Move the snake upwards
- **Down Arrow**: Move the snake downwards
- **Left Arrow**: Move the snake to the left
- **Right Arrow**: Move the snake to the right

## 3. Gameplay <a name="gameplay"></a>

Once you have installed the game and dependencies, you can start playing the Snake Game. Follow the steps below to launch the game:

1. Open a terminal or command prompt.

2. Navigate to the directory where you downloaded the Snake Game files.

3. Run the following command to start the game:

   ```
   python main.py
   ```

   This will launch the game window.

4. Use the arrow keys to control the snake and guide it to eat the food represented by dots on the grid.

5. As the snake consumes the food, it will grow longer, making the game progressively challenging.

6. The game's pace will gradually increase, making it more difficult to maneuver the snake without running into obstacles.

## 4. Scoring <a name="scoring"></a>

Each time the snake successfully consumes food, the player earns points. The score is displayed on the game screen. The more food the snake eats, the higher the score.

## 5. Game Over <a name="game-over"></a>

The game continues until one of the following conditions is met:

- The snake collides with itself. This happens when the snake's head touches any part of its body.
- The snake collides with the boundaries of the game window.

When the game is over, a message will be displayed on the screen showing the final score. You can then close the game window.

Enjoy playing the Snake Game!