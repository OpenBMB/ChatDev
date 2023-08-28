'''
This is the main file for the image editor software.
'''
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageEnhance
import os as os_module
class ImageEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Editor")
        self.current_image = None
        self.original_image = None
        self.undo_stack = []
        self.redo_stack = []
        self.create_menu()
        self.create_toolbar()
        self.create_canvas()
    def create_menu(self):
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_image)
        file_menu.add_command(label="Save", command=self.save_image)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.undo)
        edit_menu.add_command(label="Redo", command=self.redo)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)
        self.root.config(menu=menu_bar)
    def create_toolbar(self):
        toolbar = tk.Frame(self.root)
        crop_button = tk.Button(toolbar, text="Crop", command=self.crop_image)
        crop_button.pack(side=tk.LEFT, padx=5, pady=5)
        resize_button = tk.Button(toolbar, text="Resize", command=self.resize_image)
        resize_button.pack(side=tk.LEFT, padx=5, pady=5)
        rotate_button = tk.Button(toolbar, text="Rotate", command=self.rotate_image)
        rotate_button.pack(side=tk.LEFT, padx=5, pady=5)
        flip_button = tk.Button(toolbar, text="Flip", command=self.flip_image)
        flip_button.pack(side=tk.LEFT, padx=5, pady=5)
        brightness_button = tk.Button(toolbar, text="Brightness", command=self.adjust_brightness)
        brightness_button.pack(side=tk.LEFT, padx=5, pady=5)
        contrast_button = tk.Button(toolbar, text="Contrast", command=self.adjust_contrast)
        contrast_button.pack(side=tk.LEFT, padx=5, pady=5)
        saturation_button = tk.Button(toolbar, text="Saturation", command=self.adjust_saturation)
        saturation_button.pack(side=tk.LEFT, padx=5, pady=5)
        hue_button = tk.Button(toolbar, text="Hue", command=self.adjust_hue)
        hue_button.pack(side=tk.LEFT, padx=5, pady=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)
    def create_canvas(self):
        self.canvas = tk.Canvas(self.root)
        self.canvas.pack(fill=tk.BOTH, expand=True)
    def open_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg;*.jpeg;*.png;*.gif")])
        if file_path:
            self.current_image = Image.open(file_path)
            self.original_image = self.current_image.copy()
            self.display_image()
    def save_image(self):
        if self.current_image:
            file_path = filedialog.asksaveasfilename(defaultextension=".jpg",
                                                     filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("GIF", "*.gif")])
            if file_path:
                self.current_image.save(file_path)
    def display_image(self):
        if self.current_image:
            self.canvas.delete("all")
            image_width, image_height = self.current_image.size
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            if image_width > canvas_width or image_height > canvas_height:
                image_ratio = image_width / image_height
                canvas_ratio = canvas_width / canvas_height
                if image_ratio > canvas_ratio:
                    new_width = canvas_width
                    new_height = int(canvas_width / image_ratio)
                else:
                    new_width = int(canvas_height * image_ratio)
                    new_height = canvas_height
                self.current_image = self.current_image.resize((new_width, new_height), Image.ANTIALIAS)
            self.image_tk = ImageTk.PhotoImage(self.current_image)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_tk)
    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.current_image)
            self.current_image = self.undo_stack.pop()
            self.display_image()
    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.current_image)
            self.current_image = self.redo_stack.pop()
            self.display_image()
    def crop_image(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            self.current_image = self.current_image.crop((100, 100, 300, 300))
            self.display_image()
    def resize_image(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            self.current_image = self.current_image.resize((500, 500))
            self.display_image()
    def rotate_image(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            self.current_image = self.current_image.rotate(90)
            self.display_image()
    def flip_image(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            self.current_image = self.current_image.transpose(Image.FLIP_LEFT_RIGHT)
            self.display_image()
    def adjust_brightness(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            enhancer = ImageEnhance.Brightness(self.current_image)
            self.current_image = enhancer.enhance(1.5)  # Increase brightness by a factor of 1.5
            self.display_image()
    def adjust_contrast(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            enhancer = ImageEnhance.Contrast(self.current_image)
            self.current_image = enhancer.enhance(1.5)  # Increase contrast by a factor of 1.5
            self.display_image()
    def adjust_saturation(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            enhancer = ImageEnhance.Color(self.current_image)
            self.current_image = enhancer.enhance(1.5)  # Increase saturation by a factor of 1.5
            self.display_image()
    def adjust_hue(self):
        if self.current_image:
            self.undo_stack.append(self.current_image)
            enhancer = ImageEnhance.Color(self.current_image)
            self.current_image = enhancer.enhance(0.5)  # Reduce hue by a factor of 0.5
            self.display_image()
if __name__ == "__main__":
    root = tk.Tk()
    image_editor = ImageEditor(root)
    root.mainloop()