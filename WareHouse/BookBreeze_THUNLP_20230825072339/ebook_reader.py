'''
This file contains the EbookReader class which represents the e-book reader application.
'''
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import PyPDF2
import ebooklib
from ebooklib import epub
import mobi
class EbookReader:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("E-book Reader")
        self.root.geometry("800x600")
        self.current_book = None
        self.bookmarks = []
        self.create_menu()
        self.create_book_display()
        self.create_bookmarks_panel()
    def create_menu(self):
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_book)
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menu_bar)
    def create_book_display(self):
        self.book_display = tk.Text(self.root, wrap=tk.WORD)
        self.book_display.pack(fill=tk.BOTH, expand=True)
    def create_bookmarks_panel(self):
        self.bookmarks_panel = tk.Frame(self.root)
        self.bookmarks_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.bookmarks_label = tk.Label(self.bookmarks_panel, text="Bookmarks")
        self.bookmarks_label.pack()
        self.bookmarks_listbox = tk.Listbox(self.bookmarks_panel)
        self.bookmarks_listbox.pack(fill=tk.BOTH, expand=True)
        self.add_bookmark_button = tk.Button(self.bookmarks_panel, text="Add Bookmark", command=self.add_bookmark)
        self.add_bookmark_button.pack()
        self.remove_bookmark_button = tk.Button(self.bookmarks_panel, text="Remove Bookmark", command=self.remove_bookmark)
        self.remove_bookmark_button.pack()
    def open_book(self):
        filetypes = [("PDF Files", "*.pdf"), ("EPUB Files", "*.epub"), ("MOBI Files", "*.mobi")]
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            self.current_book = filepath
            self.book_display.delete(1.0, tk.END)
            self.book_display.insert(tk.END, f"Opening book: {filepath}")
            if filepath.endswith(".pdf"):
                pdf_file = open(filepath, "rb")
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                num_pages = len(pdf_reader.pages)
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    self.book_display.insert(tk.END, page.extract_text())
                pdf_file.close()
            elif filepath.endswith(".epub"):
                book = epub.read_epub(filepath)
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        self.book_display.insert(tk.END, item.get_content())
            elif filepath.endswith(".mobi"):
                mobi_book = mobi.open(filepath)
                for i in range(mobi_book.num_pages):
                    self.book_display.insert(tk.END, mobi_book.read_page(i))
        else:
            messagebox.showinfo("No File Selected", "No e-book file selected.")
    def add_bookmark(self):
        if self.current_book:
            bookmark = self.book_display.index(tk.INSERT)
            self.bookmarks.append(bookmark)
            self.bookmarks_listbox.insert(tk.END, f"Bookmark {len(self.bookmarks)}")
    def remove_bookmark(self):
        selected_index = self.bookmarks_listbox.curselection()
        if selected_index:
            bookmark_index = selected_index[0]
            self.bookmarks.pop(bookmark_index)
            self.bookmarks_listbox.delete(selected_index)
    def start(self):
        self.root.mainloop()