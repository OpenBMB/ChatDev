from html_generator import generate_html
def main():
    html_code = generate_html()
    with open("index.html", "w") as file:
        file.write(html_code)
if __name__ == "__main__":
    main()