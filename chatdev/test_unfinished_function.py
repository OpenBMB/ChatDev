import os
import subprocess
import re
import ast
import textwrap


def get_py_files_in_folder(folder_path):
    py_files = [f for f in os.listdir(folder_path) if f.endswith('.py')]
    py_files_paths = [os.path.join(folder_path, f) for f in py_files]
    return py_files_paths


def insert_pass(file_path, line_number):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    indentation_level = 0
    if 1 <= line_number <= len(lines):
        line = lines[line_number - 1]
        stripped_line = line.lstrip()
        indentation_level = len(line) - len(stripped_line)

    new_line_number = line_number + 1
    new_line = ' ' * (indentation_level + 4) + 'pass\n'
    lines.insert(new_line_number - 1, new_line)

    with open(file_path, 'w') as file:
        file.writelines(lines)


def detect_pass(file_path):
    def has_pass(node):
        if isinstance(node, ast.Pass):
            return True
        for child_node in ast.iter_child_nodes(node):
            if has_pass(child_node):
                return True
        return False

    def check_functions_for_pass(file_path):
        with open(file_path, 'r') as file:
            code = file.read()

        tree = ast.parse(code)
        function_name = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if has_pass(node):
                    function_name.append(node.name)
        return function_name

    function_name = check_functions_for_pass(file_path)
    return function_name


def copy_file_content(source_file_path, destination_file_path):
    with open(source_file_path, 'r') as source_file:
        content = source_file.read()

    with open(destination_file_path, 'w') as destination_file:
        destination_file.write(content)


def run_flake8(file_path):
    try:
        result = subprocess.run(['flake8', file_path], check=True, capture_output=True, text=True)
        return False, 0
    except subprocess.CalledProcessError as e:
        if 'E999' in e.stdout:
            match = re.search(r'on line (\d+)', e.stdout)

            if match:
                line_number = match.group(1)
                return True, int(line_number)
            else:
                print("Line number information not found")
                return False, -1
        else:
            return False, -1


def find_print_statement(node):
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func,
                                                                                      ast.Name) and node.value.func.id == 'print':
        return node.lineno
    else:
        for child in ast.iter_child_nodes(node):
            line = find_print_statement(child)
            if line is not None:
                return line
        return None


def has_only_print(node):
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func,
                                                                                      ast.Name) and node.value.func.id == 'print':
        return True
    elif isinstance(node, ast.FunctionDef):
        return all(has_only_print(child) for child in node.body)
    else:
        return False


def find_functions_with_only_print(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        code = file.read()
    tree = ast.parse(code)

    unfinished_function = []
    passline = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if has_only_print(node):
                unfinished_function.append(node.name)
                passline.append(find_print_statement(node))
                print(f"Function '{node.name}' only contains a print statement on line {find_print_statement(node)}.")
    return unfinished_function, passline


def replace_with_pass(file_path, test_path, line_list):
    with open(test_path, 'r') as file:
        lines = file.readlines()
    for printline in line_list:
        line = lines[printline - 1]
        stripped_line = line.lstrip()
        indentation_level = len(line) - len(stripped_line)
        line = ' ' * (indentation_level) + 'pass\n'
        lines[printline - 1] = line
        with open(file_path, 'w') as file:
            file.writelines(lines)


def remove_pass_in_flake8_functions(file_path, line_list):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    for line_number in sorted(line_list, reverse=True):
        del lines[line_number]

    with open(file_path, 'w') as file:
        file.writelines(lines)


class FunctionTest:
    def __init__(self, directory):
        self.functions_with_lines = {}
        self.directory = directory
        self.need_complete = {}

    def extract_function_name(self):
        pylist = get_py_files_in_folder(self.directory)
        test_path = self.directory + '/test_file_will_delete.py'
        if test_path in pylist:
            pylist.remove(test_path)
        for pyfile in pylist:
            copy_file_content(pyfile, test_path)
            unfilled = True
            flask8_line_number = []
            while unfilled:
                unfilled, line_number = run_flake8(test_path)
                if line_number != -1:
                    insert_pass(test_path, line_number)
                    flask8_line_number.append(line_number)
            pyname = os.path.basename(pyfile)
            self.need_complete[pyname] = []
            if detect_pass(test_path):
                self.need_complete[pyname] = detect_pass(test_path)

        self.need_complete = {key: value for key, value in self.need_complete.items() if value != []}

        return self.need_complete
