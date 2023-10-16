'''
This is the main file that handles the user interface and image processing.
'''
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import background_removal
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Background Removal")
        self.geometry("500x500")
        self.image_label = tk.Label(self)
        self.image_label.pack(pady=10)
        self.upload_button = tk.Button(self, text="Upload Image", command=self.upload_image)
        self.upload_button.pack(pady=10)
        self.remove_button = tk.Button(self, text="Remove Background", command=self.remove_background)
        self.remove_button.pack(pady=10)
        self.save_button = tk.Button(self, text="Save Image", command=self.save_image)
        self.save_button.pack(pady=10)
        self.image = None
        self.processed_image = None
    def upload_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if file_path:
            self.image = Image.open(file_path)
            self.processed_image = self.image.copy()
            self.display_image(self.image)
    def remove_background(self):
        if self.image:
            self.processed_image = background_removal.remove_background(self.image)
            self.display_image(self.processed_image)
    def save_image(self):
        if self.processed_image:
            file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Files", "*.png"), ("JPEG Files", "*.jpg *.jpeg")])
            if file_path:
                self.processed_image.save(file_path)
    def display_image(self, image):
        image.thumbnail((400, 400))
        photo = ImageTk.PhotoImage(image)
        self.image_label.configure(image=photo)
        self.image_label.image = photo
if __name__ == "__main__":
    app = Application()
    app.mainloop()