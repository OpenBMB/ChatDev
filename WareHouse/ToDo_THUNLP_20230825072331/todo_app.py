'''
This file contains the TodoApp class which represents the todo list application.
It handles the GUI and manages the tasks.
'''
from tkinter import Tk, Label, Entry, Button, Listbox, Scrollbar, StringVar, END, SINGLE
class TodoApp:
    def __init__(self):
        self.tasks = []
        self.root = Tk()
        self.root.title("Todo List App")
        self.task_var = StringVar()
        self.task_entry = Entry(self.root, textvariable=self.task_var)
        self.task_entry.pack()
        self.add_button = Button(self.root, text="Add Task", command=self.add_task)
        self.add_button.pack()
        self.task_listbox = Listbox(self.root, selectmode=SINGLE)
        self.task_listbox.pack()
        self.edit_button = Button(self.root, text="Edit Task", command=self.edit_task)
        self.edit_button.pack()
        self.delete_button = Button(self.root, text="Delete Task", command=self.delete_task)
        self.delete_button.pack()
        self.scrollbar = Scrollbar(self.root)
        self.scrollbar.pack(side="right", fill="y")
        self.task_listbox.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.task_listbox.yview)
    def start(self):
        self.root.mainloop()
    def add_task(self):
        task = self.task_var.get()
        if task:
            self.tasks.append(task)
            self.task_listbox.insert(END, task)
            self.task_var.set("")
    def edit_task(self):
        selected_index = self.task_listbox.curselection()
        if selected_index:
            selected_task = self.task_listbox.get(selected_index)
            edited_task = self.task_var.get()
            if edited_task:
                self.tasks[selected_index[0]] = edited_task
                self.task_listbox.delete(selected_index)
                self.task_listbox.insert(selected_index, edited_task)
    def delete_task(self):
        selected_index = self.task_listbox.curselection()
        if selected_index:
            self.tasks.pop(selected_index[0])
            self.task_listbox.delete(selected_index)