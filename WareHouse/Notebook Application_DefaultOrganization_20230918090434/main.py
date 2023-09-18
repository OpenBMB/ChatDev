'''
This is the main file of the Notebook Desktop application.
'''
from tkinter import Tk, Menu, Text, Scrollbar, messagebox, filedialog
class NotebookApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Notebook App")
        self.text_area = Text(self.root, undo=True)
        self.text_area.pack(fill='both', expand=True)
        self.scrollbar = Scrollbar(self.text_area)
        self.scrollbar.pack(side='right', fill='y')
        self.text_area.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.text_area.yview)
        self.create_menu()
    def create_menu(self):
        menu_bar = Menu(self.root)
        file_menu = Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_app)
        menu_bar.add_cascade(label="File", menu=file_menu)
        edit_menu = Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.text_area.edit_undo)
        edit_menu.add_command(label="Redo", command=self.text_area.edit_redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self.cut_text)
        edit_menu.add_command(label="Copy", command=self.copy_text)
        edit_menu.add_command(label="Paste", command=self.paste_text)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)
        format_menu = Menu(menu_bar, tearoff=0)
        format_menu.add_command(label="Bold", command=self.bold_text)
        format_menu.add_command(label="Italic", command=self.italic_text)
        menu_bar.add_cascade(label="Format", menu=format_menu)
        self.root.config(menu=menu_bar)
    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if file_path:
            with open(file_path, 'r') as file:
                self.text_area.delete('1.0', 'end')
                self.text_area.insert('1.0', file.read())
    def save_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if file_path:
            with open(file_path, 'w') as file:
                file.write(self.text_area.get('1.0', 'end-1c'))
    def exit_app(self):
        if messagebox.askokcancel("Exit", "Are you sure you want to exit?"):
            self.root.destroy()
    def cut_text(self):
        self.text_area.event_generate("<<Cut>>")
    def copy_text(self):
        self.text_area.event_generate("<<Copy>>")
    def paste_text(self):
        self.text_area.event_generate("<<Paste>>")
    def bold_text(self):
        current_tags = self.text_area.tag_names("sel.first")
        if "bold" in current_tags:
            self.text_area.tag_remove("bold", "sel.first", "sel.last")
        else:
            self.text_area.tag_add("bold", "sel.first", "sel.last")
            self.text_area.tag_configure("bold", font=("TkDefaultFont", 12, "bold"))
    def italic_text(self):
        current_tags = self.text_area.tag_names("sel.first")
        if "italic" in current_tags:
            self.text_area.tag_remove("italic", "sel.first", "sel.last")
        else:
            self.text_area.tag_add("italic", "sel.first", "sel.last")
            self.text_area.tag_configure("italic", font=("TkDefaultFont", 12, "italic"))
if __name__ == "__main__":
    root = Tk()
    app = NotebookApp(root)
    root.mainloop()