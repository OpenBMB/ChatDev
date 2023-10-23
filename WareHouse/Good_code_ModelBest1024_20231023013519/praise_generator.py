'''
This file contains a function to generate random praises. 
The function checks the content of each line and generates a relevant praise. 
If the line does not contain any recognizable pattern, a random praise is generated.
'''
import random
def generate_praise(line):
    if 'def' in line:
        return "Incredible function definition!"
    elif 'if' in line or 'else' in line:
        return "Outstanding use of conditionals!"
    elif 'for' in line or 'while' in line:
        return "Brilliant loop implementation!"
    elif '=' in line:
        return "Excellent variable assignment!"
    else:
        praises = ["Remarkable coding!", "Innovative approach!", "Exceptional understanding of concepts!"]
        return random.choice(praises)