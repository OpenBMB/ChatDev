import os
import re
import signal
import subprocess
import time
import numpy as np
from openai import OpenAI

client = OpenAI(
    api_key='',
    base_url="",
)

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

    codebooks = {}
    filepaths = getFilesFromType(directory, ".py")
    for filepath in filepaths:
        filename = os.path.basename(filepath)
        codebooks[filename] = _format_code(open(filepath, "r", encoding="utf-8").read())

    code = ""
    for filename in codebooks.keys():
        code += "{}\n```Python\n{}\n```\n\n".format(filename, codebooks[filename])

    if len(code) == 0:
        code = "# None"

    return code.strip()

def get_completeness(directory):
    assert os.path.isdir(directory)
    vn = get_code(directory)
    lines = vn.split("\n")
    lines = [line for line in lines if
             "password" not in line.lower() and "passenger" not in line.lower() and "passed" not in line.lower() and "passes" not in line.lower()]
    lines = [line for line in lines if "pass" in line.lower() or "todo" in line.lower()]
    if len(lines) > 0:
        return 0.0
    return 1.0

def get_executability(directory):
    assert os.path.isdir(directory)
    def findFile(directory, target):
        main_py_path = None
        for subroot, _, filenames in os.walk(directory):
            for filename in filenames:
                if target in filename:
                    main_py_path = os.path.join(subroot, filename)
        return main_py_path

    def exist_bugs(directory):
        assert os.path.isdir(directory)
        success_info = "The software run successfully without errors."
        try:
            command = "cd \"{}\"; ls -l; python3 main.py;".format(directory)
            process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            time.sleep(3)

            error_type = ""
            return_code = process.returncode
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
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

    main_py_path = findFile(directory, ".py")
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
        return  1.0
    return 0.0

def get_consistency(directory):
    def remove_comments(string):
        def remove_comments_by_regex(string, regex):
            lines = string.split("\n")
            lines = [line for line in lines if not line.strip().startswith("#")]
            string = "\n".join(lines)
            comments = []
            matches = re.finditer(regex, string, re.DOTALL)
            for match in matches:
                group1 = match.group(1)
                comments.append(group1)
            for comment in comments + ["''''''\n"]:
                string = string.replace(comment, "")
            return string

        string = remove_comments_by_regex(string, r"'''(.*?)'''")
        string = remove_comments_by_regex(string, r"\"\"\"(.*?)\"\"\"")
        return string

    def get_text_embedding(text: str):
        if text == "":
            text = "None"
        ada_embedding = client.embeddings.create(input=text, model="text-embedding-ada-002").model_dump()['data'][0]['embedding']
        return ada_embedding

    def get_code_embedding(code: str):
        if code == "":
            code = "#"
        ada_embedding = client.embeddings.create(input=code, model="text-embedding-ada-002").model_dump()['data'][0]['embedding']
        return ada_embedding

    def get_cosine_similarity(embeddingi, embeddingj):
        embeddingi = np.array(embeddingi)
        embeddingj = np.array(embeddingj)
        cos_sim = embeddingi.dot(embeddingj) / (np.linalg.norm(embeddingi) * np.linalg.norm(embeddingj))
        return cos_sim

    assert os.path.isdir(directory)
    files = getFilesFromType(directory, ".txt")
    if len(files) == 0:
        print()
    filepath = files[0]
    task = open(filepath).read().strip()
    codes = get_code(directory)
    codes = remove_comments(codes)

    text_embedding = get_text_embedding(task)
    code_embedding = get_code_embedding(codes)
    task_code_alignment = get_cosine_similarity(text_embedding, code_embedding)

    return task_code_alignment

def main(warehouse_root):
    def write_string(string):
        writer.write(string)
        print(string, end="")

    directories = []
    for directory in os.listdir(warehouse_root):
        directories.append(os.path.join(warehouse_root, directory))
    directories = sorted(directories)
    directories = [directory for directory in directories if os.path.isdir(directory)]
    print("len(directories):", len(directories))

    suffix = warehouse_root.replace("/", "__").replace("-", "_")
    tsv_file = __file__.replace(".py", ".{}.tsv".format(suffix))
    print("tsv_file:", tsv_file)

    counter = 0
    completeness_list, executability_list, consistency_list = [], [], []
    with open(tsv_file, "a", encoding="utf-8") as writer:
        for i, directory in enumerate(directories):
            directory_basename = os.path.basename(directory)

            completeness = get_completeness(directory)
            executability = get_executability(directory)
            consistency = get_consistency(directory)

            completeness_list.append(completeness)
            executability_list.append(executability)
            consistency_list.append(consistency)

            counter += 1

main(warehouse_root = "./WareHouse")
