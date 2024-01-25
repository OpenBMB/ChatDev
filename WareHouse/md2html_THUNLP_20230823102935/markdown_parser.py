'''
This file contains the MarkdownParser class responsible for parsing markdown syntax.
'''
import re
class MarkdownParser:
    def parse(self, markdown_content):
        parsed_content = []
        lines = markdown_content.split("\n")
        for line in lines:
            if line.startswith("#"):
                parsed_content.append(self.parse_heading(line))
            elif line.startswith("*") or line.startswith("-"):
                parsed_content.append(self.parse_list(line))
            elif line.startswith(">"):
                parsed_content.append(self.parse_blockquote(line))
            elif line.startswith("`"):
                parsed_content.append(self.parse_code_block(line))
            else:
                parsed_content.append(self.parse_paragraph(line))
        return parsed_content
    def parse_heading(self, line):
        level = line.count("#")
        content = line.strip("#").strip()
        return {"type": "heading", "level": level, "content": content}
    def parse_list(self, line):
        ordered = line.startswith("1.")
        items = [item.strip() for item in re.split(r"[*-]\s", line) if item.strip()]
        return {"type": "list", "ordered": ordered, "content": items}
    def parse_blockquote(self, line):
        content = line.strip(">")
        return {"type": "blockquote", "content": content}
    def parse_code_block(self, line):
        content = line.strip("`")
        return {"type": "code_block", "content": content}
    def parse_paragraph(self, line):
        return {"type": "paragraph", "content": line}