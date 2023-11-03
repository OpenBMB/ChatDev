'''
This file contains the functions to generate the HTML code.
'''
def generate_html():
    '''
    Generates the HTML code for the page with three columns and a signup form.
    '''
    html_code = '''
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
            .column {
                float: left;
                width: 33.33%;
                padding: 10px;
            }
            .row::after {
                content: "";
                clear: both;
                display: table;
            }
        </style>
    </head>
    <body>
        <div class="row">
            <div class="column">
                <h2>Column 1</h2>
                <p>Some content here.</p>
            </div>
            <div class="column">
                <h2>Column 2</h2>
                <p>Some content here.</p>
            </div>
            <div class="column">
                <h2>Column 3</h2>
                <p>Some content here.</p>
            </div>
        </div>
        <form>
            <label for="name">Name:</label>
            <input type="text" id="name" name="name" required><br><br>
            <label for="email">Email:</label>
            <input type="email" id="email" name="email" required><br><br>
            <input type="submit" value="Sign Up">
        </form>
    </body>
    </html>
    '''
    return html_code