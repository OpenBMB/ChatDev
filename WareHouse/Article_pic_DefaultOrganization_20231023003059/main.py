'''
This is the main file that will run our application.
'''
from flask import Flask, render_template, request
from article_processor import ArticleProcessor
app = Flask(__name__)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        article = request.form['article']
        processor = ArticleProcessor(article)
        markdown = processor.process_article()
        return render_template('result.html', markdown=markdown)
    return render_template('index.html')
if __name__ == "__main__":
    try:
        app.run(debug=True)
    except ImportError:
        print("Error: The watchdog library is not installed. Please install it by running 'pip install watchdog' in your terminal.")