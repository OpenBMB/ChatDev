# Project Evaluator User Manual

## Introduction

The Project Evaluator is a Python program that allows you to evaluate a project based on its README.md file and assign it a score out of 10. This user manual will guide you through the installation process, explain the main functions of the software, and provide instructions on how to use it effectively.

## Installation

To install the Project Evaluator, follow these steps:

1. Make sure you have Python installed on your system. You can download Python from the official website: [https://www.python.org/downloads/](https://www.python.org/downloads/)

2. Clone or download the project files from the repository: [https://github.com/your-repository](https://github.com/your-repository)

3. Open a terminal or command prompt and navigate to the project directory.

4. Install the required dependencies by running the following command:

   ```
   pip install -r requirements.txt
   ```

   This will install all the necessary packages for the Project Evaluator.

## Main Functions

The Project Evaluator provides the following main functions:

1. **evaluate_project(readme_file)**: This function evaluates a project based on its README.md file and returns a score out of 10.

## Usage

To use the Project Evaluator, follow these steps:

1. Open the `main.py` file in a text editor.

2. Locate the line that says `readme_file = self.entry.get()`.

3. Replace `self.entry.get()` with the path to your README.md file. For example:

   ```
   readme_file = "path/to/your/README.md"
   ```

4. Save the `main.py` file.

5. Open a terminal or command prompt and navigate to the project directory.

6. Run the following command to start the Project Evaluator:

   ```
   python main.py
   ```

7. A graphical user interface (GUI) window will appear.

8. Enter the path to your README.md file in the text field.

9. Click the "Evaluate" button.

10. The Project Evaluator will process the README.md file and display the evaluation result in a message box.

## Example

Let's say you have a project with the following README.md file:

```md
# My Awesome Project

## Description

This is a Python program that does amazing things.

## Usage

To use this program, follow these steps:

1. Install Python.
2. Clone the repository.
3. Run the program.

## License

This project is licensed under the MIT License.
```

To evaluate this project using the Project Evaluator, follow these steps:

1. Open the `main.py` file in a text editor.

2. Replace `self.entry.get()` with the path to your README.md file. For example:

   ```
   readme_file = "path/to/your/README.md"
   ```

3. Save the `main.py` file.

4. Open a terminal or command prompt and navigate to the project directory.

5. Run the following command to start the Project Evaluator:

   ```
   python main.py
   ```

6. Enter the path to your README.md file in the text field.

7. Click the "Evaluate" button.

8. The Project Evaluator will process the README.md file and display the evaluation result in a message box. In this case, the result might be:

   ```
   Project score: 10/10
   ```

## Conclusion

The Project Evaluator is a powerful tool for evaluating projects based on their README.md files. By following the instructions in this user manual, you can easily install and use the software to assign a score to your projects.