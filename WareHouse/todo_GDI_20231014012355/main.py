'''
This is the main file for the Todo list application.
It initializes the GUI and handles user interactions.
'''
import datetime
from flask import Flask, render_template, request, jsonify
app = Flask(__name__)
todos = []
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/add_todo', methods=['POST'])
def add_todo():
    description = request.form.get('description')
    if description.strip() != '':
        new_todo = {
            'dateAdded': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'description': description,
            'dateCompleted': None
        }
        todos.append(new_todo)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Invalid description'})
@app.route('/complete_todo', methods=['POST'])
def complete_todo():
    index = int(request.form.get('index'))
    if index >= 0 and index < len(todos):
        todos[index]['dateCompleted'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Invalid index'})
@app.route('/get_active_todos')
def get_active_todos():
    active_todos = [todo for todo in todos if todo['dateCompleted'] is None]
    return jsonify(active_todos)
@app.route('/get_completed_todos')
def get_completed_todos():
    completed_todos = [todo for todo in todos if todo['dateCompleted'] is not None]
    return jsonify(completed_todos)
if __name__ == '__main__':
    app.run()