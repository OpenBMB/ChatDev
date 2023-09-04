# Vocabulary Builder App User Manual

## Introduction
The Vocabulary Builder App is a mobile application designed to help users expand their word knowledge. It provides synonyms, antonyms, and usage examples for various words. This user manual will guide you through the installation process and explain how to use the app effectively.

## Installation
To install the Vocabulary Builder App, follow these steps:

1. Make sure you have Python installed on your system. If not, download and install Python from the official website (https://www.python.org/).

2. Open a terminal or command prompt and navigate to the directory where you have downloaded the app's source code.

3. Create a virtual environment by running the following command:
   ```
   python -m venv venv
   ```

4. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

5. Install the required dependencies by running the following command:
   ```
   pip install -r requirements.txt
   ```

## Usage
Once you have installed the app, follow these steps to use it:

1. Open a terminal or command prompt and navigate to the directory where you have downloaded the app's source code.

2. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

3. Run the app by executing the following command:
   ```
   python main.py
   ```

4. The Vocabulary Builder App window will open. You will see a text field labeled "Word" where you can enter the word you want to search for.

5. Enter a word in the "Word" field and click the "Search" button.

6. If the word is found in the vocabulary, the synonyms, antonyms, and usage examples will be displayed in the respective text fields. If the word is not found, a message box will appear indicating that the word was not found.

7. You can search for multiple words by repeating steps 5 and 6.

8. To exit the app, simply close the Vocabulary Builder App window.

## Additional Information
- The Vocabulary Builder App uses a pre-defined vocabulary stored in the `vocabulary.py` file. You can add more words and their synonyms, antonyms, and usage examples to expand the vocabulary.

- The app provides a simple and intuitive user interface for searching words and displaying their synonyms, antonyms, and usage examples.

- The app is built using the Python programming language and the Tkinter library for creating the graphical user interface.

- If you encounter any issues or have any questions, please refer to the documentation or contact our support team for assistance.

We hope you find the Vocabulary Builder App useful in expanding your word knowledge. Enjoy using the app!