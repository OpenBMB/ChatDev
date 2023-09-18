from tkinter import filedialog
def save_file(self):
    file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
    if file_path:
        with open(file_path, 'w') as file:
            file.write(self.text_area.get('1.0', 'end-1c'))