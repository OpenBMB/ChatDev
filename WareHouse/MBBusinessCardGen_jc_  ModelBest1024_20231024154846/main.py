'''
This is the main file that runs the business card generator program.
'''
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageFont
class BusinessCardGenerator:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Business Card Generator")
        self.name_label = tk.Label(self.root, text="Name:")
        self.name_label.pack()
        self.name_entry = tk.Entry(self.root)
        self.name_entry.pack()
        self.title_label = tk.Label(self.root, text="Title:")
        self.title_label.pack()
        self.title_entry = tk.Entry(self.root)
        self.title_entry.pack()
        self.email_label = tk.Label(self.root, text="Email:")
        self.email_label.pack()
        self.email_entry = tk.Entry(self.root)
        self.email_entry.pack()
        self.generate_button = tk.Button(self.root, text="Generate", command=self.generate_business_card)
        self.generate_button.pack()
        self.root.mainloop()
    def generate_business_card(self):
        name = self.name_entry.get()
        title = self.title_entry.get()
        email = self.email_entry.get()
        image = Image.new("RGB", (500, 300), (53, 154, 256))
        draw = ImageDraw.Draw(image)
        # Draw company name
        company_name = "ModelBest"
        company_name_font = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 24)
        company_name_width, company_name_height = draw.textsize(company_name, font=company_name_font)
        draw.text((400 - company_name_width, 20), company_name, font=company_name_font, fill="black")
        # Draw name
        name_font = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 18)
        name_width, name_height = draw.textsize(name, font=name_font)
        draw.text((20, 100), name, font=name_font, fill="black")
        # Draw title
        title_font = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 14)
        title_width, title_height = draw.textsize(title, font=title_font)
        draw.text((20, 140), title, font=title_font, fill="black")
        # Draw email
        email_font = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 14)
        email_width, email_height = draw.textsize(email, font=email_font)
        draw.text((20, 180), email, font=email_font, fill="black")
        # Draw slogan
        slogan = "AGI For Lives"
        slogan_font = ImageFont.truetype("/Library/Fonts/Arial Unicode.ttf", 12)
        slogan_width, slogan_height = draw.textsize(slogan, font=slogan_font)
        draw.text((400 - slogan_width, 280 - slogan_height), slogan, font=slogan_font, fill="black")
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")])
        if file_path:
            image.save(file_path)
            print("Business card saved successfully!")
        else:
            print("Business card not saved.")
if __name__ == "__main__":
    BusinessCardGenerator()