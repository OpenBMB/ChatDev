'''
This file contains the ImageFinder class which is responsible for finding an image related to the article.
'''
import requests
from bs4 import BeautifulSoup
class ImageFinder:
    def __init__(self, article):
        self.article = article
    def find_image(self):
        # Here we use a simple method to find an image: we search for the article title on Google Images and return the first result.
        # In a real application, you would want to use a more sophisticated method, such as a machine learning model trained to find relevant images.
        query = self.article.split(' ')[0]  # Use the first word of the article as the query
        url = f"https://www.google.com/search?q={query}&tbm=isch"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        image_url = soup.find('img')['src']
        return image_url