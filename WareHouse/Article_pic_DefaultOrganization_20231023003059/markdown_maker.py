'''
This file contains the MarkdownMaker class which is responsible for creating the markdown.
'''
import markdown
class MarkdownMaker:
    def __init__(self, article, image_url):
        self.article = article
        self.image_url = image_url
    def create_markdown(self):
        md = markdown.Markdown()
        md_article = md.convert(self.article)
        md_image = f"![Image]({self.image_url})"
        md_article = md_article.replace("\n", "\n\n" + md_image + "\n\n", 1)
        with open('output.md', 'w') as file:
            file.write(md_article)