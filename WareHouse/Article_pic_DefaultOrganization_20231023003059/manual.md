# User Manual

## Introduction

Welcome to our Article Processor tool. This tool is designed to help you enhance your articles by automatically finding suitable images from the internet and placing them at suitable positions in your article. The tool also provides a markdown-based layout for your article, making it look like a professional official account article. 

## Main Functions

1. **Image Finder**: This function takes your article as input and finds a suitable image from the internet that matches the context of your article.

2. **Markdown Layout**: This function takes your article and the found image and creates a markdown-based layout for your article. The image is placed at a suitable position in the article.

## Installation

To install the required dependencies for this tool, you need to have Python installed on your system. If you don't have Python installed, you can download it from the official Python website.

Once you have Python installed, open your terminal and navigate to the project directory. Then, run the following command to install the required dependencies:

```bash
pip install -r requirements.txt
```

This command will install Flask for web development, BeautifulSoup for parsing HTML and extracting data, Markdown for creating markdown-based layout for the article, and Requests for making HTTP requests to fetch images from the internet.

## How to Use

1. **Start the Application**: To start the application, open your terminal, navigate to the project directory, and run the following command:

```bash
python main.py
```

This command will start the Flask server and the application will be accessible at `http://localhost:5000`.

2. **Input Your Article**: Open your web browser and go to `http://localhost:5000`. You will see a text area where you can input your article. After inputting your article, click the `Process Article` button.

3. **View the Result**: After clicking the `Process Article` button, you will be redirected to a new page where you can see your article with the found image and the markdown-based layout.

Please note that the image finding process is based on the first word of your article. Therefore, make sure the first word of your article is a good representation of the overall context of the article.