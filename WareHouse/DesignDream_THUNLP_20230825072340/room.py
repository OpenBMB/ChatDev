'''
This file defines the Room class, which represents a virtual room in the interior design application.
'''
class Room:
    def __init__(self):
        self.furniture = []
        self.selected_furniture = None
        self.undo_stack = []
        self.redo_stack = []
    def add_furniture(self, furniture_type):
        # Add a furniture item to the room
        furniture = Furniture(furniture_type)
        self.furniture.append(furniture)
        self.selected_furniture = furniture
    def select_furniture(self, x, y):
        # Select a furniture item based on the given coordinates
        for furniture in self.furniture:
            if furniture.contains_point(x, y):
                self.selected_furniture = furniture
                break
    def move_selected_furniture(self, x, y):
        # Move the selected furniture item to the given coordinates
        if self.selected_furniture is not None:
            self.selected_furniture.move(x, y)
    def draw(self, canvas):
        # Draw the room and furniture on the canvas
        # Draw room walls, floor, etc.
        canvas.create_rectangle(0, 0, 800, 600, fill="white")
        for furniture in self.furniture:
            furniture.draw(canvas)
    def save_design(self):
        # Save the current room design to a file
        # Serialize the room object and write to a file
        with open("design.txt", "w") as file:
            for furniture in self.furniture:
                file.write(furniture.type + "," + str(furniture.x) + "," + str(furniture.y) + "\n")
    def load_design(self):
        # Load a saved room design from a file
        # Read the serialized room object from a file and deserialize
        self.furniture = []
        with open("design.txt", "r") as file:
            for line in file:
                furniture_data = line.strip().split(",")
                furniture_type = furniture_data[0]
                furniture_x = int(furniture_data[1])
                furniture_y = int(furniture_data[2])
                furniture = Furniture(furniture_type, furniture_x, furniture_y)
                self.furniture.append(furniture)
    def undo(self):
        # Undo the last action
        if len(self.undo_stack) > 0:
            action = self.undo_stack.pop()
            action.undo()
            self.redo_stack.append(action)
    def redo(self):
        # Redo the last undone action
        if len(self.redo_stack) > 0:
            action = self.redo_stack.pop()
            action.redo()
class Furniture:
    def __init__(self, furniture_type, x=0, y=0):
        self.type = furniture_type
        self.x = x
        self.y = y
    def contains_point(self, x, y):
        # Check if the furniture item contains the given point
        # Use dimensions and position to determine containment
        return self.x <= x <= self.x + 50 and self.y <= y <= self.y + 50
    def move(self, x, y):
        # Move the furniture item to the given coordinates
        self.x = x
        self.y = y
    def draw(self, canvas):
        # Draw the furniture item on the canvas
        if self.type == "chair":
            canvas.create_rectangle(self.x, self.y, self.x + 50, self.y + 50, fill="brown")
        elif self.type == "table":
            canvas.create_rectangle(self.x, self.y, self.x + 100, self.y + 100, fill="gray")
class Action:
    def __init__(self):
        pass
    def undo(self):
        pass
    def redo(self):
        pass