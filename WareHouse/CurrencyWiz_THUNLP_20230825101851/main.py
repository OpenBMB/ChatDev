'''
Currency Converter App
Fetches real-time exchange rates online and provides a modern and intuitive GUI.
Author: Programmer
'''
import tkinter as tk
import requests
class CurrencyConverterApp:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Currency Converter")
        self.amount_label = tk.Label(self.window, text="Amount:")
        self.amount_label.pack()
        self.amount_entry = tk.Entry(self.window)
        self.amount_entry.pack()
        self.from_currency_label = tk.Label(self.window, text="From Currency:")
        self.from_currency_label.pack()
        self.from_currency_entry = tk.Entry(self.window)
        self.from_currency_entry.pack()
        self.to_currency_label = tk.Label(self.window, text="To Currency:")
        self.to_currency_label.pack()
        self.to_currency_entry = tk.Entry(self.window)
        self.to_currency_entry.pack()
        self.convert_button = tk.Button(self.window, text="Convert", command=self.convert)
        self.convert_button.pack()
        self.result_label = tk.Label(self.window, text="")
        self.result_label.pack()
    def run(self):
        self.window.mainloop()
    def convert(self):
        amount = float(self.amount_entry.get())
        from_currency = self.from_currency_entry.get().upper()
        to_currency = self.to_currency_entry.get().upper()
        if from_currency == to_currency:
            self.result_label.config(text="Cannot convert between the same currency.")
            return
        try:
            response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{from_currency}")
            response.raise_for_status()  # Add this line to raise an exception if the request fails
            exchange_rates = response.json()["rates"]
            if to_currency in exchange_rates:
                converted_amount = amount * exchange_rates[to_currency]
                self.result_label.config(text=f"{amount} {from_currency} = {converted_amount} {to_currency}")
            else:
                self.result_label.config(text=f"Invalid currency: {to_currency}")
        except requests.exceptions.RequestException as e:
            self.result_label.config(text="Failed to fetch exchange rates. Please try again later.")
            print(f"RequestException: {e}")
        except requests.exceptions.HTTPError as e:
            self.result_label.config(text="Failed to fetch exchange rates. Please try again later.")
            print(f"HTTPError: {e}")
if __name__ == "__main__":
    app = CurrencyConverterApp()
    app.run()