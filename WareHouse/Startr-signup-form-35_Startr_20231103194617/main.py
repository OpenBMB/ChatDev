'''
This is the main file to generate the HTML page and launch the GUI.
'''
import tkinter as tk
import html_generator
# Generate the HTML code
html_code = html_generator.generate_html()
# Launch the GUI
root = tk.Tk()
root.title("HTML Page Generator")
# Create a text widget to display the generated HTML code
text_widget = tk.Text(root, height=30, width=80)
text_widget.insert(tk.END, html_code)
text_widget.pack()
root.mainloop()