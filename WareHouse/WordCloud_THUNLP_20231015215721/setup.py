from setuptools import setup
setup(
    name="wordcloud_generator",
    version="1.0",
    description="A word cloud generator program",
    author="ChatDev",
    py_modules=["main"],
    install_requires=[
        "wordcloud",
        "matplotlib"
    ],
    entry_points={
        "console_scripts": [
            "wordcloud_generator=main:WordCloudGenerator"
        ]
    }
)