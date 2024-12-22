'''
main.py
This file is the entry point of the application.
'''
from app import TodoApp, save_tasks
# Create an instance of the TodoApp
todo_app = TodoApp()
# Add tasks
todo_app.add_task("Task 1")
todo_app.add_task("Task 2")
todo_app.add_task("Task 3")
# Mark a task as completed
todo_app.mark_task_completed("Task 2")
# Edit a task
todo_app.edit_task("Task 3", "Task 3 (edited)")
# Delete a task
todo_app.delete_task("Task 1")
# Get all tasks
tasks = todo_app.get_tasks()
# Save tasks
save_tasks(tasks)
print(tasks)