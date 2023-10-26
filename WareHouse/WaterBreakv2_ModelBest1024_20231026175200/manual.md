# Water Break Reminder User Manual

## Introduction

The Water Break Reminder software is designed to help you stay hydrated during your work hours by reminding you to take water breaks at specific intervals. This user manual will guide you through the installation process, explain the main functions of the software, and provide instructions on how to use it effectively.

## Installation

To install the Water Break Reminder software, follow these steps:

1. Make sure you have Python installed on your computer. If not, you can download it from the official Python website (https://www.python.org/downloads/).

2. Download the source code files from the provided link.

3. Open a terminal or command prompt and navigate to the directory where you downloaded the source code files.

4. Create a virtual environment (optional but recommended) by running the following command:

   ```
   python -m venv venv
   ```

5. Activate the virtual environment by running the appropriate command for your operating system:

   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

6. Install the required dependencies by running the following command:

   ```
   pip install -r requirements.txt
   ```

7. Once the installation is complete, you are ready to use the Water Break Reminder software.

## Main Functions

The Water Break Reminder software provides the following main functions:

1. Input Start and End Times: You can input your start and end times for work down to the minute. This will define the time range during which the software will remind you to take water breaks.

2. Set Time Interval: You can specify the time interval between two water breaks. This will determine how frequently the software will remind you to drink water.

3. Generate Schedule: After submitting your start and end times and the time interval, the software will generate a schedule for water breaks. The schedule will be precise to the minute and will indicate when each water break should occur.

4. Countdown Timer: The software will display a countdown timer to the next scheduled water break from the current time. This will help you track the time remaining until your next water break.

## Usage Instructions

To use the Water Break Reminder software, follow these instructions:

1. Open a terminal or command prompt and navigate to the directory where you downloaded the source code files.

2. Activate the virtual environment (if you created one) by running the appropriate command for your operating system:

   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

3. Run the main.py file by executing the following command:

   ```
   python main.py
   ```

4. The Water Break Reminder application window will open.

5. Enter your start time, end time, and time interval in the respective entry fields.

6. Click the "Start Timer" button to start the reminder.

7. The application will display the countdown timer to the next scheduled water break.

8. Take a water break when the timer reaches zero.

9. Repeat steps 7-8 until your work hours end.

10. Close the application window when you are done.

## Conclusion

The Water Break Reminder software is a helpful tool for staying hydrated during your work hours. By following the installation instructions and using the software as described in this user manual, you can ensure that you take regular water breaks and maintain a healthy level of hydration. Enjoy your work and stay hydrated!