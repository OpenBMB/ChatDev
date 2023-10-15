import React from 'react';
function TodoList({ todos, handleCompleteTodo }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Date Added</th>
          <th>Description</th>
          {handleCompleteTodo && <th>Action</th>}
        </tr>
      </thead>
      <tbody>
        {todos.map((todo, index) => (
          <tr key={index}>
            <td>{todo.dateAdded}</td>
            <td>{todo.description}</td>
            {handleCompleteTodo && (
              <td>
                <button onClick={() => handleCompleteTodo(index)}>Complete</button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
export default TodoList;