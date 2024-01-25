# Random Password Generator App User Manual

## Introduction

The Random Password Generator App is a user-friendly application that allows users to generate strong and customizable passwords. It provides a simple and intuitive interface for users to specify the length and complexity of the generated passwords. The app generates passwords that include a combination of uppercase and lowercase letters, numbers, and special characters. Users can also exclude certain characters or character types from the generated passwords. The app includes a secure random number generator to ensure the randomness of the generated passwords. Additionally, it provides a feature to check the strength of a given password based on commonly used password criteria. The app is platform-independent and compatible with major operating systems such as Windows, macOS, and Linux.

## Installation

To use the Random Password Generator App, you need to have Python installed on your system. Follow the steps below to install the required dependencies and run the app:

1. Open a terminal or command prompt.

2. Clone the repository or download the source code files.

3. Navigate to the directory where the source code files are located.

4. Create a virtual environment (optional but recommended):

   ```shell
   python -m venv venv
   ```

5. Activate the virtual environment:

   - For Windows:

     ```shell
     venv\Scripts\activate
     ```

   - For macOS and Linux:

     ```shell
     source venv/bin/activate
     ```

6. Install the required dependencies:

   ```shell
   pip install -r requirements.txt
   ```

## Usage

To run the Random Password Generator App, follow the steps below:

1. Make sure you have activated the virtual environment (if you created one).

2. In the terminal or command prompt, navigate to the directory where the source code files are located.

3. Run the following command:

   ```shell
   python main.py
   ```

4. The app window will open, displaying the user interface.

## User Interface

The Random Password Generator App has a user-friendly interface that allows users to specify the length and complexity of the generated passwords. Here is an overview of the different elements in the interface:

- **Password Length**: Enter the desired length of the generated passwords in the corresponding entry field.

- **Password Complexity**: Select the complexity requirements for the generated passwords by checking the corresponding checkboxes. The available options are:
  - Uppercase Letters
  - Lowercase Letters
  - Numbers
  - Special Characters

- **Excluded Characters**: If you want to exclude certain characters or character types from the generated passwords, enter them in the corresponding entry field. For example, if you want to exclude the characters "a" and "1", enter "a1".

- **Number of Passwords**: Enter the desired number of passwords to generate in the corresponding entry field.

- **Generate Passwords**: Click this button to generate the passwords based on the specified parameters. The generated passwords will be displayed in the "Generated Passwords" section.

- **Generated Passwords**: This section displays the generated passwords in a clear and organized manner. Each password is shown on a separate line.

- **Check Password Strength**: Enter a password in the corresponding entry field and click this button to check its strength based on commonly used password criteria. The strength will be displayed in a message box.

## Examples

Here are a few examples to demonstrate how to use the Random Password Generator App:

1. Generate a password with a length of 8 characters, including uppercase letters and numbers:

   - Password Length: 8
   - Password Complexity: Uppercase Letters, Numbers

2. Generate 5 passwords with a length of 10 characters, including lowercase letters and special characters, excluding the characters "a" and "1":

   - Password Length: 10
   - Password Complexity: Lowercase Letters, Special Characters
   - Excluded Characters: a1
   - Number of Passwords: 5

3. Check the strength of a password:

   - Check Password Strength: Enter the password in the corresponding entry field and click the "Check Strength" button.

## Conclusion

The Random Password Generator App provides a user-friendly interface for generating strong and customizable passwords. It allows users to specify the length and complexity of the passwords, exclude certain characters, and generate multiple passwords at once. The app also includes a feature to check the strength of a given password. It is platform-independent and compatible with major operating systems. Follow the installation instructions and refer to the user manual for usage instructions.