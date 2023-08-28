'''
This file contains the Budget class which handles income, expense tracking, and reporting.
'''
class Budget:
    def __init__(self):
        self.income = []
        self.expenses = []
    def add_income(self, amount, description):
        # Add income to the list
        self.income.append({"amount": amount, "description": description})
    def add_expense(self, amount, description):
        # Add expense to the list
        self.expenses.append({"amount": amount, "description": description})
    def calculate_total_income(self):
        # Calculate the total income
        total_income = sum(income["amount"] for income in self.income)
        return total_income
    def calculate_total_expenses(self):
        # Calculate the total expenses
        total_expenses = sum(expense["amount"] for expense in self.expenses)
        return total_expenses
    def generate_report(self):
        # Generate a report with income, expenses, and analytics
        total_income = self.calculate_total_income()
        total_expenses = self.calculate_total_expenses()
        net_income = total_income - total_expenses if total_expenses else total_income
        report = f"Total Income: ${total_income}\n"
        report += f"Total Expenses: ${total_expenses}\n"
        report += f"Net Income: ${net_income}\n"
        return report