import tkinter as tk
class TaskManager:
    def __init__(self):
        self.tasks = []
    def add_task(self, task_name):
        task = {"name": task_name, "completed": False}
        self.tasks.append(task)
    def edit_task(self, task_index, new_task_name):
        if task_index < len(self.tasks):
            self.tasks[task_index]["name"] = new_task_name
    def delete_task(self, task_index):
        if task_index < len(self.tasks):
            del self.tasks[task_index]
    def complete_task(self, task_index):
        if task_index < len(self.tasks):
            self.tasks[task_index]["completed"] = True
    def is_task_completed(self, task_index):
        if task_index < len(self.tasks):
            return self.tasks[task_index]["completed"]
        return False
    def get_tasks(self):
        return self.tasks