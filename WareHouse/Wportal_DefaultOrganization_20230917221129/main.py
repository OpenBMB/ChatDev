import pdf2docx
def convert_pdf_to_docx(pdf_file, docx_file):
    pdf2docx.convert(pdf_file, docx_file)
if __name__ == "__main__":
    pdf_file = "input.pdf"
    docx_file = "output.docx"
    convert_pdf_to_docx(pdf_file, docx_file)