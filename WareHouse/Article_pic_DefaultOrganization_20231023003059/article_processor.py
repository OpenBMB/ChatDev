'''
This file contains the ArticleProcessor class which is responsible for processing the article.
'''
from markdown_maker import MarkdownMaker
from image_finder import ImageFinder
class ArticleProcessor:
    def __init__(self, article):
        self.article = article
    def process_article(self):
        # Find an image for the article
        finder = ImageFinder(self.article)
        image_url = finder.find_image()
        # Create the markdown
        maker = MarkdownMaker(self.article, image_url)
        markdown = maker.create_markdown()
        return markdown