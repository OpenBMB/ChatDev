from openai import OpenAI
import os
import json
import os

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="",
)


class HR:
    def __init__(self) -> None:
        self.recruitment_queue = []
        self.role_dic = {}
        self.role_name = ''
        self.result = {}
        self.response = ''
        self.prompt = ''

    def load_roles(self):
        file_path = './CompanyConfig/Default/RoleConfig.json'
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                self.role_dic = json.load(file)
        else:
            print(f"The file at {file_path} does not exist.")

    def recruit(self, index):
        for i in range (100):
            self.load_roles()
            for role_name in self.role_dic.keys():
                if role_name == 'Programmer':
                    self.prompt = ('You are now an HR of a company, you now need to develop a software, you now have a '
                                   'position {}, you have recruited a member, you just need to give the following: Please '
                                   'describe in the second person in 150 words or less what you want from him and his '
                                   'characteristics as an individual. Please use the second person statement of fact '
                                   'instead of the expected statement to describe his ability to write codes in a certain style'
                                   '(Examples: simplicity, versatility, extendability, etc. Keep in mind, these are templates that you can refer to but not copy. )'
                                   'in software development. '
                                   'Do not specify that he has been recruited '
                                   'at the beginning, and do not begin by stating that he has been'
                                   'recruited or As an HR of our company, you require... .'.format(role_name))
                    messages = [{"role": "user", "content": self.prompt
                                 }]
                    response = client.chat.completions.create(
                        messages=messages,
                        model="gpt-3.5-turbo-16k",
                        temperature=1.0,
                        top_p=1.0,
                        n=1,
                        stream=False,
                        frequency_penalty=0.0,
                        presence_penalty=0.0,
                        logit_bias={}
                    ).model_dump()
                    response_text = response['choices'][0]['message']['content']
                    self.response = response_text
                    self.result[role_name] = ["{chatdev_prompt}\n", response_text,
                                              "\nHere is a new customer's task: {task}.\n"]



            RoleConfig_path = './CompanyConfig/HR/RoleConfig.json'
            RoleConfig_store = './CompanyConfig/HR/Existing_Role_Component/{}.txt'.format(index)
            with open(RoleConfig_store, 'w') as file:
                json.dump(self.result, file)
            with open(RoleConfig_path, "a") as json_file:
                json.dump(self.result, json_file, indent=4)
            print("RoleConfig{} has generated".format(index))


    # def format_json(self):
