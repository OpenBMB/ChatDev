'''
tasks.py
This file is used to store and retrieve tasks from a JSON file.
'''
import json
def save_tasks(tasks):
    """
    Save the tasks to a JSON file.
    """
    with open('tasks.json', 'w') as file:
        json.dump(tasks, file)
def load_tasks():
    """
    Load tasks from a JSON file.
    """
    try:
        with open('tasks.json', 'r') as file:
            tasks = json.load(file)
    except FileNotFoundError:
        tasks = []
    return tasks