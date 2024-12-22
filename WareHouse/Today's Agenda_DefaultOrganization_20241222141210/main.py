'''
This is the main file for the Task Manager web application.
'''
from flask import Flask, render_template, request
app = Flask(__name__)
tasks = []
completed_tasks = []
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        task = request.form['task']
        action = request.form['action']
        if action == 'add':
            tasks.append(task)
        elif action == 'edit':
            # Implement edit logic here
            pass
        elif action == 'delete':
            # Implement delete logic here
            pass
        elif action == 'complete':
            tasks.remove(task)
            completed_tasks.append(task)
    return render_template('index.html', tasks=tasks, completed_tasks=completed_tasks)
if __name__ == '__main__':
    app.run()