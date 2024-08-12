/**
 * File that handles the graphical user interface.
 */
class GUI {
  constructor() {
    this.element = document.createElement('div');
    this.element.id = 'gui';
  }
  render(container) {
    this.element.innerHTML = `
      <h1>Basic Website</h1>
      <button id="button">Click me!</button>
    `;
    const button = document.getElementById('button');
    button.addEventListener('click', () => {
      console.log('Button clicked!');
    });
  }
}
export { GUI };