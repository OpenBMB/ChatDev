import tkinter as tk
import webbrowser
from html_generator import generate_html
class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title("Signup Form")
        self.pack()
        self.create_widgets()
    def create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        # Generate HTML code
        html_code = generate_html()
        # Create a web browser widget to display the HTML page
        browser = tk.Text(self)
        browser.insert(tk.END, html_code)
        browser.configure(state='disabled')
        browser.grid(row=0, column=0, columnspan=3, sticky="nsew")
        # Signup button
        signup_button = tk.Button(self, text="Signup", command=self.open_signup_page)
        signup_button.grid(row=1, column=1, pady=10)
    def open_signup_page(self):
        webbrowser.open_new_tab("signup.html")