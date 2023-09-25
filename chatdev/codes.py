import difflib
import os
import re
import subprocess

from chatdev.utils import log_and_print_online


class Codes:
    def __init__(self, generated_content=""):
        self.directory: str = None
        self.version: float = 0.0
        self.generated_content: str = generated_content
        self.codebooks = {}

        def extract_filename_from_line(lines):
            file_name = ""
            for candidate in re.finditer(r"(\w+\.\w+)", lines, re.DOTALL):
                file_name = candidate.group()
                file_name = file_name.lower()
            return file_name

        def extract_filename_from_code(code):
            file_name = ""
            regex_extract = r"class (\S+?):\n"
            matches_extract = re.finditer(regex_extract, code, re.DOTALL)
            for match_extract in matches_extract:
                file_name = match_extract.group(1)
            file_name = file_name.lower().split("(")[0] + ".py"
            return file_name

        if generated_content != "":
            regex = r"(.+?)\n```.*?\n(.*?)```"
            matches = re.finditer(regex, self.generated_content, re.DOTALL)
            for match in matches:
                code = match.group(2)
                if "CODE" in code:
                    continue
                group1 = match.group(1)
                filename = extract_filename_from_line(group1)
                if "__main__" in code:
                    filename = "main.py"
                if filename == "":  # post-processing
                    filename = extract_filename_from_code(code)
                assert filename != ""
                if filename is not None and code is not None and len(filename) > 0 and len(code) > 0:
                    self.codebooks[filename] = self._format_code(code)

    def _format_code(self, code):
        code = "\n".join([line for line in code.split("\n") if len(line.strip()) > 0])
        return code

    def _update_codes(self, generated_content):
        new_codes = Codes(generated_content)
        differ = difflib.Differ()
        for key in new_codes.codebooks.keys():
            if key not in self.codebooks.keys() or self.codebooks[key] != new_codes.codebooks[key]:
                update_codes_content = "**[Update Codes]**\n\n"
                update_codes_content += "{} updated.\n".format(key)
                old_codes_content = self.codebooks[key] if key in self.codebooks.keys() else "# None"
                new_codes_content = new_codes.codebooks[key]

                lines_old = old_codes_content.splitlines()
                lines_new = new_codes_content.splitlines()

                unified_diff = difflib.unified_diff(lines_old, lines_new, lineterm='', fromfile='Old', tofile='New')
                unified_diff = '\n'.join(unified_diff)
                update_codes_content = update_codes_content + "\n\n" + """```
'''

'''\n""" + unified_diff + "\n```"

                log_and_print_online(update_codes_content)
                self.codebooks[key] = new_codes.codebooks[key]

    def _rewrite_codes(self, git_management, phase_info=None) -> None:
        directory = self.directory
        rewrite_codes_content = "**[Rewrite Codes]**\n\n"
        if os.path.exists(directory) and len(os.listdir(directory)) > 0:
            self.version += 1.0
        if not os.path.exists(directory):
            os.mkdir(self.directory)
            rewrite_codes_content += "{} Created\n".format(directory)

        for filename in self.codebooks.keys():
            filepath = os.path.join(directory, filename)
            with open(filepath, "w", encoding="utf-8") as writer:
                writer.write(self.codebooks[filename])
                rewrite_codes_content += os.path.join(directory, filename) + " Wrote\n"

        if git_management:
            if not phase_info:
                phase_info = ""
            git_online_log = "**[Git Information]**\n\n"
            if self.version == 1.0:
                os.system("cd {}; git init".format(self.directory))
                git_online_log += "cd {}; git init\n".format(self.directory)
            os.system("cd {}; git add .".format(self.directory))
            git_online_log += "cd {}; git add .\n".format(self.directory)

            # check if there exist diff
            completed_process = subprocess.run("cd {}; git status".format(self.directory), shell=True, text=True,
                                               stdout=subprocess.PIPE)
            if "nothing to commit" in completed_process.stdout:
                self.version -= 1.0
                return

            os.system("cd {}; git commit -m \"v{}\"".format(self.directory, str(self.version) + " " + phase_info))
            git_online_log += "cd {}; git commit -m \"v{}\"\n".format(self.directory,
                                                                      str(self.version) + " " + phase_info)
            if self.version == 1.0:
                os.system("cd {}; git submodule add ./{} {}".format(os.path.dirname(os.path.dirname(self.directory)),
                                                                    "WareHouse/" + os.path.basename(self.directory),
                                                                    "WareHouse/" + os.path.basename(self.directory)))
                git_online_log += "cd {}; git submodule add ./{} {}\n".format(
                    os.path.dirname(os.path.dirname(self.directory)),
                    "WareHouse/" + os.path.basename(self.directory),
                    "WareHouse/" + os.path.basename(self.directory))
                log_and_print_online(rewrite_codes_content)
            log_and_print_online(git_online_log)

    def _get_codes(self) -> str:
        content = ""
        for filename in self.codebooks.keys():
            content += "{}\n```{}\n{}\n```\n\n".format(filename,
                                                       "python" if filename.endswith(".py") else filename.split(".")[
                                                           -1], self.codebooks[filename])
        return content

    def _load_from_hardware(self, directory) -> None:
        assert len([filename for filename in os.listdir(directory) if filename.endswith(".py")]) > 0
        for root, directories, filenames in os.walk(directory):
            for filename in filenames:
                if filename.endswith(".py"):
                    code = open(os.path.join(directory, filename), "r", encoding="utf-8").read()
                    self.codebooks[filename] = self._format_code(code)
        log_and_print_online("{} files read from {}".format(len(self.codebooks.keys()), directory))
