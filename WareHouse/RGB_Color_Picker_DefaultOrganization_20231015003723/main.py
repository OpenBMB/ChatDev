'''
This is the main file of the RGB color picker application.
It imports the ColorPickerGUI class from the gui.py file and initializes the GUI.
'''
from gui import ColorPickerGUI
if __name__ == "__main__":
    # Create an instance of the ColorPickerGUI class
    color_picker = ColorPickerGUI()
    # Start the GUI
    color_picker.start()