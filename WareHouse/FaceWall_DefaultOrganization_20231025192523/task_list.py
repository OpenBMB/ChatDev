'''
Task List Module
This module provides the task list functionality. Employees can add, edit, and mark tasks as completed.
'''
import tkinter as tk
class TaskList(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.tasks = []
        self.task_entry = tk.Entry(self)
        self.task_entry.pack()
        self.add_button = tk.Button(self, text="Add Task", command=self.add_task)
        self.add_button.pack()
        self.task_listbox = tk.Listbox(self)
        self.task_listbox.pack()
        self.edit_button = tk.Button(self, text="Edit Task", command=self.edit_task)
        self.edit_button.pack()
        self.delete_button = tk.Button(self, text="Delete Task", command=self.delete_task)
        self.delete_button.pack()
        self.complete_button = tk.Button(self, text="Mark as Completed", command=self.mark_completed)
        self.complete_button.pack()
    def add_task(self):
        task = self.task_entry.get()
        if task:
            self.tasks.append(task)
            self.task_listbox.insert(tk.END, task)
            self.task_entry.delete(0, tk.END)
    def edit_task(self):
        selected_task = self.task_listbox.curselection()
        if selected_task:
            task = self.task_entry.get()
            if task:
                self.tasks[selected_task[0]] = task
                self.task_listbox.delete(selected_task)
                self.task_listbox.insert(selected_task, task)
                self.task_entry.delete(0, tk.END)
    def delete_task(self):
        selected_task = self.task_listbox.curselection()
        if selected_task:
            index = selected_task[0]
            self.tasks.pop(index)
            self.task_listbox.delete(selected_task)
    def mark_completed(self):
        selected_task = self.task_listbox.curselection()
        if selected_task:
            self.task_listbox.itemconfig(selected_task, fg="gray")