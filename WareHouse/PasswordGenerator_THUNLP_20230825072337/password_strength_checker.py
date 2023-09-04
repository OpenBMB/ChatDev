'''
This file contains the PasswordStrengthChecker class responsible for checking the strength of a password.
'''
class PasswordStrengthChecker:
    def __init__(self):
        self.common_passwords = ["password", "123456", "qwerty", "abc123", "admin"]
    def check_strength(self, password):
        if len(password) < 8:
            return "Weak"
        if password.lower() in self.common_passwords:
            return "Weak"
        return "Strong"