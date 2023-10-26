import json
import re
import openai
class ProjectEvaluator:
    def __init__(self):
        self.prompt = """You are a professional start-up project judge. Please score the following open source software project based on the information provided, on a scale of 1 to 10. Your scoring should be divided into three dimensions: feasibility, usability, and innovativeness. Your return result should be a JSON format dictionary. An example is in the following line\n'{"feasibility": {"score": 8.5, "reason": "the idea of this project is simple but natural. tools and tech-schemes it requires are very mature so that it is easy to be implemented"}, "usability": {"score": 9.0, "reason": "the function it claims is very useful. it can help many people enhance efficiency"}, "novelty": {"score": 3.5, "reason": "main the idea of this project is not very frontier"}}'.\nNOTE: You should NOT copy the statement in the example above. You should write your reason independently."""
    def evaluate_project(self, readme_file):
        # Read the README.md file
        readme_content = self.read_file(readme_file)
        # Extract relevant information from the README.md file
        project_name = self.extract_project_name(readme_content)
        project_description = self.extract_project_description(readme_content)
        # Add more evaluation criteria as needed
        # Calculate the score based on the extracted information
        score = self.calculate_score(project_name, project_description)
        return score
    def read_file(self, file_path):
        with open(file_path, "r") as file:
            content = file.read()
        return content
    def extract_project_name(self, readme_content):
        # Extract project name from the README.md file
        # Implement your logic here
        project_name = ""
        match = re.search(r"#\s*(.*)", readme_content)
        if match:
            project_name = match.group(1)
        return project_name
    def extract_project_description(self, readme_content):
        # Extract project description from the README.md file
        # Implement your logic here
        project_description = ""
        match = re.search(r"##\s*Description\n\n(.*)", readme_content)
        if match:
            project_description = match.group(1)
        return project_description
    def calculate_score(self, project_name, project_description):
        # Calculate the score based on the project name and description
        # Implement your logic here
        score = 0
        resp = "### NOT POST YET ###"
        for i in range(10):
            try:
                print("post request ", i)
                resp = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo", 
                    messages=[
                        {"role": "system", "content": self.prompt}, 
                        {"role": "user", "content": f"Project Name: {project_name}\nProject Description: {project_description}\n"}
                    ]
                )
                print("response got", i)
                content = resp.choices[0]["message"]["content"]
                json_str = re.search(r'\{.+\}', content, re.S).group(0) 
                scores_dict = json.loads(json_str)
                return scores_dict
            except Exception as e:
                print(e)
                print(resp)
                print('api calling failed')
        return 
