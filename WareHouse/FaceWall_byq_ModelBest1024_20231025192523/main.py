'''
FaceWall - Memo Software for Company Employees
This is the main file of the FaceWall software. It initializes the application and sets up the graphical user interface.
'''
import tkinter as tk
from task_list import TaskList
from brief_note import BriefNote
class FaceWallApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FaceWall")
        self.task_list = TaskList(root)
        self.brief_note = BriefNote(root)
        self.task_list.pack()
        self.brief_note.pack()
if __name__ == "__main__":
    root = tk.Tk()
    app = FaceWallApp(root)
    root.mainloop()