import React, { useState, useEffect } from 'react';
import TodoList from './TodoList';
function App() {
  const [todos, setTodos] = useState([]);
  const [inputValue, setInputValue] = useState('');
  useEffect(() => {
    fetch('/get_active_todos')
      .then(response => response.json())
      .then(data => setTodos(data));
  }, []);
  const handleInputChange = (event) => {
    setInputValue(event.target.value);
  };
  const handleAddTodo = () => {
    if (inputValue.trim() !== '') {
      fetch('/add_todo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
          description: inputValue
        })
      })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            fetch('/get_active_todos')
              .then(response => response.json())
              .then(data => setTodos(data));
            setInputValue('');
          } else {
            alert(data.message);
          }
        });
    }
  };
  const handleCompleteTodo = (index) => {
    fetch('/complete_todo', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: new URLSearchParams({
        index: index.toString()
      })
    })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          fetch('/get_active_todos')
            .then(response => response.json())
            .then(data => setTodos(data));
        } else {
          alert(data.message);
        }
      });
  };
  const activeTodos = todos.filter((todo) => todo.dateCompleted === null);
  const completedTodos = todos.filter((todo) => todo.dateCompleted !== null);
  return (
    <div className="App">
      <h1 className="header">Todo items</h1>
      <div className="input-container">
        <input type="text" value={inputValue} onChange={handleInputChange} placeholder="Type your task here..." />
        <button onClick={handleAddTodo}>Submit</button>
      </div>
      <h2 className="table-header">Active Todo Items</h2>
      <TodoList todos={activeTodos} handleCompleteTodo={handleCompleteTodo} />
      <h2 className="table-header">Completed Todo Items</h2>
      <TodoList todos={completedTodos} />
    </div>
  );
}
export default App;