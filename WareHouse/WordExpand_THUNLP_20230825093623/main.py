'''
This is the main file of the vocabulary builder app.
'''
import tkinter as tk
from tkinter import messagebox
from vocabulary import Vocabulary
class VocabularyApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Vocabulary Builder")
        self.vocabulary = Vocabulary()
        self.word_label = tk.Label(self.root, text="Word:")
        self.word_label.pack()
        self.word_entry = tk.Entry(self.root)
        self.word_entry.pack()
        self.synonyms_label = tk.Label(self.root, text="Synonyms:")
        self.synonyms_label.pack()
        self.synonyms_text = tk.Text(self.root, height=5, width=30)
        self.synonyms_text.pack()
        self.antonyms_label = tk.Label(self.root, text="Antonyms:")
        self.antonyms_label.pack()
        self.antonyms_text = tk.Text(self.root, height=5, width=30)
        self.antonyms_text.pack()
        self.examples_label = tk.Label(self.root, text="Usage Examples:")
        self.examples_label.pack()
        self.examples_text = tk.Text(self.root, height=5, width=30)
        self.examples_text.pack()
        self.search_button = tk.Button(self.root, text="Search", command=self.search_word)
        self.search_button.pack()
        self.root.mainloop()
    def search_word(self):
        word = self.word_entry.get()
        synonyms, antonyms, examples = self.vocabulary.search(word)
        if not any([synonyms, antonyms, examples]):
            messagebox.showinfo("Word Not Found", "The word was not found in the vocabulary.")
        else:
            self.synonyms_text.delete(1.0, tk.END)
            self.synonyms_text.insert(tk.END, "\n".join(synonyms))
            self.antonyms_text.delete(1.0, tk.END)
            self.antonyms_text.insert(tk.END, "\n".join(antonyms))
            self.examples_text.delete(1.0, tk.END)
            self.examples_text.insert(tk.END, "\n".join(examples))
if __name__ == "__main__":
    app = VocabularyApp()