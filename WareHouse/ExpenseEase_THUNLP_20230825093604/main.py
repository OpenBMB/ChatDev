'''
Expense Tracker
This program allows users to input their expenses and visualize the data using a graphical user interface (GUI).
Author: ChatDev
'''
import tkinter as tk
import matplotlib.pyplot as plt
class ExpenseTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Expense Tracker")
        self.geometry("400x300")
        self.expenses = []
        self.create_widgets()
    def create_widgets(self):
        self.expense_label = tk.Label(self, text="Expense:")
        self.expense_label.pack()
        self.expense_entry = tk.Entry(self)
        self.expense_entry.pack()
        self.add_button = tk.Button(self, text="Add Expense", command=self.add_expense)
        self.add_button.pack()
        self.expense_listbox = tk.Listbox(self)
        self.expense_listbox.pack()
        self.visualize_button = tk.Button(self, text="Visualize Data", command=self.visualize_data)
        self.visualize_button.pack()
    def add_expense(self):
        expense = self.expense_entry.get()
        self.expenses.append(expense)
        self.expense_listbox.insert(tk.END, expense)
        self.expense_entry.delete(0, tk.END)
    def visualize_data(self):
        # Plotting the expenses as a bar chart
        plt.bar(range(len(self.expenses)), [float(expense) for expense in self.expenses])
        plt.xlabel("Expense")
        plt.ylabel("Amount")
        plt.title("Expense Tracker")
        plt.show()
if __name__ == "__main__":
    app = ExpenseTrackerApp()
    app.mainloop()