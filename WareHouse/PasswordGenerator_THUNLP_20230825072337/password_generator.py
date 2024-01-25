'''
This file contains the PasswordGenerator class responsible for generating random passwords.
'''
import random
import string
class PasswordGenerator:
    def __init__(self):
        self.uppercase_letters = string.ascii_uppercase
        self.lowercase_letters = string.ascii_lowercase
        self.numbers = string.digits
        self.special_chars = string.punctuation
    def generate_passwords(self, length, complexity, excluded_chars, num_passwords):
        passwords = []
        for _ in range(num_passwords):
            password = self.generate_password(length, complexity, excluded_chars)
            passwords.append(password)
        return passwords
    def generate_password(self, length, complexity, excluded_chars):
        chars = ""
        password = ""
        # Add at least one character from each complexity requirement
        if "uppercase" in complexity:
            chars += self.uppercase_letters
            password += random.choice(self.uppercase_letters)
        if "lowercase" in complexity:
            chars += self.lowercase_letters
            password += random.choice(self.lowercase_letters)
        if "numbers" in complexity:
            chars += self.numbers
            password += random.choice(self.numbers)
        if "special_chars" in complexity:
            chars += self.special_chars
            password += random.choice(self.special_chars)
        # Remove excluded characters
        chars = self.remove_excluded_chars(chars, excluded_chars)
        # Fill the remaining length with random characters
        remaining_length = length - len(password)
        if remaining_length > 0:
            password += "".join(random.choice(chars) for _ in range(remaining_length))
        return password
    def remove_excluded_chars(self, chars, excluded_chars):
        for char in excluded_chars:
            chars = chars.replace(char, "")
        return chars