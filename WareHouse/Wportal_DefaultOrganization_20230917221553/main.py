from tkinter import Tk, filedialog
from docx import Document
from converter import Converter
# Create an instance of the Converter class
converter = Converter()
# Prompt the user to select a PDF file
root = Tk()
root.withdraw()
pdf_file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
# Convert the selected PDF file to DOCX format
converter.convert(pdf_file_path)