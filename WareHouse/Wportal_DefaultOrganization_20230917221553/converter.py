'''
This file contains the Converter class responsible for converting PDF files to DOCX format.
'''
from docx import Document
import os
from PyPDF2 import PdfFileReader
class Converter:
    def convert(self, pdf_file_path):
        docx_file_path = self.get_docx_file_path(pdf_file_path)
        self.convert_pdf_to_docx(pdf_file_path, docx_file_path)
    def get_docx_file_path(self, pdf_file_path):
        pdf_file_name = os.path.basename(pdf_file_path)
        docx_file_name = os.path.splitext(pdf_file_name)[0] + ".docx"
        docx_file_path = os.path.join(os.path.dirname(pdf_file_path), docx_file_name)
        return docx_file_path
    def convert_pdf_to_docx(self, pdf_file_path, docx_file_path):
        pdf_file = open(pdf_file_path, 'rb')
        pdf_reader = PdfFileReader(pdf_file)
        document = Document()
        for page_num in range(pdf_reader.numPages):
            page = pdf_reader.getPage(page_num)
            text = page.extract_text()
            document.add_paragraph(text)
        pdf_file.close()
        document.save(docx_file_path)