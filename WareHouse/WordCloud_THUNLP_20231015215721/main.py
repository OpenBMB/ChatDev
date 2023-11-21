'''
Word Cloud Generator
This program generates a word cloud from user input text.
Author: ChatDev
'''
import tkinter as tk
from tkinter import messagebox, filedialog
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from PIL import ImageTk, Image
class WordCloudGenerator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Word Cloud Generator")
        self.text_entry = tk.Text(self.root, height=10, width=50)
        self.text_entry.pack()
        self.generate_button = tk.Button(self.root, text="Generate Word Cloud", command=self.generate_word_cloud)
        self.generate_button.pack()
        self.canvas = tk.Canvas(self.root, width=400, height=400)
        self.canvas.pack()
        self.root.mainloop()
    def generate_word_cloud(self):
        text = self.text_entry.get("1.0", tk.END)
        if not text.strip():
            messagebox.showerror("Error", "Please enter some text.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png")])
        if not file_path:
            return
        wordcloud = WordCloud().generate(text)
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis("off")
        plt.savefig(file_path)
        plt.close()
        self.update_canvas(file_path)
    def update_canvas(self, image_path):
        image = Image.open(image_path)
        image = image.resize((400, 400), Image.ANTIALIAS)
        self.wordcloud_image = ImageTk.PhotoImage(image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.wordcloud_image)
if __name__ == "__main__":
    WordCloudGenerator()