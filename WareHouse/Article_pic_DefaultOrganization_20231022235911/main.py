'''
This is the main file that will be executed to run the tool.
'''
import tkinter as tk
from article import Article
from image_finder import ImageFinder
class ToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Article Tool")
        self.article = Article()
        self.image_finder = ImageFinder()
        self.create_widgets()
    def create_widgets(self):
        # Create input text box for the article
        self.article_text = tk.Text(self.root, height=10, width=50)
        self.article_text.pack()
        # Create button to find and assign image
        self.find_image_button = tk.Button(self.root, text="Find Image", command=self.find_and_assign_image)
        self.find_image_button.pack()
        # Create button to generate markdown layout
        self.generate_layout_button = tk.Button(self.root, text="Generate Layout", command=self.generate_layout)
        self.generate_layout_button.pack()
    def find_and_assign_image(self):
        article_text = self.article_text.get("1.0", tk.END)
        image_url = self.image_finder.find_image(article_text)
        self.article.assign_image(image_url)
    def generate_layout(self):
        article_text = self.article_text.get("1.0", tk.END)
        layout = self.article.generate_layout(article_text)
        # Display layout in a new window or save it to a file
if __name__ == "__main__":
    root = tk.Tk()
    tool_gui = ToolGUI(root)
    root.mainloop()