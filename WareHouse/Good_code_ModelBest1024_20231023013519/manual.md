manual.md

# Python Praise Generator

A tool to add praises to your Python code

## Quick Install

This application is built using Python. If you don't have Python installed, you can download it from [here](https://www.python.org/downloads/).

After installing Python, you need to install the tkinter library. You can do this by running the following command in your terminal:

`pip install tkinter`

## 🤔 What is this?

This is a simple application that adds praises to your Python code. When you select a Python file, the application will praise the programmer. 

## 📖 Documentation

Please see below for full documentation on:

- Getting started (installation, setting up the environment, simple examples)

- How-To examples (demos, integrations, helper functions)

- Reference (full API docs)

- Resources (high-level explanation of core concepts)

## Getting Started

After installing Python and tkinter, download the application files (main.py, praise_generator.py, and file_processor.py) and save them in the same directory.

To run the application, open your terminal, navigate to the directory where you saved the files, and run the following command:

`python main.py`

A window will open with a button saying "Select Python File". Click on this button to select the Python file you want to process. The application will add a line of praise at the end of each line of code in the file.

## How-To Examples

Here is an example of how the application works:

Original Python code:

```python
def hello_world():
    print("Hello, world!")
```

After processing with the application:

```python
def hello_world():  # Incredible function definition!
    print("Hello, world!")  # Excellent variable assignment!
```

Also the appilication can also comment other information:

```python
你挑着担
我牵着马
```

After processing with the application:

```python
你挑着担  # Exceptional understanding of concepts!
我牵着马  # Innovative approach!
```

you mean, why don't I add more file formats in it? Because I'm poor and busy :P

## Reference

The application consists of three Python files:

- main.py: This is the main file that runs the application.

- praise_generator.py: This file contains a function to generate random praises.

- file_processor.py: This file contains a function to process the selected Python file.

## Resources

For more information about Python and tkinter, you can check out the following resources:

- [Python Documentation](https://docs.python.org/3/)

- [Tkinter Documentation](https://docs.python.org/3/library/tkinter.html)