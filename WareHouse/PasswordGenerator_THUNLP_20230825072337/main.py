'''
This is the main file for the random password generator app.
'''
import tkinter as tk
from tkinter import messagebox
import string
import random
from password_generator import PasswordGenerator
from password_strength_checker import PasswordStrengthChecker
class RandomPasswordGeneratorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Random Password Generator")
        self.password_generator = PasswordGenerator()
        self.password_strength_checker = PasswordStrengthChecker()
        self.create_widgets()
    def create_widgets(self):
        # Length Label and Entry
        length_label = tk.Label(self.root, text="Password Length:")
        length_label.pack()
        self.length_entry = tk.Entry(self.root)
        self.length_entry.pack()
        # Complexity Label and Checkbuttons
        complexity_label = tk.Label(self.root, text="Password Complexity:")
        complexity_label.pack()
        self.uppercase_var = tk.IntVar()
        self.uppercase_checkbutton = tk.Checkbutton(self.root, text="Uppercase Letters", variable=self.uppercase_var)
        self.uppercase_checkbutton.pack()
        self.lowercase_var = tk.IntVar()
        self.lowercase_checkbutton = tk.Checkbutton(self.root, text="Lowercase Letters", variable=self.lowercase_var)
        self.lowercase_checkbutton.pack()
        self.numbers_var = tk.IntVar()
        self.numbers_checkbutton = tk.Checkbutton(self.root, text="Numbers", variable=self.numbers_var)
        self.numbers_checkbutton.pack()
        self.special_chars_var = tk.IntVar()
        self.special_chars_checkbutton = tk.Checkbutton(self.root, text="Special Characters", variable=self.special_chars_var)
        self.special_chars_checkbutton.pack()
        # Excluded Characters Label and Entry
        excluded_chars_label = tk.Label(self.root, text="Excluded Characters:")
        excluded_chars_label.pack()
        self.excluded_chars_entry = tk.Entry(self.root)
        self.excluded_chars_entry.pack()
        # Number of Passwords Label and Entry
        num_passwords_label = tk.Label(self.root, text="Number of Passwords:")
        num_passwords_label.pack()
        self.num_passwords_entry = tk.Entry(self.root)
        self.num_passwords_entry.pack()
        # Generate Passwords Button
        generate_button = tk.Button(self.root, text="Generate Passwords", command=self.generate_passwords)
        generate_button.pack()
        # Generated Passwords Label and Text
        generated_passwords_label = tk.Label(self.root, text="Generated Passwords:")
        generated_passwords_label.pack()
        self.generated_passwords_text = tk.Text(self.root)
        self.generated_passwords_text.pack()
        # Password Strength Label and Entry
        password_strength_label = tk.Label(self.root, text="Check Password Strength:")
        password_strength_label.pack()
        self.password_strength_entry = tk.Entry(self.root)
        self.password_strength_entry.pack()
        # Check Strength Button
        check_strength_button = tk.Button(self.root, text="Check Strength", command=self.check_strength)
        check_strength_button.pack()
    def generate_passwords(self):
        length = int(self.length_entry.get())
        complexity = []
        if self.uppercase_var.get():
            complexity.append("uppercase")
        if self.lowercase_var.get():
            complexity.append("lowercase")
        if self.numbers_var.get():
            complexity.append("numbers")
        if self.special_chars_var.get():
            complexity.append("special_chars")
        excluded_chars = self.excluded_chars_entry.get()
        num_passwords = int(self.num_passwords_entry.get())
        if length < len(complexity):
            messagebox.showerror("Invalid Input", "Password length should be greater than or equal to the complexity requirements.")
            return
        passwords = self.password_generator.generate_passwords(length, complexity, excluded_chars, num_passwords)
        self.generated_passwords_text.delete(1.0, tk.END)
        for password in passwords:
            self.generated_passwords_text.insert(tk.END, password + "\n")
    def check_strength(self):
        password = self.password_strength_entry.get()
        strength = self.password_strength_checker.check_strength(password)
        messagebox.showinfo("Password Strength", strength)
    def run(self):
        self.root.mainloop()
if __name__ == "__main__":
    app = RandomPasswordGeneratorApp()
    app.run()