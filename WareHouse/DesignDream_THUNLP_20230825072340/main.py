'''
This is the main file of the virtual interior design application. It provides the entry point for the application and handles the user interface.
'''
import tkinter as tk
from room import Room
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Virtual Interior Design Application")
        self.geometry("800x600")
        self.room = Room()
        self.create_menu()
        self.create_toolbar()
        self.create_canvas()
    def create_menu(self):
        # Create menu bar and menus
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save", command=self.save_design)
        file_menu.add_command(label="Load", command=self.load_design)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        edit_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.undo)
        edit_menu.add_command(label="Redo", command=self.redo)
    def create_toolbar(self):
        # Create toolbar with furniture options
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        # Add furniture buttons to the toolbar
        button1 = tk.Button(toolbar, text="Chair", command=self.add_chair)
        button1.pack(side=tk.LEFT)
        button2 = tk.Button(toolbar, text="Table", command=self.add_table)
        button2.pack(side=tk.LEFT)
        # Add more furniture buttons as needed
    def create_canvas(self):
        # Create canvas to display the room
        self.canvas = tk.Canvas(self)
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Bind mouse events to canvas
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
    def add_chair(self):
        # Add a chair to the room
        self.room.add_furniture("chair")
        self.update_canvas()
    def add_table(self):
        # Add a table to the room
        self.room.add_furniture("table")
        self.update_canvas()
    def update_canvas(self):
        # Clear canvas and redraw room and furniture
        self.canvas.delete("all")
        self.room.draw(self.canvas)
    def on_canvas_click(self, event):
        # Handle click event on canvas
        self.room.select_furniture(event.x, event.y)
    def on_canvas_drag(self, event):
        # Handle drag event on canvas
        self.room.move_selected_furniture(event.x, event.y)
        self.update_canvas()
    def save_design(self):
        # Save the current room design
        self.room.save_design()
    def load_design(self):
        # Load a saved room design
        self.room.load_design()
        self.update_canvas()
    def undo(self):
        # Undo the last action
        self.room.undo()
        self.update_canvas()
    def redo(self):
        # Redo the last undone action
        self.room.redo()
        self.update_canvas()
if __name__ == "__main__":
    app = Application()
    app.mainloop()