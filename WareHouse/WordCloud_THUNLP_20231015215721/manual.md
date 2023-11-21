# Word Cloud Generator User Manual

## Introduction
The Word Cloud Generator is a Python program that allows users to generate word clouds from input text. A word cloud is a visualization of the frequency of words in a given text, with more frequent words appearing larger in the visualization. This program uses the wordcloud library in combination with matplotlib to create the word cloud visualization.

## Installation
To use the Word Cloud Generator, you need to have Python installed on your computer. You also need to install the required dependencies by running the following command in your terminal or command prompt:

```
pip install -r requirements.txt
```

This will install the wordcloud and matplotlib libraries.

## Usage
1. Run the program by executing the `main.py` file.
2. A window will appear with a text entry field and a "Generate Word Cloud" button.
3. Enter the desired text in the text entry field.
4. Click the "Generate Word Cloud" button to generate the word cloud.
5. A file dialog will open, allowing you to choose the output file name and location.
6. The word cloud will be saved as a PNG image.

## Customization
You can customize the appearance of the word cloud by modifying the code in the `generate_word_cloud` method of the `WordCloudGenerator` class in the `main.py` file. For example, you can change the color scheme, size, and font of the word cloud.

## Additional Information
- The word cloud is generated using the WordCloud library.
- The program uses the matplotlib library to display the word cloud visualization.
- The word cloud image is saved as a PNG file.
- You can test the program with various input texts to verify that it generates meaningful word clouds.

For more information, please refer to the `readme.md` file included in the program files.

## Support
If you encounter any issues or have any questions, please reach out to our support team at support@chatdev.com.