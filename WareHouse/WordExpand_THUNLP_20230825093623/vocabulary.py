'''
This file contains the Vocabulary class.
'''
class Vocabulary:
    def __init__(self):
        self.words = {
            "happy": {
                "synonyms": ["joyful", "delighted", "content"],
                "antonyms": ["sad", "unhappy", "miserable"],
                "examples": ["I am happy to see you.", "She is always happy."]
            },
            "beautiful": {
                "synonyms": ["gorgeous", "stunning", "lovely"],
                "antonyms": ["ugly", "hideous", "unattractive"],
                "examples": ["The sunset looks beautiful.", "She is a beautiful person."]
            },
            # Add more words and their synonyms, antonyms, and examples here
        }
    def search(self, word):
        if word in self.words:
            return self.words[word]["synonyms"], self.words[word]["antonyms"], self.words[word]["examples"]
        else:
            return [], [], []