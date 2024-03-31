import requests
from bs4 import BeautifulSoup
import wikipediaapi
import os
import time

USE_OPENAI = False
if USE_OPENAI == True:
    import openai
    from openai import OpenAI
    self_api_key = os.environ.get('OPENAI_API_KEY')
    BASE_URL = os.environ.get('BASE_URL')

    if BASE_URL:
        client = openai.OpenAI(
            api_key=self_api_key,
            base_url=BASE_URL,
        )
    else:
        client = openai.OpenAI(
            api_key=self_api_key
        )
else:
    import re
    from urllib.parse import urlencode
    import subprocess
    import json
    import jsonstreams
    from io import StringIO
    from contextlib import redirect_stdout
    BASE_URL = "http://localhost:11434/api/generate"
    mistral_new_api = True  # new mistral api version

    def generate_stream_json_response(prompt):
        data = json.dumps({"model": "openhermes", "prompt": prompt})
        process = subprocess.Popen(["curl", "-X", "POST", "-d", data, "http://localhost:11434/api/generate"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        full_response = ""
        with jsonstreams.Stream(jsonstreams.Type.array, filename='./response_log.txt') as output:
            while True:
                line, _ = process.communicate()
                if not line:
                    break
                try:
                    record = line.decode("utf-8").split("\n")
                    for i in range(len(record)-1):
                        data = json.loads(record[i].replace('\0', ''))
                        if "response" in data:
                            full_response += data["response"]
                            with output.subobject() as output_e:
                                output_e.write('response', data["response"])
                        else:
                            return full_response.replace('\0', '')
                    if len(record)==1:
                        data = json.loads(record[0].replace('\0', ''))
                        if "error" in data:
                            full_response += data["error"]
                            with output.subobject() as output_e:
                                output_e.write('error', data["error"])
                    return full_response.replace('\0', '')
                except Exception as error:
                    # handle the exception
                    print("An exception occurred:", error)
        return full_response.replace('\0', '')


def get_baidu_baike_content(keyword):
    # design api by the baidubaike
    url = f'https://baike.baidu.com/item/{keyword}'
    # post request
    response = requests.get(url)

    # Beautiful Soup part for the html content
    soup = BeautifulSoup(response.content, 'html.parser')
    # find the main content in the page
    # main_content = soup.find('div', class_='lemma-summary')
    main_content = soup.contents[-1].contents[0].contents[4].attrs['content']
    # find the target content
    # content_text = main_content.get_text().strip()
    return main_content


def get_wiki_content(keyword):
    #  Wikipedia API ready
    wiki_wiki = wikipediaapi.Wikipedia('MyProjectName (merlin@example.com)', 'en')
    #the topic content which you want to spider
    search_topic = keyword
    # get the page content
    page_py = wiki_wiki.page(search_topic)
    # check the existence of the content in the page
    if page_py.exists():
        print("Page - Title:", page_py.title)
        print("Page - Summary:", page_py.summary)
    else:
        print("Page not found.")
    return page_py.summary



def modal_trans(task_dsp):
    try:
        task_in ="'" + task_dsp + \
               "'Just give me the most important keyword about this sentence without explaining it and your answer should be only one keyword."
        #messages = [{"role": "user", "content": task_in}]
        #response = client.chat.completions.create(messages=messages,
        #model="gpt-3.5-turbo-16k",
        #temperature=0.2,
        #top_p=1.0,
        #n=1,
        #stream=False,
        #frequency_penalty=0.0,
        #presence_penalty=0.0,
        #logit_bias={})
        response = generate_stream_json_response("<|im_start|>user" + '\n' + task_in + "<|im_end|>")
        response_text = response.choices[0].message.content
        spider_content = get_wiki_content(response_text)
        # time.sleep(1)
        task_in = "'" + spider_content + \
               "',Summarize this paragraph and return the key information."
        messages = [{"role": "user", "content": task_in}]
        #response = client.chat.completions.create(messages=messages,
        #model="gpt-3.5-turbo-16k",
        #temperature=0.2,
        #top_p=1.0,
        #n=1,
        #stream=False,
        #frequency_penalty=0.0,
        #presence_penalty=0.0,
        #logit_bias={})
        response = generate_stream_json_response("<|im_start|>user" + '\n' + task_in + "<|im_end|>")
        result = response.choices[0].message.content
        print("web spider content:", result)
    except:
        result = ''
        print("the content is none")
    return result
