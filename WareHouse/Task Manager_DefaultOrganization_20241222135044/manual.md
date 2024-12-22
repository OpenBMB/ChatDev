# Simple To-Do App User Manual

Welcome to the Simple To-Do App! This user manual will guide you through the installation process, explain the main functions of the app, and provide instructions on how to use it effectively.

## Table of Contents

1. [Installation](#installation)
2. [Main Functions](#main-functions)
    - [Adding Tasks](#adding-tasks)
    - [Marking Tasks as Completed](#marking-tasks-as-completed)
    - [Editing Tasks](#editing-tasks)
    - [Deleting Tasks](#deleting-tasks)
3. [Styling](#styling)

## 1. Installation <a name="installation"></a>

To use the Simple To-Do App, you need to have Python installed on your computer. Follow these steps to install the required dependencies and run the app:

1. Open a terminal or command prompt.
2. Navigate to the directory where you have downloaded the app files.
3. Create a virtual environment (optional but recommended):
   - Run `python -m venv todo-env` to create a new virtual environment.
   - Activate the virtual environment:
     - On Windows: Run `todo-env\Scripts\activate`.
     - On macOS/Linux: Run `source todo-env/bin/activate`.
4. Install the required dependencies:
   - Run `pip install -r requirements.txt` to install the necessary packages.
5. Start the app:
   - Run `python main.py` to launch the Simple To-Do App.

## 2. Main Functions <a name="main-functions"></a>

The Simple To-Do App provides the following main functions:

### Adding Tasks <a name="adding-tasks"></a>

To add a new task to the to-do list, follow these steps:

1. Locate the "ADD TASK" field at the top of the app.
2. Enter the task description in the field.
3. Press the "ADD" button or press Enter to add the task.
4. The task will be added to the to-do list, and the "ADD TASK" field will be cleared for the next task.

### Marking Tasks as Completed <a name="marking-tasks-as-completed"></a>

Once you have completed a task, you can mark it as completed. Here's how:

1. Locate the task in the to-do list that you want to mark as completed.
2. Click the "Complete" button next to the task.
3. The task will be moved to the "COMPLETED" section below the to-do list.

### Editing Tasks <a name="editing-tasks"></a>

If you need to edit a task, you can do so by following these steps:

1. Locate the task in the to-do list that you want to edit.
2. Double-click on the task description.
3. The task description will become editable.
4. Make the necessary changes to the task description.
5. Press Enter or click outside the task description field to save the changes.

### Deleting Tasks <a name="deleting-tasks"></a>

To remove a task from the to-do list, follow these steps:

1. Locate the task in the to-do list that you want to delete.
2. Click the "Delete" button next to the task.
3. The task will be permanently removed from the to-do list.

## 3. Styling <a name="styling"></a>

The Simple To-Do App comes with a default styling, but you can customize it to your liking. To modify the app's appearance, you can edit the `styles.css` file included with the app.

Here are some CSS classes you can modify:

- `body`: Styles for the app's body.
- `h1`: Styles for the app's title.
- `#todo-frame`: Styles for the to-do list section.
- `#completed-frame`: Styles for the completed tasks section.
- `#add-task-entry`: Styles for the "ADD TASK" input field.
- `#add-task-button`: Styles for the "ADD" button.
- `.task-frame`: Styles for each task in the to-do list or completed tasks section.
- `.task-label`: Styles for the task description label.
- `.complete-button`: Styles for the "Complete" button.
- `.delete-button`: Styles for the "Delete" button.

Feel free to experiment with different styles to make the app look nice according to your preferences.

---

Congratulations! You have successfully installed the Simple To-Do App and learned how to use its main functions. Start organizing your tasks and enjoy a more productive day!