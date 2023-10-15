'''
This file contains the TodoList class which manages the list of todos.
'''
import datetime
class Todo:
    def __init__(self, description):
        self.date_added = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.description = description
        self.date_completed = None
    def complete(self):
        self.date_completed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
class TodoList:
    def __init__(self):
        self.todos = []
    def add_todo(self, description):
        todo = Todo(description)
        self.todos.append(todo)
    def complete_todo(self, todo):
        todo.complete()
    def get_active_todos(self):
        return [todo for todo in self.todos if todo.date_completed is None]
    def get_completed_todos(self):
        return [todo for todo in self.todos if todo.date_completed is not None]