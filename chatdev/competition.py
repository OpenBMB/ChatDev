import os
import glob
import time
import random
import tiktoken
from openai import OpenAI
import re
import signal
import subprocess
from chatdev.codes import Codes
from chatdev.utils import log_macnet
from chatdev.test_unfinished_function import FunctionTest


def competition_filter(dir_program):
    def getFilesFromType(sourceDir, filetype):
        files = []
        for root, directories, filenames in os.walk(sourceDir):
            for filename in filenames:
                if filename.endswith(filetype):
                    files.append(os.path.join(root, filename))
        return files

    def get_code(directory):
        def _format_code(code):
            code = "\n".join([line for line in code.split("\n") if len(line.strip()) > 0])
            return code

        # Read all .py files
        codebooks = {}
        filepaths = getFilesFromType(directory, ".py")
        for filepath in filepaths:
            filename = os.path.basename(filepath)
            codebooks[filename] = _format_code(open(filepath, "r", encoding="utf-8").read())

        # Format Codes
        code = ""
        for filename in codebooks.keys():
            code += "{}\n```Python\n{}\n```\n\n".format(filename, codebooks[filename])

        if len(code) == 0:
            code = "# None"

        return code.strip()

    def get_completeness(directory):
        vn = get_code(directory)
        lines = vn.split("\n")

        lines = [line for line in lines if
                 "password" not in line.lower() and "passenger" not in line.lower() and "passed" not in line.lower() and "passes" not in line.lower()]
        lines = [line for line in lines if "pass" in line.lower() or "todo" in line.lower()]
        if len(lines) > 0:
            return 0.0
        return 1.0

    def get_executability(directory):
        def findFile(directory, target):
            main_py_path = None
            for subroot, _, filenames in os.walk(directory):
                for filename in filenames:
                    if filename == target:
                        main_py_path = os.path.join(subroot, filename)
            return main_py_path

        def exist_bugs(directory):
            success_info = "The software run successfully without errors."
            try:
                command = "cd \"{}\"; ls -l; python3 main.py;".format(directory)
                process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
                time.sleep(1)  # to 3 once stuck

                error_type = ""
                return_code = process.returncode
                # Check if the software is still running
                if process.poll() is None:
                    timeout = 10
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        process.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        process.wait()
                if return_code == 0:
                    return False, success_info, error_type
                else:
                    error_output = process.stderr.read().decode('utf-8')
                    try:
                        error_pattern = r'\w+Error:'
                        error_matches = re.findall(error_pattern, error_output)
                        error_type = error_matches[0].replace(":", "")
                    except:
                        pass
                    if error_output:
                        if "Traceback".lower() in error_output.lower():
                            errs = error_output.replace(directory + "/", "")
                            return True, errs, error_type
                    else:
                        return False, success_info, error_type

            except subprocess.CalledProcessError as e:
                return True, f"Error: {e}", "subprocess.CalledProcessError"
            except Exception as ex:
                return True, f"An error occurred: {ex}", "OtherException"

            return False, success_info, error_type

        main_py_path = findFile(directory, "main.py")
        pass_flag, error_type = True, ""
        if main_py_path is not None:
            main_py_path = os.path.dirname(main_py_path)
            bug_flag, info, error_type = exist_bugs(main_py_path)
            pass_flag = not bug_flag
        else:
            pass_flag, error_type = False, "NoMain"

        if error_type == "":
            error_type = info.replace("\n", "\\n")

        if pass_flag:
            return 1.0
        return 0.0

    def get_code_line(directory):
        total_lines = 0
        for root, dirs, files in os.walk(directory):
            for file_name in files:
                if file_name.endswith(".py") and file_name != 'test_file_will_delete.py':
                    file_path = os.path.join(root, file_name)

                    with open(file_path, 'r', encoding='utf-8') as file:
                        lines = file.readlines()
                        total_lines += len(lines)

        return total_lines

    completeness_dict = {}
    executability_dict = {}
    code_line_dict = {}
    competition_dict = {}
    completeness = get_completeness(dir_program)
    executability = get_executability(dir_program)
    # code_line = get_code_line(dir_program)
    function_test = FunctionTest(dir_program)
    need_complete = function_test.extract_function_name()
    # completeness_dict[content] = completeness
    # executability_dict[content] = executability
    # code_line_dict[content] = code_line
    need_complete_number = 0
    for function in need_complete.values():
        need_complete_number += len(function)
    rate_number = (executability * 10 + completeness) * 10000 - need_complete_number
    del function_test

    return rate_number
