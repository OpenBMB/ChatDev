'''
This file contains the function to convert PDF to DOCX using the pdf2docx library.
'''
import pdf2docx
def convert(pdf_file, docx_file):
    pdf2docx.parse(pdf_file, docx_file)