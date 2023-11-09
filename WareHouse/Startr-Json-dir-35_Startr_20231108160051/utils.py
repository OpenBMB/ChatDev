'''
Utility functions for the main script.
'''
import os
import re
def sanitize_key(key):
    '''
    Sanitize the key to remove or replace characters that are not allowed in file or directory names.
    '''
    sanitized_key = re.sub(r'[<>:"/\\|?*]', '', key)
    return sanitized_key
def create_directory(directory_path):
    '''
    Create a directory if it doesn't exist.
    '''
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
def write_markdown_file(file_path, content):
    '''
    Write content to a Markdown file.
    '''
    with open(file_path, 'w') as file:
        file.write(content)