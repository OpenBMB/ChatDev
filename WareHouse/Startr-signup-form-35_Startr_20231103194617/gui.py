'''
This file contains the GUI code using tkinter.
'''
import tkinter as tk
import html_generator
def generate_html():
    '''
    Generates the HTML code and updates the text widget.
    '''
    html_code = html_generator.generate_html()
    text_widget.delete(1.0, tk.END)
    text_widget.insert(tk.END, html_code)
# Create the main window
root = tk.Tk()
root.title("HTML Page Generator")
# Create a text widget to display the generated HTML code
text_widget = tk.Text(root, height=30, width=80)
text_widget.pack()
# Create a button to generate the HTML code
generate_button = tk.Button(root, text="Generate HTML", command=generate_html)
generate_button.pack()
root.mainloop()