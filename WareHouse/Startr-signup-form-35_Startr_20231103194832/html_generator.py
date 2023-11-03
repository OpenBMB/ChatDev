from typing import List, Dict
def generate_html() -> str:
    html_code = """
    <!DOCTYPE html>
    <html>
    <head>
        <link rel="stylesheet" href="https://startr.style/style.css">
        <link rel="stylesheet" href="https://raw.githack.com/opencoca/system7.css/main/style.css">
        <style>
            body {
                --maxw: 50rem;
                --m: auto;
            }
        </style>
    </head>
    <body>
        <div class="column">Column 1</div>
        <div class="column">Column 2</div>
        <div class="column">Column 3</div>
        <form>
            <label for="name">Name:</label>
            <input type="text" id="name" name="name" required>
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" required>
            <input type="submit" value="Sign Up">
        </form>
    </body>
    </html>
    """
    return html_code