'''
This is the main file that creates the landing page for the images.
'''
import tkinter as tk
from PIL import ImageTk, Image
import requests
from io import BytesIO
class LandingPage(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("Image Landing Page")
        # Create canvas to display images
        self.canvas = tk.Canvas(self, width=1000, height=400)
        self.canvas.pack()
        # Load and display blue image
        self.load_and_display_image("https://image.startr.cloud/1000x400/blue_", 0, 0)
        # Load and display purple image
        self.load_and_display_image("https://image.startr.cloud/1000x400/purple_", 500, 0)
    def load_and_display_image(self, url, x, y):
        response = requests.get(url)
        image = Image.open(BytesIO(response.content))
        image = image.resize((1000, 400), Image.ANTIALIAS)
        photo = ImageTk.PhotoImage(image)
        self.canvas.create_image(x, y, anchor=tk.NW, image=photo)
        self.canvas.image = photo
if __name__ == "__main__":
    landing_page = LandingPage()
    landing_page.mainloop()