'''
This file contains the Article class that represents an article and its layout.
'''
class Article:
    def __init__(self):
        self.content = ""
        self.image_url = ""
    def assign_image(self, image_url):
        self.image_url = image_url
    def generate_layout(self, article_text):
        self.content = article_text
        # Generate markdown layout based on the article content and assigned image
        layout = f"![Article Image]({self.image_url})\n\n{self.content}"
        return layout