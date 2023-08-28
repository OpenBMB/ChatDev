'''
This is the main file of the todo list application.
It initializes the GUI and starts the application.
'''
from todo_app import TodoApp
def main():
    app = TodoApp()
    app.start()
if __name__ == "__main__":
    main()