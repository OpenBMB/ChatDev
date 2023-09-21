'''
This is the main file of the BMI calculator application.
'''
import tkinter as tk
from bmi_calculator import BMICalculator
class BMIApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BMI Calculator")
        self.geometry("300x200")
        self.bmi_calculator = BMICalculator()
        self.weight_label = tk.Label(self, text="Weight (kg):")
        self.weight_label.pack()
        self.weight_entry = tk.Entry(self)
        self.weight_entry.pack()
        self.height_label = tk.Label(self, text="Height (cm):")
        self.height_label.pack()
        self.height_entry = tk.Entry(self)
        self.height_entry.pack()
        self.calculate_button = tk.Button(self, text="Calculate", command=self.calculate_bmi)
        self.calculate_button.pack()
        self.result_label = tk.Label(self, text="")
        self.result_label.pack()
    def calculate_bmi(self):
        try:
            weight = float(self.weight_entry.get())
            height = float(self.height_entry.get()) / 100
            bmi = self.bmi_calculator.calculate_bmi(weight, height)
            self.result_label.config(text=f"BMI: {bmi:.2f}")
        except ValueError:
            self.result_label.config(text="Invalid input. Please enter numeric values for weight and height.")
        except ZeroDivisionError:
            self.result_label.config(text="Invalid input. Height cannot be zero.")
if __name__ == "__main__":
    app = BMIApplication()
    app.mainloop()