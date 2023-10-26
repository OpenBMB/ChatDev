'''
Design a software that allows users to input several strings. Then the user randomly chooses one.
'''
from tkinter import Tk, Label, Entry, Button
import random
# Create a Tkinter window
window = Tk()
window.title("String Chooser")
# Create a label to prompt the user for input
label = Label(window, text="Enter strings (separated by commas):")
label.pack()
# Create an entry field for the user to input strings
entry = Entry(window)
entry.pack()
# Create a button to trigger the random selection
def choose_string():
    strings = entry.get().split(",")
    chosen_string = random.choice(strings)
    result_label.config(text=f"Randomly chosen string: {chosen_string}")
button = Button(window, text="Choose", command=choose_string)
button.pack()
# Create a label to display the randomly chosen string
result_label = Label(window, text="")
result_label.pack()
# Run the Tkinter event loop
window.mainloop()