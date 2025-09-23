import subprocess
import json
import yaml
import time
import logging
from easydict import EasyDict
import re
import os
from typing import  Optional, List
import ast
from model import query_gpt
# =============================
# File / JSON / Code Utilities
# =============================

def write_jsonl(fd, record: dict):
    fd.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_code(file_path: str) -> str:
    if file_path and os.path.isfile(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


def read_text(file_path: str) -> str:
    return read_code(file_path)


def write_file(work_path: str, content: str, ext: str = "py", file_path: Optional[str] = None) -> str:
    """Write code/text to a file, auto-increment file name if needed."""
    if file_path and os.path.isfile(file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            if len(content) > 0:
                f.write(content)
        return file_path

    index = 0
    while os.path.exists(os.path.join(work_path, f"agent-main_{index}.{ext}")):
        index += 1
    file_path = os.path.join(work_path, f"agent-main_{index}.{ext}")

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return file_path


def write_code(work_path: str, code: str, code_path: Optional[str] = None) -> str:
    return write_file(work_path, code, ext="py", file_path=code_path)


def write_text(work_path: str, text: str, text_path: Optional[str] = None) -> str:
    return write_file(work_path, text, ext="txt", file_path=text_path)


def format_code(code: str) -> str:
    """Remove empty lines."""
    return "\n".join([line for line in code.splitlines() if line.strip()])


def iter_jsonl(data_path: str) -> List[dict]:
    with open(data_path, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def get_files_from_type(source_dir: str, filetype: str) -> List[str]:
    files = []
    for root, _, filenames in os.walk(source_dir):
        for filename in filenames:
            if filename.endswith(filetype):
                files.append(os.path.join(root, filename))
    return files


def cmd(command: str) -> str:
    logging.info(f">> {command}")
    return subprocess.run(command, shell=True, text=True, stdout=subprocess.PIPE).stdout


def get_easyDict_from_filepath(path: str) -> Optional[EasyDict]:
    if path.endswith('.json'):
        with open(path, 'r', encoding="utf-8") as f:
            return EasyDict(json.load(f, strict=False))
    elif path.endswith(('.yaml', '.yml')):
        with open(path, 'r', encoding="utf-8") as f:
            return EasyDict(yaml.load(f, Loader=yaml.FullLoader))
    return None


def now() -> str:
    return time.strftime("%Y%m%d%H%M%S", time.localtime())


def code_is_valid(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except Exception:
        return False


def extract_code_from_text(text: str) -> str:
    """Extract valid Python code blocks from text."""
    code_blocks = re.findall(r"```.*?```", text, re.DOTALL)
    code_blocks = [
        "\n".join([line for line in block.splitlines() if "```" not in line])
        for block in code_blocks
    ]
    code = "\n\n".join(code_blocks) if code_blocks else text

    if len(code.strip().splitlines()) == 1:
        return ""

    if code_is_valid(code):
        return code

    # Search for longest valid code segment
    lines = text.splitlines()
    candidates = []
    for start in range(len(lines)):
        for end in range(start, len(lines)):
            segment = "\n".join(lines[start:end + 1])
            if code_is_valid(segment):
                candidates.append((end - start, segment))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][1]


def format_code_with_prints(code: Optional[str]) -> str:
    """Ensure code has print statements for important info."""
    if code is None:
        return ""
    if not isinstance(code, str):
        code = str(code)
    if re.search(r'print$begin:math:text$.+$end:math:text$', code):
        return extract_code_from_text(code)
    prompt = f"Add 'print' statements to print all necessary information.\nCode:\n{code}"
    code_out, _ = query_gpt(prompt)
    return extract_code_from_text(code_out) or code_out