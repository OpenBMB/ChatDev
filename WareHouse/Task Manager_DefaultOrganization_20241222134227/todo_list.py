class TodoList:
    def __init__(self):
        self.tasks = []
    def get_tasks(self):
        return self.tasks
    def add_task(self, task):
        self.tasks.append(task)
    def mark_complete(self, task):
        if task in self.tasks:
            self.tasks.remove(task)
    def edit_task(self, old_task, new_task):
        if old_task in self.tasks:
            index = self.tasks.index(old_task)
            self.tasks[index] = new_task
    def delete_task(self, task):
        if task in self.tasks:
            self.tasks.remove(task)