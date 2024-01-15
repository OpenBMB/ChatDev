'''
This file contains the Shape classes which represent the Tetris pieces.
'''
import random
class Shape:
    def __init__(self):
        self.rotation = 0
    def rotate(self):
        self.rotation = (self.rotation + 1) % 4
    def rotate_back(self):
        self.rotation = (self.rotation - 1) % 4
    def move_left(self):
        self.x -= 1
    def move_right(self):
        self.x += 1
    def move_down(self):
        self.y += 1
    def move_up(self):
        self.y -= 1
    def get_coordinates(self):
        pass
    def get_bounding_box(self):
        pass
class ShapeI(Shape):
    def __init__(self):
        super().__init__()
        self.x = 3
        self.y = 0
    def get_coordinates(self):
        if self.rotation == 0 or self.rotation == 2:
            return [(self.x, self.y), (self.x, self.y + 1), (self.x, self.y + 2), (self.x, self.y + 3)]
        else:
            return [(self.x, self.y), (self.x + 1, self.y), (self.x + 2, self.y), (self.x + 3, self.y)]
    def get_bounding_box(self):
        if self.rotation == 0 or self.rotation == 2:
            return (self.x, self.y, self.x, self.y + 3)
        else:
            return (self.x, self.y, self.x + 3, self.y)
class ShapeJ(Shape):
    def __init__(self):
        super().__init__()
        self.x = 3
        self.y = 0
    def get_coordinates(self):
        if self.rotation == 0:
            return [(self.x, self.y), (self.x, self.y + 1), (self.x, self.y + 2), (self.x + 1, self.y + 2)]
        elif self.rotation == 1:
            return [(self.x, self.y), (self.x + 1, self.y), (self.x + 2, self.y), (self.x, self.y + 1)]
        elif self.rotation == 2:
            return [(self.x, self.y), (self.x + 1, self.y), (self.x + 1, self.y + 1), (self.x + 1, self.y + 2)]
        else:
            return [(self.x, self.y + 1), (self.x + 1, self.y + 1), (self.x + 2, self.y + 1), (self.x + 2, self.y)]
    def get_bounding_box(self):
        if self.rotation == 0:
            return (self.x, self.y, self.x + 1, self.y + 2)
        elif self.rotation == 1:
            return (self.x, self.y, self.x + 2, self.y + 1)
        elif self.rotation == 2:
            return (self.x, self.y, self.x + 1, self.y + 2)
        else:
            return (self.x, self.y + 1, self.x + 2, self.y)
class ShapeL(Shape):
    def __init__(self):
        super().__init__()
        self.x = 3
        self.y = 0
    def get_coordinates(self):
        if self.rotation == 0:
            return [(self.x, self.y + 2), (self.x + 1, self.y + 2), (self.x + 2, self.y + 2), (self.x + 2, self.y + 1)]
        elif self.rotation == 1:
            return [(self.x, self.y), (self.x, self.y + 1), (self.x + 1, self.y), (self.x + 2, self.y)]
        elif self.rotation == 2:
            return [(self.x, self.y), (self.x + 1, self.y), (self.x, self.y + 1), (self.x, self.y + 2)]
        else:
            return [(self.x, self.y), (self.x + 1, self.y), (self.x + 2, self.y), (self.x + 2, self.y + 1)]
    def get_bounding_box(self):
        if self.rotation == 0:
            return (self.x, self.y + 1, self.x + 2, self.y + 2)
        elif self.rotation == 1:
            return (self.x, self.y, self.x + 2, self.y + 1)
        elif self.rotation == 2:
            return (self.x, self.y, self.x + 1, self.y + 2)
        else:
            return (self.x, self.y, self.x + 2, self.y + 1)
class ShapeO(Shape):
    def __init__(self):
        super().__init__()
        self.x = 3
        self.y = 0
    def get_coordinates(self):
        return [(self.x, self.y), (self.x + 1, self.y), (self.x, self.y + 1), (self.x + 1, self.y + 1)]
    def get_bounding_box(self):
        return (self.x, self.y, self.x + 1, self.y + 1)
class ShapeS(Shape):
    def __init__(self):
        super().__init__()
        self.x = 3
        self.y = 0
    def get_coordinates(self):
        if self.rotation == 0 or self.rotation == 2:
            return [(self.x + 1, self.y), (self.x + 2, self.y), (self.x, self.y + 1), (self.x + 1, self.y + 1)]
        else:
            return [(self.x, self.y), (self.x, self.y + 1), (self.x + 1, self.y + 1), (self.x + 1, self.y + 2)]
    def get_bounding_box(self):
        if self.rotation == 0 or self.rotation == 2:
            return (self.x, self.y, self.x + 2, self.y + 1)
        else:
            return (self.x, self.y, self.x + 1, self.y + 2)
class ShapeT(Shape):
    def __init__(self):
        super().__init__()
        self.x = 3
        self.y = 0
    def get_coordinates(self):
        if self.rotation == 0:
            return [(self.x, self.y), (self.x + 1, self.y), (self.x + 2, self.y), (self.x + 1, self.y + 1)]
        elif self.rotation == 1:
            return [(self.x + 1, self.y), (self.x, self.y + 1), (self.x + 1, self.y + 1), (self.x + 1, self.y + 2)]
        elif self.rotation == 2:
            return [(self.x, self.y + 1), (self.x + 1, self.y), (self.x + 1, self.y + 1), (self.x + 2, self.y + 1)]
        else:
            return [(self.x, self.y), (self.x, self.y + 1), (self.x, self.y + 2), (self.x + 1, self.y + 1)]
    def get_bounding_box(self):
        if self.rotation == 0:
            return (self.x, self.y, self.x + 2, self.y)
        elif self.rotation == 1:
            return (self.x, self.y, self.x + 1, self.y + 2)
        elif self.rotation == 2:
            return (self.x, self.y + 1, self.x + 2, self.y + 1)
        else:
            return (self.x, self.y, self.x + 1, self.y + 2)
class ShapeZ(Shape):
    def __init__(self):
        super().__init__()
        self.x = 3
        self.y = 0
    def get_coordinates(self):
        if self.rotation == 0 or self.rotation == 2:
            return [(self.x, self.y), (self.x + 1, self.y), (self.x + 1, self.y + 1), (self.x + 2, self.y + 1)]
        else:
            return [(self.x + 1, self.y), (self.x, self.y + 1), (self.x + 1, self.y + 1), (self.x, self.y + 2)]
    def get_bounding_box(self):
        if self.rotation == 0 or self.rotation == 2:
            return (self.x, self.y, self.x + 2, self.y + 1)
        else:
            return (self.x, self.y, self.x + 1, self.y + 2)