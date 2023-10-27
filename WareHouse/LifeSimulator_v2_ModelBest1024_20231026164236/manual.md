# Life Restart Simulator User Manual

## Introduction
The Life Restart Simulator is an application that simulates different life events based on user input. Users can click the "Go On" button to trigger the simulation and see the outcomes of various life events. The simulator starts with the user's age set to 5 years and an initial amount of money set to 1000 yuan. Each click of the "Go On" button advances the simulation by a random number of years between 1 and 10. The simulation can result in earning or losing money, or even death. The goal is to see how long the user can live and how much money they have at the end.

## Installation
To use the Life Restart Simulator, you need to have Python installed on your computer. You also need to install the `tkinter` library, which is used for the graphical user interface.

1. Install Python: You can download Python from the official website (https://www.python.org) and follow the installation instructions for your operating system.

2. Install `tkinter`: Open a terminal or command prompt and run the following command:
   ```
   pip install tkinter==8.6
   ```

3. Download the simulator files: Download the `main.py` and `simulator.py` files from the provided source.

## Usage
Once you have installed the necessary dependencies and downloaded the simulator files, you can run the Life Restart Simulator by following these steps:

1. Open a terminal or command prompt and navigate to the directory where you saved the simulator files.

2. Run the following command to start the simulator:
   ```
   python main.py
   ```

3. The Life Restart Simulator window will open, displaying the user's age and money.

4. Click the "Go On" button to trigger the simulation and see the outcomes of different life events.

5. Each click of the "Go On" button will advance the simulation by a random number of years and update the age and money values accordingly.

6. If the simulation results in death, the "Go On" button will be disabled and a message box will appear, showing the user's final age and money.

7. You can close the simulator window at any time to exit the application.

## Customization
If you want to customize the Life Restart Simulator, you can modify the `simulator.py` file. The `Simulator` class in this file handles the simulation logic. You can adjust the initial age and money values, as well as the range of years and money values for each life event.

## Conclusion
The Life Restart Simulator is a fun and interactive application that allows users to experience different life events and see how they can affect their age and financial situation. By clicking the "Go On" button, users can simulate the passage of time and explore the outcomes of various life events. Have fun playing and see how long you can live and how much money you can accumulate!