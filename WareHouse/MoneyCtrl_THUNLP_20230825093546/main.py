'''
This is the main file of the personal budget app. It contains the main function that initializes the GUI and starts the application.
'''
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from budget import Budget
def main():
    # Create an instance of the Budget class
    budget = Budget()
    # Function to add income
    def add_income():
        amount = float(income_amount_entry.get())
        description = income_description_entry.get()
        budget.add_income(amount, description)
        messagebox.showinfo("Success", "Income added successfully!")
    # Function to add expenses
    def add_expenses():
        amount = float(expenses_amount_entry.get())
        description = expenses_description_entry.get()
        budget.add_expense(amount, description)
        messagebox.showinfo("Success", "Expenses added successfully!")
    # Function to generate report
    def generate_report():
        report = budget.generate_report()
        report_text.delete(1.0, tk.END)
        report_text.insert(tk.END, report)
    # Create the main window
    root = tk.Tk()
    root.title("Personal Budget App")
    # Create and configure the GUI elements
    income_label = ttk.Label(root, text="Income:")
    income_label.grid(row=0, column=0, padx=10, pady=10)
    income_amount_entry = ttk.Entry(root)
    income_amount_entry.grid(row=0, column=1, padx=10, pady=10)
    income_description_entry = ttk.Entry(root)
    income_description_entry.grid(row=0, column=2, padx=10, pady=10)
    add_income_button = ttk.Button(root, text="Add Income", command=add_income)
    add_income_button.grid(row=0, column=3, padx=10, pady=10)
    expenses_label = ttk.Label(root, text="Expenses:")
    expenses_label.grid(row=1, column=0, padx=10, pady=10)
    expenses_amount_entry = ttk.Entry(root)
    expenses_amount_entry.grid(row=1, column=1, padx=10, pady=10)
    expenses_description_entry = ttk.Entry(root)
    expenses_description_entry.grid(row=1, column=2, padx=10, pady=10)
    add_expenses_button = ttk.Button(root, text="Add Expenses", command=add_expenses)
    add_expenses_button.grid(row=1, column=3, padx=10, pady=10)
    generate_report_button = ttk.Button(root, text="Generate Report", command=generate_report)
    generate_report_button.grid(row=2, column=0, columnspan=4, padx=10, pady=10)
    report_text = tk.Text(root, height=10, width=40)
    report_text.grid(row=3, column=0, columnspan=4, padx=10, pady=10)
    # Start the main event loop
    root.mainloop()
if __name__ == "__main__":
    main()