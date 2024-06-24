'''
Main file for the Pixel Art Creator application.
Contains the PixelArtApp class and application entry point.
'''
import tkinter as tk
from tkinter import filedialog
from color_palette import ColorPalette
from PIL import Image, ImageDraw
class PixelArtApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Pixel Art Creator")
        self.pixel_size = 20
        self.canvas_width = 400
        self.canvas_height = 400
        self.color_palette = ColorPalette()
        self.current_tool = "draw"
        self.undo_stack = []
        self.create_widgets()
    def create_widgets(self):
        self.canvas = tk.Canvas(self.master, width=self.canvas_width, height=self.canvas_height, bg="white")
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)
        self.canvas.bind("<B1-Motion>", self.use_tool)
        self.canvas.bind("<Button-1>", self.use_tool)
        self.setup_canvas()
        control_frame = tk.Frame(self.master)
        control_frame.pack(side=tk.RIGHT, padx=10, pady=10)
        color_label = tk.Label(control_frame, text="Select Color:")
        color_label.pack()
        for color in self.color_palette.colors:
            color_button = tk.Button(control_frame, bg=color, width=2, command=lambda c=color: self.change_color(c))
            color_button.pack(side=tk.LEFT, padx=2, pady=2)
        tool_frame = tk.Frame(control_frame)
        tool_frame.pack(pady=5)
        draw_button = tk.Button(tool_frame, text="Draw", command=lambda: self.set_tool("draw"))
        draw_button.pack(side=tk.LEFT, padx=2)
        eraser_button = tk.Button(tool_frame, text="Eraser", command=lambda: self.set_tool("erase"))
        eraser_button.pack(side=tk.LEFT, padx=2)
        undo_button = tk.Button(control_frame, text="Undo", command=self.undo)
        undo_button.pack(pady=5)
        clear_button = tk.Button(control_frame, text="Clear Canvas", command=self.clear_canvas)
        clear_button.pack(pady=5)
        export_button = tk.Button(control_frame, text="Export Image", command=self.export_image)
        export_button.pack(pady=5)
    def setup_canvas(self):
        for i in range(0, self.canvas_width, self.pixel_size):
            for j in range(0, self.canvas_height, self.pixel_size):
                self.canvas.create_rectangle(i, j, i+self.pixel_size, j+self.pixel_size, outline="gray", fill="white")
    def use_tool(self, event):
        x = event.x - (event.x % self.pixel_size)
        y = event.y - (event.y % self.pixel_size)
        item = self.canvas.find_closest(x, y)[0]
        old_color = self.canvas.itemcget(item, "fill")
        new_color = self.color_palette.get_color() if self.current_tool == "draw" else "white"
        if old_color != new_color:
            self.undo_stack.append((item, old_color))
            self.canvas.itemconfig(item, fill=new_color)
    def change_color(self, color):
        self.color_palette.set_color(color)
        self.current_tool = "draw"
    def set_tool(self, tool):
        self.current_tool = tool
    def undo(self):
        if self.undo_stack:
            item, color = self.undo_stack.pop()
            self.canvas.itemconfig(item, fill=color)
    def clear_canvas(self):
        self.canvas.delete("all")
        self.setup_canvas()
        self.undo_stack.clear()
    def export_image(self):
        filename = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png")])
        if filename:
            image = Image.new("RGB", (self.canvas_width, self.canvas_height), "white")
            draw = ImageDraw.Draw(image)
            for i in range(0, self.canvas_width, self.pixel_size):
                for j in range(0, self.canvas_height, self.pixel_size):
                    item = self.canvas.find_closest(i, j)
                    color = self.canvas.itemcget(item, "fill")
                    if color != "white":
                        draw.rectangle([i, j, i+self.pixel_size, j+self.pixel_size], fill=color, outline=color)
            image.save(filename)
if __name__ == "__main__":
    root = tk.Tk()
    app = PixelArtApp(root)
    root.mainloop()