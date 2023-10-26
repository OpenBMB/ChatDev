'''
This file contains the logic for getting conversation topics.
'''
import requests
from bs4 import BeautifulSoup

def get_conversation_topics():
    url = "https://top.baidu.com/board?tab=realtime"

    # Send an HTTP GET request to the URL
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the elements containing the top trending topics
        trending_topics = soup.find_all("div", class_="c-single-text-ellipsis")

        # Get the top three trending topics
        top_three_topics = trending_topics[:5]

        # Extract and print the titles of the top three topics
        return [topic.get_text() for topic in top_three_topics]
    else:
        return ["Error: Could not retrieve top trending topics"]