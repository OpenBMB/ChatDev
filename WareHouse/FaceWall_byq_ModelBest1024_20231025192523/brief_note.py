import tkinter as tk
from tkinter import simpledialog
import os

class BriefNote(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.note_text = tk.Text(self, height=10, width=30)
        self.note_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # 添加滚动条以支持滚动查看长文本
        scrollbar = tk.Scrollbar(self)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.note_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.note_text.yview)
        
        self.file_listbox = tk.Listbox(self, height=10, width=20)
        self.file_listbox.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        self.load_saved_files()

        self.save_button = tk.Button(self, text="Save", command=self.save_note)
        self.save_button.grid(row=1, column=0, sticky="ew")
        self.open_button = tk.Button(self, text="Open", command=self.open_note)
        self.open_button.grid(row=1, column=1, sticky="ew")
        self.delete_button = tk.Button(self, text="Delete", command=self.delete_note)
        self.delete_button.grid(row=1, column=2, sticky="ew")

    def save_note(self):
        note = self.note_text.get(1.0, tk.END)
        if note.strip():
            file_name = self.get_user_file_name() 
            if file_name:
                file_path = os.path.join(os.path.dirname(__file__), file_name)
                with open(file_path, "w") as file:
                    file.write(note)
                self.note_text.delete(1.0, tk.END)  # 清空文本框内容
                self.load_saved_files()
                print("Note saved as:", file_name)

    def open_note(self):
        selected_file = self.file_listbox.curselection()
        if selected_file:
            file_name = self.file_listbox.get(selected_file)
            file_path = os.path.join(os.path.dirname(__file__), file_name)
            with open(file_path, "r") as file:
                note = file.read()
                self.note_text.delete(1.0, tk.END)
                self.note_text.insert(tk.END, note)

    def load_saved_files(self):
        file_names = [f for f in os.listdir(os.path.dirname(__file__)) if f.endswith(".txt") and (f != "meta.txt" and f != "requirements.txt")]
        self.file_listbox.delete(0, tk.END)
        for file_name in file_names:
            self.file_listbox.insert(tk.END, file_name)

    def get_user_file_name(self):
        user_file_name = tk.simpledialog.askstring("File Name", "Enter a file name (e.g., my_note):")
        if user_file_name:
            return user_file_name + '.txt'

    def delete_note(self):
        selected_file = self.file_listbox.curselection()
        if selected_file:
            file_name = self.file_listbox.get(selected_file)
            file_path = os.path.join(os.path.dirname(__file__), file_name)
            os.remove(file_path)  # 删除文件
            self.load_saved_files()  # 重新加载已保存的文件列表

if __name__ == "__main__":
    root = tk.Tk()
    app = BriefNote(root)
    app.pack()
    root.mainloop()
