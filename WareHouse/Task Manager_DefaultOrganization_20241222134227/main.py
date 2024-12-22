from tkinter import messagebox
from todo_list import TodoList
from tkinter import Tk, Label, Entry, Button, Listbox
class TodoApp:
    def __init__(self):
        self.todo_list = TodoList()
        self.window = Tk()
        self.window.title("To-Do App")
        self.task_entry = Entry(self.window)
        self.task_entry.pack()
        self.add_button = Button(self.window, text="Add Task", command=self.add_task)
        self.add_button.pack()
        self.task_listbox = Listbox(self.window)
        self.task_listbox.pack()
        self.complete_button = Button(self.window, text="Mark Complete", command=self.mark_complete)
        self.complete_button.pack()
        self.edit_button = Button(self.window, text="Edit Task", command=self.edit_task)
        self.edit_button.pack()
        self.delete_button = Button(self.window, text="Delete Task", command=self.delete_task)
        self.delete_button.pack()
        self.update_task_listbox()
        self.window.mainloop()
    def add_task(self):
        task = self.task_entry.get()
        self.todo_list.add_task(task)
        self.update_task_listbox()
    def mark_complete(self):
        selected_task = self.task_listbox.get(self.task_listbox.curselection())
        if selected_task:
            self.todo_list.mark_complete(selected_task)
            self.update_task_listbox()
    def edit_task(self):
        selected_task = self.task_listbox.get(self.task_listbox.curselection())
        if selected_task:
            new_task = self.task_entry.get()
            self.todo_list.edit_task(selected_task, new_task)
            self.update_task_listbox()
    def delete_task(self):
        selected_task = self.task_listbox.get(self.task_listbox.curselection())
        if selected_task:
            self.todo_list.delete_task(selected_task)
            self.update_task_listbox()
    def update_task_listbox(self):
        self.task_listbox.delete(0, "end")
        tasks = self.todo_list.get_tasks()
        for task in tasks:
            self.task_listbox.insert("end", task)
if __name__ == "__main__":
    app = TodoApp()