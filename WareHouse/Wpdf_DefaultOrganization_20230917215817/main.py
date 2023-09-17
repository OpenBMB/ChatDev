'''
This is the main file of the PDF to DOCX converter software.
'''
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from converter import Converter
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF to DOCX Converter")
        self.geometry("400x200")
        self.file_path = None
        self.converter = Converter()
        self.select_button = tk.Button(self, text="Select PDF", command=self.select_pdf)
        self.select_button.pack(pady=20)
        self.convert_button = tk.Button(self, text="Convert", command=self.convert_pdf_to_docx)
        self.convert_button.pack(pady=10)
    def select_pdf(self):
        """
        Opens a file dialog to select a PDF file.
        """
        self.file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
    def convert_pdf_to_docx(self):
        """
        Converts the selected PDF file to DOCX format using the Converter class.
        """
        if self.file_path:
            self.converter.convert(self.file_path)
            messagebox.showinfo("Conversion Complete", "PDF converted to DOCX successfully!")
        else:
            messagebox.showerror("Error", "Please select a PDF file.")
if __name__ == "__main__":
    app = Application()
    app.mainloop()