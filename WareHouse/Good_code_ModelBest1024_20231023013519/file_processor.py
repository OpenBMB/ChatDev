'''
This file contains a function to process the selected Python file. 
The function reads the file, adds praises to each line, and writes the result to a new file. 
The new file has the same name as the original file, but with "praised_" added at the beginning.
'''
from praise_generator import generate_praise
def process_file(filename):
    try:
        with open(filename, "r", encoding="utf8") as file:
            lines = file.readlines()
    except IOError as e:
        print(f"Unable to open file: {e}")
        return
    new_lines = []
    for line in lines:
        if line.strip() and not line.strip().startswith("#"):
            # Check if there is already a comment on the line
            if "#" not in line:
                line = line.rstrip() + "  # " + generate_praise(line) + "\n"
        new_lines.append(line)
    try:
        with open("praised_" + filename.split('/')[-1], "w", encoding="utf8") as file:
            for line in new_lines:
                file.write(line)
    except IOError as e:
        print(f"Unable to write to file: {e}")