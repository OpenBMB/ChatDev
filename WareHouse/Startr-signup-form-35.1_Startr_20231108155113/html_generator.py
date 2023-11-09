def generate_html():
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
                width: 33.33%;
                float: left;
            }
            .signup-form {
                margin: 0 auto;
                max-width: 400px;
                padding: 20px;
                background-color: #f2f2f2;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
        </style>
    </head>
    <body style="--maxw:50rem; --m:auto;">
        <div class="column">
            <!-- Column 1 content here -->
        </div>
        <div class="column">
            <!-- Column 2 content here -->
        </div>
        <div class="column">
            <div class="signup-form">
                <h2>Signup Form</h2>
                <form>
                    <!-- Signup form fields here -->
                </form>
            </div>
        </div>
    </body>
    </html>
    '''
    return html_code