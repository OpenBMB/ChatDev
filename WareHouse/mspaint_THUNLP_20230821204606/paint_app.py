'''
This file contains the PaintApp class which represents the MS Paint application.
'''
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
class PaintApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MS Paint")
        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="white")
        self.canvas.pack()
        self.current_tool = "pencil"
        self.current_color = "black"
        self.shapes = []
        self.create_menu()
        self.create_toolbar()
        self.canvas.bind("<Button-1>", self.start_drawing)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drawing)
    def run(self):
        self.root.mainloop()
    def create_menu(self):
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menu_bar)
    def create_toolbar(self):
        toolbar = tk.Frame(self.root)
        pencil_button = tk.Button(toolbar, text="Pencil", command=self.set_pencil_tool)
        pencil_button.pack(side=tk.LEFT)
        brush_button = tk.Button(toolbar, text="Brush", command=self.set_brush_tool)
        brush_button.pack(side=tk.LEFT)
        shape_button = tk.Button(toolbar, text="Shape", command=self.set_shape_tool)
        shape_button.pack(side=tk.LEFT)
        color_label = tk.Label(toolbar, text="Color:")
        color_label.pack(side=tk.LEFT)
        color_button = tk.Button(toolbar, text="Select Color", command=self.select_color)
        color_button.pack(side=tk.LEFT)
        toolbar.pack(side=tk.TOP, fill=tk.X)
    def set_pencil_tool(self):
        self.current_tool = "pencil"
    def set_brush_tool(self):
        self.current_tool = "brush"
    def set_shape_tool(self):
        self.current_tool = "shape"
    def select_color(self):
        self.current_color = tk.colorchooser.askcolor()[1]
    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if file_path:
            # Logic to open and display the image
            pass
    def save_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if file_path:
            # Logic to save the canvas as an image
            pass
    def draw(self, event):
        if self.current_tool == "pencil":
            self.canvas.create_line(event.x, event.y, event.x + 1, event.y + 1, fill=self.current_color, width=1)
        elif self.current_tool == "brush":
            self.canvas.create_oval(event.x - 5, event.y - 5, event.x + 5, event.y + 5, fill=self.current_color, outline=self.current_color)
        elif self.current_tool == "shape":
            self.canvas.create_rectangle(event.x, event.y, event.x + 50, event.y + 50, fill=self.current_color, outline=self.current_color)
    def start_drawing(self, event):
        self.canvas.bind("<B1-Motion>", self.draw)
    def stop_drawing(self, event):
        self.canvas.unbind("<B1-Motion>")
    def clear_canvas(self):
        self.canvas.delete("all")
        self.shapes = []
    def show_error_message(self, message):
        messagebox.showerror("Error", message)