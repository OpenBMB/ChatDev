import requests
from bs4 import BeautifulSoup
import openai
from openai import OpenAI
import wikipediaapi
import os

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

# client = OpenAI(
#     api_key=self_api_key,
#     base_url="https://sailaoda.cn/v1",
# )
import time


# THUNLP内部API_KEY，后台有使用监控，切勿外传
 # Key找钱忱提供
# TODO: The 'openai.api_base' option isn't read in the client API. You will need to pass it when you instantiate the client, e.g. 'OpenAI(api_base="https://sailaoda.cn/v1")'
# openai.api_base = "https://sailaoda.cn/v1"

def get_baidu_baike_content(keyword):
    # 构建百度百科的URL
    url = f'https://baike.baidu.com/item/{keyword}'
    # 发送请求
    response = requests.get(url)

    # 使用Beautiful Soup解析HTML页面
    soup = BeautifulSoup(response.content, 'html.parser')

    # 找到页面中的主要内容
    # main_content = soup.find('div', class_='lemma-summary')
    main_content = soup.contents[-1].contents[0].contents[4].attrs['content']
    # 提取纯文本内容
    # content_text = main_content.get_text().strip()

    return main_content


def get_wiki_content(keyword):
    # 创建 Wikipedia API 的实例并设置用户代理
    wiki_wiki = wikipediaapi.Wikipedia('MyProjectName (merlin@example.com)', 'en')
    # 定义要查询的主题
    search_topic = "Gomoku"
    # 获取页面对象
    page_py = wiki_wiki.page(search_topic)
    # 检查页面是否存在
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
        # task_in = task_dsp + '，给我这句话最关键的词汇，你的回答只能是一个关键词'
        messages = [{"role": "user", "content": task_in}]
        response = client.chat.completions.create(messages=messages,
        model="gpt-3.5-turbo-16k",
        temperature=0.2,
        top_p=1.0,
        n=1,
        stream=False,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        logit_bias={})
        response_text = response.choices[0].message.content
        spider_content = get_wiki_content(response_text)
        # time.sleep(1)
        task_in = "'" + spider_content + \
               "',Summarize this paragraph and return the key information."
        messages = [{"role": "user", "content": task_in}]
        response = client.chat.completions.create(messages=messages,
        model="gpt-3.5-turbo-16k",
        temperature=0.2,
        top_p=1.0,
        n=1,
        stream=False,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        logit_bias={})
        result = response.choices[0].message.content
        print("web spider content:", result)
    except:
        result = ''
        print("the content is none")
    return result