'''
app.py
This file contains the implementation of the TodoApp class and the save_tasks function.
'''
import json
def save_tasks(tasks):
    """
    Save the tasks to a JSON file.
    """
    with open('tasks.json', 'w') as file:
        json.dump(tasks, file)
class TodoApp:
    """
    A simple to-do app.
    """
    def __init__(self):
        self.tasks = []
    def add_task(self, task):
        """
        Add a new task to the app.
        """
        self.tasks.append(task)
    def mark_task_completed(self, task):
        """
        Mark a task as completed.
        """
        if task in self.tasks:
            self.tasks.remove(task)
            self.tasks.append(f"[COMPLETED] {task}")
    def edit_task(self, old_task, new_task):
        """
        Edit a task.
        """
        if old_task in self.tasks:
            index = self.tasks.index(old_task)
            self.tasks[index] = new_task
    def delete_task(self, task):
        """
        Delete a task.
        """
        if task in self.tasks:
            self.tasks.remove(task)
    def get_tasks(self):
        """
        Get all tasks.
        """
        return self.tasks