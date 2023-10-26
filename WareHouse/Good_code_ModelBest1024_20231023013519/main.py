'''
This is the main file that runs the application. 
When you run this application, a window will open with a button saying "Select Python File". 
Click on this button to select the Python file you want to process. 
The application will add a line of praise at the end of each line of code in the file.
'''
import tkinter as tk
from tkinter import filedialog, messagebox
from file_processor import process_file
def select_file():
    filename = filedialog.askopenfilename(filetypes=[("Python files", "*.py")])
    process_file(filename)
    messagebox.showinfo("Information","Task Completed Successfully")
root = tk.Tk()
button = tk.Button(root, text="Select Python File", command=select_file)
button.pack()
root.mainloop()