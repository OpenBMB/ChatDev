'''
This is the main file that serves as the entry point for the markdown to HTML converter application.
'''
import tkinter as tk
from tkinter import filedialog
from markdown_parser import MarkdownParser
from html_generator import HTMLGenerator
class MarkdownToHTMLConverter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Markdown to HTML Converter")
        self.root.geometry("500x300")
        self.file_path = tk.StringVar()
        self.create_widgets()
    def create_widgets(self):
        label = tk.Label(self.root, text="Select a Markdown file:")
        label.pack()
        file_entry = tk.Entry(self.root, textvariable=self.file_path, width=50)
        file_entry.pack()
        browse_button = tk.Button(self.root, text="Browse", command=self.browse_file)
        browse_button.pack()
        convert_button = tk.Button(self.root, text="Convert", command=self.convert_to_html)
        convert_button.pack()
    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Markdown Files", "*.md")])
        self.file_path.set(file_path)
    def convert_to_html(self):
        markdown_file = self.file_path.get()
        if markdown_file:
            parser = MarkdownParser()
            html_generator = HTMLGenerator()
            with open(markdown_file, 'r',encoding="utf-8") as file:
                markdown_content = file.read()
            parsed_content = parser.parse(markdown_content)
            html_output = html_generator.generate_html(parsed_content)
            save_path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML Files", "*.html")])
            if save_path:
                with open(save_path, 'w') as file:
                    file.write(html_output)
                tk.messagebox.showinfo("Conversion Complete", "Markdown to HTML conversion successful!")
        else:
            tk.messagebox.showerror("Error", "Please select a Markdown file.")
    def run(self):
        self.root.mainloop()
if __name__ == "__main__":
    converter = MarkdownToHTMLConverter()
    converter.run()