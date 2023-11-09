'''
Main script to read JSON file, parse content, and create directories and Markdown files.
'''
import json
import os
from utils import sanitize_key, create_directory, write_markdown_file

def process_value(key, value, parent_directory):
    '''
    Process the value based on its type and create directories or Markdown files accordingly.
    '''
    sanitized_key = sanitize_key(key)
    file_path = os.path.join(parent_directory, f'{sanitized_key}.md')
    if isinstance(value, (str, int, float, bool)):
        write_markdown_file(file_path, str(value))
    elif isinstance(value, dict):
        create_directory(file_path)
        process_dict(value, file_path)
    elif isinstance(value, list):
        write_markdown_file(file_path, '- ' + '\n- '.join(map(str, value)))
    elif value is None:
        write_markdown_file(file_path, '')

def process_dict(dictionary, parent_directory):
    '''
    Process the dictionary and create directories or Markdown files for each key-value pair.
    '''
    for key, value in dictionary.items():
        process_value(key, value, parent_directory)

def process_json_file(file_path):
    '''
    Read the JSON file, parse content, and create directories or Markdown files.
    '''
    with open(file_path, 'r') as file:
        json_content = json.load(file)
    root_directory = os.path.splitext(file_path)[0]
    create_directory(root_directory)
    process_dict(json_content, root_directory)
    return root_directory

def main():
    '''
    Main function to execute the script.
    '''
    json_file_path = input("Enter the path to the JSON file: ")
    try:
        root_directory = process_json_file(json_file_path)
        print(f"Task completed successfully. Root directory: {root_directory}")
    except FileNotFoundError:
        print("Error: JSON file not found.")
    except json.JSONDecodeError:
        print("Error: Invalid JSON format.")
    except PermissionError:
        print("Error: Permission denied.")
    except Exception as e:
        print(f"Error: {str(e)}")
if __name__ == "__main__":
    main()
