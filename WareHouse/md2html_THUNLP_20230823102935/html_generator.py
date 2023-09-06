'''
This file contains the HTMLGenerator class responsible for generating HTML markup from parsed markdown content.
'''
class HTMLGenerator:
    def generate_html(self, parsed_content):
        html_output = ""
        for element in parsed_content:
            if element["type"] == "heading":
                html_output += self.generate_heading(element["content"], element["level"])
            elif element["type"] == "paragraph":
                html_output += self.generate_paragraph(element["content"])
            elif element["type"] == "list":
                html_output += self.generate_list(element["content"], element["ordered"])
            elif element["type"] == "emphasis":
                html_output += self.generate_emphasis(element["content"])
            elif element["type"] == "link":
                html_output += self.generate_link(element["content"], element["url"])
            elif element["type"] == "image":
                html_output += self.generate_image(element["alt_text"], element["url"])
            elif element["type"] == "code_block":
                html_output += self.generate_code_block(element["content"])
        return html_output
    def generate_heading(self, content, level):
        return f"<h{level}>{content}</h{level}>\n"
    def generate_paragraph(self, content):
        return f"<p>{content}</p>\n"
    def generate_list(self, items, ordered):
        list_type = "ol" if ordered else "ul"
        list_items = "".join([f"<li>{item}</li>\n" for item in items])
        return f"<{list_type}>\n{list_items}</{list_type}>\n"
    def generate_emphasis(self, content):
        return f"<em>{content}</em>"
    def generate_link(self, content, url):
        return f'<a href="{url}">{content}</a>'
    def generate_image(self, alt_text, url):
        return f'<img src="{url}" alt="{alt_text}">'
    def generate_code_block(self, content):
        return f"<pre><code>{content}</code></pre>\n"