import json
import tkinter as tk
from tkinter import messagebox
from project_evaluator import ProjectEvaluator
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Project Evaluator")
        self.geometry("400x200")
        self.evaluator = ProjectEvaluator()
        self.create_widgets()
    def create_widgets(self):
        self.label = tk.Label(self, text="Enter README.md file path:")
        self.label.pack()
        self.entry = tk.Entry(self)
        self.entry.pack()
        self.button = tk.Button(self, text="Evaluate", command=self.evaluate_project)
        self.button.pack()
    def evaluate_project(self):
        readme_file = self.entry.get()
        scores_dict = self.evaluator.evaluate_project(readme_file)
        scores_dict_str = json.dumps(scores_dict, indent=4, ensure_ascii=False)
        result = f"Project score:\n{scores_dict_str}"
        messagebox.showinfo("Evaluation Result", result)
if __name__ == "__main__":
    app = Application()
    app.mainloop()
