'''
Color palette module for the Pixel Art Creator application.
Contains the ColorPalette class to manage color selection.
'''
class ColorPalette:
    def __init__(self):
        self.colors = ["black", "white", "red", "green", "blue", "yellow", "orange", "purple", "pink", "brown"]
        self.current_color = "black"
    def get_color(self):
        return self.current_color
    def set_color(self, color):
        if color in self.colors:
            self.current_color = color