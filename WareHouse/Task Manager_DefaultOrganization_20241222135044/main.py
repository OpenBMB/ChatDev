from tkinter import Tk, Frame, Entry, Button, Label
class ToDoApp:
    def __init__(self):
        self.tasks = []
        self.root = Tk()
        self.root.title("Simple To-Do App")
        self.todo_frame = Frame(self.root, bg="#fff", bd=1, relief="solid")
        self.todo_frame.pack(padx=10, pady=10)
        self.completed_frame = Frame(self.root, bg="#fff", bd=1, relief="solid")
        self.completed_frame.pack(padx=10, pady=10)
        self.add_task_entry = Entry(self.root, width=30)
        self.add_task_entry.pack(padx=10, pady=10)
        self.add_task_button = Button(self.root, text="ADD", command=self.add_task)
        self.add_task_button.pack(padx=10, pady=10)
        self.root.mainloop()
    def add_task(self):
        task_text = self.add_task_entry.get()
        if task_text:
            self.tasks.append(task_text)
            self.add_task_entry.delete(0, "end")
            self.display_tasks()
    def display_tasks(self):
        self.clear_frames()
        for i, task in enumerate(self.tasks):
            task_frame = Frame(self.todo_frame)
            task_frame.pack(pady=5)
            task_label = Label(task_frame, text=task)
            task_label.pack(side="left")
            complete_button = Button(task_frame, text="Complete", command=lambda i=i: self.mark_completed(i))
            complete_button.pack(side="left")
            delete_button = Button(task_frame, text="Delete", command=lambda i=i: self.delete_task(i))
            delete_button.pack(side="left")
    def mark_completed(self, index):
        task = self.tasks.pop(index)
        self.completed_frame.configure(bg="#fff", bd=1, relief="solid")
        task_frame = Frame(self.completed_frame)
        task_frame.pack(pady=5)
        task_label = Label(task_frame, text=task)
        task_label.pack(side="left")
        delete_button = Button(task_frame, text="Delete", command=lambda: self.delete_completed_task(task_frame))
        delete_button.pack(side="left")
    def delete_task(self, index):
        self.tasks.pop(index)
        self.display_tasks()
    def delete_completed_task(self, task_frame):
        task_frame.destroy()
    def clear_frames(self):
        for widget in self.todo_frame.winfo_children():
            widget.destroy()
        for widget in self.completed_frame.winfo_children():
            widget.destroy()
if __name__ == "__main__":
    app = ToDoApp()