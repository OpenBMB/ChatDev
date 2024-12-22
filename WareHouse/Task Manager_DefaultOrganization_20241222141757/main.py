import tkinter as tk
from task_manager import TaskManager
class TaskManagerApp:
    def __init__(self, root):
        self.root = root
        self.task_manager = TaskManager()
        self.root.title("Task Manager")
        self.task_entry = tk.Entry(self.root)
        self.task_entry.pack()
        self.add_button = tk.Button(self.root, text="Add Task", command=self.add_task)
        self.add_button.pack()
        self.task_listbox = tk.Listbox(self.root)
        self.task_listbox.pack()
        self.edit_button = tk.Button(self.root, text="Edit Task", command=self.edit_task)
        self.edit_button.pack()
        self.delete_button = tk.Button(self.root, text="Delete Task", command=self.delete_task)
        self.delete_button.pack()
        self.completed_button = tk.Button(self.root, text="Completed", command=self.complete_task)
        self.completed_button.pack()
        self.completed_label = tk.Label(self.root, text="Completed Tasks")
        self.completed_label.pack()
        self.completed_listbox = tk.Listbox(self.root)
        self.completed_listbox.pack()
        self.load_tasks()
    def load_tasks(self):
        tasks = self.task_manager.get_tasks()
        self.task_listbox.delete(0, tk.END)
        self.completed_listbox.delete(0, tk.END)
        for task in tasks:
            if task["completed"]:
                self.completed_listbox.insert(tk.END, task["name"])
            else:
                self.task_listbox.insert(tk.END, task["name"])
    def add_task(self):
        task_name = self.task_entry.get()
        if task_name:
            self.task_manager.add_task(task_name)
            self.task_entry.delete(0, tk.END)
            self.load_tasks()
    def edit_task(self):
        selected_task = self.task_listbox.curselection()
        if selected_task:
            task_name = self.task_entry.get()
            if task_name:
                self.task_manager.edit_task(selected_task[0], task_name)
                self.task_entry.delete(0, tk.END)
                self.load_tasks()
    def delete_task(self):
        selected_task = self.task_listbox.curselection()
        if selected_task:
            self.task_manager.delete_task(selected_task[0])
            self.load_tasks()
    def complete_task(self):
        selected_task = self.task_listbox.curselection()
        if selected_task:
            if not self.task_manager.is_task_completed(selected_task[0]):
                self.task_manager.complete_task(selected_task[0])
                self.load_tasks()
root = tk.Tk()
app = TaskManagerApp(root)
root.mainloop()