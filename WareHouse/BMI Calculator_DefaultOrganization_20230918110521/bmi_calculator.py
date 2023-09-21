'''
This file contains the BMICalculator class.
'''
class BMICalculator:
    def calculate_bmi(self, weight, height):
        if height <= 0:
            raise ValueError("Height cannot be zero or negative.")
        bmi = weight / (height ** 2)
        return bmi