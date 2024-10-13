import os
import re
import signal
import subprocess
import time
import numpy as np
from typing import List, Tuple, Dict
import logging
from openai import OpenAI
import yaml
import unittest

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

client = OpenAI(
    api_key=config['openai_api_key'],
    base_url=config['openai_base_url'],
)

class CodeAnalyzer:
    @staticmethod
    def get_files_from_type(source_dir: str, file_type: str) -> List[str]:
        """Get all files of a specific type from a directory."""
        files = []
        for root, _, filenames in os.walk(source_dir):
            for filename in filenames:
                if filename.endswith(file_type):
                    files.append(os.path.join(root, filename))
        return files

    @staticmethod
    def get_code(directory: str) -> str:
        """Get all Python code from a directory."""
        def _format_code(code: str) -> str:
            return "\n".join([line for line in code.split("\n") if len(line.strip()) > 0])

        codebooks = {}
        filepaths = CodeAnalyzer.get_files_from_type(directory, ".py")
        for filepath in filepaths:
            filename = os.path.basename(filepath)
            with open(filepath, "r", encoding="utf-8") as file:
                codebooks[filename] = _format_code(file.read())

        code = ""
        for filename, content in codebooks.items():
            code += f"{filename}\n```Python\n{content}\n```\n\n"

        return code.strip() or "# None"

    @staticmethod
    def get_completeness(directory: str) -> float:
        """Check the completeness of the code."""
        assert os.path.isdir(directory), f"Directory does not exist: {directory}"
        vn = CodeAnalyzer.get_code(directory)
        lines = vn.split("\n")
        lines = [line for line in lines if
                 all(word not in line.lower() for word in ["password", "passenger", "passed", "passes"])]
        incomplete_lines = [line for line in lines if "pass" in line.lower() or "todo" in line.lower()]
        return 0.0 if incomplete_lines else 1.0

    @staticmethod
    def get_executability(directory: str) -> float:
        """Check if the code is executable."""
        assert os.path.isdir(directory), f"Directory does not exist: {directory}"
        
        def find_file(directory: str, target: str) -> str:
            for subroot, _, filenames in os.walk(directory):
                for filename in filenames:
                    if target in filename:
                        return os.path.join(subroot, filename)
            return None

        def exist_bugs(directory: str) -> Tuple[bool, str, str]:
            success_info = "The software run successfully without errors."
            try:
                command = f"cd \"{directory}\"; ls -l; python3 main.py;"
                process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
                time.sleep(3)

                error_type = ""
                return_code = process.poll()
                if return_code is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    return True, "Process timed out", "Timeout"
                if return_code == 0:
                    return False, success_info, error_type
                else:
                    error_output = process.stderr.read().decode('utf-8')
                    try:
                        error_pattern = r'\w+Error:'
                        error_matches = re.findall(error_pattern, error_output)
                        error_type = error_matches[0].replace(":", "")
                    except IndexError:
                        pass
                    if "Traceback".lower() in error_output.lower():
                        errs = error_output.replace(f"{directory}/", "")
                        return True, errs, error_type
                    else:
                        return False, success_info, error_type
            except subprocess.CalledProcessError as e:
                return True, f"Error: {e}", "subprocess.CalledProcessError"
            except Exception as ex:
                return True, f"An error occurred: {ex}", "OtherException"

        main_py_path = find_file(directory, ".py")
        if main_py_path is not None:
            main_py_path = os.path.dirname(main_py_path)
            bug_flag, info, error_type = exist_bugs(main_py_path)
            return 0.0 if bug_flag else 1.0
        else:
            return 0.0

    @staticmethod
    def get_consistency(directory: str) -> float:
        """Check the consistency between the task description and the code."""
        assert os.path.isdir(directory), f"Directory does not exist: {directory}"

        def remove_comments(string: str) -> str:
            def remove_comments_by_regex(string: str, regex: str) -> str:
                lines = string.split("\n")
                lines = [line for line in lines if not line.strip().startswith("#")]
                string = "\n".join(lines)
                comments = re.findall(regex, string, re.DOTALL)
                for comment in comments + ["''''''\n"]:
                    string = string.replace(comment, "")
                return string

            string = remove_comments_by_regex(string, r"'''(.*?)'''")
            string = remove_comments_by_regex(string, r"\"\"\"(.*?)\"\"\"")
            return string

        def get_embedding(text: str, is_code: bool = False) -> List[float]:
            if not text:
                text = "None" if not is_code else "#"
            return client.embeddings.create(input=text, model="text-embedding-ada-002").model_dump()['data'][0]['embedding']

        def get_cosine_similarity(embedding_i: List[float], embedding_j: List[float]) -> float:
            embedding_i = np.array(embedding_i)
            embedding_j = np.array(embedding_j)
            return embedding_i.dot(embedding_j) / (np.linalg.norm(embedding_i) * np.linalg.norm(embedding_j))

        files = CodeAnalyzer.get_files_from_type(directory, ".txt")
        if not files:
            logger.warning(f"No .txt files found in {directory}")
            return 0.0

        with open(files[0], 'r') as file:
            task = file.read().strip()

        codes = CodeAnalyzer.get_code(directory)
        codes = remove_comments(codes)

        text_embedding = get_embedding(task)
        code_embedding = get_embedding(codes, is_code=True)
        return get_cosine_similarity(text_embedding, code_embedding)

def main(warehouse_root: str):
    """Main function to analyze code in the warehouse."""
    directories = [os.path.join(warehouse_root, d) for d in os.listdir(warehouse_root) if os.path.isdir(os.path.join(warehouse_root, d))]
    directories.sort()
    logger.info(f"Number of directories to analyze: {len(directories)}")

    suffix = warehouse_root.replace("/", "__").replace("-", "_")
    tsv_file = f"{os.path.splitext(__file__)[0]}.{suffix}.tsv"
    logger.info(f"Results will be written to: {tsv_file}")

    results = []
    for directory in directories:
        try:
            completeness = CodeAnalyzer.get_completeness(directory)
            executability = CodeAnalyzer.get_executability(directory)
            consistency = CodeAnalyzer.get_consistency(directory)
            results.append((os.path.basename(directory), completeness, executability, consistency))
        except Exception as e:
            logger.error(f"Error analyzing directory {directory}: {str(e)}")

    with open(tsv_file, "w", encoding="utf-8") as writer:
        writer.write("Directory\tCompleteness\tExecutability\tConsistency\n")
        for result in results:
            writer.write(f"{result[0]}\t{result[1]}\t{result[2]}\t{result[3]}\n")

    logger.info(f"Analysis complete. Results written to {tsv_file}")

class TestCodeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.test_dir = "./test_warehouse"
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, "test.py"), "w") as f:
            f.write("print('Hello, World!')")
        with open(os.path.join(self.test_dir, "task.txt"), "w") as f:
            f.write("Create a Hello World program")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    def test_get_completeness(self):
        completeness = CodeAnalyzer.get_completeness(self.test_dir)
        self.assertEqual(completeness, 1.0)

    def test_get_executability(self):
        executability = CodeAnalyzer.get_executability(self.test_dir)
        self.assertEqual(executability, 1.0)

    def test_get_consistency(self):
        consistency = CodeAnalyzer.get_consistency(self.test_dir)
        self.assertGreater(consistency, 0.5)

if __name__ == "__main__":
    main(warehouse_root="./WareHouse")
    unittest.main()
