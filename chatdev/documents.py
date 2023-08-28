import re
import os
import time
from colorama import Fore


class Documents():
    def __init__(self, generated_content = "", parse = True, predifined_filename = None):
        self.directory: str = None
        self.generated_content = generated_content
        self.docbooks = {}

        if generated_content != "":
            if parse:
                regex = r"```\n(.*?)```"
                matches = re.finditer(regex, self.generated_content, re.DOTALL)
                for match in matches:
                    filename = "requirements.txt"
                    doc = match.group(1)
                    self.docbooks[filename] = doc
            else:
                self.docbooks[predifined_filename] = self.generated_content

    def _update_docs(self, generated_content, parse = True, predifined_filename = ""):
        new_docs = Documents(generated_content, parse, predifined_filename)
        for key in new_docs.docbooks.keys():
            if key not in self.docbooks.keys() or self.docbooks[key] != new_docs.docbooks[key]:
                print("{} updated.".format(key))
                print(Fore.WHITE + "------Old:\n{}\n------New:\n{}".format(self.docbooks[key] if key in self.docbooks.keys() else "# None", new_docs.docbooks[key]))
                self.docbooks[key] = new_docs.docbooks[key]


    def _rewrite_docs(self):
        directory = self.directory
        if not os.path.exists(directory):
            os.mkdir(directory)
            print("{} Created.".format(directory))
        for filename in self.docbooks.keys():
            with open(os.path.join(directory, filename), "w", encoding="utf-8") as writer:
                writer.write(self.docbooks[filename])
                print(os.path.join(directory, filename), "Writed")

    def _get_docs(self):
        content = ""
        for filename in self.docbooks.keys():
            content += "{}\n```\n{}\n```\n\n".format(filename, self.docbooks[filename])
        return content
